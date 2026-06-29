#!/usr/bin/env python3
"""
TDRR: Trace-Differential Rule Refinement
Entry point — see docs/tdrr_design.md for full method description.

Usage:
  # Bootstrap: use baseline traces to generate initial optimized rules.json
  python main.py --task econ-detrending-correlation --mode bootstrap

  # Iterate: run harbor with current rules, optimize, repeat
  python main.py --task econ-detrending-correlation --mode iterate --rounds 3

  # Dry-run (no LLM calls, no harbor runs)
  python main.py --task econ-detrending-correlation --mode bootstrap --dry-run
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import config
import utils.state as state_io
import utils.memory as memory_io
from tdrr import pattern_mining, stages, update
from tdrr.harbor import collect_traces
from utils.task_helpers import (
    TraceData,
    extract_workflow_steps_from_summaries,
    generate_initial_rules,
    get_skill_name,
    get_tasks_for_skill,
    get_workflow_steps,
    load_baseline_traces,
    load_baseline_traces_for_skill,
    load_current_rules,
    load_current_rules_for_skill,
    load_queries,
    load_queries_for_skill,
    load_skill_md,
    load_skill_md_for_skill,
    load_task_skill_map,
)


# ---------------------------------------------------------------------------
# Skill resolver — convert task or skill name into (skill_name, task_names)
# ---------------------------------------------------------------------------

def _resolve_skill_and_tasks(task_or_skill: str) -> tuple[str, list[str]]:
    """Return (skill_name, task_names) from either a task name or a skill name.

    - If task_or_skill is a known task_name in the map → return its skill + all
      sibling tasks that share the same skill.
    - If task_or_skill is a skill_name (present as a value in the map) → return
      it directly with all tasks that use it.
    - Otherwise → treat it as a bare task_name: skill = get_skill_name(task),
      task_names = [task_or_skill].
    """
    mapping = load_task_skill_map()

    # Case 1: known task_name
    if task_or_skill in mapping:
        skill_name = mapping[task_or_skill]["skill_name"]
        task_names = get_tasks_for_skill(skill_name)
        return skill_name, task_names

    # Case 2: bare skill_name
    task_names = get_tasks_for_skill(task_or_skill)
    if task_names:
        return task_or_skill, task_names

    # Case 3: unknown — treat as single task
    skill_name = get_skill_name(task_or_skill)
    return skill_name, [task_or_skill]


# ---------------------------------------------------------------------------
# One full TDRR round
# ---------------------------------------------------------------------------

def run_round(
    task_name: str,
    skill_name: str,
    skill_md: str,
    round_num: int,
    traces: list[TraceData],
    current_rules: dict[str, Any],
    task_out_dir: Path,
    prev_context: dict[str, Any] | None = None,
) -> tuple[dict, list[dict], bool]:
    """
    Run one full TDRR round.
    Returns (new_rules, diff_log, was_pass).
    """
    from typing import Any

    successes = [t for t in traces if t.success]
    failures  = [t for t in traces if not t.success]
    print(f"  Round {round_num}: {len(successes)} success, {len(failures)} failure")

    workflow_steps = get_workflow_steps(current_rules)

    # Stage 1: Extract directly from traces (no LLM calls)
    print("  Stage 1: Extracting trace info (no LLM)...")
    success_summaries, fail_summaries = [], []
    for t in successes:
        success_summaries.append(stages.summarize(t, task_name, workflow_steps))
    for t in failures:
        fail_summaries.append(stages.summarize(t, task_name, workflow_steps))
    print(f"  Stage 1: {len(success_summaries)} success, {len(fail_summaries)} failure traces ready")

    # Update global memory AFTER Stage 1 so structured_summary is populated
    memory = memory_io.load(task_out_dir)
    memory = memory_io.update(memory, traces, workflow_steps, rules=current_rules)
    memory_io.save(task_out_dir, memory)
    print(f"  Memory: {memory['rounds_accumulated']} rounds, "
          f"{memory['total_success_traces']} success / "
          f"{memory['total_fail_traces']} fail traces total")

    # Stage 0: Pattern Mining (current round, for display only)
    print("  Stage 0: Pattern mining...", end=" ", flush=True)
    current_patterns = pattern_mining.mine_current_round(successes)
    print(f"{len(current_patterns)} patterns this round")

    # Handle missing success or failure traces
    if not successes and not failures:
        print("  [skip] No traces at all")
        return current_rules, [], True, memory

    if not failures:
        print("  [skip] All succeeded — no failures to analyze, rules are good")
        return current_rules, [], True, memory

    if not successes:
        # All failed — try to use historical success traces from memory
        hist_success = memory.get("total_success_traces", 0)
        if hist_success > 0:
            print(f"  [fallback] No success this round, using {hist_success} historical "
                  f"success traces from memory for group advantage")
            # Build synthetic success summaries from memory patterns
            # (we don't have the actual TraceData objects, but we can use memory
            #  to inform the diagnosis via candidates)
            # Mark successes as empty list — Stage 2 will use memory candidates instead
            successes = []
            success_summaries = []
        else:
            # No historical success either — check if we should rollback
            print("  [rollback] No success traces in memory either — "
                  "checking previous round for rollback")
            prev_rules_file = task_out_dir / f"round_{round_num-1:02d}" / "rules.json"
            if round_num > 0 and prev_rules_file.exists():
                prev_rules = json.loads(prev_rules_file.read_text(encoding="utf-8"))
                print(f"  [rollback] Rolling back to round_{round_num-1:02d} rules")
                return prev_rules, [{"action": "ROLLBACK",
                                     "rationale": "All traces failed with no historical success"}], \
                       False, memory
            else:
                print("  [skip] No success traces and no previous rules to rollback to")
                return current_rules, [], True, memory

    # Derive candidates from global memory (after update)
    candidates = pattern_mining.derive_candidates(memory, workflow_steps)
    n_mc = sum(len(v) for v in candidates["must_call_candidates"].values())
    n_fb = sum(len(v) for v in candidates["forbidden_candidates"].values())
    print(f"  Candidates: {n_mc} must_call tokens, {n_fb} forbidden tokens (global)")

    # Stage 2: Field-level Diagnosis
    # When success_summaries is empty (all failed this round), pass memory context
    # so LLM can use historical success patterns for comparison
    print("  Stage 2: Field-level diagnosis...", end=" ", flush=True)
    diagnosis = stages.diagnose(
        task_name, round_num, current_rules,
        current_patterns, success_summaries, fail_summaries,
        success_traces=successes,
        fail_traces=failures,
        prev_context=prev_context,
        memory=memory if not successes else None,
    )
    n_issues  = len(diagnosis.get("field_diagnoses", []))
    n_healthy = len(diagnosis.get("healthy_fields", []))
    print(f"done ({n_issues} issues, {n_healthy} healthy)")
    if diagnosis.get("cross_round_notes"):
        print(f"    Cross-round: {diagnosis['cross_round_notes'][:100]}")
    print(f"    {diagnosis.get('summary', '')}")

    # Stage 3: Field-level Gradient (LLM selects from global candidates)
    print("  Stage 3: Field-level gradient...", end=" ", flush=True)
    grad = stages.gradient(
        task_name, skill_name, skill_md, round_num,
        current_rules, diagnosis,
        candidates=candidates,
        
    )
    decision = grad.get("decision", "update")
    print(f"done (decision={decision}, "
          f"{len(grad.get('field_updates', []))} updates proposed)")

    # Stage 4: Conservative Update (FSM + Pareto, using global memory)
    print("  Stage 4: Conservative update...", end=" ", flush=True)
    new_rules, diff_log, was_pass = update.apply(
        current_rules, grad,
        success_traces=successes,
        fail_traces=failures,
        global_memory=memory,
    )
    if was_pass:
        print("pass (no changes)")
    else:
        print(f"done ({len(diff_log)} fields changed)")
        for d in diff_log:
            print(f"    [{d['action']}] {d['step_id']}.{d['field']} "
                  f"(conf={d['confidence']:.2f}): {d['rationale'][:80]}")

    # Save round artifacts
    round_dir = task_out_dir / f"round_{round_num:02d}"
    round_dir.mkdir(parents=True, exist_ok=True)
    (round_dir / "rules.json").write_text(
        json.dumps(new_rules, indent=2, ensure_ascii=False), encoding="utf-8")
    (round_dir / "diff_log.json").write_text(
        json.dumps(diff_log, indent=2, ensure_ascii=False), encoding="utf-8")
    (round_dir / "analysis.json").write_text(
        json.dumps({
            "round": round_num,
            "was_pass": was_pass,
            "n_success": len(successes),
            "n_fail": len(failures),
            "current_patterns": current_patterns,
            "candidates": candidates,
            "success_summaries": success_summaries,
            "fail_summaries": fail_summaries,
            "diagnosis": diagnosis,
            "gradient": grad,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return new_rules, diff_log, was_pass, memory


def _should_early_stop(
    reward_history: list[dict],
    max_consecutive_pass: int = 3,
    max_consecutive_perfect: int = 2,
) -> tuple[bool, str]:
    """
    Check early stopping conditions:
    1. Consecutive pass rounds (no field changes) >= max_consecutive_pass
    2. Consecutive perfect rounds (mean_reward=1.0) >= max_consecutive_perfect
    """
    iterate_history = [h for h in reward_history if h.get("mode") == "iterate"]
    if not iterate_history:
        return False, ""

    # Check consecutive perfect rounds
    consecutive_perfect = 0
    for h in reversed(iterate_history):
        if h.get("mean_reward", 0) >= 1.0:
            consecutive_perfect += 1
        else:
            break
    if consecutive_perfect >= max_consecutive_perfect:
        return True, (f"Early stop: {consecutive_perfect} consecutive perfect rounds "
                      f"(mean_reward=1.0)")

    # Check consecutive pass rounds
    consecutive_pass = 0
    for h in reversed(iterate_history):
        if h.get("was_pass", False):
            consecutive_pass += 1
        else:
            break
    if consecutive_pass >= max_consecutive_pass:
        return True, (f"Early stop: {consecutive_pass} consecutive pass rounds "
                      f"(no field changes)")

    return False, ""


def _print_round_report(
    round_num: int,
    mode: str,
    traces: list,
    diff_log: list[dict],
    was_pass: bool,
    memory: dict[str, Any],
    prev_mean: float | None = None,
) -> None:
    """Print a concise per-round report with all key metrics."""
    rewards  = [t.reward for t in traces]
    n        = len(rewards)
    n_ok     = sum(t.success for t in traces)
    mean_r   = sum(rewards) / n if n else 0
    pass_pct = n_ok / n * 100 if n else 0

    delta_str = ""
    if prev_mean is not None:
        delta = mean_r - prev_mean
        delta_str = f"  Δ={delta:+.2f}"

    mem_rounds = memory.get("rounds_accumulated", 0)
    mem_ok     = memory.get("total_success_traces", 0)
    mem_fail   = memory.get("total_fail_traces", 0)

    print(f"\n  ┌─ Round {round_num} ({mode}) {'─'*30}")
    print(f"  │  Reward:   {mean_r:.2f}  ({n_ok}/{n} pass, {pass_pct:.0f}%){delta_str}")
    print(f"  │  Changes:  {len(diff_log)} fields  |  pass={was_pass}")
    print(f"  │  Memory:   {mem_rounds} rounds  |  {mem_ok} success / {mem_fail} fail traces")
    if diff_log:
        for d in diff_log:
            print(f"  │    [{d['action']}] {d['step_id']}.{d['field']} "
                  f"(conf={d.get('confidence', 0):.2f}): {d.get('rationale','')[:60]}")
    print(f"  └{'─'*50}")


def _print_final_report(task_name: str, state: dict[str, Any]) -> None:
    """Print a summary table of all rounds."""
    history = state.get("reward_history", [])
    if not history:
        return

    print(f"\n{'='*60}")
    print(f"TDRR Summary: {task_name}")
    print(f"{'='*60}")
    print(f"  {'Rnd':<5} {'Mode':<12} {'Reward':<8} {'Δ':<7} {'Pass%':<7} {'Changes'}")
    print(f"  {'---':<5} {'----':<12} {'------':<8} {'---':<7} {'-----':<7} {'-------'}")

    prev_mean = None
    for h in history:
        r        = h["round"]
        mode     = h["mode"]
        mean_r   = h.get("mean_reward", 0)
        n_ok     = h.get("n_success", 0)
        n        = h.get("n_traces", 0)
        chg      = h.get("n_field_changes", 0)
        pass_pct = n_ok / n * 100 if n else mean_r * 100

        delta_str = f"{mean_r - prev_mean:+.2f}" if prev_mean is not None else "  —  "
        print(f"  {r:<5} {mode:<12} {mean_r:<8.2f} {delta_str:<7} "
              f"{pass_pct:<6.0f}%  {chg}")
        prev_mean = mean_r

    best = max(history, key=lambda h: h.get("mean_reward", 0))
    print(f"\n  Best: Round {best['round']} ({best['mode']}) — "
          f"reward={best['mean_reward']:.2f}")
    print(f"{'='*60}")


def run_bootstrap(task_name: str, dry_run: bool = False) -> None:
    print(f"\n{'='*60}")
    print(f"Bootstrap (TDRR): {task_name}")
    print(f"{'='*60}")

    skill_name   = get_skill_name(task_name)
    skill_out_dir = config.OUTPUT_DIR / skill_name
    skill_out_dir.mkdir(parents=True, exist_ok=True)

    skill_md = load_skill_md(task_name)
    print(f"  Skill: {skill_name} | SKILL.md: {'found' if skill_md else 'not found'}")

    # Step 1: Load baseline traces
    traces    = load_baseline_traces(task_name)
    successes = [t for t in traces if t.success]
    failures  = [t for t in traces if not t.success]
    print(f"  Baseline traces: {len(traces)} ({len(successes)} success, {len(failures)} failure)")

    if not traces:
        print("  [error] No baseline traces found")
        return

    if dry_run:
        print("  [dry-run] Skipping LLM calls")
        for t in traces:
            print(f"    {t.source}: reward={t.reward}, "
                  f"tool_calls={len(t.parsed.tool_calls)}, "
                  f"hook_events={len(t.parsed.hook_events)}")
        return

    # Step 2: Stage 1 — extract directly (no LLM calls)
    print("  Stage 1: Extracting trace info (no LLM)...")
    for t in traces:
        stages.summarize(t, task_name, workflow_steps=[])
    print(f"  Stage 1: {len(traces)} traces ready")

    # During bootstrap there are no rules, so workflow_steps is empty;
    # let the _global bucket absorb all patterns
    workflow_steps = []

    # Step 3: Update memory with traces
    memory = memory_io.load(skill_out_dir)
    memory = memory_io.update(memory, traces, workflow_steps=workflow_steps, rules={})
    memory_io.save(skill_out_dir, memory)
    print(f"  Memory: {memory['rounds_accumulated']} rounds, "
          f"{memory['total_success_traces']} success / "
          f"{memory['total_fail_traces']} fail traces total")

    # Step 4: Derive candidates from _global bucket
    candidates = pattern_mining.derive_candidates(memory, workflow_steps=workflow_steps)
    n_mc = sum(len(v) for v in candidates["must_call_candidates"].values())
    n_fb = sum(len(v) for v in candidates["forbidden_candidates"].values())
    print(f"  Candidates: {n_mc} must_call tokens, {n_fb} forbidden tokens (global)")

    # Step 5: Always generate initial rules from SKILL.md + trace patterns (no reference fallback)
    print("  Generating initial rules from SKILL.md + trace patterns...", end=" ", flush=True)
    current_rules = generate_initial_rules(task_name, skill_name, skill_md, candidates)
    if current_rules:
        print(f"done ({len(current_rules.get('steps', []))} steps)")
    else:
        print("failed — no rules available")
        return

    # Step 6: Run Stage 2-4 (diagnose + gradient + update)
    new_rules, diff_log, was_pass, memory = run_round(
        task_name, skill_name, skill_md, round_num=0,
        traces=traces, current_rules=current_rules,
        task_out_dir=skill_out_dir,
        prev_context=None,
    )

    (skill_out_dir / "rules.json").write_text(
        json.dumps(new_rules, indent=2, ensure_ascii=False), encoding="utf-8")

    st = state_io.load(skill_out_dir)
    st["round"] = 1
    rewards = [t.reward for t in traces]
    mean_r  = sum(rewards) / len(rewards) if rewards else 0
    st.setdefault("reward_history", []).append({
        "round": 0, "mode": "bootstrap",
        "n_traces": len(traces),
        "mean_reward": mean_r,
        "n_success": len(successes),
        "n_fail": len(failures),
        "n_field_changes": len(diff_log),
        "was_pass": was_pass,
    })
    st.setdefault("diff_history", []).append({"round": 0, "diff_log": diff_log})
    state_io.save(skill_out_dir, st)

    _print_round_report(0, "bootstrap", traces, diff_log, was_pass, memory)
    print(f"\n  Bootstrap done. Rules: {skill_out_dir / 'rules.json'}")
    print(f"  Fields changed: {len(diff_log)} | pass: {was_pass}")


# ---------------------------------------------------------------------------
# Iterate mode
# ---------------------------------------------------------------------------

def run_iterate(task_name: str, num_rounds: int, queries_per_round: int,
                dry_run: bool = False) -> None:
    print(f"\n{'='*60}")
    print(f"Iterate (TDRR): {task_name} | rounds={num_rounds} | "
          f"queries/round={queries_per_round}")
    print(f"{'='*60}")

    skill_name    = get_skill_name(task_name)
    skill_out_dir = config.OUTPUT_DIR / skill_name
    skill_out_dir.mkdir(parents=True, exist_ok=True)

    skill_md = load_skill_md(task_name)
    print(f"  Skill: {skill_name} | SKILL.md: {'found' if skill_md else 'not found'}")

    rules_file = skill_out_dir / "rules.json"
    if rules_file.exists():
        current_rules = json.loads(rules_file.read_text(encoding="utf-8"))
        print(f"  Loaded rules from: {rules_file}")
    else:
        current_rules = load_current_rules(task_name)
        print("  No bootstrap rules found, using reference rules")

    st = state_io.load(skill_out_dir)
    start_round = max(st.get("round", 1), 1)

    all_queries = load_queries(task_name)
    if not all_queries:
        print("  [error] No queries found")
        return
    print(f"  Available queries: {len(all_queries)}")

    for round_num in range(start_round, start_round + num_rounds):
        print(f"\n--- Round {round_num} ---")

        offset   = (round_num - 1) * queries_per_round
        selected = [all_queries[(offset + i) % len(all_queries)]
                    for i in range(queries_per_round)]

        work_dir = skill_out_dir / f"round_{round_num:02d}" / "trials"
        print(f"  Running {len(selected)} harbor trials...")
        traces = collect_traces(
            task_name, current_rules, selected, work_dir, dry_run=dry_run)

        if dry_run:
            st["round"] = round_num + 1
            state_io.save(skill_out_dir, st)
            continue

        if not traces:
            print("  [warn] No traces collected")
            continue

        # Build cross-round context with counterfactual attribution
        prev_context = None
        prev_entry   = None
        history      = st.get("reward_history", [])
        diff_history = st.get("diff_history", [])
        if history:
            prev_entry = history[-1]
            prev_mean  = prev_entry.get("mean_reward", 0)
            curr_rewards = [t.reward for t in traces]
            curr_mean    = sum(curr_rewards) / len(curr_rewards) if curr_rewards else 0
            prev_diff    = diff_history[-1].get("diff_log", []) if diff_history else []

            prev_fail_steps: set[str] = set()
            prev_analysis_file = (skill_out_dir
                                  / f"round_{prev_entry['round']:02d}"
                                  / "analysis.json")
            if prev_analysis_file.exists():
                prev_analysis = json.loads(prev_analysis_file.read_text())
                for s in prev_analysis.get("fail_summaries", []):
                    prev_fail_steps.update(s.get("steps_skipped", []))
                    if s.get("error_at_step"):
                        prev_fail_steps.add(s["error_at_step"])

            curr_fail_steps: set[str] = set()
            for t in [t for t in traces if not t.success]:
                ev = t.eval_result
                curr_fail_steps.update(ev.get("missing_steps", []))

            prev_context = {
                "round_num":        prev_entry["round"],
                "mean_reward":      prev_mean,
                "curr_mean_reward": curr_mean,
                "reward_delta":     curr_mean - prev_mean,
                "diff_log":         prev_diff,
                "prev_fail_steps":  prev_fail_steps,
                "curr_fail_steps":  curr_fail_steps,
            }

            reward_delta = curr_mean - prev_mean
            rollback_threshold = float(os.environ.get("ROLLBACK_THRESHOLD", "-0.6"))
            if reward_delta <= rollback_threshold and prev_diff:
                prev_rules_file = skill_out_dir / f"round_{prev_entry['round']:02d}" / "rules.json"
                if prev_rules_file.exists():
                    print(f"  [rollback] Reward dropped {reward_delta:+.2f} "
                          f"(threshold={rollback_threshold}) — reverting to "
                          f"round_{prev_entry['round']:02d} rules")
                    current_rules = json.loads(prev_rules_file.read_text(encoding="utf-8"))
                    prev_context["rolled_back"] = True
                    prev_context["rollback_reason"] = (
                        f"Reward dropped {reward_delta:+.2f} — reverting and re-analyzing"
                    )

        new_rules, diff_log, was_pass, memory = run_round(
            task_name, skill_name, skill_md, round_num=round_num,
            traces=traces, current_rules=current_rules,
            task_out_dir=skill_out_dir,
            prev_context=prev_context,
        )

        current_rules = new_rules
        rules_file.write_text(
            json.dumps(new_rules, indent=2, ensure_ascii=False), encoding="utf-8")

        rewards = [t.reward for t in traces]
        mean_r  = sum(rewards) / len(rewards) if rewards else 0
        st["round"] = round_num + 1
        st.setdefault("reward_history", []).append({
            "round": round_num, "mode": "iterate",
            "n_traces": len(traces),
            "mean_reward": mean_r,
            "n_success": sum(t.success for t in traces),
            "n_fail": sum(not t.success for t in traces),
            "n_field_changes": len(diff_log),
            "was_pass": was_pass,
            "rolled_back": prev_context.get("rolled_back", False) if prev_context else False,
        })
        st.setdefault("diff_history", []).append({"round": round_num, "diff_log": diff_log})
        state_io.save(skill_out_dir, st)

        prev_mean_for_report = prev_entry.get("mean_reward") if prev_entry else None
        _print_round_report(round_num, "iterate", traces, diff_log, was_pass,
                            memory, prev_mean_for_report)

        should_stop, stop_reason = _should_early_stop(st["reward_history"])
        if should_stop:
            print(f"\n  {stop_reason}")
            break

    _print_final_report(task_name, st)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="TDRR: Trace-Differential Rule Refinement for skillsentry rules.json")
    parser.add_argument("--task", required=True,
        help="Task name (e.g. econ-detrending-correlation)")
    parser.add_argument("--mode", choices=["bootstrap", "iterate"], default="bootstrap")
    parser.add_argument("--rounds", type=int, default=3,
        help="Optimization rounds (iterate mode)")
    parser.add_argument("--queries-per-round", type=int, default=5,
        help="Harbor trials per round (iterate mode)")
    parser.add_argument("--dry-run", action="store_true",
        help="Skip LLM calls and harbor runs")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--dataset-root", default=None)
    args = parser.parse_args()

    if args.output_dir:
        config.OUTPUT_DIR = Path(args.output_dir)
    if args.dataset_root:
        config.DATASET_ROOT = Path(args.dataset_root)

    if not config.LLM_API_KEY and not args.dry_run:
        print("[error] LLM_API_KEY / OPENAI_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    print(f"Method:       TDRR (Trace-Differential Rule Refinement)")
    print(f"LLM model:    {config.LLM_MODEL}")
    print(f"Harbor:       {config.HARBOR_AGENT} / {config.HARBOR_MODEL}")
    print(f"Output dir:   {config.OUTPUT_DIR}")

    if args.mode == "bootstrap":
        run_bootstrap(args.task, dry_run=args.dry_run)
    else:
        run_iterate(args.task, num_rounds=args.rounds,
                    queries_per_round=args.queries_per_round,
                    dry_run=args.dry_run)


if __name__ == "__main__":
    main()
