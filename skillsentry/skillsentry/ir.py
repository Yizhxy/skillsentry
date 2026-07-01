"""Workflow IR — load rules.json, resolve a skill name to its rules file.

DSL field mapping (rules.json → internal), following the DSL in the paper (Fig. 4):
  stepId          → step.step_id
  description     → step.description
  depends_on      → step.depends_on
  constraints     → step.constraints   (list of ToolConstraint / ParameterConstraint)
  logical_actions → step.logical_actions  (list of LogicalAction with action patterns)
  failure_patterns→ step.failure_patterns (list of Signature with reason)
  on_enter        → step.on_enter     ({suggestions: [...], warnings: [...]})
  termination     → ir.termination    (list of stepId strings)
"""
from __future__ import annotations

import json
import os
import pathlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Signature (action pattern)
# ---------------------------------------------------------------------------

@dataclass
class Signature:
    tool: Optional[str] = None
    command_match: Optional[str] = None
    path_match: Optional[str] = None
    input_match: Dict[str, str] = field(default_factory=dict)
    reason: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Signature":
        return cls(
            tool=d.get("tool"),
            command_match=d.get("command_match"),
            path_match=d.get("path_match"),
            input_match=dict(d.get("input_match") or {}),
            reason=d.get("reason"),
        )

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        if self.tool:          out["tool"] = self.tool
        if self.command_match: out["command_match"] = self.command_match
        if self.path_match:    out["path_match"] = self.path_match
        if self.input_match:   out["input_match"] = dict(self.input_match)
        if self.reason:        out["reason"] = self.reason
        return out


# ---------------------------------------------------------------------------
# LogicalAction  (one logical action = one or more alternative patterns)
# ---------------------------------------------------------------------------

@dataclass
class LogicalAction:
    action_id: int = 0
    patterns: List[Signature] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LogicalAction":
        return cls(
            action_id=int(d.get("actionId", 0)),
            patterns=[Signature.from_dict(p) for p in d.get("patterns", [])],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actionId": self.action_id,
            "patterns": [p.to_dict() for p in self.patterns],
        }


# ---------------------------------------------------------------------------
# Constraint  (tool or parameter constraint, extracted from SKILL.md)
# ---------------------------------------------------------------------------

@dataclass
class Constraint:
    tool: Optional[str] = None          # ToolConstraint
    parameter: Optional[str] = None    # ParameterConstraint
    requirement: Optional[str] = None  # ParameterConstraint requirement text

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Constraint":
        return cls(
            tool=d.get("tool"),
            parameter=d.get("parameter"),
            requirement=d.get("requirement"),
        )

    def to_hint(self) -> str:
        """Format as a human-readable hint for on_enter injection."""
        if self.tool:
            return f"Use {self.tool} for this step."
        if self.parameter and self.requirement:
            return f"Parameter '{self.parameter}': {self.requirement}"
        return ""


# ---------------------------------------------------------------------------
# Step
# ---------------------------------------------------------------------------

@dataclass
class Step:
    step_id: str
    description: str = ""
    depends_on: List[str] = field(default_factory=list)
    constraints: List[Constraint] = field(default_factory=list)
    logical_actions: List[LogicalAction] = field(default_factory=list)
    failure_patterns: List[Signature] = field(default_factory=list)
    on_enter: Optional[Dict[str, Any]] = None

    # -- convenience properties for FSM / layers that still need flat lists --

    @property
    def action_patterns(self) -> List[Signature]:
        """Flat list of all action patterns across this step's logical_actions."""
        out: List[Signature] = []
        for la in self.logical_actions:
            out.extend(la.patterns)
        return out

    @property
    def forbidden(self) -> List[Signature]:
        return self.failure_patterns

    @property
    def requires(self) -> List[str]:
        return self.depends_on

    # For backward-compat with layers/fsm code that reads step.id / step.label
    @property
    def id(self) -> str:
        return self.step_id

    @property
    def label(self) -> str:
        return self.description

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Step":
        step_id = d.get("stepId", "")
        description = d.get("description", "")
        depends_on = list(d.get("depends_on") or [])
        constraints = [Constraint.from_dict(c) for c in (d.get("constraints") or [])]
        logical_actions = [LogicalAction.from_dict(la) for la in (d.get("logical_actions") or [])]
        failure_patterns = [Signature.from_dict(x) for x in (d.get("failure_patterns") or [])]
        on_enter = d.get("on_enter")

        return cls(
            step_id=step_id,
            description=description,
            depends_on=depends_on,
            constraints=constraints,
            logical_actions=logical_actions,
            failure_patterns=failure_patterns,
            on_enter=on_enter,
        )


# ---------------------------------------------------------------------------
# Global rules (unchanged from v1)
# ---------------------------------------------------------------------------

@dataclass
class GlobalRules:
    forbidden_tools: List[str] = field(default_factory=list)
    forbidden_bash: List[str] = field(default_factory=list)
    forbidden_paths: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GlobalRules":
        return cls(
            forbidden_tools=list(d.get("forbidden_tools", [])),
            forbidden_bash=list(d.get("forbidden_bash", [])),
            forbidden_paths=list(d.get("forbidden_paths", [])),
        )


# ---------------------------------------------------------------------------
# Completion / Termination
# ---------------------------------------------------------------------------

@dataclass
class CompletionAssertion:
    """Completion check derived from the DSL `termination` field.

    A step is "completed" once all of its logical_actions have been matched
    (paper §III-D); `termination` lists the stepIds that must be completed
    before the final output is accepted. The completion signature for a step
    is '<stepId>.completed'.
    """
    required_step_ids: List[str] = field(default_factory=list)

    @property
    def required_signatures(self) -> List[str]:
        return [f"{sid}.completed" for sid in self.required_step_ids]

    @classmethod
    def from_termination(cls, termination: List[str]) -> "CompletionAssertion":
        return cls(required_step_ids=list(termination))


# ---------------------------------------------------------------------------
# IR  (top-level runtime guidance object)
# ---------------------------------------------------------------------------

@dataclass
class IR:
    skill: str
    steps: List[Step] = field(default_factory=list)
    global_rules: GlobalRules = field(default_factory=GlobalRules)
    completion: CompletionAssertion = field(default_factory=CompletionAssertion)
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "IR":
        steps = [Step.from_dict(s) for s in d.get("steps", [])]

        if "termination" in d:
            completion = CompletionAssertion.from_termination(d["termination"])
        else:
            # Default: every step must be completed.
            completion = CompletionAssertion.from_termination([s.step_id for s in steps])

        return cls(
            skill=d.get("skill", ""),
            steps=steps,
            global_rules=GlobalRules.from_dict(d.get("global", {}) or {}),
            completion=completion,
            raw=d,
        )

    def step_by_id(self, sid: str) -> Optional[Step]:
        for s in self.steps:
            if s.step_id == sid:
                return s
        return None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

VALID_SIGNATURE_KEYS = {"tool", "command_match", "path_match", "input_match", "reason"}
VALID_STEP_KEYS = {
    "stepId", "description", "depends_on", "constraints",
    "logical_actions", "failure_patterns", "on_enter",
}
VALID_GLOBAL_KEYS = {"forbidden_tools", "forbidden_bash", "forbidden_paths"}
VALID_TOP_KEYS = {
    "skill", "version", "steps", "global", "termination",
}


def validate_ir(d: Dict[str, Any]) -> List[str]:
    """Return a list of warnings about the raw rules.json dict (fail-open)."""
    warnings: List[str] = []

    if not isinstance(d, dict):
        warnings.append("rules.json must be a JSON object")
        return warnings

    unknown_top = set(d.keys()) - VALID_TOP_KEYS
    if unknown_top:
        warnings.append(f"unknown top-level keys: {sorted(unknown_top)}")
    if not d.get("skill"):
        warnings.append("missing or empty 'skill' field")
    if "steps" not in d:
        warnings.append("missing 'steps' field (an empty list is valid)")

    seen_ids: set = set()
    for i, step in enumerate(d.get("steps") or []):
        if not isinstance(step, dict):
            warnings.append(f"steps[{i}]: not a JSON object")
            continue
        unknown = set(step.keys()) - VALID_STEP_KEYS
        if unknown:
            warnings.append(f"steps[{i}]: unknown keys {sorted(unknown)}")

        sid = step.get("stepId")
        if not sid:
            warnings.append(f"steps[{i}]: missing 'stepId'")
            continue
        if sid in seen_ids:
            warnings.append(f"steps[{i}]: duplicate stepId '{sid}'")
        seen_ids.add(sid)

        # Validate logical_actions patterns
        for j, la in enumerate(step.get("logical_actions") or []):
            for k, sig in enumerate(la.get("patterns") or []):
                if not isinstance(sig, dict):
                    warnings.append(f"steps[{i}].logical_actions[{j}].patterns[{k}]: not a dict")
                    continue
                u = set(sig.keys()) - VALID_SIGNATURE_KEYS
                if u:
                    warnings.append(f"steps[{i}].logical_actions[{j}].patterns[{k}]: unknown keys {sorted(u)}")

        # Validate failure_patterns signatures
        for j, sig in enumerate(step.get("failure_patterns") or []):
            if not isinstance(sig, dict):
                warnings.append(f"steps[{i}].failure_patterns[{j}]: not a JSON object")
                continue
            u = set(sig.keys()) - VALID_SIGNATURE_KEYS
            if u:
                warnings.append(f"steps[{i}].failure_patterns[{j}]: unknown signature keys {sorted(u)}")

    # Validate depends_on references
    for i, step in enumerate(d.get("steps") or []):
        if not isinstance(step, dict):
            continue
        deps = step.get("depends_on") or []
        for j, r in enumerate(deps):
            if r not in seen_ids:
                warnings.append(f"steps[{i}].depends_on[{j}]: references unknown stepId '{r}'")

    # Validate termination references
    for ref in d.get("termination") or []:
        if ref not in seen_ids:
            warnings.append(f"termination: references unknown stepId '{ref}'")

    return warnings


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_rules_file(path: pathlib.Path) -> "IR":
    raw = json.loads(path.read_text(encoding="utf-8"))
    return IR.from_dict(raw)


def load_rules_file_validated(path: pathlib.Path) -> Tuple["IR", List[str]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return IR.from_dict(raw), validate_ir(raw)


def find_rules_for_skill(skill_name: str, cwd: Optional[str] = None) -> Optional[pathlib.Path]:
    """Search standard locations for a skill's rules.json. Returns None if not found."""
    if not skill_name:
        return None
    cwd_p = pathlib.Path(cwd or os.getcwd())
    home = pathlib.Path.home()

    candidates: List[pathlib.Path] = []
    rules_dir = os.environ.get("SKILLSENTRY_RULES_DIR")
    if rules_dir:
        rd = pathlib.Path(rules_dir)
        candidates.extend([rd / skill_name / "rules.json", rd / f"{skill_name}.rules.json"])

    candidates.extend([
        cwd_p / ".claude" / "skills" / skill_name / "rules.json",
        cwd_p / "skills" / skill_name / "rules.json",
        cwd_p / "environment" / "skills" / skill_name / "rules.json",
        home / ".claude" / "skills" / skill_name / "rules.json",
    ])

    repo_root = pathlib.Path(__file__).resolve().parent.parent
    candidates.append(repo_root / "examples" / "rules" / f"{skill_name}.rules.json")

    for up in [cwd_p, *cwd_p.parents][:4]:
        candidates.append(up / "environment" / "skills" / skill_name / "rules.json")
        candidates.append(up / "skills" / skill_name / "rules.json")

    for p in candidates:
        if p.exists():
            return p
    return None
