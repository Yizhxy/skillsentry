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
        "satisfied": [],         # list[str] of step ids
        "observed_signatures": [],  # list[str] like '<step_id>.must_call' once a step's must_call seen
        "recent_decisions": [],     # list of {tool, step, kind, ts}
        # v3 additions:
        "no_advance_streak": 0,     # consecutive PreToolUse calls without L2 advance; reset on advance
        "judge_cache": {},          # {cache_key: {"verdict": {...}, "ts": float}} — per-session L3 cache
        # v3.1 additions: tally counters for session_summary on Stop.
        "counters": {
            "decisions_by_layer": {},   # "L1"|"L2"|"L2.5"|"L3"|"L4" → count
            "decisions_by_kind":  {},   # "hard-deny"|"soft-deny"|"hint"|"allow" → count
            "judge_cache_hits":   0,
            "judge_cache_misses": 0,
            "stale_budget_hints": 0,
            "post_backfills":     0,
            "no_advance_max":     0,
            "variance_downgrades": 0,
        },
    }


JUDGE_CACHE_TTL = float(os.environ.get("SKILLSENTRY_JUDGE_CACHE_TTL", "600"))
JUDGE_CACHE_MAX = int(os.environ.get("SKILLSENTRY_JUDGE_CACHE_MAX", "64"))


def judge_cache_get(state: Dict[str, Any], key: str) -> Optional[Dict[str, Any]]:
    cache = state.get("judge_cache") or {}
    entry = cache.get(key)
    if not entry:
        return None
    if time.time() - float(entry.get("ts", 0)) > JUDGE_CACHE_TTL:
        return None
    return entry.get("verdict")


def judge_cache_put(state: Dict[str, Any], key: str, verdict: Dict[str, Any]) -> None:
    cache = state.setdefault("judge_cache", {})
    # Drop expired entries first, then trim oldest if over cap.
    now = time.time()
    expired = [k for k, v in cache.items()
               if now - float(v.get("ts", 0)) > JUDGE_CACHE_TTL]
    for k in expired:
        cache.pop(k, None)
    cache[key] = {"verdict": verdict, "ts": now}
    if len(cache) > JUDGE_CACHE_MAX:
        # FIFO trim: drop the oldest 25% of entries.
        items = sorted(cache.items(), key=lambda kv: kv[1].get("ts", 0))
        drop = max(1, len(items) // 4)
        for k, _ in items[:drop]:
            cache.pop(k, None)


def record_decision(state: Dict[str, Any], tool: str, step: Optional[str], kind: str) -> None:
    """Append a decision to the cooldown log; trim to last 32 entries."""
    state.setdefault("recent_decisions", []).append({
        "tool": tool, "step": step, "kind": kind, "ts": time.time(),
    })
    state["recent_decisions"] = state["recent_decisions"][-32:]


def cooldown_downgrade(
    state: Dict[str, Any], tool: str, step: Optional[str], kind: str
) -> str:
    """Return the (possibly downgraded) decision kind given cooldown history.

    Same (tool, step, kind) seen within COOLDOWN_SEC → step the kind down one tier.
    Order: hard-deny > soft-deny > hint > allow.
    """
    if kind == "allow":
        return kind
    now = time.time()
    cutoff = now - COOLDOWN_SEC
    matches = [
        d for d in state.get("recent_decisions", [])
        if d.get("tool") == tool and d.get("step") == step and d.get("kind") == kind
        and d.get("ts", 0) >= cutoff
    ]
    if not matches:
        return kind
    # Repeated within window → downgrade
    return _downgrade(kind)


def _downgrade(kind: str) -> str:
    return {
        "hard-deny": "soft-deny",
        "soft-deny": "hint",
        "hint": "allow",
    }.get(kind, "allow")


def mark_satisfied(state: Dict[str, Any], step_id: str) -> None:
    sat = state.setdefault("satisfied", [])
    if step_id not in sat:
        sat.append(step_id)


def add_observed_signature(state: Dict[str, Any], sig_ref: str) -> None:
    obs = state.setdefault("observed_signatures", [])
    if sig_ref not in obs:
        obs.append(sig_ref)


def bump_no_advance(state: Dict[str, Any]) -> int:
    """Increment no-advance streak; return new value."""
    new = int(state.get("no_advance_streak", 0)) + 1
    state["no_advance_streak"] = new
    counters = state.setdefault("counters", {})
    counters["no_advance_max"] = max(int(counters.get("no_advance_max", 0)), new)
    return new


def reset_no_advance(state: Dict[str, Any]) -> None:
    state["no_advance_streak"] = 0


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
