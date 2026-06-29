"""
Pattern Mining — derives must_call and forbidden candidates from global memory.

Key design:
- must_call candidates: from global SUCCESS patterns (high-frequency tokens)
- forbidden candidates: from global FAILURE patterns (error-attributed, not in success)

Both are passed to Stage 3 as structured candidates.
LLM's job in Stage 3:
  - must_call: select and combine tokens into regex, verify SKILL.md alignment
  - forbidden: write reason text, judge if it's root cause vs side effect
  - on_enter: derive hints from success/failure contrast
"""
from __future__ import annotations

from typing import Any

import config
from utils import memory as mem_module
from utils.task_helpers import TraceData


def mine_current_round(
    success_traces: list[TraceData],
    min_freq: int = config.PATTERN_MIN_FREQ,
) -> list[dict[str, Any]]:
    """
    Quick per-round pattern mining (used for Stage 0 display and 2x2 matrix).
    Returns high-frequency tokens from current round's success traces only.
    """
    from collections import Counter, defaultdict
    import re

    # Generic patterns — same logic as memory._extract_tokens
    _RE = re.compile(
        r'\b([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)+(?:\()?)'
        r'|\b([a-zA-Z_]\w{3,})\s*\('
    )
    _SKIP = {
        "print", "open", "True", "False", "None", "self", "return", "import",
        "from", "with", "else", "pass", "break", "continue", "raise",
        "range", "list", "dict", "str", "int", "float", "bool", "len",
        "isinstance", "hasattr", "getattr", "super", "object",
        "json.loads", "json.dumps", "json.load", "json.dump",
    }

    def _tokens(tool: str, command: str | None, content: str | None) -> set[str]:
        text = command if tool == "Bash" else (content if tool in ("Write", "Edit") else None)
        if not text:
            return set()
        result = set()
        for m in _RE.finditer(text):
            tok = (m.group(1) or m.group(2) or "").rstrip("(").strip()
            if tok and tok not in _SKIP and len(tok) > 3:
                result.add(tok)
        return result

    pattern_counts: Counter = Counter()
    pattern_examples: dict[str, list[str]] = defaultdict(list)
    n = len(success_traces)

    for trace in success_traces:
        seen: set[str] = set()
        for tc in trace.parsed.tool_calls:
            tokens = _tokens(tc.tool, tc.command, tc.content_snippet)
            for tok in tokens:
                key = f"{tc.tool}::{tok}"
                if key not in seen:
                    pattern_counts[key] += 1
                    seen.add(key)
                    if len(pattern_examples[key]) < 3:
                        src = tc.command or tc.content_snippet or ""
                        pattern_examples[key].append(src[:80])

    results = []
    for key, count in pattern_counts.most_common():
        if count < min_freq:
            break
        tool, pattern = key.split("::", 1)
        results.append({
            "tool": tool,
            "pattern": pattern,
            "frequency": count,
            "total_traces": n,
            "examples": pattern_examples[key],
        })
    return results


def derive_candidates(
    memory: dict[str, Any],
    workflow_steps: list[str],
    min_must_call_freq: int = 2,
    min_forbidden_freq: int = 2,
) -> dict[str, Any]:
    """
    Derive structured must_call and forbidden candidates from global memory.

    Returns:
    {
      "must_call_candidates": {
        "<step_id>": [{"token": "...", "count": N}, ...]
      },
      "forbidden_candidates": {
        "<step_id>": [{"token": "...", "fail_count": N, "error_at_step_count": M}, ...]
      },
      "summary": "human-readable summary for LLM"
    }
    """
    step_ids = [s.split(":")[0].strip() for s in workflow_steps]

    must_call_candidates: dict[str, list] = {}
    forbidden_candidates: dict[str, list] = {}

    if step_ids:
        for sid in step_ids:
            mc = mem_module.get_must_call_candidates(memory, sid, min_freq=min_must_call_freq)
            if mc:
                must_call_candidates[sid] = mc

            fb = mem_module.get_forbidden_candidates(
                memory, sid,
                min_fail_count=1,
                max_success_ratio=0.3,
            )
            if fb:
                forbidden_candidates[sid] = fb
    else:
        # During bootstrap, step_ids is empty; use the _global bucket directly
        mc = mem_module.get_must_call_candidates(memory, "_global", min_freq=1)
        if mc:
            must_call_candidates["_global"] = mc
        fb = mem_module.get_forbidden_candidates(memory, "_global", min_fail_count=1, max_success_ratio=0.3)
        if fb:
            forbidden_candidates["_global"] = fb

    return {
        "must_call_candidates": must_call_candidates,
        "forbidden_candidates": forbidden_candidates,
        "memory_summary": mem_module.format_for_prompt(memory, step_ids),
        "rounds_accumulated": memory.get("rounds_accumulated", 0),
        "total_success_traces": memory.get("total_success_traces", 0),
        "total_fail_traces": memory.get("total_fail_traces", 0),
    }
