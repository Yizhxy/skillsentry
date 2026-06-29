"""Match a pending tool call against a Signature."""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from .ir import Signature


def _safe_search(pattern: Optional[str], text: Any) -> bool:
    if not pattern:
        return True
    if not isinstance(text, str):
        return False
    try:
        return re.search(pattern, text) is not None
    except re.error:
        return False


def _path_field(tool_name: str, tool_input: Dict[str, Any]) -> Optional[str]:
    if not isinstance(tool_input, dict):
        return None
    for k in ("file_path", "path", "notebook_path"):
        v = tool_input.get(k)
        if isinstance(v, str):
            return v
    return None


def _command_field(tool_name: str, tool_input: Dict[str, Any]) -> Optional[str]:
    if not isinstance(tool_input, dict):
        return None
    if tool_name == "Bash":
        v = tool_input.get("command")
        return v if isinstance(v, str) else None
    return None


def match_signature(sig: Signature, tool_name: str, tool_input: Dict[str, Any]) -> bool:
    """Return True iff (tool_name, tool_input) matches the signature's filters.

    All specified filters must hold (AND). Empty signature matches everything.
    """
    if sig.tool and sig.tool != tool_name:
        return False

    if sig.command_match:
        cmd = _command_field(tool_name, tool_input)
        if cmd is None or not _safe_search(sig.command_match, cmd):
            return False

    if sig.path_match:
        path = _path_field(tool_name, tool_input)
        if path is None or not _safe_search(sig.path_match, path):
            return False

    if sig.input_match and isinstance(tool_input, dict):
        for k, pat in sig.input_match.items():
            if not _safe_search(pat, tool_input.get(k)):
                return False
    elif sig.input_match:
        return False

    return True


def signature_label(sig: Signature) -> str:
    parts = []
    if sig.tool: parts.append(f"tool={sig.tool}")
    if sig.command_match: parts.append(f"cmd~/{sig.command_match}/")
    if sig.path_match: parts.append(f"path~/{sig.path_match}/")
    for k, v in sig.input_match.items():
        parts.append(f"{k}~/{v}/")
    return ", ".join(parts) or "<empty-sig>"
