"""
Trace parser — extracts useful signal from a raw JSONL trajectory.

Each line in the JSONL is an event; we only care about:
  - assistant: tool_use in content (tool call parameters) and text (model text)
  - user: tool_result in content (tool return results, mainly Bash stdout)
  - result/success: final result summary (optional)

Discarded: thinking blocks, all ID fields, system/thinking_tokens, system/init, hook_* etc.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolCall:
    tool: str
    command: Optional[str] = None           # Bash command (full, not truncated)
    file_path: Optional[str] = None         # Write / Read / Edit path
    content: Optional[str] = None           # Write/Edit full content
    stdout: Optional[str] = None            # Bash tool_result full output
    tool_use_id: Optional[str] = None       # used to match tool_result

    def to_diagnostic(self, stdout_lines: int = 30) -> str:
        """Generate text for LLM diagnostics, stripping format noise but preserving full content."""
        parts = []
        if self.tool == "Bash":
            cmd = (self.command or "").strip()
            # Skip pure probe commands (short read-only commands like ls, find, cat)
            if re.match(r'^(ls|find|cat|echo|which|pwd)\b', cmd) and len(cmd) < 100:
                return f"[Bash] {cmd[:100]}"
            parts.append(f"[Bash]\n{cmd}")
            if self.stdout:
                lines = self.stdout.strip().split("\n")
                error_lines = [l for l in lines if re.search(
                    r'Error|Exception|Traceback|assert|FAILED|raise|'
                    r'TypeError|ValueError|KeyError|AttributeError', l, re.IGNORECASE)]
                tail = lines[-stdout_lines:]
                shown = (error_lines[:5] + ["..."] if error_lines else []) + tail
                parts.append("stdout:\n" + "\n".join(shown))
        elif self.tool in ("Write", "Edit"):
            parts.append(f"[{self.tool} → {self.file_path}]\n{self.content or ''}")
        elif self.tool == "Read":
            parts.append(f"[Read {self.file_path}]")
        else:
            parts.append(f"[{self.tool}]")
        return "\n".join(parts)

    def to_line(self) -> str:
        """Single-line summary for backward compatibility."""
        if self.tool == "Bash":
            cmd = (self.command or "").strip().replace("\n", " ")
            line = f"Bash: {cmd}"
            if self.stdout:
                out = self.stdout.strip().replace("\n", " | ")
                line += f"\n  → {out[:200]}"
            return line
        if self.tool in ("Write", "Edit"):
            snippet = (self.content or "")[:1000].strip()
            return f"{self.tool}({self.file_path}):\n{snippet}"
        if self.tool == "Read":
            return f"Read: {self.file_path}"
        return self.tool

    # backward-compat property for code that accesses content_snippet
    @property
    def content_snippet(self) -> Optional[str]:
        return (self.content or "")[:1000] if self.content else None

    @property
    def stdout_snippet(self) -> Optional[str]:
        if not self.stdout:
            return None
        return _extract_stdout_snippet(self.stdout)

    @stdout_snippet.setter
    def stdout_snippet(self, value: Optional[str]) -> None:
        # backward compat for code that assigns stdout_snippet directly
        if value is not None:
            self.stdout = value


@dataclass
class HookEvent:
    """A single skillsentry PreToolUse decision recorded in the trace."""
    tool: str
    decision: str        # allow / hint / soft-deny / hard-deny
    layer: str           # L1 / L2 / L3
    matched_step: Optional[str]
    reason: str

    def to_line(self) -> str:
        step = f" [step={self.matched_step}]" if self.matched_step else ""
        return f"  SkillSentry({self.layer},{self.decision}){step}: {self.reason[:120]}"


@dataclass
class ParsedTrace:
    tool_calls: list[ToolCall] = field(default_factory=list)
    hook_events: list[HookEvent] = field(default_factory=list)
    verifier_stdout: Optional[str] = None

    def to_diagnostic_text(self) -> str:
        """
        Generate diagnostic text for LLM reading (TraceFormat re-encoding).
        Strips format noise (thinking, IDs, timestamps) while preserving full behaviour:
        - Verifier output (complete)
        - SkillSentry interventions (complete)
        - Each tool call's full command/code + stdout
        GPT-5.4 has 1M token context — no truncation needed.
        """
        parts = []

        if self.verifier_stdout:
            parts.append("=== Verifier output ===")
            parts.append(self.verifier_stdout[:800])

        # Insert hook events in order of tool calls
        hook_by_idx: dict[int, list[HookEvent]] = {}
        hi = 0
        for ti, tc in enumerate(self.tool_calls):
            while hi < len(self.hook_events) and self.hook_events[hi].tool == tc.tool:
                hook_by_idx.setdefault(ti, []).append(self.hook_events[hi])
                hi += 1

        parts.append("=== Agent trajectory ===")
        for ti, tc in enumerate(self.tool_calls):
            for he in hook_by_idx.get(ti, []):
                if he.decision != "allow":
                    parts.append(he.to_line())
            parts.append(tc.to_diagnostic())

        for he in self.hook_events[hi:]:
            if he.decision != "allow":
                parts.append(he.to_line())

        return "\n\n".join(parts)

    def compact_summary(self, max_calls: int = 0) -> str:
        """Backward-compatible summary."""
        lines = []
        if self.verifier_stdout:
            lines.append("=== Verifier output ===")
            lines.append(self.verifier_stdout[:500])
            lines.append("")

        hook_by_tool_idx: dict[int, list[HookEvent]] = {}
        hi = 0
        for ti, tc in enumerate(self.tool_calls):
            while hi < len(self.hook_events) and self.hook_events[hi].tool == tc.tool:
                hook_by_tool_idx.setdefault(ti, []).append(self.hook_events[hi])
                hi += 1

        calls_to_show = (self.tool_calls if max_calls == 0
                         else self.tool_calls[:max_calls])
        lines.append("=== Agent actions ===")
        for ti, tc in enumerate(calls_to_show):
            lines.append(tc.to_line())
            for he in hook_by_tool_idx.get(ti, []):
                lines.append(he.to_line())

        if max_calls > 0 and len(self.tool_calls) > max_calls:
            lines.append(f"  ... ({len(self.tool_calls) - max_calls} more tool calls)")

        for he in self.hook_events[hi:]:
            lines.append(he.to_line())

        return "\n".join(lines)

    @property
    def has_skillsentry_interventions(self) -> bool:
        return any(he.decision != "allow" for he in self.hook_events)

    @property
    def denied_steps(self) -> list[str]:
        return [he.matched_step for he in self.hook_events
                if he.decision in ("soft-deny", "hard-deny") and he.matched_step]

    @property
    def hinted_steps(self) -> list[str]:
        return [he.matched_step for he in self.hook_events
                if he.decision == "hint" and he.matched_step]


def _extract_stdout_snippet(text: str) -> Optional[str]:
    """
    Extract the most diagnostic lines from Bash stdout:
    - Error messages (Traceback, Error, Exception, assert)
    - Last few lines with numeric results
    - Keep under 300 chars total
    """
    if not text or not text.strip():
        return None

    lines = text.strip().split("\n")

    # Collect error lines
    error_lines = [l for l in lines if re.search(
        r'Error|Exception|Traceback|assert|FAILED|raise|TypeError|ValueError|'
        r'KeyError|IndexError|AttributeError', l, re.IGNORECASE)]

    # Collect lines with numbers (likely results)
    result_lines = [l for l in lines[-10:] if re.search(r'\d+\.\d+|\d{4,}', l)]

    selected = []
    if error_lines:
        selected.extend(error_lines[:3])
    if result_lines and not error_lines:
        selected.extend(result_lines[-3:])
    if not selected:
        # Fall back to last 3 lines
        selected = lines[-3:]

    snippet = "\n".join(selected)
    return snippet[:300] if snippet.strip() else None


def parse_trajectory(trajectory_jsonl: str) -> ParsedTrace:
    """
    Extract diagnostically useful content from a JSONL trajectory.

    Only processes:
    - assistant: tool_use (tool call parameters, fully preserved)
    - user: tool_result (tool return results, Bash stdout fully preserved)

    Discarded: thinking blocks, system/* noise lines, all ID and timestamp fields.
    """
    result = ParsedTrace()
    lines = [l for l in trajectory_jsonl.strip().split("\n") if l.strip()]

    pending: dict[str, ToolCall] = {}  # tool_use_id → ToolCall

    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        etype = entry.get("type", "")

        if etype == "assistant":
            msg = entry.get("message", {})
            for item in msg.get("content", []):
                if not isinstance(item, dict):
                    continue
                # Only take tool_use, skip thinking and text
                if item.get("type") != "tool_use":
                    continue
                tc = _parse_tool_use(item)
                if tc:
                    result.tool_calls.append(tc)
                    if tc.tool_use_id:
                        pending[tc.tool_use_id] = tc

        elif etype == "user":
            msg = entry.get("message", {})
            content = msg.get("content", []) if isinstance(msg, dict) else []
            if not isinstance(content, list):
                continue
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "tool_result":
                    uid = item.get("tool_use_id", "")
                    tc = pending.get(uid)
                    if tc and tc.tool == "Bash":
                        rc = item.get("content", "")
                        text = (rc if isinstance(rc, str)
                                else "".join(x.get("text", "") for x in rc
                                             if isinstance(x, dict)))
                        tc.stdout = text  # fully preserved; filtered in to_diagnostic()

                    # skillsentry hook output
                    he = _extract_hook_from_tool_result(item)
                    if he:
                        result.hook_events.append(he)

                if item.get("type") == "text":
                    he = _extract_hook_from_text(item.get("text", ""))
                    if he:
                        result.hook_events.append(he)

    return result


def parse_skillsentry_log(log_text: str) -> list[HookEvent]:
    """Parse SKILLSENTRY_LOG file (one JSON per line)."""
    events = []
    for line in log_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("event") != "pretool_decision":
            continue
        events.append(HookEvent(
            tool=rec.get("tool", ""),
            decision=rec.get("kind", "allow"),
            layer=rec.get("layer", ""),
            matched_step=rec.get("step"),
            reason=rec.get("reason", ""),
        ))
    return events


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_tool_use(item: dict) -> Optional[ToolCall]:
    tool = item.get("name", "")
    inp = item.get("input", {}) or {}
    tc = ToolCall(tool=tool, tool_use_id=item.get("id", ""))
    if tool == "Bash":
        tc.command = inp.get("command", "")  # fully preserved, not truncated
    elif tool in ("Write", "Edit", "NotebookEdit"):
        tc.file_path = inp.get("file_path", inp.get("path", ""))
        content = inp.get("content", inp.get("new_string", ""))
        if content:
            tc.content = str(content)  # fully preserved
    elif tool == "Read":
        tc.file_path = inp.get("file_path", inp.get("path", ""))
    else:
        return None  # skip tools with no diagnostic value (Skill, Task*, etc.)
    return tc


def _extract_hook_from_tool_result(item: dict) -> Optional[HookEvent]:
    rc = item.get("content", "")
    text = (rc if isinstance(rc, str)
            else " ".join(x.get("text", "") for x in rc if isinstance(x, dict)))
    m = re.search(r'\{[^{}]*"hookSpecificOutput"[^{}]*\}', text)
    if m:
        try:
            obj = json.loads(m.group(0))
            hso = obj.get("hookSpecificOutput", {})
            decision_map = {"allow": "allow", "ask": "soft-deny", "deny": "hard-deny"}
            decision = decision_map.get(hso.get("permissionDecision", "allow"), "allow")
            reason = hso.get("permissionDecisionReason") or hso.get("additionalContext", "")
            if decision != "allow" or reason:
                return HookEvent(tool="", decision=decision, layer="hook",
                                 matched_step=None, reason=reason)
        except (json.JSONDecodeError, KeyError):
            pass
    return None


def _extract_hook_from_text(text: str) -> Optional[HookEvent]:
    keywords = ["skillsentry", "workflow", "deviat", "step requires", "action pattern",
                "forbidden", "order violation", "next_actionable"]
    if any(k in text.lower() for k in keywords):
        return HookEvent(tool="", decision="hint", layer="injected",
                         matched_step=None, reason=text[:200])
    return None
