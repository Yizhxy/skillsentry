"""L2 ordering FSM (procedure-checker core).

Per-session FSM state:
  - `satisfied`: step ids that are COMPLETED (all of their logical actions matched).
  - `matched_actions`: {step_id: [actionId, ...]} logical actions matched so far.
  - `observed_signatures`: '<step_id>.completed' once a step is completed.

A logical action is matched when a tool call conforms to ANY of its alternative
action patterns. A step is completed only after ALL of its logical actions have
been matched (M(s_i) = LA(s_i), paper §III-D); a step with no logical actions is
completed once its depends_on are completed.

Step fields accessed via compatibility properties:
  step.action_patterns → flat list of all action patterns across logical_actions
  step.requires        → alias for depends_on
  step.id              → alias for step_id
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .ir import IR, Step
from .matchers import match_signature


@dataclass
class L2Result:
    # 'no_match' | 'allow_progress' | 'allow_already_done' | 'order_violation'
    kind: str
    matched_step: Optional[str] = None
    matched_action_ids: List[int] = field(default_factory=list)
    missing_requires: List[str] = None
    reason: str = ""
    step_obj: Optional[Step] = None  # the Step object, for on_enter hints


def matched_logical_actions(
    step: Step, tool_name: str, tool_input: Dict[str, Any]
) -> List[int]:
    """Return the actionIds of `step`'s logical actions that this call matches.

    A logical action matches when the call conforms to ANY of its alternative
    action patterns.
    """
    out: List[int] = []
    for la in step.logical_actions:
        if any(match_signature(sig, tool_name, tool_input) for sig in la.patterns):
            out.append(la.action_id)
    return out


def recompute_completion(
    ir: IR, satisfied: List[str], matched_actions: Dict[str, List[int]]
) -> set:
    """Return the set of completed step ids.

    A step is completed when every one of its logical actions has been matched
    (M(s_i) = LA(s_i)) and its depends_on are completed. A step with no logical
    actions is completed once its depends_on are completed. Iterates to a fixpoint
    so completing a step can cascade to dependent (e.g. action-less) steps.
    """
    done = set(satisfied)
    changed = True
    while changed:
        changed = False
        for step in ir.steps:
            if step.id in done:
                continue
            if not all(d in done for d in step.depends_on):
                continue
            required = {la.action_id for la in step.logical_actions}
            if required.issubset(set(matched_actions.get(step.id, []))):
                done.add(step.id)
                changed = True
    return done


def evaluate_l2(
    ir: IR,
    satisfied: List[str],
    matched_actions: Dict[str, List[int]],
    tool_name: str,
    tool_input: Dict[str, Any],
) -> L2Result:
    """Classify a pending tool call against the FSM.

    A call may match one or more logical actions of one or more steps. We prefer
    to credit NEW progress on an already-activated step (depends_on satisfied);
    only if the call exclusively matches steps whose dependencies are unmet do we
    report an order violation.
    """
    sat = set(satisfied)

    activated: List[tuple] = []       # (step, matched_ids): deps met, not completed
    blocked: List[tuple] = []         # (step, matched_ids): deps NOT met
    completed_hit: List[Step] = []    # step already completed
    for step in ir.steps:
        ids = matched_logical_actions(step, tool_name, tool_input)
        if not ids:
            continue
        if step.id in sat:
            completed_hit.append(step)
        elif all(d in sat for d in step.depends_on):
            activated.append((step, ids))
        else:
            blocked.append((step, ids))

    if not activated and not blocked and not completed_hit:
        return L2Result(kind="no_match")

    # 1. Progress a not-yet-matched logical action of an activated step.
    for step, ids in activated:
        already = set(matched_actions.get(step.id, []))
        new_ids = [i for i in ids if i not in already]
        if new_ids:
            return L2Result(
                kind="allow_progress", matched_step=step.id,
                matched_action_ids=new_ids, step_obj=step,
                reason=f"matches logical action(s) {new_ids} of step {step.id}",
            )

    # 2. Activated step, but every matched logical action was already seen → allow
    #    with no FSM side-effect.
    if activated:
        step = activated[0][0]
        return L2Result(
            kind="allow_already_done", matched_step=step.id, step_obj=step,
            reason=f"re-matches an already-matched action of step {step.id}",
        )

    # 3. Only steps with unmet dependencies matched → order violation.
    if blocked:
        step = blocked[0][0]
        missing = [r for r in step.depends_on if r not in sat]
        base = f"step {step.id} requires {missing} which are not yet completed"
        from .layers import suggest_for_missing_requires  # avoid circular import
        hint = suggest_for_missing_requires(ir, missing)
        reason = f"{base}. {hint}" if hint else base
        return L2Result(
            kind="order_violation", matched_step=step.id,
            missing_requires=missing, reason=reason, step_obj=step,
        )

    # 4. Only already-completed steps matched → allow with no side-effect.
    step = completed_hit[0]
    return L2Result(
        kind="allow_already_done", matched_step=step.id, step_obj=step,
        reason=f"matches an action of completed step {step.id}",
    )
