"""L2 ordering FSM.

State per session: which step ids are 'satisfied' (their logical_actions patterns have been seen
and approved), plus the set of observed signatures for L4 completion checks.

For a pending call we look up which steps it would satisfy (via logical_actions pattern match);
if any such step has unmet depends_on, that's an order violation.

Step fields accessed via compatibility properties:
  step.must_call  → flat list of all patterns across logical_actions
  step.requires   → alias for depends_on
  step.id         → alias for step_id
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .ir import IR, Step
from .matchers import match_signature


@dataclass
class L2Result:
    kind: str  # 'no_match' | 'allow_satisfies' | 'order_violation'
    matched_step: Optional[str] = None
    missing_requires: List[str] = None
    reason: str = ""
    step_obj: Optional[Step] = None  # The actual Step object for on_enter hints


def matched_steps(ir: IR, tool_name: str, tool_input: Dict[str, Any]) -> List[Step]:
    out: List[Step] = []
    for step in ir.steps:
        for sig in step.must_call:
            if match_signature(sig, tool_name, tool_input):
                out.append(step)
                break
    return out


def evaluate_l2(
    ir: IR,
    satisfied: List[str],
    tool_name: str,
    tool_input: Dict[str, Any],
) -> L2Result:
    candidates = matched_steps(ir, tool_name, tool_input)
    if not candidates:
        return L2Result(kind="no_match")

    sat = set(satisfied)
    # Prefer steps that ADVANCE the FSM (not yet satisfied, requires met).
    # Only fall back to re-matching an already-satisfied step if no advancing
    # candidate exists. This fixes the case where a Bash command matches both
    # an already-satisfied step (e.g. load_data via read_excel) and a new step
    # (e.g. deflate_cpi via CPI.xlsx) — we should credit the new step.
    advancing = [s for s in candidates if s.id not in sat]
    already_done = [s for s in candidates if s.id in sat]

    # First, check if any advancing step has its requires satisfied.
    for step in advancing:
        missing = [r for r in step.requires if r not in sat]
        if not missing:
            return L2Result(
                kind="allow_satisfies",
                matched_step=step.id,
                reason=f"matches must_call of step {step.id}",
                step_obj=step,
            )

    # Fall back: if an already-done step matches (and its requires are met),
    # allow it with no FSM side-effect (step stays satisfied, no real advance).
    # Use kind="allow_already_done" so callers know NOT to reset the stale streak.
    for step in already_done:
        missing = [r for r in step.requires if r not in sat]
        if not missing:
            return L2Result(
                kind="allow_already_done",
                matched_step=step.id,
                reason=f"matches must_call of step {step.id} (already satisfied)",
                step_obj=step,
            )

    # All candidates have unmet requires — report the most actionable violation.
    # Prefer advancing steps over already-done ones for the error message.
    violation_candidates = advancing if advancing else already_done
    step = violation_candidates[0]
    missing = [r for r in step.requires if r not in sat]
    base = f"step {step.id} requires {missing} which are not yet satisfied"
    # v3: append actionable suggestion (mirror of L1 Cycle 1 Finding 2 fix).
    from .layers import suggest_for_missing_requires  # avoid circular import
    hint = suggest_for_missing_requires(ir, missing)
    reason = f"{base}. {hint}" if hint else base
    return L2Result(
        kind="order_violation",
        matched_step=step.id,
        missing_requires=missing,
        reason=reason,
        step_obj=step,
    )


def matches_step_must_call(step: Step, tool_name: str, tool_input: Dict[str, Any]) -> bool:
    return any(match_signature(sig, tool_name, tool_input) for sig in step.must_call)
