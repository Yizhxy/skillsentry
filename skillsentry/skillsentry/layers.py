"""L1 deny-list, L4 stop-gate, and the three-tier feedback assembler."""
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
    patterns = step.must_call  # flat list via property
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
        if not step or not step.must_call:
            continue
        parts = [_render_signature_hint(sig) for sig in step.must_call[:3]]
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

    For step-scoped forbidden hits we surface the same step's must_call as a
    suggested alternative in the reason text — this turns a "stop" signal
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
# L2.5: stale-budget detector (v3)
# --------------------------------------------------------------------------

def next_unsatisfied_steps(ir: IR, satisfied: List[str]) -> List[str]:
    """Return the first 1-2 step ids that are NOT satisfied yet AND whose
    depends_on are already satisfied (i.e., immediately actionable steps).
    """
    sat = set(satisfied or [])
    actionable: List[str] = []
    unsat_all: List[str] = []
    for s in ir.steps:
        if s.step_id in sat:
            continue
        unsat_all.append(s.step_id)
        if all(r in sat for r in s.depends_on):
            actionable.append(s.step_id)
    return (actionable or unsat_all)[:2]


def evaluate_stale_budget(
    ir: IR,
    satisfied: List[str],
    no_advance_streak: int,
    threshold: int,
) -> Optional[Decision]:
    """v3 L2.5: emit a HINT when the agent has issued `threshold` consecutive
    no-match tool calls while the workflow still has unsatisfied steps.

    Captures Finding 7: L3 LLM-judge sloppily passes 'irrelevant but legal'
    calls; this layer is deterministic, can't be evaded by prompt-injection,
    and tells the agent exactly which step to advance next.
    """
    if no_advance_streak < threshold:
        return None
    if not ir.steps:
        return None
    next_steps = next_unsatisfied_steps(ir, satisfied)
    if not next_steps:
        return None  # everything satisfied → nothing to suggest

    parts: List[str] = []
    for sid in next_steps:
        step = ir.step_by_id(sid)
        if not step or not step.must_call:
            parts.append(sid)
            continue
        sig_hints = [_render_signature_hint(sig) for sig in step.must_call[:2]]
        parts.append(f"{sid} (try: {' / '.join(sig_hints)})")

    reason = (
        f"{no_advance_streak} consecutive tool calls did not advance the workflow; "
        f"unsatisfied step(s) remain. Next step suggestion: " + " | ".join(parts)
    )
    return Decision(
        kind=DECISION_HINT, layer="L2.5",
        reason=reason,
        matched_step=next_steps[0] if next_steps else None,
    )


# --------------------------------------------------------------------------
# L4: stop-gate completion assertion
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


def _signature_ref_to_sigs(ir: IR, ref: str) -> List[Signature]:
    """Resolve a completion reference → list[Signature] from that step.

    Supports both:
    - New DSL termination: plain stepId → returns step's logical_actions patterns
    - Legacy: 'stepId.must_call' or 'stepId.forbidden' format
    """
    if "." in ref:
        step_id, slot = ref.split(".", 1)
    else:
        step_id, slot = ref, "must_call"

    step = ir.step_by_id(step_id)
    if not step:
        return []
    if slot == "must_call":
        return list(step.must_call)   # flat patterns via property
    if slot in ("forbidden", "failure_patterns"):
        return list(step.failure_patterns)
    return []


def evaluate_l4(
    ir: IR,
    transcript_path: Optional[str],
    observed_signatures: Optional[List[str]] = None,
    strict: bool = False,
) -> Optional[Decision]:
    """Stop-gate: any required signature/artifact missing → hard-deny (block).

    Two coverage sources (Finding 3 from experiment analysis cycle 0):
      - transcript scan (default): walks tool_use blocks; counts any executed
        call that matches must_call signatures, including ones L2 soft-denied
        but which `bypassPermissions` let through.
      - strict mode (SKILLSENTRY_L4_STRICT=1): only counts signatures L2
        actually advanced (= state.observed_signatures). Aligns L4 with L2's
        FSM view, at the cost of missing tool_uses that bypassed the hook.
    """
    if not ir.completion.required_signatures and not ir.completion.required_artifacts:
        return None

    observed_set = set(observed_signatures or [])
    seen: List[Tuple[str, Dict[str, Any]]] = []
    if not strict and transcript_path:
        seen = list(_iter_transcript_tool_uses(transcript_path))

    missing_sigs: List[str] = []
    for ref in ir.completion.required_signatures:
        if strict:
            covered = ref in observed_set
        else:
            sigs = _signature_ref_to_sigs(ir, ref)
            covered = bool(sigs) and any(
                match_signature(sig, n, i) for sig in sigs for n, i in seen
            )
        if not covered:
            missing_sigs.append(ref)

    missing_arts: List[str] = []
    for art in ir.completion.required_artifacts:
        if strict:
            # artifacts have no direct strict equivalent; trust transcript if available
            covered = bool(transcript_path) and any(
                match_signature(art, n, i)
                for n, i in (list(_iter_transcript_tool_uses(transcript_path)) if not seen else seen)
            )
        else:
            covered = any(match_signature(art, n, i) for n, i in seen)
        if not covered:
            missing_arts.append(signature_label(art))

    if not missing_sigs and not missing_arts:
        return None

    parts = []
    if missing_sigs: parts.append(f"missing required steps: {missing_sigs}")
    if missing_arts: parts.append(f"missing required artifacts: {missing_arts}")
    layer = "L4-strict" if strict else "L4"
    return Decision(
        kind=DECISION_HARD_DENY, layer=layer,
        reason="completion-assertion failed — " + "; ".join(parts),
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


def ir_summary(ir: IR, satisfied: List[str]) -> Dict[str, Any]:
    """Compact view of the IR for the L3 judge."""
    sat = list(satisfied)
    return {
        "skill": ir.skill,
        "steps": [
            {
                "id": s.step_id,
                "description": s.description,
                "depends_on": s.depends_on,
                "satisfied": s.step_id in sat,
            }
            for s in ir.steps
        ],
        "satisfied_step_ids": sat,
        "unsatisfied_step_ids": [s.step_id for s in ir.steps if s.step_id not in sat],
        "next_actionable_step_ids": next_unsatisfied_steps(ir, sat),
    }
