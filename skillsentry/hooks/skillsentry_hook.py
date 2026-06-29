#!/usr/bin/env python3
"""SkillSentry v2 (basic) — Claude Code hook entry point.

Wire-up in `.claude/settings.json`:
  "hooks": {
    "PostToolUse":  [{ "matcher": "Skill",
                       "hooks": [{ "type": "command",
                         "command": "python3 /data/hxy/Skillfuzz/hooks/skillsentry_hook.py" }] }],
    "PreToolUse":   [{ "hooks": [{ "type": "command",
                         "command": "python3 /data/hxy/Skillfuzz/hooks/skillsentry_hook.py" }] }],
    "Stop":         [{ "hooks": [{ "type": "command",
                         "command": "python3 /data/hxy/Skillfuzz/hooks/skillsentry_hook.py" }] }],
    "SubagentStop": [{ "hooks": [{ "type": "command",
                         "command": "python3 /data/hxy/Skillfuzz/hooks/skillsentry_hook.py" }] }]
  }

Pipeline per PreToolUse:
  L1 (deny-list)  → if hits, hard-deny.
  L2 (FSM order)  → if pending matches a step's must_call but its requires
                    are unsatisfied, soft-deny; otherwise mark step satisfied.
  L3 (LLM judge)  → only when L1/L2 don't fire; honest 'maybe deviated' returns
                    hint or soft-deny based on confidence.
  Cooldown: same (tool, step, kind) repeated within window → downgrade by one
            tier to avoid deny death-loops.

Pipeline on Stop / SubagentStop:
  L4 (completion assertion) → block if any required signature/artifact missing.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time
from typing import Any, Dict, List, Optional

# Make `skillsentry` package importable regardless of where Claude Code launches us.
_HERE = pathlib.Path(__file__).resolve()
_REPO_ROOT = _HERE.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from skillsentry.ir import IR, find_rules_for_skill, load_rules_file, load_rules_file_validated  # noqa: E402
from skillsentry.fsm import evaluate_l2, matched_steps  # noqa: E402
from skillsentry.judge import call_judge, call_judge_voting  # noqa: E402
from skillsentry.layers import (  # noqa: E402
    Decision,
    DECISION_ALLOW,
    DECISION_HARD_DENY,
    DECISION_HINT,
    DECISION_SOFT_DENY,
    evaluate_l1,
    evaluate_l4,
    evaluate_stale_budget,
    ir_summary,
    render_pretooluse_output,
    render_stop_output,
)
from skillsentry.state import (  # noqa: E402
    add_observed_signature,
    bump_counter,
    bump_layer_kind,
    bump_no_advance,
    cooldown_downgrade,
    judge_cache_get,
    judge_cache_put,
    load_state,
    mark_satisfied,
    record_decision,
    reset_no_advance,
    save_state,
)


LOG_PATH = os.environ.get("SKILLSENTRY_LOG")
TRACE_CHARS = int(os.environ.get("SKILLSENTRY_TRACE_CHARS", "20000"))
JUDGE_TIMEOUT = float(os.environ.get("SKILLSENTRY_JUDGE_TIMEOUT", "30"))
JUDGE_CONF_DENY = float(os.environ.get("SKILLSENTRY_JUDGE_CONF_DENY", "0.6"))
JUDGE_VOTES = int(os.environ.get("SKILLSENTRY_JUDGE_VOTES", "1"))
DISABLE_L3 = os.environ.get("SKILLSENTRY_DISABLE_L3", "1") == "1"
DISABLE_L25 = os.environ.get("SKILLSENTRY_DISABLE_L25", "1") == "1"
GUARD_MODE = os.environ.get("SKILLSENTRY_MODE", "strict")  # strict|soft|monitor|off
# v3: stale-budget (L2.5) — fire a HINT after K consecutive no-advance calls.
STALE_BUDGET_THRESHOLD = int(os.environ.get("SKILLSENTRY_STALE_BUDGET_K", "5"))
# v3: L3 in-session verdict cache — skip duplicate LLM calls within a session.
JUDGE_CACHE_ENABLED = os.environ.get("SKILLSENTRY_JUDGE_CACHE", "1") != "0"


def log(record: Dict[str, Any]) -> None:
    if not LOG_PATH:
        return
    try:
        record["ts"] = time.time()
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _read_transcript_tail(path: Optional[str], n: int) -> str:
    if not path or not os.path.exists(path):
        return ""
    try:
        return pathlib.Path(path).read_text(encoding="utf-8", errors="replace")[-n:]
    except OSError:
        return ""


_RULES_VALIDATED_FOR_PATH: set = set()  # process-level "warned once" dedup


def _maybe_capture_skill_from_read(
    data: Dict[str, Any], state: Dict[str, Any]
) -> bool:
    """v3.1: PostToolUse(Read) fallback skill capture.

    If a Read targets a path containing `.../skills/<name>/SKILL.md` (or
    `.../<name>/SKILL.md`), infer the skill name from the path segment
    preceding SKILL.md and seed state. Returns True if a new skill was
    captured. No-op if state already has a skill, or path doesn't match.
    """
    if state.get("skill"):
        return False  # already captured via PostToolUse(Skill) — don't override

    tool_input = data.get("tool_input") or {}
    path = tool_input.get("file_path") or tool_input.get("path") or ""
    if not isinstance(path, str) or not path.endswith("SKILL.md"):
        return False

    parts = path.replace("\\", "/").rstrip("/").split("/")
    if len(parts) < 2 or parts[-1] != "SKILL.md":
        return False
    skill_name = parts[-2]
    if not skill_name or skill_name == "skills":
        return False

    # Prefer the actual Read response if available, else fall back to disk.
    resp = data.get("tool_response")
    workflow_text = ""
    if isinstance(resp, str) and resp.strip():
        workflow_text = resp
    elif isinstance(resp, dict):
        for k in ("content", "result", "output", "text"):
            v = resp.get(k)
            if isinstance(v, str) and v.strip():
                workflow_text = v
                break
    if not workflow_text:
        workflow_text = _load_skill_from_disk(skill_name, cwd=data.get("cwd"))

    state["skill"] = skill_name
    state["workflow"] = workflow_text or state.get("workflow")
    rules_path = find_rules_for_skill(skill_name, cwd=data.get("cwd"))
    state["rules_path"] = str(rules_path) if rules_path else None
    log({"event": "capture_skill_via_read", "skill": skill_name,
         "path": path, "workflow_chars": len(workflow_text or ""),
         "rules_path": state["rules_path"]})
    return True


def _try_load_rules(skill_name: str, cwd: Optional[str]) -> Optional[IR]:
    p = find_rules_for_skill(skill_name, cwd=cwd)
    if not p:
        return None
    try:
        ir, warnings = load_rules_file_validated(p)
    except (OSError, json.JSONDecodeError, KeyError):
        return None
    # v3.1: warn-once per rules.json path so authors see schema issues
    # without spamming the log on every PreToolUse.
    p_str = str(p)
    if warnings and p_str not in _RULES_VALIDATED_FOR_PATH:
        log({"event": "rules_schema_warnings", "skill": skill_name,
             "rules_path": p_str, "warnings": warnings})
        _RULES_VALIDATED_FOR_PATH.add(p_str)
    return ir


def _load_skill_from_disk(skill_name: str, cwd: Optional[str]) -> str:
    cwd_p = pathlib.Path(cwd or os.getcwd())
    candidates = [
        cwd_p / ".claude" / "skills" / skill_name / "SKILL.md",
        cwd_p / "skills" / skill_name / "SKILL.md",
        cwd_p / "environment" / "skills" / skill_name / "SKILL.md",
        pathlib.Path.home() / ".claude" / "skills" / skill_name / "SKILL.md",
    ]
    for up in [cwd_p, *cwd_p.parents][:4]:
        candidates.append(up / "environment" / "skills" / skill_name / "SKILL.md")
        candidates.append(up / "skills" / skill_name / "SKILL.md")
    for p in candidates:
        if p.exists():
            try:
                return p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
    return ""


def _capture_skill(data: Dict[str, Any], state: Dict[str, Any]) -> None:
    skill = (data.get("tool_input") or {}).get("skill", "")
    if not skill:
        return
    resp = data.get("tool_response")
    workflow_text = ""
    if isinstance(resp, str) and resp.strip():
        workflow_text = resp
    elif isinstance(resp, dict):
        for k in ("content", "result", "output", "text"):
            v = resp.get(k)
            if isinstance(v, str) and v.strip():
                workflow_text = v
                break
    if not workflow_text:
        workflow_text = _load_skill_from_disk(skill, cwd=data.get("cwd"))

    state["skill"] = skill
    state["workflow"] = workflow_text or state.get("workflow")
    rules_path = find_rules_for_skill(skill, cwd=data.get("cwd"))
    state["rules_path"] = str(rules_path) if rules_path else None
    log({"event": "capture_skill", "skill": skill,
         "workflow_chars": len(workflow_text or ""), "rules_path": state["rules_path"]})


def _apply_mode(decision: Decision) -> Decision:
    """Honor SKILLSENTRY_MODE: off → allow everything; monitor → log-only;
    soft → downgrade hard-deny to soft-deny; strict → as-is."""
    if GUARD_MODE == "off" or GUARD_MODE == "monitor":
        return Decision(kind=DECISION_ALLOW, reason=decision.reason,
                        layer=decision.layer, matched_step=decision.matched_step)
    if GUARD_MODE == "soft" and decision.kind == DECISION_HARD_DENY:
        return Decision(kind=DECISION_SOFT_DENY, reason=decision.reason,
                        layer=decision.layer, matched_step=decision.matched_step)
    return decision


def _judge_cache_key(tool_name: str, tool_input: Any, satisfied: List[str]) -> str:
    """Stable key for L3 verdict cache. Order satisfied list before hashing
    so identical state under different insertion order shares the same key."""
    import hashlib
    payload = json.dumps(
        {"t": tool_name, "i": tool_input, "s": sorted(satisfied or [])},
        sort_keys=True, ensure_ascii=False, default=str,
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _decide_pretooluse(
    data: Dict[str, Any], state: Dict[str, Any], ir: IR
) -> Decision:
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input") or {}

    # L1
    l1 = evaluate_l1(ir, tool_name, tool_input)
    if l1:
        return l1

    # L2
    l2 = evaluate_l2(ir, state.get("satisfied", []), tool_name, tool_input)
    if l2.kind == "order_violation":
        return Decision(
            kind=DECISION_SOFT_DENY, layer="L2", reason=l2.reason,
            matched_step=l2.matched_step,
        )
    advanced_step: Optional[str] = None
    if l2.kind == "allow_satisfies":
        mark_satisfied(state, l2.matched_step)
        add_observed_signature(state, f"{l2.matched_step}.must_call")
        advanced_step = l2.matched_step
        reset_no_advance(state)
    else:
        # No FSM advance — bump the streak counter so L2.5 (stale-budget)
        # can fire after enough idle calls.
        streak = bump_no_advance(state)
        l25 = None if DISABLE_L25 else evaluate_stale_budget(
            ir, state.get("satisfied", []), streak, STALE_BUDGET_THRESHOLD,
        )
        if l25:
            bump_counter(state, "stale_budget_hints")
            log({"event": "stale_budget_hint", "streak": streak,
                 "next_step": l25.matched_step})
            return l25

    # L3
    if DISABLE_L3:
        return Decision(
            kind=DECISION_ALLOW,
            layer="L2" if advanced_step else "L0",
            reason=f"advanced step {advanced_step}" if advanced_step else "",
            matched_step=advanced_step,
        )

    workflow = state.get("workflow") or ""
    pending = {"tool_name": tool_name, "tool_input": tool_input}
    trace_tail = _read_transcript_tail(data.get("transcript_path"), TRACE_CHARS)
    summary = ir_summary(ir, state.get("satisfied", []))

    cache_key = _judge_cache_key(tool_name, tool_input, state.get("satisfied", []))
    cached = judge_cache_get(state, cache_key) if JUDGE_CACHE_ENABLED else None
    if cached is not None:
        log({"event": "judge_cache_hit", "tool": tool_name, "key": cache_key[:12],
             "verdict": {k: cached.get(k) for k in
                         ("deviated", "confidence", "deviation_class", "_variance")}})
        bump_counter(state, "judge_cache_hits")
        verdict = cached
    elif JUDGE_VOTES > 1:
        bump_counter(state, "judge_cache_misses")
        verdict, all_votes = call_judge_voting(
            skill=ir.skill, workflow=workflow, trace_tail=trace_tail,
            pending=pending, ir_summary=summary, timeout=JUDGE_TIMEOUT,
            n_votes=JUDGE_VOTES,
        )
        log({"event": "judge_vote",
             "votes_n": JUDGE_VOTES,
             "variance": verdict.get("_variance"),
             "deviated_count": sum(1 for v in all_votes if v.get("deviated") is True),
             "individual": [
                 {"deviated": v.get("deviated"),
                  "confidence": v.get("confidence"),
                  "deviation_class": v.get("deviation_class"),
                  "_meta": v.get("_meta")}
                 for v in all_votes
             ]})
        log({"event": "judge", "tool": tool_name, "verdict": {
            k: verdict[k] for k in
            ("deviated", "confidence", "deviation_class", "target_step",
             "suggested_step", "reason", "_meta", "_variance")
            if k in verdict
        }})
        if JUDGE_CACHE_ENABLED:
            judge_cache_put(state, cache_key, verdict)
    else:
        bump_counter(state, "judge_cache_misses")
        verdict = call_judge(
            skill=ir.skill, workflow=workflow, trace_tail=trace_tail,
            pending=pending, ir_summary=summary, timeout=JUDGE_TIMEOUT,
        )
        log({"event": "judge", "tool": tool_name, "verdict": verdict})
        if JUDGE_CACHE_ENABLED and verdict.get("_meta") not in ("error", "skipped"):
            judge_cache_put(state, cache_key, verdict)

    if not verdict.get("deviated"):
        return Decision(
            kind=DECISION_ALLOW,
            layer="L3" if not advanced_step else "L2+L3",
            reason=verdict.get("reason", ""),
            matched_step=advanced_step,
        )

    conf = float(verdict.get("confidence") or 0.0)
    variance = int(verdict.get("_variance") or 1)
    # v3 Finding 13: split vote (variance >= 2) means the judges disagree;
    # force HINT regardless of mean confidence so the agent gets a cue but
    # not a block. Unanimous (variance == 1) keeps the old confidence-gated
    # SOFT-DENY / HINT split.
    if variance >= 2:
        kind = DECISION_HINT
        bump_counter(state, "variance_downgrades")
        log({"event": "variance_downgrade", "tool": tool_name,
             "variance": variance, "confidence": conf})
    elif conf >= JUDGE_CONF_DENY:
        kind = DECISION_SOFT_DENY
    else:
        kind = DECISION_HINT
    return Decision(
        kind=kind, layer="L3",
        reason=verdict.get("reason", "judge flagged deviation"),
        matched_step=verdict.get("target_step") or None,
    )


def _handle_pretooluse(data: Dict[str, Any]) -> int:
    session_id = data.get("session_id") or "default"
    state = load_state(session_id)

    tool_name = data.get("tool_name", "")
    if tool_name == "Skill":
        return 0  # never gate the Skill loader itself
    if not state.get("skill"):
        return 0  # no skill captured yet → nothing to enforce against

    ir = _try_load_rules(state["skill"], cwd=data.get("cwd"))
    if not ir:
        # Rules file not found — fall back to L3-only via legacy path.
        log({"event": "no_rules", "skill": state["skill"]})
        if DISABLE_L3:
            return 0
        decision = _decide_pretooluse_no_ir(data, state)
    else:
        decision = _decide_pretooluse(data, state, ir)

    decision = _apply_mode(decision)
    decision_kind = cooldown_downgrade(state, tool_name, decision.matched_step, decision.kind)
    if decision_kind != decision.kind:
        log({"event": "cooldown_downgrade", "from": decision.kind, "to": decision_kind,
             "tool": tool_name, "step": decision.matched_step})
        decision = Decision(kind=decision_kind, layer=decision.layer,
                            reason=decision.reason + " [cooldown-downgraded]",
                            matched_step=decision.matched_step)

    record_decision(state, tool_name, decision.matched_step, decision.kind)
    bump_layer_kind(state, decision.layer, decision.kind)
    save_state(session_id, state)
    log({"event": "pretool_decision", "tool": tool_name,
         "kind": decision.kind, "layer": decision.layer,
         "step": decision.matched_step, "reason": decision.reason})

    out = render_pretooluse_output(decision)
    if out:
        print(json.dumps(out, ensure_ascii=False))
    return 0


def _decide_pretooluse_no_ir(data: Dict[str, Any], state: Dict[str, Any]) -> Decision:
    """Fallback to legacy L3-only behaviour when no rules.json is present."""
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input") or {}
    workflow = state.get("workflow") or ""
    pending = {"tool_name": tool_name, "tool_input": tool_input}
    trace_tail = _read_transcript_tail(data.get("transcript_path"), TRACE_CHARS)
    verdict = call_judge(
        skill=state.get("skill") or "", workflow=workflow, trace_tail=trace_tail,
        pending=pending, ir_summary={}, timeout=JUDGE_TIMEOUT,
    )
    log({"event": "judge_no_ir", "tool": tool_name, "verdict": verdict})
    if not verdict.get("deviated"):
        return Decision(kind=DECISION_ALLOW, layer="L3")
    return Decision(
        kind=DECISION_SOFT_DENY, layer="L3",
        reason=verdict.get("reason", "workflow deviation"),
    )


STOP_BLOCK_CAP = int(os.environ.get("SKILLSENTRY_STOP_BLOCK_CAP", "2"))
L4_STRICT = os.environ.get("SKILLSENTRY_L4_STRICT", "0") == "1"


def _emit_session_summary(session_id: str, state: Dict[str, Any],
                          outcome: str, ir: Optional[IR]) -> None:
    """v3.1: one aggregated log line per Stop event for downstream metrics.
    Includes coverage, decision tally, and v3 feature counters. Cheap, runs
    on Stop / SubagentStop only — no per-PreToolUse overhead."""
    counters = state.get("counters") or {}
    coverage = None
    if ir is not None and ir.steps:
        sat = set(state.get("satisfied", []))
        coverage = round(len([s for s in ir.steps if s.id in sat]) / len(ir.steps), 3)
    log({
        "event": "session_summary",
        "session": session_id,
        "skill": state.get("skill"),
        "outcome": outcome,           # "stop_pass" | "stop_block" | "stop_block_capped"
        "satisfied": list(state.get("satisfied", [])),
        "coverage": coverage,
        "observed_signatures": list(state.get("observed_signatures", [])),
        "stop_block_count": int(state.get("stop_block_count", 0)),
        "decisions_by_layer": dict(counters.get("decisions_by_layer") or {}),
        "decisions_by_kind": dict(counters.get("decisions_by_kind") or {}),
        "judge_cache_hits": int(counters.get("judge_cache_hits", 0)),
        "judge_cache_misses": int(counters.get("judge_cache_misses", 0)),
        "stale_budget_hints": int(counters.get("stale_budget_hints", 0)),
        "post_backfills": int(counters.get("post_backfills", 0)),
        "no_advance_max": int(counters.get("no_advance_max", 0)),
        "variance_downgrades": int(counters.get("variance_downgrades", 0)),
    })


def _handle_stop(data: Dict[str, Any]) -> int:
    session_id = data.get("session_id") or "default"
    state = load_state(session_id)
    if not state.get("skill"):
        return 0
    ir = _try_load_rules(state["skill"], cwd=data.get("cwd"))
    if not ir:
        # v3.2: still emit a session_summary so trace-replay / offline
        # aggregation get a row even for skills without a rules.json.
        _emit_session_summary(session_id, state, "stop_pass_no_rules", None)
        return 0
    decision = evaluate_l4(
        ir, data.get("transcript_path"),
        observed_signatures=state.get("observed_signatures", []),
        strict=L4_STRICT,
    )
    if not decision:
        state["stop_block_count"] = 0
        save_state(session_id, state)
        log({"event": "stop_pass", "skill": state["skill"]})
        _emit_session_summary(session_id, state, "stop_pass", ir)
        return 0
    decision = _apply_mode(decision)
    if decision.kind == DECISION_ALLOW:
        save_state(session_id, state)
        return 0

    # Cap consecutive Stop blocks per session: after STOP_BLOCK_CAP times, let
    # the agent terminate with a final hint instead of looping forever.
    n = int(state.get("stop_block_count", 0)) + 1
    state["stop_block_count"] = n
    save_state(session_id, state)
    if n > STOP_BLOCK_CAP:
        log({"event": "stop_block_capped", "skill": state["skill"], "count": n,
             "reason": decision.reason})
        _emit_session_summary(session_id, state, "stop_block_capped", ir)
        return 0  # allow termination

    log({"event": "stop_block", "skill": state["skill"], "count": n,
         "layer": decision.layer, "reason": decision.reason})
    # v3.2: also emit a summary on every block (not only on capped) so that
    # offline replay / aggregator always has a row per Stop event. Multiple
    # Stops in one session → aggregator keeps the latest summary.
    _emit_session_summary(session_id, state, "stop_block", ir)
    print(json.dumps(render_stop_output(decision), ensure_ascii=False))
    return 0


def _detect_skill_from_environment(data: Dict[str, Any], state: Dict[str, Any]) -> bool:
    """v3.2: Proactive skill detection at SessionStart.

    Attempts to infer the skill from:
    1. Task directory structure (skills/ subdirectory)
    2. instruction.md content (skill name references)
    3. SKILL.md files in common locations

    Returns True if a skill was detected and loaded.
    """
    if state.get("skill"):
        return False  # Already captured

    cwd = data.get("cwd") or os.getcwd()
    cwd_p = pathlib.Path(cwd)

    # Strategy 1: Check for skills/ directory
    skills_dir = cwd_p / "skills"
    if skills_dir.exists() and skills_dir.is_dir():
        # List all skill directories
        skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()]
        if len(skill_dirs) == 1:
            # Exactly one skill found - use it
            skill_name = skill_dirs[0].name
            skill_md = skill_dirs[0] / "SKILL.md"
            try:
                workflow_text = skill_md.read_text(encoding="utf-8", errors="replace")
                state["skill"] = skill_name
                state["workflow"] = workflow_text
                rules_path = find_rules_for_skill(skill_name, cwd=cwd)
                state["rules_path"] = str(rules_path) if rules_path else None
                log({"event": "detect_skill_from_dir", "skill": skill_name,
                     "workflow_chars": len(workflow_text), "rules_path": state["rules_path"]})
                return True
            except OSError:
                pass
        elif len(skill_dirs) > 1:
            # Multiple skills - try to infer from instruction.md
            log({"event": "multiple_skills_found", "skills": [d.name for d in skill_dirs]})

    # Strategy 2: Check instruction.md for skill hints
    instruction = cwd_p / "instruction.md"
    if instruction.exists():
        try:
            content = instruction.read_text(encoding="utf-8", errors="replace")
            # Look for /skill-name patterns
            import re
            skill_refs = re.findall(r'/([a-z][a-z0-9-]+)', content)
            if skill_refs:
                # Try each candidate
                for skill_name in skill_refs:
                    workflow_text = _load_skill_from_disk(skill_name, cwd=cwd)
                    if workflow_text:
                        state["skill"] = skill_name
                        state["workflow"] = workflow_text
                        rules_path = find_rules_for_skill(skill_name, cwd=cwd)
                        state["rules_path"] = str(rules_path) if rules_path else None
                        log({"event": "detect_skill_from_instruction", "skill": skill_name,
                             "workflow_chars": len(workflow_text), "rules_path": state["rules_path"]})
                        return True
        except OSError:
            pass

    return False


def _fix_session_file_permissions(data: Dict[str, Any]) -> None:
    """Fix permissions on session files so hooks can read them.

    Claude Code agent creates session files with 600 permissions, which prevents
    hooks from reading them. This function finds and fixes those permissions.
    """
    transcript_path = data.get("transcript_path")
    if not transcript_path:
        return

    try:
        # Fix the transcript file itself
        transcript_file = pathlib.Path(transcript_path)
        if transcript_file.exists():
            os.chmod(transcript_file, 0o644)

        # Fix parent directories to be traversable
        sessions_dir = transcript_file.parent
        if sessions_dir.exists():
            os.chmod(sessions_dir, 0o755)
            # Fix grandparent too
            if sessions_dir.parent.exists():
                os.chmod(sessions_dir.parent, 0o755)
    except (OSError, PermissionError) as e:
        # Log but don't fail - permissions might already be correct
        log({"event": "permission_fix_error", "error": str(e), "path": transcript_path})


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    # Fix permissions on session files before doing anything else
    _fix_session_file_permissions(data)

    event = data.get("hook_event_name", "")
    session_id = data.get("session_id") or "default"
    log({"event": "hook_invoked", "kind": event, "tool": data.get("tool_name"),
         "session": session_id})

    if event == "PostToolUse" and data.get("tool_name") == "Skill":
        state = load_state(session_id)
        _capture_skill(data, state)
        save_state(session_id, state)
        return 0

    if event == "PostToolUse" and data.get("tool_name") == "Read":
        # v3.1: fallback skill capture — if the agent Reads a .../SKILL.md
        # path, infer the skill name from the path and seed state. Helps when
        # the harness didn't fire PostToolUse(Skill) (e.g., direct read).
        state = load_state(session_id)
        captured = _maybe_capture_skill_from_read(data, state)
        if captured:
            save_state(session_id, state)
            return 0
        # Otherwise treat as any other non-Skill PostToolUse → run backfill.
        return _handle_posttooluse_nonskill(data)

    if event == "PostToolUse":
        # v3: backfill L2 satisfied + observed_signatures from any successful
        # non-Skill tool call. Closes the L2-state vs L4-transcript view gap
        # (Finding 3.3 / 11) when the call bypassed PreToolUse gating.
        return _handle_posttooluse_nonskill(data)

    if event == "SessionStart":
        # Pre-create state so other events have something to merge into.
        state = load_state(session_id)
        # Priority 1: explicit env var (highest precedence, set by task harness).
        # SKILLSENTRY_SKILL=<name> lets tasks enforce workflow without requiring
        # the agent to invoke /skill first (direct Bash-only workflows).
        env_skill = os.environ.get("SKILLSENTRY_SKILL", "").strip()
        if env_skill and not state.get("skill"):
            state["skill"] = env_skill
            state["workflow"] = _load_skill_from_disk(env_skill, cwd=data.get("cwd"))
            rules_path = find_rules_for_skill(env_skill, cwd=data.get("cwd"))
            state["rules_path"] = str(rules_path) if rules_path else None
            log({"event": "capture_skill_via_env", "skill": env_skill,
                 "workflow_chars": len(state["workflow"] or ""),
                 "rules_path": state["rules_path"]})
        else:
            # Priority 2: v3.2 proactive skill detection from task directory structure
            _detect_skill_from_environment(data, state)
        save_state(session_id, state)
        return 0

    if event == "PreToolUse":
        return _handle_pretooluse(data)

    if event in ("Stop", "SubagentStop"):
        return _handle_stop(data)

    return 0


def _handle_posttooluse_nonskill(data: Dict[str, Any]) -> int:
    """Mark FSM steps as satisfied if a non-Skill tool actually executed
    a step's must_call signature. Resolves the bypassPermissions case where
    PreToolUse hook never advanced the FSM (e.g., due to soft-deny + bypass)
    but the underlying call still ran — L4 transcript scan would credit it
    but L2 state would not. v3."""
    session_id = data.get("session_id") or "default"
    state = load_state(session_id)
    if not state.get("skill"):
        return 0
    ir = _try_load_rules(state["skill"], cwd=data.get("cwd"))
    if not ir:
        return 0

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input") or {}
    if not tool_name:
        return 0

    # Find matching steps (independent of requires — backfill is observational).
    steps = matched_steps(ir, tool_name, tool_input)
    if not steps:
        return 0

    sat_set = set(state.get("satisfied", []))
    advanced: List[str] = []
    for step in steps:
        if step.id in sat_set:
            continue
        # Only credit if requires already met — otherwise we'd retroactively
        # legitimize an order violation.
        if all(r in sat_set for r in step.requires):
            mark_satisfied(state, step.id)
            add_observed_signature(state, f"{step.id}.must_call")
            sat_set.add(step.id)
            advanced.append(step.id)
    if advanced:
        reset_no_advance(state)
        bump_counter(state, "post_backfills", len(advanced))
        log({"event": "post_backfill", "tool": tool_name, "advanced": advanced})
    save_state(session_id, state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
