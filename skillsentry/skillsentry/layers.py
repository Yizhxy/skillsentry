"""L1 deny-list, L3 stop-gate, and the feedback assembler."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .ir import IR, Signature, Step  # noqa: F401  (Step is referenced in _suggest_alternatives's quoted annotation)
from .matchers import _command_field, _path_field, match_signature, signature_label

# Decision kinds (ordered most → least restrictive).
DECISION_HARD_DENY = "hard-deny"
DECISION_SOFT_DENY = "soft-deny"
DECISION_HINT = "hint"
DECISION_ALLOW = "allow"


@dataclass
class Decision:
    kind: str
    reason: str = ""
    layer: str = ""
    matched_step: Optional[str] = None


# --------------------------------------------------------------------------
# L1: deny-list (deterministic, microsecond-scale)
# --------------------------------------------------------------------------

def _matches_any(patterns: List[str], text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    for p in patterns:
        try:
            if re.search(p, text):
                return p
        except re.error:
            continue
    return None


def _unanchor_for_body_scan(pattern: str) -> str:
    """Rewrite a path pattern so it can match inside a Bash command body.

    Path patterns like `^/etc/` mean 'path starts with /etc/'; in a Bash
    command body the same path occurs mid-string. Translate the leading `^`
    into a word/space boundary so e.g. `cat /etc/passwd` still fires.
    """
    if pattern.startswith("^"):
        return r"(?:^|[\s=\"'])" + pattern[1:]
    return pattern


def _render_signature_hint(sig: Signature) -> str:
    if sig.tool == "Bash" and sig.command_match:
        return f"Bash command matching /{sig.command_match}/"
    if sig.tool and sig.path_match:
        return f"{sig.tool} on a path matching /{sig.path_match}/"
    if sig.tool:
        return f"{sig.tool} call"
    return signature_label(sig)


def _suggest_alternatives(step: "Step") -> str:
    """Render the step's logical_actions patterns as a hint string so a denied
    agent has a concrete next move.
    """
    patterns = step.action_patterns  # flat list via property
    if not patterns:
        return ""
    parts = [_render_signature_hint(sig) for sig in patterns[:3]]
    return "Try the documented alternative for this step: " + "; or ".join(parts)


def suggest_for_missing_requires(
    ir: "IR", missing_step_ids: List[str]
) -> str:
    """Render the logical_actions patterns of the FIRST missing prerequisite step."""
    for sid in missing_step_ids:
        step = ir.step_by_id(sid)
        if not step or not step.action_patterns:
            continue
        parts = [_render_signature_hint(sig) for sig in step.action_patterns[:3]]
        return (f"First satisfy step '{sid}' — call: " + "; or ".join(parts))
    return ""


def format_on_enter_hints(step: "Step") -> str:
    """Format on_enter suggestions, warnings, and constraints for display when entering a step.

    New DSL on_enter: {"suggestions": [...], "warnings": [...]}
    Constraints from step.constraints are appended as additional hints.
    """
    if not step:
        return ""

    lines: List[str] = []
    header = f"Entering step '{step.step_id}' ({step.description})."

    suggestions: List[str] = []
    warnings: List[str] = []

    if step.on_enter:
        suggestions = list(step.on_enter.get("suggestions") or [])
        warnings = list(step.on_enter.get("warnings") or [])

    # Constraints → additional hints
    constraint_hints = [c.to_hint() for c in (step.constraints or []) if c.to_hint()]

    if not suggestions and not warnings and not constraint_hints:
        return ""

    lines.append(header)
    if suggestions:
        lines.append("  Suggestions:")
        for i, s in enumerate(suggestions, 1):
            lines.append(f"    {i}. {s}")
    if warnings:
        lines.append("  Warnings:")
        for i, w in enumerate(warnings, 1):
            lines.append(f"    {i}. ⚠️  {w}")
    if constraint_hints:
        lines.append("  Constraints:")
        for i, h in enumerate(constraint_hints, 1):
            lines.append(f"    {i}. {h}")

    return "\n".join(lines)


def evaluate_l1(ir: IR, tool_name: str, tool_input: Dict[str, Any]) -> Optional[Decision]:
    """Return a hard-deny Decision if any L1 rule fires; else None.

    For step-scoped forbidden hits we surface the same step's action patterns as
    a suggested alternative in the reason text — this turns a "stop" signal
    into a "switch lane" signal (Finding 2 from experiment analysis cycle 0).
    """
    g = ir.global_rules

    if tool_name in g.forbidden_tools:
        return Decision(
            kind=DECISION_HARD_DENY, layer="L1",
            reason=f"tool '{tool_name}' is on the skill's forbidden list",
        )

    cmd = _command_field(tool_name, tool_input)
    if cmd is not None:
        hit = _matches_any(g.forbidden_bash, cmd)
        if hit:
            return Decision(
                kind=DECISION_HARD_DENY, layer="L1",
                reason=f"Bash command matches forbidden pattern /{hit}/",
            )
        # v3: also scan Bash command body for forbidden path patterns. Catches
        # `cat /etc/passwd`, `rm -rf .git/...` where the dangerous path is
        # inside the command string rather than a file_path argument. The
        # `^` anchor in path patterns means "path starts with", which becomes
        # "appears at a word boundary in the Bash command".
        cmd_patterns = [_unanchor_for_body_scan(p) for p in g.forbidden_paths]
        hit_path = _matches_any(cmd_patterns, cmd)
        if hit_path:
            return Decision(
                kind=DECISION_HARD_DENY, layer="L1",
                reason=f"Bash command body references forbidden path pattern /{hit_path}/",
            )

    path = _path_field(tool_name, tool_input)
    if path is not None:
        hit = _matches_any(g.forbidden_paths, path)
        if hit:
            return Decision(
                kind=DECISION_HARD_DENY, layer="L1",
                reason=f"path '{path}' matches forbidden pattern /{hit}/",
            )

    for step in ir.steps:
        for sig in step.forbidden:
            if match_signature(sig, tool_name, tool_input):
                base = f"matches step {step.id} forbidden signature ({signature_label(sig)})"
                hint = _suggest_alternatives(step)
                reason = f"{base}. {hint}" if hint else base
                return Decision(
                    kind=DECISION_HARD_DENY, layer="L1",
                    reason=reason,
                    matched_step=step.id,
                )
    return None


# --------------------------------------------------------------------------
# L3: stop-gate completion assertion
# --------------------------------------------------------------------------

def _iter_transcript_tool_uses(transcript_path: str):
    """Yield (tool_name, tool_input) for every tool_use in the JSONL transcript."""
    try:
        f = open(transcript_path, "r", encoding="utf-8", errors="replace")
    except OSError:
        return
    with f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg = obj.get("message") or obj
            content = msg.get("content") if isinstance(msg, dict) else None
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    yield block.get("name", ""), block.get("input") or {}


def _step_completed_in_transcript(step: "Step", seen: List[Tuple[str, Dict[str, Any]]]) -> bool:
    """True if EVERY logical action of the step has at least one alternative
    pattern matched among the executed tool calls (M(s_i) = LA(s_i)).

    A step with no logical actions is trivially complete.
    """
    for la in step.logical_actions:
        if not any(match_signature(sig, n, i) for sig in la.patterns for n, i in seen):
            return False
    return True


def evaluate_l3(
    ir: IR,
    transcript_path: Optional[str],
    observed_signatures: Optional[List[str]] = None,
    strict: bool = False,
) -> Optional[Decision]:
    """Termination checker: any required step in `termination` not completed →
    hard-deny (block).

    A step is completed only when ALL of its logical actions have been matched
    (M(s_i) = LA(s_i)). Two coverage sources:
      - transcript scan (default): a step is complete iff every one of its logical
        actions has a pattern matched somewhere in the executed tool calls
        (including ones L2 soft-denied but which `bypassPermissions` let through).
      - strict mode (SKILLSENTRY_L3_STRICT=1): a step is complete iff L2 recorded
        its '<stepId>.completed' signal (= state.observed_signatures). Aligns L3
        with L2's FSM view, at the cost of missing tool_uses that bypassed the hook.
    """
    required = ir.completion.required_step_ids
    if not required:
        return None

    observed_set = set(observed_signatures or [])
    seen: List[Tuple[str, Dict[str, Any]]] = []
    if not strict and transcript_path:
        seen = list(_iter_transcript_tool_uses(transcript_path))

    missing: List[str] = []
    for sid in required:
        if strict:
            covered = f"{sid}.completed" in observed_set
        else:
            step = ir.step_by_id(sid)
            covered = bool(step) and _step_completed_in_transcript(step, seen)
        if not covered:
            missing.append(sid)

    if not missing:
        return None

    layer = "L3-strict" if strict else "L3"
    return Decision(
        kind=DECISION_HARD_DENY, layer=layer,
        reason=f"completion check failed — missing required steps: {missing}",
    )


# --------------------------------------------------------------------------
# Three-tier feedback → Claude Code hookSpecificOutput
# --------------------------------------------------------------------------

REASON_MODE_VALID = ("verbose", "neutral", "terse", "minimal", "none")


def _reason_mode() -> str:
    """v3.1: SKILLSENTRY_REASON_MODE controls how much of the decision reason
    is exposed to the agent. Lets Cycle 5 experiments do reason ablation
    (§10.3 P1) without code changes, and also serves as the meta-awareness
    mitigation for Finding 1 (Sonnet reads '[skill-sentry/Lk]' tags and
    enters meta-cognitive mode)."""
    import os
    m = os.environ.get("SKILLSENTRY_REASON_MODE", "verbose").lower()
    return m if m in REASON_MODE_VALID else "verbose"


def _format_reason(decision: Decision, *, for_stop: bool = False) -> str:
    """Render a decision reason according to the configured reason mode.

    Modes:
      - verbose (default): full reason + `[skill-sentry/Lk]` tag + step suffix.
        Optimized for debugging / paper-grade traces.
      - neutral: generic prefix `[policy]`, full reason + step suffix.
        Drops the layer name but keeps actionable detail.
      - terse: `policy:` prefix, drops layer + step suffix, keeps reason body.
        Lowest 'meta-awareness footprint' that still says something.
      - minimal: a single-line direction. For deny: 'Try the documented
        alternative.' For Stop: 'Workflow not complete.' Drops every internal.
      - none: empty string. For reason ablation.
    """
    mode = _reason_mode()
    if mode == "none":
        return ""

    layer = decision.layer or ""
    step = decision.matched_step or ""
    body = decision.reason or ""

    if mode == "minimal":
        if for_stop or decision.kind == DECISION_HARD_DENY:
            return "Policy gate: this action is not permitted; consult the workflow."
        if decision.kind == DECISION_SOFT_DENY:
            return "Policy gate: prerequisite missing."
        return "Policy hint."

    if mode == "terse":
        # Strip "First satisfy step 'X' — call: <sig>" → keep just the call hint
        # when present; otherwise truncate body to a short clause.
        short = body
        if "First satisfy step" in body:
            short = body.split("First satisfy step", 1)[1]
            short = "First satisfy step" + short
        elif "Try the documented alternative" in body:
            short = body[body.index("Try the documented alternative"):]
        else:
            short = (body[:160] + "…") if len(body) > 160 else body
        return f"policy: {short}"

    if mode == "neutral":
        prefix = "[policy]"
        msg = f"{prefix} {body}".strip()
        if step:
            msg += f" (step={step})"
        return msg

    # verbose (default)
    prefix = f"[skill-sentry/{layer}]" if layer else "[skill-sentry]"
    msg = f"{prefix} {body}".strip()
    if step:
        msg += f" (step={step})"
    return msg


def render_pretooluse_output(decision: Decision) -> Optional[Dict[str, Any]]:
    """Convert a Decision into a PreToolUse hookSpecificOutput dict.

    Returns None for ALLOW (no output → harness lets the call through).
    """
    if decision.kind == DECISION_ALLOW:
        return None

    msg = _format_reason(decision)

    if decision.kind == DECISION_HINT:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "additionalContext": msg,
            }
        }
    if decision.kind == DECISION_SOFT_DENY:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": msg,
            }
        }
    # hard-deny
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": msg,
        }
    }


def render_stop_output(decision: Decision) -> Dict[str, Any]:
    return {
        "decision": "block",
        "reason": _format_reason(decision, for_stop=True),
    }
