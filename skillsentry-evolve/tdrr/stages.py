"""
TDRR Stages 1-3: LLM-based analysis.

Stage 1 — No longer does LLM summarization; extracts structured info directly from traces (zero LLM calls)
Stage 2 — Field-level Diagnosis, passes complete diagnostic text directly
Stage 3 — Field-level Gradient, generates rules based on real code
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any

import config
import utils.llm as llm
from utils.task_helpers import TraceData


# ---------------------------------------------------------------------------
# Stage 1: Extract directly from traces, no LLM calls
# ---------------------------------------------------------------------------

def summarize(
    trace: TraceData,
    task_name: str,
    workflow_steps: list[str],
) -> dict[str, Any]:
    """
    Stage 1: No LLM calls — construct structured_summary directly from existing fields.
    diagnostic_text is stored directly in the trace for use by Stage 2/3.
    """
    ev = trace.eval_result

    result = {
        "outcome": "success" if trace.success else "failure",
        "reward": trace.reward,
        "steps_executed": [],
        "steps_skipped": ev.get("missing_steps", []),
        "error_at_step": ev.get("error_at_step"),
        "error_description": ev.get("deviation_summary", ""),
        "repeated_mistake": None,
        "skillsentry_interventions": {
            "denied_steps": trace.parsed.denied_steps,
            "hinted_steps": trace.parsed.hinted_steps,
        },
        # full diagnostic text for direct use by Stage 2/3
        "diagnostic_text": trace.parsed.to_diagnostic_text(),
        "verifier_output": (trace.parsed.verifier_stdout or "")[:500],
    }

    trace.structured_summary = result
    return result


# ---------------------------------------------------------------------------
# Stage 2: Field-level Diagnosis
# ---------------------------------------------------------------------------

def _format_prev_round_context(prev_context: dict[str, Any] | None) -> str:
    """Format previous round context for the diagnosis prompt."""
    if not prev_context:
        return "Not available (this is the first round)."

    prev_mean = prev_context.get("mean_reward", 0)
    curr_mean = prev_context.get("curr_mean_reward", 0)
    delta     = prev_context.get("reward_delta", 0)
    diff_log  = prev_context.get("diff_log", [])

    lines = [
        f"Previous round: {prev_context.get('round_num', '?')}",
        f"Previous mean_reward: {prev_mean:.2f}  →  This round: {curr_mean:.2f}  "
        f"(delta: {delta:+.2f})",
        "",
        "Changes made in previous round:",
        json.dumps(diff_log, indent=2, ensure_ascii=False) if diff_log else "  (none)",
    ]

    # Counterfactual attribution: compare failure step patterns
    prev_fail_steps = prev_context.get("prev_fail_steps", set())
    curr_fail_steps = prev_context.get("curr_fail_steps", set())
    if prev_fail_steps or curr_fail_steps:
        new_failures  = curr_fail_steps - prev_fail_steps
        fixed         = prev_fail_steps - curr_fail_steps
        persistent    = prev_fail_steps & curr_fail_steps
        lines += [
            "",
            "Counterfactual attribution (failure step comparison):",
            f"  Steps newly failing this round: {sorted(new_failures) or 'none'}",
            f"  Steps fixed since last round:   {sorted(fixed) or 'none'}",
            f"  Steps still failing:            {sorted(persistent) or 'none'}",
        ]
        if new_failures and diff_log:
            changed_steps = {d.get("step_id") for d in diff_log}
            overlap = new_failures & changed_steps
            if overlap:
                lines.append(
                    f"  ⚠️  New failures overlap with changed steps {overlap} "
                    f"— consider REVERT for those fields"
                )
            else:
                lines.append(
                    f"  ✓  New failures do NOT overlap with changed steps "
                    f"— likely query difficulty, not rule regression"
                )

    return "\n".join(lines)


def _build_dual_signal_matrix(
    success_traces: list[TraceData],
    fail_traces: list[TraceData],
) -> str:
    """
    Build the 2x2 matrix: reward × skillsentry intervention.
    Returns a formatted string for the diagnosis prompt.
    """
    cells = {
        (True,  False): [],  # reward=1, no intervention
        (True,  True):  [],  # reward=1, with intervention
        (False, False): [],  # reward=0, no intervention
        (False, True):  [],  # reward=0, with intervention
    }
    for t in success_traces + fail_traces:
        has_intervention = t.parsed.has_skillsentry_interventions
        cells[(t.success, has_intervention)].append(t.source)

    lines = [
        f"reward=1, no intervention  ({len(cells[(True,False)])} traces): {cells[(True,False)]}",
        f"reward=1, with intervention ({len(cells[(True,True)])} traces): {cells[(True,True)]}",
        f"reward=0, no intervention  ({len(cells[(False,False)])} traces): {cells[(False,False)]}",
        f"reward=0, with intervention ({len(cells[(False,True)])} traces): {cells[(False,True)]}",
    ]

    # Add interpretation hints
    if cells[(False, True)]:
        lines.append("→ FP candidates: failed traces WITH intervention — rules may have blocked correct behavior")
    if cells[(False, False)]:
        lines.append("→ FN candidates: failed traces WITHOUT intervention — rules missed the error")
    if cells[(True, True)]:
        lines.append("→ Effective rules: successful traces WITH intervention — rules helped agent")

    return "\n".join(lines)


def diagnose(
    task_name: str,
    round_num: int,
    current_rules: dict[str, Any],
    high_freq_patterns: list[dict[str, Any]],
    success_summaries: list[dict[str, Any]],
    fail_summaries: list[dict[str, Any]],
    success_traces: list[TraceData] | None = None,
    fail_traces: list[TraceData] | None = None,
    prev_context: dict[str, Any] | None = None,
    memory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Stage 2: Diagnose using complete diagnostic text directly, no longer relying on LLM summaries.

    Full code and stdout of successful/failed traces are passed directly so the LLM
    can see actual code differences.
    """
    def fmt_traces(traces: list[TraceData], label: str) -> str:
        if not traces:
            return f"No {label} traces this round."
        parts = []
        # GPT-5.4 context 1M tokens — keep full traces, show up to 5
        shown = traces[:5]
        for i, t in enumerate(shown):
            diag = t.parsed.to_diagnostic_text()
            parts.append(
                f"--- {label.upper()} Trace {i+1} (reward={t.reward}, source={t.source}) ---\n{diag}"
            )
        if len(traces) > 5:
            parts.append(f"... ({len(traces)-5} more {label} traces not shown)")
        return "\n\n".join(parts)

    s_traces = success_traces or []
    f_traces = fail_traces or []

    # Build dual signal matrix
    dual_signal_matrix = _build_dual_signal_matrix(s_traces, f_traces) if (s_traces or f_traces) \
        else "(no traces available)"

    memory_context = ""
    if not s_traces and memory:
        total_ok = memory.get("total_success_traces", 0)
        total_fail = memory.get("total_fail_traces", 0)
        memory_context = (
            f"\nNOTE: 0 successful traces this round. "
            f"Global memory has {total_ok} success / {total_fail} fail traces as reference."
        )

    if s_traces and f_traces:
        diagnosis_mode_hint = "Mode A: both success and failure traces — compare directly"
    elif not s_traces:
        diagnosis_mode_hint = "Mode B: only failure traces — focus on forbidden rules and rollback"
    else:
        diagnosis_mode_hint = "Mode C: only success traces — focus on must_call coverage"

    success_text = fmt_traces(s_traces, "success")
    fail_text = fmt_traces(f_traces, "failure")

    try:
        up = llm.up("stage2_diagnosis_up",
            task_name=task_name,
            round_num=round_num,
            current_rules=json.dumps(current_rules, indent=2, ensure_ascii=False)[:5000],
            high_freq_patterns=json.dumps(high_freq_patterns[:10], indent=2, ensure_ascii=False)[:1000],
            dual_signal_matrix=dual_signal_matrix + memory_context + f"\n\nDiagnosis mode: {diagnosis_mode_hint}",
            n_success=len(s_traces),
            n_fail=len(f_traces),
            success_summaries=success_text,
            fail_summaries=fail_text,
            prev_round_context=_format_prev_round_context(prev_context),
        )
        raw = llm.call(
            [{"role": "system", "content": llm.sp_with_dsl("stage2_diagnosis_sp")},
             {"role": "user",   "content": up}],
            temperature=0.2,
            json_mode=True,
        )
        if not raw or not raw.strip():
            print(f"  [warn] diagnosis: empty LLM response (prompt_len={len(up)})", file=sys.stderr)
            return {"field_diagnoses": [], "healthy_fields": [], "summary": "Empty LLM response"}
        return json.loads(raw)
    except Exception as e:
        import traceback
        print(f"  [warn] diagnosis failed: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return {"field_diagnoses": [], "healthy_fields": [], "summary": "Diagnosis failed"}


# ---------------------------------------------------------------------------
# Stage 3: Field-level Gradient
# ---------------------------------------------------------------------------

def gradient(
    task_name: str,
    skill_name: str,
    skill_md: str,
    round_num: int,
    current_rules: dict[str, Any],
    diagnosis: dict[str, Any],
    candidates: dict[str, Any],
) -> dict[str, Any]:
    """
    Generate precise field-level update proposals.

    logical_actions: LLM selects/combines from must_call_candidates (success tokens only)
    failure_patterns: LLM judges root cause vs side effect from forbidden_candidates
    on_enter:  LLM derives hints from success/failure contrast in diagnosis
    """
    healthy = diagnosis.get("healthy_fields", [])
    skill_md_excerpt = skill_md[:2000] if skill_md else "(not available)"

    sp_text = (llm.sp_with_dsl("stage3_gradient_sp")
               .replace("{skill_md}", skill_md_excerpt))

    try:
        up = llm.up("stage3_gradient_up",
            task_name=task_name,
            skill_name=skill_name,
            round_num=round_num,
            max_field_changes="no limit — apply all evidence-based changes",
            memory_summary=str(candidates.get("memory_summary", "(none)"))[:500],
            must_call_candidates=json.dumps(
                candidates.get("must_call_candidates", {}), indent=2, ensure_ascii=False)[:2000],
            forbidden_candidates=json.dumps(
                candidates.get("forbidden_candidates", {}), indent=2, ensure_ascii=False)[:2000],
            current_rules=json.dumps(current_rules, indent=2, ensure_ascii=False)[:2000],
            diagnosis=json.dumps(diagnosis, indent=2, ensure_ascii=False),
            healthy_fields="\n".join(healthy) if healthy else "None identified",
        )
        raw = llm.call(
            [{"role": "system", "content": sp_text},
             {"role": "user",   "content": up}],
            temperature=0.2,
            json_mode=True,
        )
        if not raw or not raw.strip():
            print(f"  [warn] gradient: empty LLM response (prompt_len={len(up)})", file=sys.stderr)
            return {"decision": "pass", "pass_reason": "Empty LLM response",
                    "field_updates": [], "unchanged_fields": []}
        return json.loads(raw)
    except Exception as e:
        import traceback
        print(f"  [warn] gradient failed: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return {"decision": "pass", "pass_reason": f"LLM error: {e}",
                "field_updates": [], "unchanged_fields": []}
