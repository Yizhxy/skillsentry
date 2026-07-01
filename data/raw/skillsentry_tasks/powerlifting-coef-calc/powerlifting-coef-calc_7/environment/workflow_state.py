#!/usr/bin/env python3
"""
WorkflowState - Lightweight stateful workflow tracker for Claude Code hooks.

Each PreToolUse hook invocation is a fresh process, so state is persisted to a
JSON file. This module loads that file, checks the incoming action, updates
state, and writes it back — all in one call to check_action().

Intentionally avoids heavy dependencies (no sentence-transformers) so that the
hook starts in <200ms. Phase matching uses keyword-based heuristics derived from
the workflow spec, falling back to the full SWT embedding if SWAG_USE_EMBEDDINGS=1.
"""

import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Lightweight phase matcher (no ML dependency for fast hook startup)
# ---------------------------------------------------------------------------

def _keywords_from_step(step_text: str) -> List[str]:
    """Extract lowercase keywords from a workflow step description."""
    # Remove common stopwords and punctuation
    text = re.sub(r'[^\w\s]', ' ', step_text.lower())
    stopwords = {'the', 'a', 'an', 'and', 'or', 'to', 'in', 'for', 'of',
                 'with', 'by', 'from', 'on', 'at', 'is', 'are', 'be', 'as',
                 'all', 'any', 'that', 'this', 'step', 'phase', 'using',
                 'use', 'via', 'into'}
    return [w for w in text.split() if w not in stopwords and len(w) > 2]


TOOL_PHASE_HINTS: Dict[str, List[str]] = {
    # search / discovery
    'WebSearch': ['search', 'discover', 'find', 'lookup', 'query', 'fetch', 'pubmed', 'scholar'],
    'WebFetch':  ['fetch', 'download', 'retrieve', 'get', 'extract', 'scrape'],
    # file I/O
    'Read':      ['read', 'load', 'open', 'parse', 'check', 'verify', 'validate'],
    'Write':     ['write', 'save', 'generate', 'output', 'format', 'create', 'produce'],
    'Edit':      ['edit', 'modify', 'update', 'transform', 'convert', 'clean', 'correct'],
    # execution
    'Bash':      ['run', 'execute', 'apply', 'compute', 'calculate', 'analyze', 'process',
                  'install', 'build', 'compile', 'filter', 'deflate'],
    'Task':      ['plan', 'organize', 'coordinate', 'manage', 'schedule'],
}


def _score_action_against_step(tool_name: str, tool_input: Dict, step_text: str) -> float:
    """
    Heuristic relevance score ∈ [0, 1] between a tool call and a step description.
    Higher = more likely this action belongs to that step.
    """
    step_kws = set(_keywords_from_step(step_text))
    if not step_kws:
        return 0.0

    hits = 0

    # Tool-based hints
    tool_hints = TOOL_PHASE_HINTS.get(tool_name, [])
    for hint in tool_hints:
        if hint in step_kws:
            hits += 2  # double weight for tool-name match

    # Input text match: flatten all string values from tool_input
    input_text = ' '.join(
        str(v).lower()
        for v in _flatten_values(tool_input)
        if isinstance(v, (str, int, float))
    )
    for kw in step_kws:
        if kw in input_text:
            hits += 1

    max_possible = 2 * len(tool_hints) + len(step_kws)
    return hits / max_possible if max_possible > 0 else 0.0


def _flatten_values(obj, depth=3):
    """Recursively yield leaf values from nested dicts/lists."""
    if depth == 0:
        return
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _flatten_values(v, depth - 1)
    elif isinstance(obj, list):
        for v in obj:
            yield from _flatten_values(v, depth - 1)
    else:
        yield obj


# ---------------------------------------------------------------------------
# WorkflowState
# ---------------------------------------------------------------------------

class WorkflowState:
    """
    Stateful workflow enforcement logic suitable for hook invocations.

    Usage (per hook call):
        state = WorkflowState.load(spec_file, state_file)
        result = state.check_action(tool_name, tool_input)
        state.save(state_file)
        return result  # {"allow": True} or {"allow": False, "reason": "..."}
    """

    def __init__(self, workflow_spec: Dict, persistent: Dict):
        self.spec = workflow_spec
        self.steps: List[Dict] = workflow_spec.get('steps', [])
        self.step_ids: List[str] = [
            s.get('id', s.get('name', f'step_{i}'))
            for i, s in enumerate(self.steps)
        ]
        self.step_texts: List[str] = [
            s.get('description', s.get('name', ''))
            for s in self.steps
        ]

        # persistent state (loaded from / saved to JSON file)
        self._p = persistent  # dict with keys: completed, action_count, violations
        self._p.setdefault('completed', [])       # list of completed step IDs
        self._p.setdefault('action_count', 0)
        self._p.setdefault('violations', 0)
        self._p.setdefault('action_log', [])

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, spec_file: str, state_file: str) -> 'WorkflowState':
        with open(spec_file) as f:
            spec = json.load(f)

        if os.path.exists(state_file):
            try:
                with open(state_file) as f:
                    persistent = json.load(f)
            except Exception:
                persistent = {}
        else:
            persistent = {}

        return cls(spec, persistent)

    def save(self, state_file: str):
        with open(state_file, 'w') as f:
            json.dump(self._p, f, indent=2)

    # ------------------------------------------------------------------
    # Core check
    # ------------------------------------------------------------------

    def check_action(self, tool_name: str, tool_input: Dict) -> Dict:
        """
        Decide whether to allow or block this tool call.

        Returns:
            {"allow": True}
            {"allow": False, "reason": "<enforcement message>"}
        """
        self._p['action_count'] += 1

        # 1. Identify which workflow step this action most likely belongs to
        traced_step_idx = self._trace(tool_name, tool_input)

        # 2. Log action
        self._p['action_log'].append({
            'ts': time.time(),
            'tool': tool_name,
            'traced_idx': traced_step_idx,
        })

        # 3. If no step matched, allow (non-workflow tool call)
        if traced_step_idx is None:
            return {"allow": True}

        traced_id = self.step_ids[traced_step_idx]

        # 4. Check ordering: all predecessors must be completed
        missing_predecessors = self._missing_predecessors(traced_step_idx)

        if missing_predecessors:
            self._p['violations'] += 1
            reason = self._format_enforcement_message(traced_id, missing_predecessors)
            return {"allow": False, "reason": reason}

        # 5. Action is allowed — mark step as completed (incremental)
        if traced_id not in self._p['completed']:
            self._p['completed'].append(traced_id)

        return {"allow": True}

    # ------------------------------------------------------------------
    # Completion check (called at task end by PostToolUse or explicit check)
    # ------------------------------------------------------------------

    def check_completion(self) -> Dict:
        missing = [sid for sid in self.step_ids if sid not in self._p['completed']]
        return {
            "complete": len(missing) == 0,
            "completed": list(self._p['completed']),
            "missing": missing,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _trace(self, tool_name: str, tool_input: Dict) -> Optional[int]:
        """Return the index of the best-matching workflow step, or None."""
        scores = [
            _score_action_against_step(tool_name, tool_input, text)
            for text in self.step_texts
        ]
        best_idx = max(range(len(scores)), key=lambda i: scores[i])
        best_score = scores[best_idx]

        # Only claim a match if score is meaningful
        threshold = float(os.environ.get('SWAG_MATCH_THRESHOLD', '0.05'))
        if best_score < threshold:
            return None

        return best_idx

    def _missing_predecessors(self, step_idx: int) -> List[str]:
        """
        Return step IDs of predecessors (steps with index < step_idx) that have
        not yet been completed, according to the dependency rules.
        """
        completed_set = set(self._p['completed'])
        missing = []

        step_data = self.steps[step_idx]
        # Explicit dependencies take priority
        explicit_deps = step_data.get('dependencies', [])

        if explicit_deps:
            for dep in explicit_deps:
                if dep not in completed_set:
                    missing.append(dep)
        else:
            # Fall back to strict sequential ordering
            for i in range(step_idx):
                sid = self.step_ids[i]
                if sid not in completed_set:
                    missing.append(sid)

        return missing

    def _format_enforcement_message(self, target_step: str, missing: List[str]) -> str:
        lines = [
            "[WORKFLOW ENFORCEMENT]",
            "",
            f"You are attempting to execute: {target_step}",
            "However, the following prerequisite steps have not been completed:",
            "",
        ]
        for sid in missing:
            idx = self.step_ids.index(sid) if sid in self.step_ids else -1
            desc = self.step_texts[idx] if idx >= 0 else sid
            lines.append(f"  • {sid}: {desc}")

        lines += [
            "",
            "You MUST complete the missing steps in order before proceeding.",
            f"Your next action should address: {missing[0]}",
        ]
        return "\n".join(lines)
