#!/usr/bin/env python3
"""
Prepare data/evolve/<skill>/ from data/raw/skillsentry_tasks/<skill>/.

Converts the raw task instance structure into the iter_* format used by the
dataset_for_validation (compatible with load_baseline_traces and load_queries).

Raw structure (per skill):
  <skill>_0/
    instruction.md         ← original query (task-level semantic variant)
    index_0/instruction.md ← expression-level paraphrase 0
    ...
    index_6/instruction.md ← expression-level paraphrase 6
    environment/           ← shared Docker environment
    tests/                 ← verifier scripts
  <skill>_1/  ...
  <skill>_9/

Output structure (iter_* format, all 80 queries flattened):
  data/evolve/<skill>/
    iter_0000/
      query.md             ← instruction text
      environment -> ...   ← symlink to shared environment (no copy needed)
      tests -> ...         ← symlink to shared tests
    iter_0001/ ...
    iter_0079/

The Q_evol / Q_test split (50/30) is done at runtime in main.py using a
deterministic random shuffle seeded by the skill name.

Usage:
  python utils/prepare_data.py                             # all skills
  python utils/prepare_data.py --skill econ-detrending-correlation
  python utils/prepare_data.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def prepare_skill(raw_skill_dir: Path, evolve_skill_dir: Path, dry_run: bool = False) -> dict:
    """Flatten one skill's queries into iter_XXXX/ format under evolve_skill_dir."""
    skill_name = raw_skill_dir.name

    instances = sorted([
        d for d in raw_skill_dir.iterdir()
        if d.is_dir() and d.name.startswith(skill_name + "_")
    ], key=lambda d: int(d.name.rsplit("_", 1)[-1]))

    if not instances:
        print(f"  [warn] {skill_name}: no task instances found, skipping")
        return {}

    if not dry_run:
        if evolve_skill_dir.exists():
            shutil.rmtree(evolve_skill_dir)
        evolve_skill_dir.mkdir(parents=True, exist_ok=True)

    iter_idx = 0
    manifest_entries = []

    for inst in instances:
        # Collect all queries: original instruction.md + each index_*/instruction.md
        query_sources: list[tuple[str, Path]] = []

        orig = inst / "instruction.md"
        if orig.exists():
            query_sources.append((f"{inst.name}/original", orig))

        for idx_dir in sorted(inst.iterdir()):
            if idx_dir.is_dir() and idx_dir.name.startswith("index_"):
                q = idx_dir / "instruction.md"
                if q.exists():
                    query_sources.append((f"{inst.name}/{idx_dir.name}", q))

        for source_label, query_path in query_sources:
            iter_name = f"iter_{iter_idx:04d}"
            iter_dir = evolve_skill_dir / iter_name

            if dry_run:
                print(f"  [dry-run] {skill_name}/{iter_name} ← {source_label}")
            else:
                iter_dir.mkdir(parents=True, exist_ok=True)
                # Copy the query text
                shutil.copy2(query_path, iter_dir / "query.md")
                # Symlink to the shared environment and tests from this task instance
                env_src = inst / "environment"
                tests_src = inst / "tests"
                if env_src.exists():
                    (iter_dir / "environment").symlink_to(env_src.resolve())
                if tests_src.exists():
                    (iter_dir / "tests").symlink_to(tests_src.resolve())

            manifest_entries.append({
                "iter": iter_name,
                "source": source_label,
                "instance": inst.name,
            })
            iter_idx += 1

    manifest = {
        "skill": skill_name,
        "n_queries": iter_idx,
        "queries": manifest_entries,
    }
    if not dry_run:
        (evolve_skill_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  {skill_name}: {iter_idx} queries → {evolve_skill_dir}")

    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare data/evolve from data/raw/skillsentry_tasks (iter_* format)")
    parser.add_argument("--skill", default=None, help="Single skill name (default: all)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--raw-dir", default=None)
    parser.add_argument("--evolve-dir", default=None)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent.parent
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
    print(f"Format:     iter_XXXX/{{query.md, environment->, tests->}}")
    print(f"Split:      Q_evol(50) / Q_test(30) done at runtime (random, skill-seeded)")
    print()

    all_manifests = {}
    for skill_dir in skills:
        manifest = prepare_skill(skill_dir, evolve_dir / skill_dir.name, dry_run=args.dry_run)
        all_manifests[skill_dir.name] = manifest

    if not args.dry_run:
        (evolve_dir / "dataset_manifest.json").write_text(
            json.dumps(all_manifests, indent=2, ensure_ascii=False), encoding="utf-8")
        total = sum(m.get("n_queries", 0) for m in all_manifests.values())
        print(f"\nTotal queries across all skills: {total}")


if __name__ == "__main__":
    main()
