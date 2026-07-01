#!/usr/bin/env python3
"""
SkillSentry guidance generation — Initialization and Self-Evolving stages (paper §III-B/§III-C).

Initialization stage (§III-B):
  Extract skill specification from SKILL.md only. No baseline traces needed —
  the first self-evolving iteration acts as the baseline (guidance not yet active).

Self-evolving stage (§III-C):
  Each iteration:
    1. Run agent on a random sample of Q_evol queries under current guidance.
    2. Collect success/failure traces.
    3. Mine execution experience → update guidance.
  After all iterations, evaluate on Q_test (randomly sampled, never used in evolving).

Dataset split (paper §IV-A, done at runtime, not pre-split on disk):
  - All 80 queries per skill are loaded together.
  - 50 randomly assigned to Q_evol, 30 to Q_test (fixed seed per skill for reproducibility).
  - Q_evol is further sampled iteration-by-iteration (5 queries × 10 iterations = 50).
  - Q_test is never used during evolving; only for final evaluation.

Usage:
  python main.py --task econ-detrending-correlation --mode initialize
  python main.py --task econ-detrending-correlation --mode evolve --iterations 10
  python main.py --task econ-detrending-correlation --mode evaluate   # run on Q_test
  python main.py --task econ-detrending-correlation --mode initialize --dry-run
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import Any

import config
import utils.state as state_io
import utils.memory as memory_io
import skill_spec_extraction
import experience_mining
from utils.runner import collect_traces
from utils.task_data import (
    get_skill_name,
    load_all_queries,
    load_current_rules,
    load_skill_md,
)


# ---------------------------------------------------------------------------
# Dataset split (paper §IV-A: 50 Q_evol / 30 Q_test, random per skill)
# ---------------------------------------------------------------------------

def _split_queries(all_queries: list[str], skill_name: str) -> tuple[list[str], list[str]]:
    """Randomly split 80 queries into Q_evol (50) and Q_test (30).

    Uses a deterministic seed derived from the skill name so the split is
    reproducible across runs but differs per skill (avoids systematic bias).
    """
    rng = random.Random(hash(skill_name) & 0xFFFFFFFF)
    indices = list(range(len(all_queries)))
    rng.shuffle(indices)
    evol_idx = indices[:50]
    test_idx  = indices[50:80]
    q_evol = [all_queries[i] for i in sorted(evol_idx)]
    q_test = [all_queries[i] for i in sorted(test_idx)]
    return q_evol, q_test


# ---------------------------------------------------------------------------
# One iteration of experience mining over a set of traces
# ---------------------------------------------------------------------------

def _mine_iteration(
    task_name: str,
    skill_name: str,
    skill_md: str,
    iteration: int,
    traces: list,
    guidance: dict[str, Any],
    out_dir: Path,
) -> tuple[dict[str, Any], list[dict]]:
    successes = [t for t in traces if t.success]
    failures  = [t for t in traces if not t.success]
    print(f"  Iteration {iteration}: {len(successes)} success, {len(failures)} failure")

    workflow_steps = experience_mining.get_workflow_steps(guidance)
    memory = memory_io.load(out_dir)
    memory = memory_io.update(memory, traces, workflow_steps, rules=guidance)
    memory_io.save(out_dir, memory)
    print(f"  Memory: {memory['rounds_accumulated']} iterations accumulated, "
          f"{memory['total_success_traces']} success / {memory['total_fail_traces']} fail traces")

    if not successes and not failures:
        return guidance, []

    new_guidance, diff_log = experience_mining.mine_experience(
        guidance, successes, failures, memory,
        task_name=task_name, skill_name=skill_name, skill_md=skill_md, round_num=iteration,
    )

    iter_dir = out_dir / f"iter_{iteration:02d}"
    iter_dir.mkdir(parents=True, exist_ok=True)
    (iter_dir / "guidance.json").write_text(
        json.dumps(new_guidance, indent=2, ensure_ascii=False), encoding="utf-8")
    (iter_dir / "diff_log.json").write_text(
        json.dumps(diff_log, indent=2, ensure_ascii=False), encoding="utf-8")

    for d in diff_log:
        print(f"    [{d['action']}] {d['step_id']}.{d['field']}: {d.get('rationale', '')[:80]}")
    return new_guidance, diff_log


def _record_iteration(out_dir: Path, iteration: int, mode: str,
                      traces: list, diff_log: list) -> None:
    st = state_io.load(out_dir)
    rewards = [t.reward for t in traces]
    mean_r = sum(rewards) / len(rewards) if rewards else 0.0
    st["iteration"] = iteration + 1
    st.setdefault("history", []).append({
        "iteration": iteration, "mode": mode,
        "n_traces": len(traces),
        "mean_reward": mean_r,
        "n_success": sum(t.success for t in traces),
        "n_fail": sum(not t.success for t in traces),
        "n_field_changes": len(diff_log),
    })
    state_io.save(out_dir, st)
    print(f"  Reward: {mean_r:.2f}  ({sum(t.success for t in traces)}/{len(traces)} pass)"
          f"  | {len(diff_log)} field changes")


# ---------------------------------------------------------------------------
# Initialization stage (paper §III-B)
# ---------------------------------------------------------------------------

def initialize_stage(task_name: str, dry_run: bool = False) -> None:
    """Initialization stage: extract skill specification from SKILL.md only.

    No baseline traces are needed here. The first self-evolving iteration (iter 1)
    acts as the baseline — at that point guidance is not yet active, so the agent
    runs freely and the resulting traces bootstrap the experience mining.
    """
    print(f"\n{'='*60}\nInitialization stage: {task_name}\n{'='*60}")
    skill_name = get_skill_name(task_name)
    out_dir = config.OUTPUT_DIR / skill_name
    out_dir.mkdir(parents=True, exist_ok=True)

    skill_md = load_skill_md(task_name)
    print(f"  Skill: {skill_name} | SKILL.md: {'found' if skill_md else 'NOT FOUND'}")
    if not skill_md:
        print("  [error] SKILL.md not found — cannot extract skill specification")
        return

    if dry_run:
        print("  [dry-run] Would extract skill specification from SKILL.md")
        return

    # §III-B — Skill Specification Extraction: LLM parses SKILL.md → DSL skeleton
    print("  §III-B Skill Specification Extraction ...", end=" ", flush=True)
    spec = skill_spec_extraction.extract_skill_spec(skill_md, skill_name)
    print(f"done ({len(spec.get('steps', []))} steps)")

    # Save as initial guidance (experience fields empty — to be populated by evolving)
    (out_dir / "guidance.json").write_text(
        json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")

    # Also save to data/results/dsl/ for reference
    dsl_path = config.RULES_REF_DIR / skill_name / "guidance.json"
    dsl_path.parent.mkdir(parents=True, exist_ok=True)
    dsl_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n  Initialization done.")
    print(f"  Guidance skeleton: {out_dir / 'guidance.json'}")
    print(f"  DSL reference:     {dsl_path}")
    print(f"  Next: run 'evolve' to start self-evolving (iteration 1 = baseline).")


# ---------------------------------------------------------------------------
# Self-evolving stage (paper §III-C)
# ---------------------------------------------------------------------------

def self_evolving_stage(task_name: str, num_iterations: int, queries_per_iter: int,
                        dry_run: bool = False) -> None:
    """Self-evolving stage.

    Iteration 1 is the baseline: guidance is loaded (DSL skeleton only, no experience
    fields yet), so the agent runs with minimal intervention. Subsequent iterations
    progressively improve the guidance.

    Queries are randomly split at runtime:
      - Q_evol (50 queries): used for self-evolving iterations
      - Q_test (30 queries): held-out, never used during evolving
    """
    print(f"\n{'='*60}\nSelf-evolving stage: {task_name} | iterations={num_iterations} | "
          f"queries/iter={queries_per_iter}\n{'='*60}")
    skill_name = get_skill_name(task_name)
    out_dir = config.OUTPUT_DIR / skill_name
    out_dir.mkdir(parents=True, exist_ok=True)

    skill_md = load_skill_md(task_name)
    guidance_file = out_dir / "guidance.json"
    if guidance_file.exists():
        guidance = json.loads(guidance_file.read_text(encoding="utf-8"))
        print(f"  Loaded guidance from: {guidance_file}")
    else:
        guidance = load_current_rules(task_name)
        if guidance:
            print("  No initialized guidance found, using reference rules")
        else:
            print("  [warn] No guidance found — run 'initialize' first")
            guidance = {}

    st = state_io.load(out_dir)
    start_iter = max(st.get("iteration", 1), 1)

    # Load all queries and split into Q_evol / Q_test at runtime
    all_queries = load_all_queries(task_name)
    if not all_queries:
        print("  [error] No queries found under data/evolve/<task>/")
        return

    q_evol, q_test = _split_queries(all_queries, skill_name)
    print(f"  All queries: {len(all_queries)} | Q_evol: {len(q_evol)} | Q_test: {len(q_test)}")

    # Save the split for reproducibility
    split_file = out_dir / "query_split.json"
    if not split_file.exists():
        split_file.write_text(json.dumps({
            "skill": skill_name,
            "seed": hash(skill_name) & 0xFFFFFFFF,
            "n_evol": len(q_evol),
            "n_test": len(q_test),
        }, indent=2), encoding="utf-8")

    for iteration in range(start_iter, start_iter + num_iterations):
        is_baseline = (iteration == 1)
        print(f"\n--- Iteration {iteration} {'(baseline — guidance skeleton only)' if is_baseline else ''} ---")

        # Sample queries_per_iter from Q_evol for this iteration (rotate through)
        offset = (iteration - 1) * queries_per_iter
        selected = [q_evol[(offset + i) % len(q_evol)] for i in range(queries_per_iter)]

        work_dir = out_dir / f"iter_{iteration:02d}" / "trials"
        print(f"  Running {len(selected)} trials ...")
        traces = collect_traces(task_name, guidance, selected, work_dir, dry_run=dry_run)

        if dry_run:
            st["iteration"] = iteration + 1
            state_io.save(out_dir, st)
            continue
        if not traces:
            print("  [warn] No traces collected")
            continue

        guidance, diff_log = _mine_iteration(
            task_name, skill_name, skill_md, iteration, traces, guidance, out_dir)
        guidance_file.write_text(
            json.dumps(guidance, indent=2, ensure_ascii=False), encoding="utf-8")
        _record_iteration(out_dir, iteration, "evolve", traces, diff_log)

    _print_summary(task_name, state_io.load(out_dir))


# ---------------------------------------------------------------------------
# Evaluation on Q_test
# ---------------------------------------------------------------------------

def evaluate_stage(task_name: str, dry_run: bool = False) -> None:
    """Run the final evolved guidance on Q_test (held-out) and report success rate."""
    print(f"\n{'='*60}\nEvaluation on Q_test: {task_name}\n{'='*60}")
    skill_name = get_skill_name(task_name)
    out_dir = config.OUTPUT_DIR / skill_name

    guidance_file = out_dir / "guidance.json"
    if not guidance_file.exists():
        print("  [error] No evolved guidance found — run 'evolve' first")
        return
    guidance = json.loads(guidance_file.read_text(encoding="utf-8"))

    all_queries = load_all_queries(task_name)
    _, q_test = _split_queries(all_queries, skill_name)
    print(f"  Q_test: {len(q_test)} queries (held-out, never used during evolving)")

    work_dir = out_dir / "evaluation" / "trials"
    traces = collect_traces(task_name, guidance, q_test, work_dir, dry_run=dry_run)

    if not dry_run and traces:
        rewards = [t.reward for t in traces]
        mean_r = sum(rewards) / len(rewards)
        n_ok = sum(t.success for t in traces)
        print(f"\n  Q_test result: {mean_r:.2f} ({n_ok}/{len(traces)} pass)")

        st = state_io.load(out_dir)
        st.setdefault("eval_history", []).append({
            "n_traces": len(traces), "mean_reward": mean_r,
            "n_success": n_ok, "n_fail": len(traces) - n_ok,
        })
        state_io.save(out_dir, st)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_summary(task_name: str, state: dict) -> None:
    history = state.get("history", [])
    if not history:
        return
    print(f"\n{'='*60}\nSkillSentry Summary: {task_name}\n{'='*60}")
    print(f"  {'Iter':<6} {'Stage':<15} {'Reward':<8} {'Pass%':<7} {'Changes'}")
    print(f"  {'----':<6} {'-----':<15} {'------':<8} {'-----':<7} {'-------'}")
    for h in history:
        n = h.get("n_traces", 0)
        n_ok = h.get("n_success", 0)
        label = "(baseline)" if h["iteration"] == 1 else ""
        print(f"  {h['iteration']:<6} {h['mode']:<15} {h['mean_reward']:<8.2f} "
              f"{n_ok/n*100 if n else 0:<6.0f}%  {h['n_field_changes']} {label}")
    best = max(history, key=lambda h: h.get("mean_reward", 0))
    print(f"\n  Best: Iteration {best['iteration']} — reward={best['mean_reward']:.2f}")
    print(f"{'='*60}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="SkillSentry guidance generation (Initialization + Self-Evolving stages)")
    parser.add_argument("--task", required=True, help="Task name (e.g. econ-detrending-correlation)")
    parser.add_argument("--mode", default="initialize",
                        choices=["initialize", "evolve", "evaluate"],
                        help="'initialize' (§III-B) | 'evolve' (§III-C) | 'evaluate' (Q_test)")
    parser.add_argument("--iterations", type=int, default=10,
                        help="Number of self-evolving iterations (evolve mode)")
    parser.add_argument("--queries-per-iter", type=int, default=5,
                        help="Queries sampled per iteration from Q_evol (default: 5)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip LLM calls and harbor runs")
    parser.add_argument("--output-dir", default=None,
                        help="Override OUTPUT_DIR (data/results/evolve)")
    args = parser.parse_args()

    if args.output_dir:
        config.OUTPUT_DIR = Path(args.output_dir)

    if not config.LLM_API_KEY and not args.dry_run:
        print("[error] LLM_API_KEY / OPENAI_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    print(f"SkillSentry | model: {config.LLM_MODEL} | output: {config.OUTPUT_DIR}")

    if args.mode == "initialize":
        initialize_stage(args.task, dry_run=args.dry_run)
    elif args.mode == "evolve":
        self_evolving_stage(args.task,
                            num_iterations=args.iterations,
                            queries_per_iter=args.queries_per_iter,
                            dry_run=args.dry_run)
    elif args.mode == "evaluate":
        evaluate_stage(args.task, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
