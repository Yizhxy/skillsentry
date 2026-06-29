"""
FSM reachability validator.

Before applying a must_call update, simulate whether the new regex
can be satisfied by at least one successful trace's tool calls.

If a must_call regex cannot be matched by ANY tool call in ANY successful trace,
the FSM will be stuck at that step — the update is rejected.

Uses skillsentry's matchers.py for consistent matching logic.
"""
from __future__ import annotations

import re
import sys
from typing import Any

# Try to import skillsentry matchers for consistent regex matching
try:
    import importlib.util, pathlib
    _ss_path = pathlib.Path(__file__).resolve().parent.parent.parent / \
               "skillsentry" / "skillsentry"
    if _ss_path.exists():
        spec = importlib.util.spec_from_file_location(
            "skillsentry_matchers", _ss_path / "matchers.py")
        _matchers_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_matchers_mod)
        _safe_search = _matchers_mod._safe_search
    else:
        _safe_search = None
except Exception:
    _safe_search = None


def _regex_matches_command(pattern: str, command: str) -> bool:
    """Check if a regex pattern matches a command string."""
    if _safe_search:
        return _safe_search(pattern, command)
    try:
        return re.search(pattern, command) is not None
    except re.error:
        return False


def _signature_matches_tool_call(sig: dict[str, Any], tool: str,
                                  command: str | None,
                                  content: str | None) -> bool:
    """Check if a signature dict matches a tool call."""
    # Tool filter
    sig_tool = sig.get("tool")
    if sig_tool and sig_tool != tool:
        return False

    # command_match (Bash)
    cmd_pat = sig.get("command_match")
    if cmd_pat:
        if not command:
            return False
        if not _regex_matches_command(cmd_pat, command):
            return False

    # input_match.content (Write/Edit) — also check Bash heredoc content
    input_match = sig.get("input_match", {})
    content_pat = input_match.get("content") if isinstance(input_match, dict) else None
    if content_pat:
        # for Write/Edit: check content_snippet
        # for Bash: also check command body (handles python3 << 'EOF' ... EOF pattern)
        text_to_check = content or command or ""
        if not text_to_check:
            return False
        if not _regex_matches_command(content_pat, text_to_check):
            return False

    return True


def check_must_call_reachable(
    new_must_call: list[dict[str, Any]],
    step_id: str,
    success_traces: list,           # current round traces
    global_success_tokens: dict | None = None,  # from memory.success_patterns[step_id]
) -> tuple[bool, str]:
    """
    Check if the new must_call signatures can be satisfied.

    Uses BOTH current-round success traces AND global memory tokens.
    This prevents false rejections when the current round has few success traces.

    Returns (is_reachable, reason).
    """
    if not new_must_call:
        return True, "empty must_call — always reachable"

    valid_sigs = [s for s in new_must_call if isinstance(s, dict)]
    if not valid_sigs:
        return True, "no valid signature dicts — allowing by default"

    # First check: does any signature match current-round success traces?
    matched_traces = 0
    for trace in success_traces:
        for sig in valid_sigs:
            for tc in trace.parsed.tool_calls:
                command = tc.command or ""
                content = tc.content_snippet or ""
                if _signature_matches_tool_call(sig, tc.tool, command, content):
                    matched_traces += 1
                    break
            else:
                continue
            break

    if matched_traces > 0:
        return True, f"matched {matched_traces}/{len(success_traces)} current-round success traces"

    # Second check: does any signature's regex appear in global memory tokens?
    # This handles the case where current round has few/no success traces
    if global_success_tokens:
        for sig in valid_sigs:
            cmd_pat = sig.get("command_match", "")
            content_pat = (sig.get("input_match") or {}).get("content", "")
            pattern = cmd_pat or content_pat
            if not pattern:
                continue
            # Check if any global success token matches this regex
            for token in global_success_tokens:
                try:
                    if re.search(pattern, token):
                        return True, f"matched global memory token '{token}' for step '{step_id}'"
                except re.error:
                    pass

    # Both checks failed — this regex would cause FSM stuck
    sig_descs = []
    for sig in valid_sigs[:3]:
        parts = []
        if sig.get("tool"):
            parts.append(f"tool={sig['tool']}")
        if sig.get("command_match"):
            parts.append(f"cmd~/{sig['command_match']}/")
        if sig.get("input_match", {}).get("content"):
            parts.append(f"content~/{sig['input_match']['content']}/")
        sig_descs.append("{" + ", ".join(parts) + "}")

    reason = (f"must_call {sig_descs} matched 0/{len(success_traces)} current traces "
              f"and 0 global memory tokens — FSM would be stuck at step '{step_id}'")
    return False, reason


def format_constraints_hint(constraints: list[dict]) -> str:
    """Format a constraints list into readable hint text for on_enter injection."""
    if not constraints:
        return ""

    hints = []
    for c in constraints:
        if "tool" in c:
            hints.append(f"Use {c['tool']} tool for this step")
        elif "parameter" in c:
            param = c["parameter"]
            req = c.get("requirement", "")
            hints.append(f"Parameter {param}: {req}")

    return " | ".join(hints) if hints else ""
