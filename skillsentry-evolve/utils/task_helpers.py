"""Task-level helpers: load rules, SKILL.md, traces from dataset_for_validation."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
import pathlib
from typing import Any, Optional

import config
from tdrr.trace_parser import ParsedTrace, parse_trajectory, parse_skillsentry_log


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
    """Load SKILL.md for the canonical skill of a task."""
    skill_name = get_skill_name(task_name)
    # Try canonical skill dir first
    for root in [config.TASKS_ROOT, config.TASKS_ROOT.parent / "skillsentry" / "tasks"]:
        skill_md_path = root / task_name / "environment" / "skills" / skill_name / "SKILL.md"
        if skill_md_path.exists():
            return skill_md_path.read_text(encoding="utf-8", errors="replace")
    # Fallback: first SKILL.md found
    for root in [config.TASKS_ROOT, config.TASKS_ROOT.parent / "skillsentry" / "tasks"]:
        skills_dir = root / task_name / "environment" / "skills"
        if skills_dir.exists():
            for skill_subdir in sorted(skills_dir.iterdir()):
                skill_md_path = skill_subdir / "SKILL.md"
                if skill_md_path.exists():
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


def _extract_steps_from_skill_md(skill_md: str) -> list[dict]:
    """Extract step structure from the frontmatter or body of SKILL.md."""
    steps = []
    lines = skill_md.split("\n")
    prev_id = None
    for line in lines:
        # Match "Step N: label" or "## N. label" format
        m = re.match(r'^(?:Step\s+\d+|##?\s+\d+)[:\.\s]+(.+)$', line.strip(), re.IGNORECASE)
        if m:
            label = m.group(1).strip()
            # Generate snake_case id
            sid = re.sub(r'[^a-z0-9]+', '_', label.lower()).strip('_')[:30]
            step = {
                "stepId": sid,
                "description": label,
                "depends_on": [prev_id] if prev_id else [],
                "constraints": [],
            }
            steps.append(step)
            prev_id = sid
    return steps



def _must_call_to_logical_actions(must_call: list[dict]) -> list[dict]:
    """Convert a flat must_call list to the nested logical_actions structure.
    Patterns from the same tool are merged into the same action.
    """
    action_map: dict[str, list] = {}
    for sig in must_call:
        tool = sig.get("tool", "Bash")
        action_map.setdefault(tool, []).append(sig)
    actions = []
    for action_id, (tool, patterns) in enumerate(action_map.items(), start=1):
        actions.append({"actionId": action_id, "patterns": patterns})
    return actions


def generate_initial_rules(
    task_name: str,
    skill_name: str,
    skill_md: str,
    candidates: dict,  # from pattern_mining.derive_candidates()
) -> dict:
    """
    Generate initial rules.json from scratch using SKILL.md + trace patterns.
    Called during bootstrap when no existing rules are available or when
    we want to generate rules purely from traces (not load hand-crafted ones).

    Step structure comes from SKILL.md.
    must_call regex comes from success trace tokens (candidates).
    forbidden rules come from failure trace tokens (candidates).
    """
    import utils.llm as llm

    skill_md_excerpt = skill_md[:3000] if skill_md else "(not available)"

    # Flatten candidates, remove the _global level, and give LLM a direct pattern+example list
    mc_all = []
    for step_cands in candidates.get("must_call_candidates", {}).values():
        mc_all.extend(step_cands)
    # Deduplicate, sort by count descending, take top 30
    seen = set()
    mc_dedup = []
    for c in sorted(mc_all, key=lambda x: x.get("count", 0), reverse=True):
        if c["pattern"] not in seen:
            seen.add(c["pattern"])
            mc_dedup.append(c)
    mc_dedup = mc_dedup[:30]

    fb_all = []
    for step_cands in candidates.get("forbidden_candidates", {}).values():
        fb_all.extend(step_cands)
    fb_dedup = sorted(fb_all, key=lambda x: x.get("fail_count", 0), reverse=True)[:20]

    try:
        sp_text = llm.sp_with_dsl("bootstrap_rules_gen_sp")
        up = llm.up("bootstrap_rules_gen_up",
            task_name=task_name,
            skill_name=skill_name,
            skill_md=skill_md_excerpt,
            must_call_candidates=json.dumps(mc_dedup, indent=2, ensure_ascii=False)[:2000],
            forbidden_candidates=json.dumps(fb_dedup, indent=2, ensure_ascii=False)[:2000],
            memory_summary=str(candidates.get("memory_summary", "(none)"))[:500],
        )
        import utils.llm as llm_mod
        raw = llm_mod.call(
            [{"role": "system", "content": sp_text},
             {"role": "user", "content": up}],
            temperature=0.2,
            json_mode=True,
        )
        raw_rules = json.loads(raw)
        # Error tolerance: LLM sometimes uses old field names; auto-correct to new DSL
        for step in raw_rules.get("steps", []):
            if "name" in step and "stepId" not in step:
                step["stepId"] = step.pop("name")
            if "id" in step and "stepId" not in step:
                step["stepId"] = step.pop("id")
            if "label" in step and "description" not in step:
                step["description"] = step.pop("label")
            if "requires" in step and "depends_on" not in step:
                step["depends_on"] = step.pop("requires")
            if "must_call" in step and "logical_actions" not in step:
                # Convert flat must_call list to nested logical_actions structure
                step["logical_actions"] = _must_call_to_logical_actions(step.pop("must_call"))
            if "forbidden" in step and "failure_patterns" not in step:
                step["failure_patterns"] = step.pop("forbidden")
            if "constraints" not in step:
                step["constraints"] = []
        # completion_assertion → termination
        if "completion_assertion" in raw_rules and "termination" not in raw_rules:
            sigs = raw_rules.pop("completion_assertion", {}).get("required_signatures", [])
            raw_rules["termination"] = [s.replace(".must_call", "") for s in sigs]

        # Fallback: extract step structure from SKILL.md if LLM generated too few steps
        # (fewer than half the number of steps in SKILL.md), rebuild from SKILL.md
        # structure and merge in LLM-generated must_call/forbidden/on_enter content
        skill_steps = _extract_steps_from_skill_md(skill_md)
        llm_steps = raw_rules.get("steps", [])
        if skill_steps and len(llm_steps) < max(2, len(skill_steps) // 2):
            # Merge LLM-generated content into SKILL.md structure
            merged_steps = []
            # Flatten LLM's logical_actions patterns and failure_patterns
            all_llm_patterns = [
                p
                for s in llm_steps
                for la in s.get("logical_actions", [])
                for p in la.get("patterns", [])
            ]
            all_llm_forbidden = [fb for s in llm_steps for fb in s.get("failure_patterns", [])]

            for i, sk_step in enumerate(skill_steps):
                sid = sk_step["stepId"]
                n = len(skill_steps)
                chunk = len(all_llm_patterns) // n if n else 0
                step_patterns = all_llm_patterns[i*chunk:(i+1)*chunk] if chunk else []
                if not step_patterns:
                    step_patterns = [{"tool": "Bash", "command_match": "python3"},
                                     {"tool": "Write", "input_match": {"content": "unified_planning"}}]
                merged_steps.append({
                    "stepId": sid,
                    "description": sk_step["description"],
                    "depends_on": sk_step["depends_on"],
                    "constraints": [],
                    "logical_actions": [{"actionId": 1, "patterns": step_patterns}],
                    "on_enter": {"suggestions": [], "warnings": []},
                    "failure_patterns": [],
                })
            if all_llm_forbidden and merged_steps:
                merged_steps[-1]["failure_patterns"] = all_llm_forbidden

            raw_rules["steps"] = merged_steps
            raw_rules["skill"] = skill_name
            if not raw_rules.get("termination"):
                raw_rules["termination"] = [s["stepId"] for s in merged_steps]

        return raw_rules
    except Exception as e:
        import traceback, sys
        print(f"  [warn] generate_initial_rules failed: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return {}


def get_workflow_steps(rules: dict[str, Any]) -> list[str]:
    return [f"{s['stepId']}: {s.get('description', '')}" for s in rules.get("steps", [])]


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


def load_queries(task_name: str) -> list[str]:
    queries = []
    task_dir = config.DATASET_ROOT / task_name
    for iter_path in sorted(task_dir.glob("iter_*")):
        q = iter_path / "query.md"
        if q.exists():
            queries.append(q.read_text(encoding="utf-8"))
    return queries


def load_baseline_traces(task_name: str) -> list[TraceData]:
    """Load all baseline traces from dataset_for_validation."""
    traces = []
    task_dir = config.DATASET_ROOT / task_name
    if not task_dir.exists():
        return traces

    for iter_path in sorted(task_dir.glob("iter_*")):
        artifacts_file = iter_path / "artifacts.json"
        if not artifacts_file.exists():
            continue
        try:
            artifacts = json.loads(artifacts_file.read_text(encoding="utf-8"))
            reward = float(artifacts.get("reward", 0.0))
            traj_raw = artifacts.get("trajectory", "")
            parsed = parse_trajectory(traj_raw)

            # verifier_stdout: direct test failure evidence (Stage 1 only, NOT Stage 3)
            verifier_stdout = artifacts.get("verifier_stdout", "")
            if verifier_stdout:
                extracted = _extract_test_results(verifier_stdout)
                extracted = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', extracted)
                parsed.verifier_stdout = extracted

            eval_result = {}
            ef = iter_path / "eval.json"
            if ef.exists():
                eval_result = json.loads(ef.read_text(encoding="utf-8"))

            query = ""
            qf = iter_path / "query.md"
            if qf.exists():
                query = qf.read_text(encoding="utf-8")

            traces.append(TraceData(
                source=iter_path.name,
                reward=reward,
                query=query,
                parsed=parsed,
                eval_result=eval_result,
            ))
        except Exception as e:
            print(f"  [warn] Failed to load {iter_path.name}: {e}")
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
