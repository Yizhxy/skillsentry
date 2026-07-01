"""Skill Specification Extraction (paper §III-B).

An LLM-based parser transforms a skill document (SKILL.md) into the specification
fields of the DSL — steps (stepId, description), depends_on, constraints, and
termination — leaving the experience fields (logical_actions, failure_patterns,
on_enter) empty for the Execution Experience Miner (§III-C) to populate.

The extracted specification is checked by lightweight structural validation
(unique stepIds, valid depends_on references, an acyclic dependency graph,
well-typed constraints, termination ⊆ steps). If validation fails, the errors are
returned to the parser to revise, bounded by MAX_PARSE_ATTEMPTS.
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

import utils.llm as llm

MAX_PARSE_ATTEMPTS = int(os.environ.get("SKILLSENTRY_MAX_PARSE_ATTEMPTS", "3"))


# ---------------------------------------------------------------------------
# SKILL.md structural aid / fallback
# ---------------------------------------------------------------------------

def extract_steps_from_skill_md(skill_md: str) -> list[dict]:
    """Extract a linear step skeleton from the headings of SKILL.md.

    Used as a structural aid / fallback when the parser returns too few steps.
    """
    steps: list[dict] = []
    prev_id = None
    for line in skill_md.split("\n"):
        m = re.match(r'^(?:Step\s+\d+|##?\s+\d+)[:\.\s]+(.+)$', line.strip(), re.IGNORECASE)
        if not m:
            continue
        label = m.group(1).strip()
        sid = re.sub(r'[^a-z0-9]+', '_', label.lower()).strip('_')[:30]
        steps.append({
            "stepId": sid,
            "description": label,
            "depends_on": [prev_id] if prev_id else [],
            "constraints": [],
        })
        prev_id = sid
    return steps


# ---------------------------------------------------------------------------
# Structural validation
# ---------------------------------------------------------------------------

def validate_spec(spec: dict[str, Any]) -> list[str]:
    """Structural validation of an extracted skill specification (paper §III-B).

    Checks: unique stepIds; every depends_on reference exists; the dependency
    graph is acyclic; constraints are well-typed; termination references only
    defined steps and is non-empty.
    """
    errors: list[str] = []
    steps = spec.get("steps") or []
    if not steps:
        errors.append("no steps extracted")
        return errors

    ids: list[str] = []
    for i, s in enumerate(steps):
        sid = s.get("stepId")
        if not sid:
            errors.append(f"steps[{i}]: missing stepId")
            continue
        if sid in ids:
            errors.append(f"duplicate stepId '{sid}'")
        ids.append(sid)
    idset = set(ids)

    # depends_on references
    for s in steps:
        for d in s.get("depends_on") or []:
            if d not in idset:
                errors.append(f"step '{s.get('stepId')}': depends_on references unknown step '{d}'")

    # acyclic dependency graph (DFS with colouring)
    graph = {s.get("stepId"): [d for d in (s.get("depends_on") or []) if d in idset]
             for s in steps if s.get("stepId")}
    WHITE, GREY, BLACK = 0, 1, 2
    color = {sid: WHITE for sid in graph}

    def _has_cycle(u: str) -> bool:
        color[u] = GREY
        for v in graph.get(u, []):
            if color.get(v) == GREY:
                return True
            if color.get(v) == WHITE and _has_cycle(v):
                return True
        color[u] = BLACK
        return False

    for sid in graph:
        if color[sid] == WHITE and _has_cycle(sid):
            errors.append("dependency graph has a cycle")
            break

    # constraints well-typed
    for s in steps:
        for j, c in enumerate(s.get("constraints") or []):
            if not isinstance(c, dict):
                errors.append(f"step '{s.get('stepId')}': constraint[{j}] is not an object")
                continue
            has_tool = bool(c.get("tool"))
            has_param = bool(c.get("parameter")) and bool(c.get("requirement"))
            if not (has_tool or has_param):
                errors.append(
                    f"step '{s.get('stepId')}': constraint[{j}] must be a tool constraint "
                    f"or a parameter+requirement constraint")

    # termination
    termination = spec.get("termination") or []
    if not termination:
        errors.append("termination is empty")
    for t in termination:
        if t not in idset:
            errors.append(f"termination references unknown step '{t}'")

    return errors


# ---------------------------------------------------------------------------
# Extraction (parse → validate → revise loop)
# ---------------------------------------------------------------------------

def _empty_experience_fields(step: dict) -> dict:
    """Leave the experience fields empty; they are populated by the miner."""
    step.setdefault("constraints", [])
    step["logical_actions"] = []
    step["failure_patterns"] = []
    step["on_enter"] = {"suggestions": [], "warnings": []}
    return step


def extract_skill_spec(skill_md: str, skill_name: str) -> dict[str, Any]:
    """Parse SKILL.md into a validated skill specification (paper §III-B).

    Returns a rules.json-shaped dict whose steps carry the specification fields and
    EMPTY experience fields (logical_actions / failure_patterns / on_enter).
    """
    excerpt = skill_md[:3000] if skill_md else "(not available)"
    md_steps = extract_steps_from_skill_md(skill_md)

    spec: dict[str, Any] = {}
    errors: list[str] = []
    for attempt in range(MAX_PARSE_ATTEMPTS):
        try:
            sp = llm.sp_with_dsl("skill_spec_extraction_sp")
            up = llm.up(
                "skill_spec_extraction_up",
                skill_name=skill_name,
                skill_md=excerpt,
                validation_errors=("\n".join(f"- {e}" for e in errors) if errors else "none"),
            )
            raw = llm.call(
                [{"role": "system", "content": sp}, {"role": "user", "content": up}],
                temperature=0.1, json_mode=True,
            )
            spec = json.loads(raw)
        except Exception as e:  # noqa: BLE001 — fail-soft; fall back to SKILL.md skeleton
            print(f"  [spec] attempt {attempt + 1} extraction failed: {e}", file=sys.stderr)
            spec = {}

        # Fallback: if the parser produced too few steps, rebuild the skeleton from SKILL.md.
        if md_steps and len(spec.get("steps") or []) < max(2, len(md_steps) // 2):
            spec["steps"] = [dict(s) for s in md_steps]
            spec.setdefault("termination", [s["stepId"] for s in md_steps])

        spec.setdefault("skill", skill_name)
        for s in spec.get("steps") or []:
            _empty_experience_fields(s)

        errors = validate_spec(spec)
        if not errors:
            return spec
        print(f"  [spec] attempt {attempt + 1}: {len(errors)} structural error(s), revising",
              file=sys.stderr)

    print(f"  [spec] returning best-effort specification with {len(errors)} residual error(s)",
          file=sys.stderr)
    return spec
