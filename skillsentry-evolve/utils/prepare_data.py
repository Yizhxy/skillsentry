#!/usr/bin/env python3
"""
Prepare data/evolve/<skill>/ from data/raw/skillsentry_tasks/<skill>/.

Paper §IV-A dataset split:
  - 10 task instances per skill, each with 8 queries (1 original + 7 paraphrases)
  - Q_evol  : task instances _0~_4  (5 instances × 8 = 50 queries) — self-evolving
  - Q_test  : task instances _5~_7  (3 instances × 8 = 30 queries) — held-out test
  - baseline: task instances _8~_9  (2 instances × 8 = 16 queries) — initialization traces

Output layout under data/evolve/<skill>/:
  evolve/    ← Q_evol task instances (symlink-free copy)
  test/      ← Q_test task instances (symlink-free copy)
  baseline/  ← baseline task instances (symlink-free copy)
  split.json ← manifest: which instances go where

Usage:
  python utils/prepare_data.py                        # all skills
  python utils/prepare_data.py --skill econ-detrending-correlation
  python utils/prepare_data.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

# Split configuration (paper §IV-A)
EVOL_INSTANCES   = list(range(0, 5))   # _0 ~ _4
TEST_INSTANCES   = list(range(5, 8))   # _5 ~ _7
BASELINE_INSTANCES = list(range(8, 10)) # _8 ~ _9


def prepare_skill(raw_skill_dir: Path, evolve_skill_dir: Path, dry_run: bool = False) -> dict:
    """Split one skill's task instances into evolve/test/baseline under evolve_skill_dir."""
    skill_name = raw_skill_dir.name

    # Detect task instances
    all_instances = sorted([
        d for d in raw_skill_dir.iterdir()
        if d.is_dir() and d.name.startswith(skill_name + "_")
    ], key=lambda d: int(d.name.rsplit("_", 1)[-1]))

    if not all_instances:
        print(f"  [warn] {skill_name}: no task instances found, skipping")
        return {}

    splits = {
        "evolve":   [all_instances[i] for i in EVOL_INSTANCES   if i < len(all_instances)],
        "test":     [all_instances[i] for i in TEST_INSTANCES    if i < len(all_instances)],
        "baseline": [all_instances[i] for i in BASELINE_INSTANCES if i < len(all_instances)],
    }

    manifest = {"skill": skill_name, "splits": {}}
    for split_name, instances in splits.items():
        dst_split = evolve_skill_dir / split_name
        manifest["splits"][split_name] = {
            "instances": [inst.name for inst in instances],
            "n_instances": len(instances),
            "n_queries": sum(
                len([q for q in inst.iterdir()
                     if q.name == "instruction.md" or q.name.startswith("index_")])
                for inst in instances
            ),
        }
        if dry_run:
            print(f"  [dry-run] {skill_name}/{split_name}: {[i.name for i in instances]}")
            continue

        if dst_split.exists():
            shutil.rmtree(dst_split)
        dst_split.mkdir(parents=True, exist_ok=True)

        for inst in instances:
            dst_inst = dst_split / inst.name
            shutil.copytree(inst, dst_inst, symlinks=False)

        print(f"  {skill_name}/{split_name}: {len(instances)} instances, "
              f"{manifest['splits'][split_name]['n_queries']} queries")

    if not dry_run:
        (evolve_skill_dir / "split.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare data/evolve from data/raw/skillsentry_tasks")
    parser.add_argument("--skill", default=None, help="Single skill to prepare (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without copying")
    parser.add_argument(
        "--raw-dir", default=None,
        help="Path to data/raw/skillsentry_tasks (default: auto-detect from script location)"
    )
    parser.add_argument(
        "--evolve-dir", default=None,
        help="Path to data/evolve output dir (default: auto-detect from script location)"
    )
    args = parser.parse_args()

    # Auto-detect paths relative to repo root
    repo_root = Path(__file__).resolve().parent.parent.parent  # .../skillsentry/
    raw_dir    = Path(args.raw_dir)    if args.raw_dir    else repo_root / "data" / "raw" / "skillsentry_tasks"
    evolve_dir = Path(args.evolve_dir) if args.evolve_dir else repo_root / "data" / "evolve"

    if not raw_dir.exists():
        print(f"[error] raw dir not found: {raw_dir}")
        return

    evolve_dir.mkdir(parents=True, exist_ok=True)

    skills = [raw_dir / args.skill] if args.skill else sorted(raw_dir.iterdir())
    skills = [s for s in skills if s.is_dir()]

    print(f"Raw dir:    {raw_dir}")
    print(f"Evolve dir: {evolve_dir}")
    print(f"Skills:     {len(skills)}")
    print(f"Split:      evol=_0~_4 (5 inst), test=_5~_7 (3 inst), baseline=_8~_9 (2 inst)")
    print()

    all_manifests = {}
    for skill_dir in skills:
        evolve_skill_dir = evolve_dir / skill_dir.name
        manifest = prepare_skill(skill_dir, evolve_skill_dir, dry_run=args.dry_run)
        all_manifests[skill_dir.name] = manifest

    if not args.dry_run:
        summary_path = evolve_dir / "dataset_manifest.json"
        summary_path.write_text(
            json.dumps(all_manifests, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nManifest written: {summary_path}")

    # Summary
    total_evol = sum(
        m.get("splits", {}).get("evolve", {}).get("n_queries", 0)
        for m in all_manifests.values()
    )
    total_test = sum(
        m.get("splits", {}).get("test", {}).get("n_queries", 0)
        for m in all_manifests.values()
    )
    total_base = sum(
        m.get("splits", {}).get("baseline", {}).get("n_queries", 0)
        for m in all_manifests.values()
    )
    print(f"\nTotal Q_evol queries:   {total_evol}")
    print(f"Total Q_test queries:   {total_test}")
    print(f"Total baseline queries: {total_base}")


if __name__ == "__main__":
    main()
