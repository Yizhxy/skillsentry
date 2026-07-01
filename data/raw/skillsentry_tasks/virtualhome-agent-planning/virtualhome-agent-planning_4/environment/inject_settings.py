#!/usr/bin/env python3
"""
inject_settings.py — Write SWAG hooks configuration into Claude Code's config dir.
Simplified version for containerized execution.
"""

import argparse
import json
import sys
from pathlib import Path

# Hardcoded workflow spec for virtualhome-agent-planning
WORKFLOW_SPEC = {
    "task_name": "virtualhome-agent-planning",
    "skill_name": "pddl-skills",
    "summary": "Automated PDDL planning: load, plan, validate, and save",
    "steps": [
        {
            "id": "step_0",
            "name": "Step 1: Load PDDL domain and problem files using load_proble",
            "description": "Step 1: Load PDDL domain and problem files using load_problem()",
            "dependencies": []
        },
        {
            "id": "step_1",
            "name": "Step 2: Generate a plan using generate_plan() with a classic",
            "description": "Step 2: Generate a plan using generate_plan() with a classical planner",
            "dependencies": [
                "step_0"
            ]
        },
        {
            "id": "step_2",
            "name": "Step 3: Validate the plan using validate() to confirm goal s",
            "description": "Step 3: Validate the plan using validate() to confirm goal satisfaction",
            "dependencies": [
                "step_0",
                "step_1"
            ]
        },
        {
            "id": "step_3",
            "name": "Step 4: Save the plan to disk using save_plan()",
            "description": "Step 4: Save the plan to disk using save_plan()",
            "dependencies": [
                "step_0",
                "step_1",
                "step_2"
            ]
        }
    ]
}


def inject(config_dir: str, session_id: str, log_file: str = ""):
    config_path = Path(config_dir)
    config_path.mkdir(parents=True, exist_ok=True)

    # 1. Write workflow spec
    spec_file = config_path / f"swag_spec_{session_id}.json"
    with open(spec_file, "w") as f:
        json.dump(WORKFLOW_SPEC, f, indent=2)

    # 2. State file path (created on first check_action call)
    state_file = config_path / f"swag_state_{session_id}.json"

    # 3. Build hook command with env vars inlined
    hook_script = "/usr/local/bin/swag_hook.py"
    env_prefix = (
        f"SWAG_WORKFLOW_SPEC={spec_file} "
        f"SWAG_STATE_FILE={state_file} "
        f"SWAG_ENABLED=1 "
    )
    if log_file:
        env_prefix += f"SWAG_LOG_FILE={log_file} "

    hook_cmd = f"{env_prefix}python3 {hook_script}"

    # 4. Write settings.json
    settings = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "",
                    "hooks": [
                        {
                            "type": "command",
                            "command": hook_cmd,
                        }
                    ],
                }
            ]
        }
    }

    settings_file = config_path / "settings.json"
    # Merge with existing settings if present
    if settings_file.exists():
        try:
            with open(settings_file) as f:
                existing = json.load(f)
            # Append our hook, don't overwrite others
            existing.setdefault("hooks", {}).setdefault("PreToolUse", [])
            existing["hooks"]["PreToolUse"].extend(
                settings["hooks"]["PreToolUse"]
            )
            settings = existing
        except Exception:
            pass  # if corrupted, overwrite with just our hooks

    with open(settings_file, "w") as f:
        json.dump(settings, f, indent=2)

    print(f"[SWAG] Injected hooks into {settings_file}", file=sys.stderr)
    print(f"[SWAG] Workflow spec: {spec_file} ({len(WORKFLOW_SPEC['steps'])} steps)", file=sys.stderr)
    print(f"[SWAG] State file:    {state_file}", file=sys.stderr)

    # Return paths so callers can inspect
    return {
        "settings_file": str(settings_file),
        "spec_file": str(spec_file),
        "state_file": str(state_file),
    }


def main():
    parser = argparse.ArgumentParser(description="Inject SWAG hooks into Claude Code config")
    parser.add_argument("--config-dir",  required=True, help="CLAUDE_CONFIG_DIR path")
    parser.add_argument("--session-id",  required=True, help="Unique session identifier")
    parser.add_argument("--log-file",    default="",    help="Optional JSONL log path")
    # task-name is ignored in this simplified version
    parser.add_argument("--task-name",   default="",    help="Task name (ignored)")
    args = parser.parse_args()

    result = inject(
        config_dir=args.config_dir,
        session_id=args.session_id,
        log_file=args.log_file,
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
