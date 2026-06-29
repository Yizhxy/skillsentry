#!/usr/bin/env python3
"""
SWAG PreToolUse hook for Claude Code.

Registered in Claude Code's settings.json as:

  "hooks": {
    "PreToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/swag_hook.py"
          }
        ]
      }
    ]
  }

Environment variables (set before running claude):
  SWAG_WORKFLOW_SPEC   Path to workflow spec JSON file
  SWAG_STATE_FILE      Path to per-session state JSON file (created if absent)
  SWAG_ENABLED         Set to "0" to disable (default: "1")
  SWAG_MATCH_THRESHOLD Minimum similarity score to claim a phase match (default: "0.05")
  SWAG_LOG_FILE        Optional: append hook decisions to this JSONL file

Input (stdin, sent by Claude Code):
  {"tool_name": "Bash", "tool_input": {"command": "..."}}

Output (stdout, read by Claude Code):
  {"decision": "allow"}
  {"decision": "block", "reason": "..."}   <- shows reason to the agent
"""

import json
import os
import sys
import time
import traceback
from pathlib import Path

# Allow running from any working directory
_HOOK_DIR = Path(__file__).parent
_CORE_DIR = _HOOK_DIR.parent / "core"
sys.path.insert(0, str(_CORE_DIR.parent))  # adds swag/ parent so `from swag.core...` works

try:
    from swag.core.workflow_state import WorkflowState
except ImportError:
    # Fallback: direct import when not installed as package
    sys.path.insert(0, str(_CORE_DIR))
    from workflow_state import WorkflowState  # type: ignore


def _log(entry: dict, log_file: str):
    """Append a JSON line to the log file."""
    try:
        with open(log_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    except Exception:
        pass


def main():
    # ------------------------------------------------------------------ #
    # 0. Read env vars                                                     #
    # ------------------------------------------------------------------ #
    enabled = os.environ.get('SWAG_ENABLED', '1').strip() not in ('0', 'false', 'False')
    spec_file = os.environ.get('SWAG_WORKFLOW_SPEC', '')
    state_file = os.environ.get('SWAG_STATE_FILE', '')
    log_file = os.environ.get('SWAG_LOG_FILE', '')

    # If not configured or disabled, pass through silently
    if not enabled or not spec_file or not state_file:
        print(json.dumps({"decision": "allow"}))
        return

    # ------------------------------------------------------------------ #
    # 1. Parse tool call from stdin                                        #
    # ------------------------------------------------------------------ #
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        print(json.dumps({"decision": "allow"}))
        return

    tool_name = payload.get('tool_name', payload.get('tool', ''))
    tool_input = payload.get('tool_input', payload.get('input', {}))

    # ------------------------------------------------------------------ #
    # 2. Load workflow state                                               #
    # ------------------------------------------------------------------ #
    try:
        wf_state = WorkflowState.load(spec_file, state_file)
    except FileNotFoundError as e:
        # Spec file missing — fail open (allow), log the error
        entry = {'ts': time.time(), 'error': f'spec not found: {e}', 'tool': tool_name}
        if log_file:
            _log(entry, log_file)
        print(json.dumps({"decision": "allow"}))
        return
    except Exception as e:
        entry = {'ts': time.time(), 'error': traceback.format_exc(), 'tool': tool_name}
        if log_file:
            _log(entry, log_file)
        print(json.dumps({"decision": "allow"}))
        return

    # ------------------------------------------------------------------ #
    # 3. Check action against workflow                                     #
    # ------------------------------------------------------------------ #
    try:
        result = wf_state.check_action(tool_name, tool_input)
    except Exception as e:
        entry = {'ts': time.time(), 'error': traceback.format_exc(), 'tool': tool_name}
        if log_file:
            _log(entry, log_file)
        print(json.dumps({"decision": "allow"}))
        return

    # ------------------------------------------------------------------ #
    # 4. Persist updated state                                             #
    # ------------------------------------------------------------------ #
    try:
        wf_state.save(state_file)
    except Exception:
        pass  # non-fatal; enforcement already decided

    # ------------------------------------------------------------------ #
    # 5. Log decision                                                      #
    # ------------------------------------------------------------------ #
    if log_file:
        _log({
            'ts': time.time(),
            'tool': tool_name,
            'allow': result['allow'],
            'reason': result.get('reason', ''),
        }, log_file)

    # ------------------------------------------------------------------ #
    # 6. Return decision to Claude Code                                    #
    # ------------------------------------------------------------------ #
    if result['allow']:
        print(json.dumps({"decision": "allow"}))
    else:
        print(json.dumps({
            "decision": "block",
            "reason": result['reason'],
        }))


if __name__ == '__main__':
    main()
