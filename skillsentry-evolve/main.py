#!/usr/bin/env python3
"""SkillSentry guidance generation — Initialization and Self-Evolving stages (paper §III-B/§III-C).

  Initialization stage: extract the skill specification from SKILL.md (§III-B) and mine
  execution experience from baseline traces (§III-C) to construct the initial runtime guidance.

  Self-evolving stage: run the agent on new task queries under the current guidance, collect
  successful/failed traces, and refine the guidance by execution-experience mining, iterating
  for a fixed number of rounds.

Usage:
  python main.py --task econ-detrending-correlation --mode initialize
  python main.py --task econ-detrending-correlation --mode evolve --rounds 3
  python main.py --task econ-detrending-correlation --mode initialize --dry-run
"""
from __future__ import annotations

import json
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
    load_baseline_traces,
    load_current_rules,
    load_queries,
    load_skill_md,
)


# ---------------------------------------------------------------------------
# One round of execution-experience mining over a set of traces
# ---------------------------------------------------------------------------

def _mine_round(
    task_name: str,
    skill_name: str,
    skill_md: str,
    round_num: int,
    traces: list,
    guidance: dict[str, Any],
    out_dir: Path,
) -> tuple[dict[str, Any], list[dict]]:
    successes = [t for t in traces if t.success]
    failures = [t for t in traces if not t.success]
    print(f"  Round {round_num}: {len(successes)} success, {len(failures)} failure")

    workflow_steps = experience_mining.get_workflow_steps(guidance)
    memory = memory_io.load(out_dir)
    memory = memory_io.update(memory, traces, workflow_steps, rules=guidance)
    memory_io.save(out_dir, memory)
    print(f"  Memory: {memory['rounds_accumulated']} rounds, "
          f"{memory['total_success_traces']} success / {memory['total_fail_traces']} fail traces")

    if not successes and not failures:
        return guidance, []

    new_guidance, diff_log = experience_mining.mine_experience(
        guidance, successes, failures, memory,
        task_name=task_name, skill_name=skill_name, skill_md=skill_md, round_num=round_num,
    )

    round_dir = out_dir / f"round_{round_num:02d}"
    round_dir.mkdir(parents=True, exist_ok=True)
    (round_dir / "rules.json").write_text(
        json.dumps(new_guidance, indent=2, ensure_ascii=False), encoding="utf-8")
    (round_dir / "diff_log.json").write_text(
        json.dumps(diff_log, indent=2, ensure_ascii=False), encoding="utf-8")

    for d in diff_log:
        print(f"    [{d['action']}] {d['step_id']}.{d['field']}: {d.get('rationale', '')[:80]}")
    return new_guidance, diff_log


def _record_round(out_dir: Path, round_num: int, mode: str, traces: list, diff_log: list) -> None:
    st = state_io.load(out_dir)
    rewards = [t.reward for t in traces]
    mean_r = sum(rewards) / len(rewards) if rewards else 0.0
    st["round"] = round_num + 1
    st.setdefault("reward_history", []).append({
        "round": round_num, "mode": mode,
        "n_traces": len(traces),
        "mean_reward": mean_r,
        "n_success": sum(t.success for t in traces),
        "n_fail": sum(not t.success for t in traces),
        "n_field_changes": len(diff_log),
    })
    state_io.save(out_dir, st)
    print(f"  Reward: {mean_r:.2f}  ({sum(t.success for t in traces)}/{len(traces)} pass)  "
          f"| {len(diff_log)} field changes")


# ---------------------------------------------------------------------------
# Initialization stage (paper §III-B + §III-C on baseline traces)
# ---------------------------------------------------------------------------

def initialize_stage(task_name: str, dry_run: bool = False) -> None:
    print(f"\n{'='*60}\nInitialization stage: {task_name}\n{'='*60}")
    skill_name = get_skill_name(task_name)
    out_dir = config.OUTPUT_DIR / skill_name
    out_dir.mkdir(parents=True, exist_ok=True)

    skill_md = load_skill_md(task_name)
    print(f"  Skill: {skill_name} | SKILL.md: {'found' if skill_md else 'not found'}")

    traces = load_baseline_traces(task_name)
    successes = [t for t in traces if t.success]
    print(f"  Baseline traces: {len(traces)} ({len(successes)} success, "
          f"{len(traces) - len(successes)} failure)")
    if not traces:
        print("  [error] No baseline traces found")
        return
    if dry_run:
        print("  [dry-run] Skipping LLM calls and mining")
        for t in traces:
            print(f"    {t.source}: reward={t.reward}, tool_calls={len(t.parsed.tool_calls)}")
        return

    # §III-B — Skill Specification Extraction
    print("  §III-B Skill Specification Extraction ...", end=" ", flush=True)
    spec = skill_spec_extraction.extract_skill_spec(skill_md, skill_name)
    print(f"done ({len(spec.get('steps', []))} steps)")

    # §III-C — Execution Experience Mining over baseline traces
    print("  §III-C Execution Experience Mining ...")
    guidance, diff_log = _mine_round(task_name, skill_name, skill_md, 0, traces, spec, out_dir)

    (out_dir / "rules.json").write_text(
        json.dumps(guidance, indent=2, ensure_ascii=False), encoding="utf-8")
    _record_round(out_dir, 0, "initialize", traces, diff_log)
    print(f"\n  Initialization done. Guidance: {out_dir / 'rules.json'}")


# ---------------------------------------------------------------------------
# Self-evolving stage (paper §III-C iterated over new queries)
# ---------------------------------------------------------------------------

def self_evolving_stage(task_name: str, num_rounds: int, queries_per_round: int,
                        dry_run: bool = False) -> None:
    print(f"\n{'='*60}\nSelf-evolving stage: {task_name} | rounds={num_rounds} | "
          f"queries/round={queries_per_round}\n{'='*60}")
    skill_name = get_skill_name(task_name)
    out_dir = config.OUTPUT_DIR / skill_name
    out_dir.mkdir(parents=True, exist_ok=True)

    skill_md = load_skill_md(task_name)
    rules_file = out_dir / "rules.json"
    if rules_file.exists():
        guidance = json.loads(rules_file.read_text(encoding="utf-8"))
        print(f"  Loaded guidance from: {rules_file}")
    else:
        guidance = load_current_rules(task_name)
        print("  No initialized guidance found, using reference rules")

    st = state_io.load(out_dir)
    start_round = max(st.get("round", 1), 1)

    all_queries = load_queries(task_name, split="evolve")  # Q_evol only
    if not all_queries:
        print("  [error] No Q_evol queries found — run utils/prepare_data.py first")
        return
    print(f"  Q_evol queries: {len(all_queries)}")

    for round_num in range(start_round, start_round + num_rounds):
        print(f"\n--- Round {round_num} ---")
        offset = (round_num - 1) * queries_per_round
        selected = [all_queries[(offset + i) % len(all_queries)]
                    for i in range(queries_per_round)]

        work_dir = out_dir / f"round_{round_num:02d}" / "trials"
        print(f"  Running {len(selected)} trials ...")
        traces = collect_traces(task_name, guidance, selected, work_dir, dry_run=dry_run)

        if dry_run:
            st["round"] = round_num + 1
            state_io.save(out_dir, st)
            continue
        if not traces:
            print("  [warn] No traces collected")
            continue

        guidance, diff_log = _mine_round(
            task_name, skill_name, skill_md, round_num, traces, guidance, out_dir)
        rules_file.write_text(
            json.dumps(guidance, indent=2, ensure_ascii=False), encoding="utf-8")
        _record_round(out_dir, round_num, "evolve", traces, diff_log)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="SkillSentry guidance generation (Initialization + Self-Evolving stages)")
    parser.add_argument("--task", required=True, help="Task name (e.g. econ-detrending-correlation)")
    parser.add_argument("--mode", default="initialize",
                        choices=["initialize", "evolve", "bootstrap", "iterate"],
                        help="'initialize' (§III-B+§III-C) or 'evolve' (self-evolving loop); "
                             "'bootstrap'/'iterate' are accepted aliases")
    parser.add_argument("--rounds", type=int, default=3, help="Self-evolving rounds")
    parser.add_argument("--queries-per-round", type=int, default=5, help="Trials per round")
    parser.add_argument("--dry-run", action="store_true", help="Skip LLM calls and trial runs")
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

    print(f"LLM model:   {config.LLM_MODEL}")
    print(f"Agent:       {config.HARBOR_AGENT} / {config.HARBOR_MODEL}")
    print(f"Output dir:  {config.OUTPUT_DIR}")

    mode = {"bootstrap": "initialize", "iterate": "evolve"}.get(args.mode, args.mode)
    if mode == "initialize":
        initialize_stage(args.task, dry_run=args.dry_run)
    else:
        self_evolving_stage(args.task, num_rounds=args.rounds,
                            queries_per_round=args.queries_per_round, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
