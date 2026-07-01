"""
Global Memory — cross-round accumulation of success/failure tool call patterns.

Persisted to output_rules/<task>/memory.json after each round.
The more rounds accumulate, the more reliable the pattern statistics become.

Structure:
{
  "rounds_accumulated": 3,
  "total_success_traces": 12,
  "total_fail_traces": 8,
  "success_patterns": {
    "<step_id>": {
      "<pattern>": <count_of_traces_containing_this_pattern>
    }
  },
  "success_examples": {
    "<step_id>": {
      "<pattern>": ["example code line 1", ...]
    }
  },
  "failure_patterns": {
    "<step_id>": {
      "error_at_step_count": <how_many_fail_traces_had_error_at_this_step>,
      "patterns": {
        "<pattern>": {
          "count": <traces_with_this_pattern_at_this_step>,
          "also_in_success": <bool>
        }
      }
    }
  }
}
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

MEMORY_FILE = "memory.json"

# Skip overly generic words
_SKIP_TOKENS = {
    "print", "open", "True", "False", "None", "self", "return", "import",
    "from", "with", "else", "pass", "break", "continue", "raise", "yield",
    "range", "list", "dict", "set", "str", "int", "float", "bool", "len",
    "type", "isinstance", "hasattr", "getattr", "setattr", "super", "object",
    "Exception", "ValueError", "KeyError", "IndexError", "TypeError",
    "os.path", "os.environ", "os.getcwd", "sys.argv", "sys.exit",
    "json.loads", "json.dumps", "json.load", "json.dump",
    "Path", "pathlib.Path",
}

# Meaningful keywords — used to identify "key lines"
_KEY_PATTERN = re.compile(
    r'\b([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)+(?:\()?)'
    r'|\b([a-zA-Z_]\w{3,})\s*\('
)


def _extract_patterns(tool: str, command: str | None, content: str | None) -> dict[str, str]:
    """
    Extract meaningful code patterns.
    Returns {pattern_key: example_line}, where:
    - pattern_key is a key API/function call name (used for counting and deduplication)
    - example_line is the full code line containing the call (used for display to LLM)
    """
    text = None
    if tool == "Bash" and command:
        text = command
    elif tool in ("Write", "Edit") and content:
        text = content
    if text is None:
        return {}

    results: dict[str, str] = {}
    lines = text.split("\n")
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped or line_stripped.startswith("#"):
            continue
        # Find key API calls on this line
        for m in _KEY_PATTERN.finditer(line):
            tok = (m.group(1) or m.group(2) or "").rstrip("(").strip()
            if not tok or tok in _SKIP_TOKENS or len(tok) <= 3:
                continue
            # use token as key, code line as example (truncated to reasonable length)
            if tok not in results:
                results[tok] = line_stripped[:120]
    return results


def load(task_out_dir: Path) -> dict[str, Any]:
    """Load memory from disk, or return empty memory."""
    mem_file = task_out_dir / MEMORY_FILE
    if mem_file.exists():
        return json.loads(mem_file.read_text(encoding="utf-8"))
    return {
        "rounds_accumulated": 0,
        "total_success_traces": 0,
        "total_fail_traces": 0,
        "success_patterns": {},
        "success_examples": {},
        "failure_patterns": {},
    }


def save(task_out_dir: Path, memory: dict[str, Any]) -> None:
    task_out_dir.mkdir(parents=True, exist_ok=True)
    (task_out_dir / MEMORY_FILE).write_text(
        json.dumps(memory, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _match_tool_call_to_step(
    tool: str,
    command: str | None,
    content: str | None,
    rules: dict[str, Any],
) -> str | None:
    """
    Reverse-match a tool call to a step using the step's logical_actions regex.
    Returns the stepId of the first matching step, or None if no match.

    This is deterministic and does not depend on LLM step attribution.
    """
    for step in rules.get("steps", []):
        step_id = step.get("stepId")
        for action in step.get("logical_actions", []):
            for sig in action.get("patterns", []):
                if not isinstance(sig, dict):
                    continue
                sig_tool = sig.get("tool")
                if sig_tool and sig_tool != tool:
                    continue
                # Check command_match for Bash
                cmd_pat = sig.get("command_match")
                if cmd_pat and tool == "Bash" and command:
                    try:
                        if re.search(cmd_pat, command):
                            return step_id
                    except re.error:
                        pass
                # Check input_match.content for Write/Edit
                content_pat = (sig.get("input_match") or {}).get("content")
                if content_pat and tool in ("Write", "Edit") and content:
                    try:
                        if re.search(content_pat, content):
                            return step_id
                    except re.error:
                        pass
    return None


def update(
    memory: dict[str, Any],
    traces: list,           # list[TraceData]
    workflow_steps: list[str],
    rules: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Update memory with a new batch of traces.

    Step attribution strategy (in priority order):
    1. Regex reverse-match: match each tool call against step action-pattern regex (deterministic)
    2. structured_summary.steps_executed: LLM-attributed steps (fallback)
    3. Distribute all tokens to all steps (last resort, least accurate)

    Using rules for reverse-match gives accurate per-step token attribution
    instead of assigning all tokens to all steps.
    """
    # Parse step ids from workflow_steps strings like "step_id: label"
    step_ids = [s.split(":")[0].strip() for s in workflow_steps]

    success_traces = [t for t in traces if t.success]
    fail_traces    = [t for t in traces if not t.success]

    memory["rounds_accumulated"] = memory.get("rounds_accumulated", 0) + 1
    memory["total_success_traces"] = memory.get("total_success_traces", 0) + len(success_traces)
    memory["total_fail_traces"]    = memory.get("total_fail_traces", 0) + len(fail_traces)

    sp = memory.setdefault("success_patterns", {})
    fp = memory.setdefault("failure_patterns", {})
    se = memory.setdefault("success_examples", {})  # pattern -> example code line

    has_rules = bool(rules and rules.get("steps"))

    # --- Update success patterns ---
    for trace in success_traces:
        seen_in_trace: set[tuple] = set()

        for tc in trace.parsed.tool_calls:
            patterns = _extract_patterns(tc.tool, tc.command, tc.content_snippet)
            if not patterns:
                continue

            # Strategy 1: regex reverse-match (deterministic, most accurate)
            matched_step = None
            if has_rules:
                matched_step = _match_tool_call_to_step(
                    tc.tool, tc.command, tc.content_snippet, rules)

            # Strategy 2: LLM step attribution from structured summary
            if not matched_step:
                summary = trace.structured_summary or {}
                steps_exec = summary.get("steps_executed", [])
                for s in steps_exec:
                    sid = s.split(":")[0].strip() if ":" in s else s
                    if sid in step_ids:
                        matched_step = sid
                        break

            # Strategy 3: no step_ids available — attribute to "_global" bucket
            # so patterns are not lost (happens during bootstrap with rules={})
            if not matched_step:
                matched_step = "_global"

            step_dict = sp.setdefault(matched_step, {})
            step_ex = se.setdefault(matched_step, {})
            for pat, example_line in patterns.items():
                key = (matched_step, pat)
                if key not in seen_in_trace:
                    step_dict[pat] = step_dict.get(pat, 0) + 1
                    # save up to 3 examples
                    if pat not in step_ex:
                        step_ex[pat] = []
                    if len(step_ex[pat]) < 3 and example_line not in step_ex[pat]:
                        step_ex[pat].append(example_line)
                    seen_in_trace.add(key)

    # --- Update failure patterns ---
    for trace in fail_traces:
        summary = trace.structured_summary or {}
        error_step = summary.get("error_at_step")
        if not error_step:
            missing = trace.eval_result.get("missing_steps", [])
            if missing:
                error_step = missing[0].split(":")[0].strip()

        if not error_step:
            # Fallback: use regex reverse-match on failure tool calls
            if has_rules:
                seen_fail: set[tuple] = set()
                for tc in trace.parsed.tool_calls:
                    patterns = _extract_patterns(tc.tool, tc.command, tc.content_snippet)
                    matched = _match_tool_call_to_step(
                        tc.tool, tc.command, tc.content_snippet, rules)
                    if matched and patterns:
                        step_fp = fp.setdefault(matched, {
                            "error_at_step_count": 0,
                            "patterns": {}
                        })
                        for pat in patterns:
                            if (matched, pat) not in seen_fail:
                                p = step_fp["patterns"].setdefault(
                                    pat, {"count": 0, "also_in_success": False})
                                p["count"] += 1
                                seen_fail.add((matched, pat))
            continue

        # Normalize
        sid = error_step.split(":")[0].strip() if ":" in error_step else error_step

        step_fp = fp.setdefault(sid, {
            "error_at_step_count": 0,
            "patterns": {}
        })
        step_fp["error_at_step_count"] += 1

        # Attribute failure patterns using regex reverse-match first
        seen_fail_tokens: set[tuple] = set()
        for tc in trace.parsed.tool_calls:
            patterns = _extract_patterns(tc.tool, tc.command, tc.content_snippet)
            if not patterns:
                continue
            # Use regex match if available, else attribute to error_step
            matched = None
            if has_rules:
                matched = _match_tool_call_to_step(
                    tc.tool, tc.command, tc.content_snippet, rules)
            target_sid = matched or sid
            target_fp = fp.setdefault(target_sid, {
                "error_at_step_count": 0 if target_sid != sid else step_fp["error_at_step_count"],
                "patterns": {}
            })
            for pat in patterns:
                if (target_sid, pat) not in seen_fail_tokens:
                    p = target_fp["patterns"].setdefault(
                        pat, {"count": 0, "also_in_success": False})
                    p["count"] += 1
                    seen_fail_tokens.add((target_sid, pat))

    # Mark also_in_success for failure patterns
    for sid, step_fp in fp.items():
        success_toks = sp.get(sid, {})
        for tok, pat in step_fp["patterns"].items():
            pat["also_in_success"] = tok in success_toks

    return memory


def get_logical_action_candidates(
    memory: dict[str, Any],
    step_id: str,
    min_freq: int = 2,
) -> list[dict[str, Any]]:
    """
    Return a list of logical-action pattern candidates for a step, with actual code examples.
    Includes patterns from the _global bucket (patterns not step-attributed during bootstrap).
    """
    success_patterns = memory.get("success_patterns", {})
    success_examples = memory.get("success_examples", {})

    step_patterns = dict(success_patterns.get(step_id, {}))
    step_examples = dict(success_examples.get(step_id, {}))
    # Merge _global bucket
    for pat, count in success_patterns.get("_global", {}).items():
        step_patterns[pat] = step_patterns.get(pat, 0) + count
        if pat not in step_examples:
            step_examples[pat] = success_examples.get("_global", {}).get(pat, [])

    candidates = [
        {
            "pattern": pat,
            "count": count,
            "examples": step_examples.get(pat, [])[:2],  # at most 2 examples
        }
        for pat, count in step_patterns.items()
        if count >= min_freq
    ]
    return sorted(candidates, key=lambda x: x["count"], reverse=True)


def get_forbidden_candidates(
    memory: dict[str, Any],
    step_id: str,
    min_fail_count: int = 1,
    max_success_ratio: float = 0.3,
) -> list[dict[str, Any]]:
    """
    Return a list of forbidden pattern candidates for a step.
    A pattern must:
    1. Appear in >= min_fail_count failure traces
    2. success_count / fail_count <= max_success_ratio (appears mainly in failures)
    """
    step_fp = memory.get("failure_patterns", {}).get(step_id, {})
    if not step_fp:
        return []

    success_patterns = memory.get("success_patterns", {}).get(step_id, {})

    candidates = []
    for pat, info in step_fp["patterns"].items():
        fail_count    = info["count"]
        success_count = success_patterns.get(pat, 0)
        ratio = success_count / fail_count if fail_count > 0 else 1.0

        if fail_count >= min_fail_count and ratio <= max_success_ratio:
            candidates.append({
                "pattern": pat,
                "fail_count": fail_count,
                "success_count": success_count,
                "success_ratio": round(ratio, 2),
                "also_in_success": info.get("also_in_success", False),
                "error_at_step_count": step_fp["error_at_step_count"],
            })
    return sorted(candidates, key=lambda x: x["fail_count"], reverse=True)


def format_for_prompt(memory: dict[str, Any], step_ids: list[str]) -> str:
    """Format memory as a readable string for LLM prompts."""
    lines = [
        f"Global memory: {memory.get('rounds_accumulated', 0)} rounds, "
        f"{memory.get('total_success_traces', 0)} success traces, "
        f"{memory.get('total_fail_traces', 0)} fail traces",
        "",
    ]
    for sid in step_ids:
        must_cands = get_logical_action_candidates(memory, sid, min_freq=1)
        forb_cands = get_forbidden_candidates(memory, sid, min_fail_count=1)
        if not must_cands and not forb_cands:
            continue
        lines.append(f"Step '{sid}':")
        if must_cands:
            top = [f"{c['pattern']}({c['count']})" for c in must_cands[:8]]
            lines.append(f"  success patterns: {', '.join(top)}")
        if forb_cands:
            top = [f"{c['pattern']}(fail={c['fail_count']})" for c in forb_cands[:5]]
            lines.append(f"  failure-only patterns: {', '.join(top)}")
    return "\n".join(lines)
