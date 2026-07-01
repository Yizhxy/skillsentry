"""Task data loading: rules, SKILL.md, queries, and traces from the dataset."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
import pathlib
from typing import Any, Optional

import config
from utils.trace import ParsedTrace, parse_trajectory, parse_skillsentry_log


def _extract_test_results(verifier_stdout: str) -> str:
    """
    Extract the diagnostic test result section from verifier stdout.

    Keeps:
    - FAILED / PASSED test lines
    - AssertionError lines (show expected vs actual values)
    - Agent's answer / Expected lines
    - Short test summary

    Strips:
    - apt/pip install output
    - Package download progress
    - Unrelated system output

    This prevents overfit: the extracted text describes WHAT went wrong
    algorithmically, not specific numeric values that would cause overfit rules.
    """
    lines = verifier_stdout.split("\n")
    result_lines = []
    in_relevant = False

    for line in lines:
        # Start capturing at test execution section
        if re.search(r'(PASSED|FAILED|ERROR|test_|AssertionError|assert|'
                     r"Agent's answer|Expected:|Tolerance|short test summary|"
                     r'=+ FAILURES =+|=+ ERRORS =+)', line, re.IGNORECASE):
            in_relevant = True

        if in_relevant:
            # Skip pure noise lines
            if re.search(r'^(Hit:|Get:|Fetching|Preparing|Unpacking|Setting up|'
                         r'Processing|Collecting|Downloading|Installing|'
                         r'Reading package|Building dependency)', line):
                continue
            result_lines.append(line)

    if not result_lines:
        # Fallback: last 20 lines
        result_lines = lines[-20:]

    return "\n".join(result_lines[:50])  # cap at 50 lines


@dataclass
class TraceData:
    source: str           # iter_id or "round{N}_query{M}"
    reward: float
    query: str
    parsed: ParsedTrace
    eval_result: dict[str, Any] = field(default_factory=dict)
    # Filled by stage1_summarize
    structured_summary: Optional[dict[str, Any]] = None

    @property
    def success(self) -> bool:
        return self.reward >= 1.0


_task_skill_map_cache: dict | None = None


def load_task_skill_map() -> dict[str, dict]:
    """Load task → skill mapping from task_skill_map.json. Returns {task_name: entry}."""
    global _task_skill_map_cache
    if _task_skill_map_cache is not None:
        return _task_skill_map_cache
    p = config.TASK_SKILL_MAP
    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
        _task_skill_map_cache = {t["task_name"]: t for t in data.get("tasks", [])}
    else:
        _task_skill_map_cache = {}
    return _task_skill_map_cache


def get_skill_name(task_name: str) -> str:
    """Return the canonical skill name for a task, using task_skill_map.json first."""
    mapping = load_task_skill_map()
    if task_name in mapping:
        return mapping[task_name]["skill_name"]
    # Fallback: scan skills directory
    skills_dir = config.TASKS_ROOT / task_name / "environment" / "skills"
    if skills_dir.exists():
        for skill_subdir in sorted(skills_dir.iterdir()):
            skill_md = skill_subdir / "SKILL.md"
            if skill_md.exists():
                content = skill_md.read_text(encoding="utf-8", errors="replace")
                m = re.search(r"^name:\s*(.+)$", content, re.MULTILINE)
                if m:
                    return m.group(1).strip()
    return task_name


def load_skill_md(task_name: str) -> str:
    """Load SKILL.md for the canonical skill of a task.

    Searches under TASKS_ROOT (data/raw/skillsentry_tasks) for a task instance
    directory containing an environment/skills/<skill_name>/SKILL.md.
    """
    skill_name = get_skill_name(task_name)
    skill_task_dir = config.TASKS_ROOT / task_name
    if skill_task_dir.exists():
        # Look inside task instances for the environment/skills dir
        for instance_dir in sorted(skill_task_dir.iterdir()):
            skill_md_path = instance_dir / "environment" / "skills" / skill_name / "SKILL.md"
            if skill_md_path.exists():
                return skill_md_path.read_text(encoding="utf-8", errors="replace")
        # Fallback: any SKILL.md inside the task dir
        for skill_md_path in sorted(skill_task_dir.rglob("SKILL.md")):
            return skill_md_path.read_text(encoding="utf-8", errors="replace")
    return ""


def load_current_rules(task_name: str) -> dict[str, Any]:
    """Load rules.json by task_name, preferring reference version."""
    skill_name = get_skill_name(task_name)
    for path in [
        config.OUTPUT_DIR / skill_name / "rules.json",
        config.RULES_REF_DIR / task_name / "rules.json",
        config.TASKS_ROOT / task_name / "rules.json",
    ]:
        if path.exists():
            print(f"  Loaded rules from: {path}")
            return json.loads(path.read_text(encoding="utf-8"))
    return {}


# ---------------------------------------------------------------------------
# Skill-centric helpers (aggregate across all tasks sharing the same skill)
# ---------------------------------------------------------------------------

def get_tasks_for_skill(skill_name: str) -> list[str]:
    """Return all task_names in the map that use this skill."""
    mapping = load_task_skill_map()
    return [t for t, entry in mapping.items() if entry["skill_name"] == skill_name]


def load_current_rules_for_skill(skill_name: str) -> dict[str, Any]:
    """Load rules.json by skill_name. Output dir takes priority over reference."""
    task_names = get_tasks_for_skill(skill_name)
    for path in [
        config.OUTPUT_DIR / skill_name / "rules.json",
        # Try reference rules keyed by task_name for legacy compat
        *(config.RULES_REF_DIR / t / "rules.json" for t in task_names),
    ]:
        if path.exists():
            print(f"  Loaded rules from: {path}")
            return json.loads(path.read_text(encoding="utf-8"))
    return {}


def load_skill_md_for_skill(skill_name: str, task_names: list[str]) -> str:
    """Find and return SKILL.md for skill_name by searching associated tasks."""
    for task_name in task_names:
        for root in [config.TASKS_ROOT, config.TASKS_ROOT.parent / "skillsentry" / "tasks"]:
            p = root / task_name / "environment" / "skills" / skill_name / "SKILL.md"
            if p.exists():
                return p.read_text(encoding="utf-8", errors="replace")
    return ""


def load_baseline_traces_for_skill(skill_name: str) -> list[TraceData]:
    """Aggregate baseline traces from all tasks that share this skill.

    Each trace's source is prefixed with 'task_name/' to remain unique.
    """
    task_names = get_tasks_for_skill(skill_name)
    if not task_names:
        return []
    all_traces: list[TraceData] = []
    for task_name in task_names:
        task_traces = load_baseline_traces(task_name)
        for t in task_traces:
            t.source = f"{task_name}/{t.source}"
        all_traces.extend(task_traces)
        print(f"    {task_name}: {len(task_traces)} traces")
    return all_traces


def load_queries_for_skill(skill_name: str) -> list[str]:
    """Aggregate queries from all tasks that share this skill."""
    task_names = get_tasks_for_skill(skill_name)
    queries: list[str] = []
    for task_name in task_names:
        queries.extend(load_queries(task_name))
    return queries


def extract_workflow_steps_from_summaries(traces: list) -> list[str]:
    """Derive workflow_steps from Stage 1 summaries when no rules exist yet.

    Collects all step ids mentioned in steps_executed across all traces,
    preserving order of first appearance. Returns ["step_id: "] format.
    """
    seen: dict[str, int] = {}  # step_id -> first appearance index
    for t in traces:
        summary = getattr(t, "structured_summary", None) or {}
        for step in summary.get("steps_executed", []):
            sid = step.split(":")[0].strip() if ":" in step else step
            if sid and sid not in seen:
                seen[sid] = len(seen)
    return [f"{sid}: " for sid in sorted(seen, key=lambda s: seen[s])]


def load_queries(task_name: str, split: str = "evolve") -> list[str]:
    """Load queries for a task from data/evolve/<task>/<split>/.

    Each task instance directory contains:
      - instruction.md       — original query
      - index_0/ … index_N/  — paraphrase variants (each with instruction.md)

    Args:
        task_name: e.g. "econ-detrending-correlation"
        split: "evolve" (Q_evol) | "test" (Q_test) | "baseline"
    """
    queries: list[str] = []
    task_split_dir = config.EVOLVE_ROOT / task_name / split
    if not task_split_dir.exists():
        return queries

    for instance_dir in sorted(task_split_dir.iterdir()):
        if not instance_dir.is_dir():
            continue
        # Original query
        orig = instance_dir / "instruction.md"
        if orig.exists():
            queries.append(orig.read_text(encoding="utf-8"))
        # Paraphrase variants
        for idx_dir in sorted(instance_dir.iterdir()):
            if idx_dir.is_dir() and idx_dir.name.startswith("index_"):
                q = idx_dir / "instruction.md"
                if q.exists():
                    queries.append(q.read_text(encoding="utf-8"))
    return queries


def load_baseline_traces(task_name: str) -> list[TraceData]:
    """Load baseline traces from data/evolve/<task>/baseline/.

    Baseline traces are pre-collected agent runs stored as artifacts.json
    (containing trajectory, reward, verifier_stdout) under each task instance.
    These are used during the Initialization Stage (§III-B) to mine initial
    execution experience before any self-evolving rounds.
    """
    traces = []
    baseline_dir = config.EVOLVE_ROOT / task_name / "baseline"
    if not baseline_dir.exists():
        return traces

    for instance_dir in sorted(baseline_dir.iterdir()):
        if not instance_dir.is_dir():
            continue
        # Collect all query variants (original + paraphrases) within the instance
        query_dirs = [instance_dir] + sorted(
            [d for d in instance_dir.iterdir() if d.is_dir() and d.name.startswith("index_")]
        )
        for qdir in query_dirs:
            artifacts_file = qdir / "artifacts.json"
            if not artifacts_file.exists():
                continue
            try:
                artifacts = json.loads(artifacts_file.read_text(encoding="utf-8"))
                reward = float(artifacts.get("reward", 0.0))
                traj_raw = artifacts.get("trajectory", "")
                parsed = parse_trajectory(traj_raw)

                verifier_stdout = artifacts.get("verifier_stdout", "")
                if verifier_stdout:
                    extracted = _extract_test_results(verifier_stdout)
                    extracted = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', extracted)
                    parsed.verifier_stdout = extracted

                eval_result = {}
                ef = qdir / "eval.json"
                if ef.exists():
                    eval_result = json.loads(ef.read_text(encoding="utf-8"))

                query = ""
                qf = qdir / "instruction.md"
                if qf.exists():
                    query = qf.read_text(encoding="utf-8")

                source = f"{instance_dir.name}/{qdir.name}" if qdir != instance_dir else instance_dir.name
                traces.append(TraceData(
                    source=source,
                    reward=reward,
                    query=query,
                    parsed=parsed,
                    eval_result=eval_result,
                ))
            except Exception as e:
                print(f"  [warn] Failed to load {qdir}: {e}")
    return traces


def load_trace_from_trial(trial_dir: Path, query: str, source: str) -> Optional[TraceData]:
    """Load a TraceData from a harbor trial directory (iterate mode)."""
    # Reward
    reward = 0.0
    reward_txt = trial_dir / "verifier" / "reward.txt"
    if reward_txt.exists():
        try:
            reward = float(reward_txt.read_text(encoding="utf-8").strip())
        except Exception:
            pass
    else:
        result_json = trial_dir.parent / "result.json"
        if result_json.exists():
            try:
                d = json.loads(result_json.read_text(encoding="utf-8"))
                for eval_data in d.get("stats", {}).get("evals", {}).values():
                    for buckets in eval_data.get("reward_stats", {}).values():
                        for bucket_val in buckets.keys():
                            reward = float(bucket_val)
            except Exception:
                pass

    # Trajectory from agent/claude-code.txt
    traj_raw = ""
    agent_dir = trial_dir / "agent"
    if agent_dir.exists():
        for f in agent_dir.glob("*.txt"):
            if f.name != "install.sh":
                traj_raw = f.read_text(encoding="utf-8", errors="replace")
                break

    parsed = parse_trajectory(traj_raw)

    # Add verifier_stdout — extract test result section only (prevents overfit)
    verifier_stdout_file = trial_dir / "verifier" / "test-stdout.txt"
    if not verifier_stdout_file.exists():
        verifier_stdout_file = trial_dir / "verifier" / "stdout.txt"
    if verifier_stdout_file.exists():
        raw_vs = verifier_stdout_file.read_text(encoding="utf-8", errors="replace")
        parsed.verifier_stdout = _extract_test_results(raw_vs)

    # Also check skillsentry log
    ss_log = trial_dir / "agent" / "skillsentry.log"
    if not ss_log.exists():
        # Also check /logs/agent/skillsentry.log path (docker mount)
        ss_log = trial_dir.parent.parent / "skillsentry.log"
    if ss_log.exists():
        hook_events = parse_skillsentry_log(ss_log.read_text(encoding="utf-8"))
        if hook_events:
            parsed.hook_events = hook_events

    return TraceData(source=source, reward=reward, query=query, parsed=parsed)
