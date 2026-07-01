"""
Harbor runner — stage and run skillsentry trials.

Handles:
- Copying task dir and writing query to instruction.md
- Setting up .claude/ with skillsentry hook + settings.json
- Placing rules.json at environment/skillsentry/<skill_name>/rules.json
- Running harbor and collecting reward + trace
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import config
from utils.task_data import TraceData, load_trace_from_trial, get_skill_name


def setup_task(
    src_task_dir: Path,
    dst_task_dir: Path,
    query: str,
    rules: dict[str, Any],
    skill_name: str,
    skillsentry_skill: str = "",
) -> None:
    """Stage a task directory with skillsentry enabled."""
    def _rm_force(path: Path) -> None:
        """Remove a directory tree, skipping files that can't be deleted (root-owned)."""
        def onerror(func, p, exc):
            try:
                os.chmod(p, 0o755)
                func(p)
            except Exception:
                pass  # silently skip files we can't remove
        shutil.rmtree(path, onerror=onerror)

    if dst_task_dir.exists():
        _rm_force(dst_task_dir)
    shutil.copytree(src_task_dir, dst_task_dir, symlinks=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    (dst_task_dir / "instruction.md").write_text(
        query.rstrip() + "\n", encoding="utf-8")

    # environment/ is mounted to /root/ inside the container.
    # Everything that needs to be at /root/<x> must go under environment/<x>.
    env_dir = dst_task_dir / "environment"
    env_dir.mkdir(parents=True, exist_ok=True)

    # Copy skillsentry package → /root/skillsentry/
    dst_ss = env_dir / "skillsentry"
    if dst_ss.exists():
        _rm_force(dst_ss)
    if config.SKILLSENTRY_SRC.exists():
        shutil.copytree(config.SKILLSENTRY_SRC, dst_ss,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))

    # Place rules.json → /root/skillsentry/<skill_name>/rules.json
    if skill_name and rules:
        rules_dst = dst_ss / skill_name
        rules_dst.mkdir(parents=True, exist_ok=True)
        (rules_dst / "rules.json").write_text(
            json.dumps(rules, indent=2, ensure_ascii=False), encoding="utf-8")

    # Copy hook → environment/skillsentry_hook.py (Dockerfile: COPY skillsentry_hook.py /root/.claude/)
    hook_file = config.HOOKS_SRC / "skillsentry_hook.py"
    if hook_file.exists():
        shutil.copy2(hook_file, env_dir / "skillsentry_hook.py")

    # Write settings.json → environment/settings.json (Dockerfile: COPY settings.json /root/.claude/)
    hook_cmd = "python3 /root/.claude/skillsentry_hook.py"
    ss_env: dict[str, str] = {
        "SKILLSENTRY_RULES_DIR": "/root/skillsentry",
        "SKILLSENTRY_MODE":      "strict",
        "SKILLSENTRY_LOG":       "/logs/agent/skillsentry.log",
        "SKILLSENTRY_STATE_DIR": "/logs/agent/skillsentry_state",
        "PYTHONPATH":            "/root",
    }
    if skillsentry_skill:
        ss_env["SKILLSENTRY_SKILL"] = skillsentry_skill
    settings = {
        "env": ss_env,
        "hooks": {
            event: [{"hooks": [{"type": "command", "command": hook_cmd}]}]
            for event in ["SessionStart", "PreToolUse", "PostToolUse", "Stop"]
        }
    }
    (env_dir / "settings.json").write_text(json.dumps(settings, indent=2))

    # Patch Dockerfile so files are COPY'd into the container at build time
    _patch_dockerfile(env_dir)


def _patch_dockerfile(env_dir: Path) -> None:
    """Inject COPY instructions into the Dockerfile so skillsentry files
    land at the correct paths inside the container.

    harbor forces CLAUDE_CONFIG_DIR to /logs/agent/sessions (a runtime mount dir),
    so Dockerfile COPY cannot write to that path directly.
    Solution: add an /entrypoint-hook.sh script to the Dockerfile that is
    automatically sourced via BASH_ENV on shell startup, copying settings.json
    to $CLAUDE_CONFIG_DIR before harbor's setup_command runs.
    """
    df_path = env_dir / "Dockerfile"
    if not df_path.exists():
        return

    content = df_path.read_text(encoding="utf-8")
    if "# SkillSentry-evolve" in content:
        return  # already patched

    # Write a shell snippet that copies settings to $CLAUDE_CONFIG_DIR at runtime
    hook_cmd = "python3 /root/.claude/skillsentry_hook.py"
    settings_json = json.dumps({
        "hooks": {
            event: [{"hooks": [{"type": "command", "command": hook_cmd}]}]
            for event in ["SessionStart", "PreToolUse", "PostToolUse", "Stop"]
        }
    }, indent=2)

    # Escape for embedding in Dockerfile RUN heredoc
    settings_escaped = settings_json.replace("\\", "\\\\").replace('"', '\\"')

    ss_block = (
        "\n"
        "# SkillSentry-evolve: inject settings at container startup via BASH_ENV\n"
        "COPY settings.json /root/.claude/settings.json\n"
        "# BASH_ENV makes every non-interactive bash source /root/.ss_init.sh\n"
        "# harbor's setup_command runs as bash -c, so this fires before setup runs\n"
        "RUN printf '#!/bin/bash\\nif [ -n \"$CLAUDE_CONFIG_DIR\" ] && "
        "[ \"$CLAUDE_CONFIG_DIR\" != \"/root\" ]; then\\n"
        "  mkdir -p \"$CLAUDE_CONFIG_DIR\"\\n"
        "  cp /root/.claude/settings.json \"$CLAUDE_CONFIG_DIR/settings.json\" 2>/dev/null || true\\n"
        "fi\\n' > /root/.ss_init.sh && chmod +x /root/.ss_init.sh\n"
        "ENV BASH_ENV=/root/.ss_init.sh\n"
        "ENV PYTHONPATH=/root:$PYTHONPATH\n"
    )

    lines = content.splitlines(keepends=True)
    insert_idx = None
    for i, line in enumerate(lines):
        if line.startswith("COPY skills "):
            insert_idx = i + 1

    if insert_idx is None:
        content += ss_block
    else:
        lines.insert(insert_idx, ss_block)
        content = "".join(lines)

    df_path.write_text(content, encoding="utf-8")


def run_trial(task_dir: Path, output_dir: Path) -> Optional[Path]:
    """
    Run a single harbor trial. Returns the trial_dir path on success, None on failure.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # harbor forces CLAUDE_CONFIG_DIR to <output_dir>/job/<task>/agent/sessions/
    # so write settings.json before harbor runs to ensure the hook can be loaded by Claude Code
    hook_cmd = "python3 /root/.claude/skillsentry_hook.py"
    settings = {
        "hooks": {
            event: [{"hooks": [{"type": "command", "command": hook_cmd}]}]
            for event in ["SessionStart", "PreToolUse", "PostToolUse", "Stop"]
        }
    }
    # harbor first creates job/<task_id>/agent/sessions/; pre-create it and write settings.json
    # actual task_id is unknown, use wildcard placeholder; harbor will look under output_dir/job/<task_id>/agent/sessions/
    # more reliable approach: write to output_dir/agent/sessions/ (harbor mount mapping path)
    # verified: harbor mounts <output_dir>/job/<task_id>/agent/ as /logs/agent/ inside the container
    # so we'd need to pre-create for every possible task_id, but task_id is unpredictable
    # solution: let environment/Dockerfile COPY handle it — the file is already at the correct location

    cmd = [
        config.HARBOR_BIN, "run",
        "-p", str(task_dir),
        "-a", config.HARBOR_AGENT,
        "-m", config.HARBOR_MODEL,
        "-o", str(output_dir),
        "--job-name", "job",
        "-q", "--delete",
        "--force-build",
        "--ae", f"ANTHROPIC_BASE_URL={config.AGENT_API_BASE}",
        "--ae", f"ANTHROPIC_API_KEY={config.AGENT_API_KEY}",
        "--ae", f"SKILLSENTRY_RULES_DIR=/root/skillsentry",
        "--ae", f"SKILLSENTRY_MODE=strict",
        "--ae", f"SKILLSENTRY_LOG=/logs/agent/skillsentry.log",
        "--ae", "PYTHONPATH=/root",
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True,
                       timeout=config.HARBOR_TIMEOUT)
    except subprocess.TimeoutExpired:
        print("  [warn] harbor timeout", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  [warn] harbor error: {e}", file=sys.stderr)
        return None

    task_dirs = [td for td in (output_dir / "job").glob("task__*/") if td.is_dir()]
    if task_dirs:
        # When multiple directories exist, take the most recent one
        # (older directories from previous rounds may have restricted permissions)
        return max(task_dirs, key=lambda p: p.stat().st_mtime)
    return None


def _run_single_query(
    i: int,
    query: str,
    task_name: str,
    rules: dict[str, Any],
    work_dir: Path,
    skill_name: str,
    src_task_dir: Path,
) -> tuple[int, Optional[TraceData]]:
    """Run a single harbor trial for one query. Returns (index, trace or None)."""
    import time
    task_stage = work_dir / f"query_{i:03d}" / "task"
    # Use a unique output directory each time to avoid conflicts with
    # root-owned files left over from previous rounds
    trial_out  = work_dir / f"query_{i:03d}" / f"output_{int(time.time())}"

    setup_task(src_task_dir, task_stage, query, rules, skill_name, skillsentry_skill=skill_name)
    trial_dir = run_trial(task_stage, trial_out)

    trace = None
    if trial_dir:
        trace = load_trace_from_trial(trial_dir, query, f"query_{i:03d}")

    # Clean up staged task dir
    if task_stage.exists():
        shutil.rmtree(task_stage)

    return i, trace


def collect_traces(
    task_name: str,
    rules: dict[str, Any],
    queries: list[str],
    work_dir: Path,
    dry_run: bool = False,
    max_workers: int = 5,
) -> list[TraceData]:
    """Run harbor for each query with current rules in parallel, return collected traces."""
    skill_name = get_skill_name(task_name)
    src_task_dir = config.TASKS_ROOT / task_name
    traces = []

    if dry_run:
        for i in range(len(queries)):
            print(f"  Query {i+1}/{len(queries)} ... [dry-run skipped]")
        return traces

    # Run trials in parallel
    results = [None] * len(queries)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _run_single_query, i, query, task_name, rules, work_dir, skill_name, src_task_dir
            ): i
            for i, query in enumerate(queries)
        }

        for future in as_completed(futures):
            i = futures[future]
            try:
                idx, trace = future.result()
                results[idx] = trace
                if trace:
                    print(f"  Query {idx+1}/{len(queries)} ... reward={trace.reward}")
                else:
                    print(f"  Query {idx+1}/{len(queries)} ... failed")
            except Exception as e:
                print(f"  Query {i+1}/{len(queries)} ... error: {e}", file=sys.stderr)

    # Collect non-None traces in original order
    traces = [t for t in results if t is not None]
    return traces
