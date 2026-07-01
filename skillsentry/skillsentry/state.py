"""Per-session state persistence + cooldown logic."""
from __future__ import annotations

import json
import os
import pathlib
import time
from typing import Any, Dict, List, Optional

STATE_DIR = pathlib.Path(os.environ.get("SKILLSENTRY_STATE_DIR", "/tmp/skillsentry"))
COOLDOWN_SEC = float(os.environ.get("SKILLSENTRY_COOLDOWN_SEC", "120"))


def _state_path(session_id: str) -> pathlib.Path:
    sid = session_id or "default"
    return STATE_DIR / f"{sid}.json"


def load_state(session_id: str) -> Dict[str, Any]:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    p = _state_path(session_id)
    if not p.exists():
        return _empty_state(session_id)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_state(session_id)


def save_state(session_id: str, state: Dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    p = _state_path(session_id)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)


def _empty_state(session_id: str) -> Dict[str, Any]:
    return {
        "session_id": session_id,
        "skill": None,           # captured skill name
        "workflow": None,        # raw SKILL.md text
        "rules_path": None,      # str path to rules.json (None if no IR)
        "satisfied": [],         # list[str] of COMPLETED step ids (all logical actions matched)
        "matched_actions": {},   # {step_id: [actionId, ...]} logical actions matched so far
        "observed_signatures": [],  # list[str] like '<step_id>.completed' once a step is completed
        "recent_decisions": [],     # list of {tool, step, kind, ts}
        # tally counters for session_summary on Stop.
        "counters": {
            "decisions_by_layer": {},   # "L1"|"L2"|"L3" → count
            "decisions_by_kind":  {},   # "hard-deny"|"soft-deny"|"allow" → count
            "post_backfills":     0,
        },
    }


def record_decision(state: Dict[str, Any], tool: str, step: Optional[str], kind: str) -> None:
    """Append a decision to the cooldown log; trim to last 32 entries."""
    state.setdefault("recent_decisions", []).append({
        "tool": tool, "step": step, "kind": kind, "ts": time.time(),
    })
    state["recent_decisions"] = state["recent_decisions"][-32:]


def cooldown_allow(
    state: Dict[str, Any], tool: str, step: Optional[str], kind: str
) -> str:
    """Temporary-deny-then-allow for failure patterns (paper §III-D).

    A failure-pattern hit is a step-scoped hard-deny: it is enforced the FIRST
    time and returns the failure reason as a hint, giving the agent a chance to
    reconsider. If the agent issues the same action again (same tool+step within
    COOLDOWN_SEC), it is allowed through — mined failure patterns are advisory
    evidence, not an absolute block.

    Order violations (soft-deny, re-plan expected) and global safety denials
    (hard-deny with no matched step) are never relaxed.
    """
    if kind != "hard-deny" or step is None:
        return kind
    cutoff = time.time() - COOLDOWN_SEC
    seen_before = any(
        d.get("tool") == tool and d.get("step") == step and d.get("kind") == "hard-deny"
        and d.get("ts", 0) >= cutoff
        for d in state.get("recent_decisions", [])
    )
    return "allow" if seen_before else kind


def mark_satisfied(state: Dict[str, Any], step_id: str) -> None:
    sat = state.setdefault("satisfied", [])
    if step_id not in sat:
        sat.append(step_id)


def record_matched_action(
    state: Dict[str, Any], step_id: str, action_ids: List[int]
) -> None:
    """Record that one or more of a step's logical actions have been matched."""
    matched = state.setdefault("matched_actions", {})
    lst = matched.setdefault(step_id, [])
    for aid in action_ids:
        if aid not in lst:
            lst.append(aid)


def add_observed_signature(state: Dict[str, Any], sig_ref: str) -> None:
    obs = state.setdefault("observed_signatures", [])
    if sig_ref not in obs:
        obs.append(sig_ref)


def bump_counter(state: Dict[str, Any], name: str, n: int = 1) -> None:
    counters = state.setdefault("counters", {})
    counters[name] = int(counters.get(name, 0)) + n


def bump_layer_kind(state: Dict[str, Any], layer: str, kind: str) -> None:
    counters = state.setdefault("counters", {})
    bl = counters.setdefault("decisions_by_layer", {})
    bk = counters.setdefault("decisions_by_kind", {})
    if layer:
        bl[layer] = int(bl.get(layer, 0)) + 1
    if kind:
        bk[kind] = int(bk.get(kind, 0)) + 1
