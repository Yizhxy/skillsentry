"""Execution Experience Mining (paper §III-C).

Given the current runtime guidance G (a rules.json specification) and historical
successful (T+) and failed (T-) execution traces, the miner populates and refines the
experience fields — logical_actions, on_enter, failure_patterns — through five stages:

  1. Trace Pattern Extraction   → candidate action / failure patterns
  2. Trace Summarization        → per-trace summary Σ = ⟨S_match, S_skip, A_unma, s_fail, y⟩
  3. Experience Field Diagnosis → per-field d_f ∈ {FP, FN, MC, OK}
  4. Experience Field Edition   → per-field edit o_f ∈ {ADD, UPDATE, REMOVE}
  5. Guidance Validation        → structural/consistency checks; on failure the errors are
                                  returned to the edition stage to revise (bounded loop).

`mine_experience` orchestrates stages 2–5 (with the guidance-validation loop) over a set of
traces and returns the refined guidance.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict
from typing import Any

import config
import utils.llm as llm
from utils import memory as mem_module

MAX_MINE_ATTEMPTS = int(os.environ.get("SKILLSENTRY_MAX_MINE_ATTEMPTS", "3"))


def get_workflow_steps(guidance: dict[str, Any]) -> list[str]:
    """Return ['stepId: description', ...] for the steps of a guidance object."""
    return [f"{s['stepId']}: {s.get('description', '')}" for s in guidance.get("steps", [])]


# ===========================================================================
# Stage 1 — Trace Pattern Extraction
# ===========================================================================

_TOKEN_RE = re.compile(
    r'\b([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)+(?:\()?)'
    r'|\b([a-zA-Z_]\w{3,})\s*\('
)
_TOKEN_SKIP = {
    "print", "open", "True", "False", "None", "self", "return", "import",
    "from", "with", "else", "pass", "break", "continue", "raise",
    "range", "list", "dict", "str", "int", "float", "bool", "len",
    "isinstance", "hasattr", "getattr", "super", "object",
    "json.loads", "json.dumps", "json.load", "json.dump",
}


def _trace_tokens(tool: str, command: str | None, content: str | None) -> set[str]:
    text = command if tool == "Bash" else (content if tool in ("Write", "Edit") else None)
    if not text:
        return set()
    result: set[str] = set()
    for m in _TOKEN_RE.finditer(text):
        tok = (m.group(1) or m.group(2) or "").rstrip("(").strip()
        if tok and tok not in _TOKEN_SKIP and len(tok) > 3:
            result.add(tok)
    return result


def current_round_patterns(
    success_traces: list[Any], min_freq: int = config.PATTERN_MIN_FREQ,
) -> list[dict[str, Any]]:
    """High-frequency action patterns from this round's successful traces (evidence for
    diagnosis). These are candidate *validated action patterns* in the paper's terms.
    """
    pattern_counts: Counter = Counter()
    pattern_examples: dict[str, list[str]] = defaultdict(list)
    n = len(success_traces)

    for trace in success_traces:
        seen: set[str] = set()
        for tc in trace.parsed.tool_calls:
            for tok in _trace_tokens(tc.tool, tc.command, tc.content_snippet):
                key = f"{tc.tool}::{tok}"
                if key not in seen:
                    pattern_counts[key] += 1
                    seen.add(key)
                    if len(pattern_examples[key]) < 3:
                        src = tc.command or tc.content_snippet or ""
                        pattern_examples[key].append(src[:80])

    results: list[dict[str, Any]] = []
    for key, count in pattern_counts.most_common():
        if count < min_freq:
            break
        tool, pattern = key.split("::", 1)
        results.append({"tool": tool, "pattern": pattern, "frequency": count,
                        "total_traces": n, "examples": pattern_examples[key]})
    return results


def trace_pattern_extraction(
    memory: dict[str, Any],
    workflow_steps: list[str],
    min_logical_action_freq: int = 2,
) -> dict[str, Any]:
    """Derive structured candidate action / failure patterns from accumulated memory.

    Successful traces yield `logical_action_candidates` (validated action patterns);
    failed traces yield `forbidden_candidates` (failure patterns).
    """
    step_ids = [s.split(":")[0].strip() for s in workflow_steps]
    logical_action_candidates: dict[str, list] = {}
    forbidden_candidates: dict[str, list] = {}

    buckets = step_ids if step_ids else ["_global"]
    for sid in buckets:
        min_freq = min_logical_action_freq if step_ids else 1
        mc = mem_module.get_logical_action_candidates(memory, sid, min_freq=min_freq)
        if mc:
            logical_action_candidates[sid] = mc
        fb = mem_module.get_forbidden_candidates(
            memory, sid, min_fail_count=1, max_success_ratio=0.3)
        if fb:
            forbidden_candidates[sid] = fb

    return {
        "logical_action_candidates": logical_action_candidates,
        "forbidden_candidates": forbidden_candidates,
        "memory_summary": mem_module.format_for_prompt(memory, step_ids),
        "rounds_accumulated": memory.get("rounds_accumulated", 0),
        "total_success_traces": memory.get("total_success_traces", 0),
        "total_fail_traces": memory.get("total_fail_traces", 0),
    }


# ===========================================================================
# Stage 2 — Trace Summarization
# ===========================================================================

def trace_summarization(trace: Any, workflow_steps: list[str]) -> dict[str, Any]:
    """Reduce a raw execution trace to a compact summary
    Σ(τ, G) = ⟨S_match, S_skip, A_unma, s_fail, y⟩ used by diagnosis.
    """
    ev = trace.eval_result
    summary = {
        "outcome": "success" if trace.success else "failure",   # y
        "reward": trace.reward,
        "steps_matched": [],                                      # S_match
        "steps_skipped": ev.get("missing_steps", []),             # S_skip
        "unmatched_actions": [],                                  # A_unma
        "failure_step": ev.get("error_at_step"),                  # s_fail
        "error_description": ev.get("deviation_summary", ""),
        "skillsentry_interventions": {
            "denied_steps": trace.parsed.denied_steps,
            "hinted_steps": trace.parsed.hinted_steps,
        },
        "diagnostic_text": trace.parsed.to_diagnostic_text(),
        "verifier_output": (trace.parsed.verifier_stdout or "")[:500],
    }
    trace.structured_summary = summary
    return summary


# ===========================================================================
# Stage 3 — Experience Field Diagnosis
# ===========================================================================

def _fmt_traces(traces: list[Any], label: str) -> str:
    if not traces:
        return f"No {label} traces this round."
    parts = []
    for i, t in enumerate(traces[:5]):
        parts.append(f"--- {label.upper()} Trace {i+1} (reward={t.reward}, source={t.source}) ---\n"
                     f"{t.parsed.to_diagnostic_text()}")
    if len(traces) > 5:
        parts.append(f"... ({len(traces)-5} more {label} traces not shown)")
    return "\n\n".join(parts)


def experience_field_diagnosis(
    task_name: str,
    round_num: int,
    guidance: dict[str, Any],
    high_freq_patterns: list[dict[str, Any]],
    success_traces: list[Any],
    fail_traces: list[Any],
) -> dict[str, Any]:
    """Diagnose each experience field of each step as FP / FN / MC / OK."""
    try:
        up = llm.up(
            "experience_diagnosis_up",
            task_name=task_name,
            round_num=round_num,
            current_rules=json.dumps(guidance, indent=2, ensure_ascii=False)[:5000],
            high_freq_patterns=json.dumps(high_freq_patterns[:10], indent=2, ensure_ascii=False)[:1000],
            n_success=len(success_traces),
            n_fail=len(fail_traces),
            success_summaries=_fmt_traces(success_traces, "success"),
            fail_summaries=_fmt_traces(fail_traces, "failure"),
        )
        raw = llm.call(
            [{"role": "system", "content": llm.sp_with_dsl("experience_diagnosis_sp")},
             {"role": "user", "content": up}],
            temperature=0.2, json_mode=True,
        )
        if not raw or not raw.strip():
            return {"field_diagnoses": [], "healthy_fields": [], "summary": "Empty LLM response"}
        return json.loads(raw)
    except Exception as e:  # noqa: BLE001
        print(f"  [diagnosis] failed: {e}", file=sys.stderr)
        return {"field_diagnoses": [], "healthy_fields": [], "summary": "Diagnosis failed"}


# ===========================================================================
# Stage 4 — Experience Field Edition
# ===========================================================================

def experience_field_edition(
    task_name: str,
    skill_name: str,
    skill_md: str,
    round_num: int,
    guidance: dict[str, Any],
    diagnosis: dict[str, Any],
    candidates: dict[str, Any],
    validation_errors: list[str] | None = None,
) -> dict[str, Any]:
    """Propose ADD / UPDATE / REMOVE edits to logical_actions / on_enter / failure_patterns."""
    healthy = diagnosis.get("healthy_fields", [])
    sp_text = (llm.sp_with_dsl("experience_edition_sp")
               .replace("{skill_md}", skill_md[:2000] if skill_md else "(not available)"))
    try:
        up = llm.up(
            "experience_edition_up",
            task_name=task_name,
            skill_name=skill_name,
            round_num=round_num,
            logical_action_candidates=json.dumps(
                candidates.get("logical_action_candidates", {}), indent=2, ensure_ascii=False)[:2000],
            forbidden_candidates=json.dumps(
                candidates.get("forbidden_candidates", {}), indent=2, ensure_ascii=False)[:2000],
            current_rules=json.dumps(guidance, indent=2, ensure_ascii=False)[:2000],
            diagnosis=json.dumps(diagnosis, indent=2, ensure_ascii=False),
            healthy_fields="\n".join(healthy) if healthy else "None identified",
            validation_errors=("\n".join(f"- {e}" for e in validation_errors)
                               if validation_errors else "none"),
        )
        raw = llm.call(
            [{"role": "system", "content": sp_text}, {"role": "user", "content": up}],
            temperature=0.2, json_mode=True,
        )
        if not raw or not raw.strip():
            return {"decision": "pass", "pass_reason": "Empty LLM response", "changes": []}
        return json.loads(raw)
    except Exception as e:  # noqa: BLE001
        print(f"  [edition] failed: {e}", file=sys.stderr)
        return {"decision": "pass", "pass_reason": f"LLM error: {e}", "changes": []}


# --- edition helpers (structural) -----------------------------------------

_OVERFIT_PATTERNS = [
    r'\.[a-z]{2,4}$',      # specific file extensions like .xlsx .csv
    r'/[a-z_]+/',          # specific paths
    r'[A-Z]{3,}\.',        # specific variable names like CPI. GDP.
]


def _is_overfit(regex_str: str) -> bool:
    return any(re.search(pat, regex_str) for pat in _OVERFIT_PATTERNS)


def _get_step(guidance: dict, step_id: str) -> dict | None:
    for step in guidance.get("steps", []):
        if step.get("stepId") == step_id:
            return step
    return None


def _logical_action_patterns(step: dict) -> list[dict]:
    patterns: list[dict] = []
    for action in step.get("logical_actions", []):
        patterns.extend(action.get("patterns", []))
    return patterns


def _find_matching_index(entries: list, match_desc) -> int | None:
    if not entries or not match_desc:
        return None
    if isinstance(match_desc, (list, dict)):
        match_desc = str(match_desc)
    match_words = {w for w in re.findall(r'\w+', str(match_desc).lower()) if len(w) > 2}
    best_idx, best_score = None, 0
    for i, entry in enumerate(entries):
        entry_words = set(re.findall(r'\w+', str(entry).lower()))
        score = len(match_words & entry_words)
        if score > best_score:
            best_idx, best_score = i, score
    return best_idx if best_score >= 1 else None


def _is_duplicate(existing_list: list, new_entry) -> bool:
    if not isinstance(new_entry, dict):
        new_str = str(new_entry).lower()
        return any(str(e).lower() == new_str for e in existing_list)
    key = (new_entry.get("tool", ""), new_entry.get("command_match", ""),
           str(new_entry.get("input_match", "")), new_entry.get("path_match", ""))
    for e in existing_list:
        if isinstance(e, dict) and (
            e.get("tool", ""), e.get("command_match", ""),
            str(e.get("input_match", "")), e.get("path_match", "")) == key:
            return True
    return False


def _normalize_edits(edition: dict[str, Any]) -> list[dict]:
    """Convert the edition 'changes' format into a flat list of field edits."""
    if "field_updates" in edition:
        return edition.get("field_updates", [])
    edits: list[dict] = []
    for change in edition.get("changes", []):
        step_id = change.get("step_id", "")
        rationale = change.get("rationale", "")
        for pat in change.get("failure_patterns_add", []):
            if not isinstance(pat, dict):
                continue
            regex, tool = pat.get("regex", ""), pat.get("tool", "Bash")
            reason = pat.get("reason", "")
            sig = ({"tool": tool, "input_match": {"content": regex}, "reason": reason}
                   if pat.get("match_in") == "content"
                   else {"tool": tool, "command_match": regex, "reason": reason})
            edits.append({"step_id": step_id, "field": "failure_patterns",
                          "action": "ADD", "content": sig, "rationale": rationale})
        for pat in change.get("logical_actions_add", []):
            if not isinstance(pat, dict):
                continue
            regex, tool = pat.get("regex", ""), pat.get("tool", "Bash")
            sig = ({"tool": tool, "input_match": {"content": regex}}
                   if pat.get("match_in") == "content"
                   else {"tool": tool, "command_match": regex})
            edits.append({"step_id": step_id, "field": "logical_actions", "action": "ADD",
                          "content": {"actionId": 999, "patterns": [sig]}, "rationale": rationale})
        on_enter = change.get("on_enter_update")
        if isinstance(on_enter, dict) and (on_enter.get("suggestions") or on_enter.get("warnings")):
            edits.append({"step_id": step_id, "field": "on_enter", "action": "UPDATE",
                          "content": on_enter, "match_existing": "", "rationale": rationale})
    return edits


def _content_signatures(field: str, content) -> list[dict]:
    """Flatten a logical_actions/failure_patterns edit's content to signature dicts."""
    if field == "logical_actions" and isinstance(content, dict) and "patterns" in content:
        return [s for s in content["patterns"] if isinstance(s, dict)]
    if isinstance(content, list):
        sigs: list[dict] = []
        for item in content:
            if isinstance(item, dict) and "patterns" in item:
                sigs.extend(p for p in item["patterns"] if isinstance(p, dict))
            elif isinstance(item, dict):
                sigs.append(item)
        return sigs
    return [content] if isinstance(content, dict) else []


def apply_edits(
    guidance: dict[str, Any],
    edition: dict[str, Any],
    success_traces: list | None = None,
    fail_traces: list | None = None,
    memory: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict]]:
    """Apply the edition's edits to the guidance, running the per-edit guidance checks
    (well-formedness, overfit rejection, FSM reachability, dedup, contradiction).
    Returns (new_guidance, diff_log)."""
    import copy
    if edition.get("decision") == "pass":
        return guidance, []
    edits = _normalize_edits(edition)
    if not edits:
        return guidance, []

    new_guidance = copy.deepcopy(guidance)
    diff_log: list[dict] = []
    s_traces = success_traces or []

    for upd in edits:
        step_id = upd.get("step_id")
        field = upd.get("field")
        action = upd.get("action", "ADD")
        content = upd.get("content")
        match_desc = upd.get("match_existing", "")

        if content is None and action != "REMOVE":
            continue
        step = _get_step(new_guidance, step_id)
        if not step:
            print(f"  [edit] step '{step_id}' not found, skipping", file=sys.stderr)
            continue

        # Well-formedness + overfit checks for regex fields.
        if content and field in ("logical_actions", "failure_patterns"):
            sigs = _content_signatures(field, content)
            rejected = False
            for sig in sigs:
                if field == "failure_patterns" and not (
                        sig.get("tool") and (sig.get("command_match") or sig.get("input_match"))):
                    print(f"  [edit] malformed failure_pattern in {step_id}, skipping", file=sys.stderr)
                    rejected = True
                    break
                regex = sig.get("command_match") or (sig.get("input_match", {}) or {}).get("content", "")
                if regex and _is_overfit(regex):
                    print(f"  [edit] overfit regex in {step_id}.{field}: {regex[:60]}", file=sys.stderr)
                    rejected = True
                    break
            if rejected:
                continue

        # FSM reachability for logical_actions ADD/UPDATE.
        if field == "logical_actions" and action in ("ADD", "UPDATE") and content:
            new_sigs = _content_signatures(field, content)
            candidate_sigs = (_logical_action_patterns(step) + new_sigs
                              if action == "ADD" else new_sigs)
            global_tokens = (memory or {}).get("success_patterns", {}).get(step_id, {})
            reachable, reason = check_logical_actions_reachable(
                candidate_sigs, step_id, s_traces, global_success_tokens=global_tokens)
            if not reachable:
                print(f"  [edit] reject unreachable logical_actions for {step_id}: {reason}",
                      file=sys.stderr)
                continue

        old_value = step.get(field)
        try:
            if action == "ADD":
                cur = step.get(field, [])
                if isinstance(cur, list):
                    if content and _is_duplicate(cur, content):
                        continue
                    step[field] = cur + [content]
                else:
                    step[field] = content
            elif action == "UPDATE":
                cur = step.get(field)
                if isinstance(cur, list):
                    idx = _find_matching_index(cur, match_desc)
                    if idx is None or str(cur[idx]) == str(content):
                        continue
                    cur[idx] = content
                    step[field] = cur
                else:
                    if str(cur) == str(content):
                        continue
                    step[field] = content
            elif action == "REMOVE":
                cur = step.get(field)
                if isinstance(cur, list):
                    idx = _find_matching_index(cur, match_desc)
                    if idx is None:
                        continue
                    cur.pop(idx)
                    step[field] = cur
                elif field == "on_enter":
                    step[field] = None
            diff_log.append({"step_id": step_id, "field": field, "action": action,
                             "old": old_value, "new": step.get(field),
                             "rationale": upd.get("rationale", "")})
        except Exception as e:  # noqa: BLE001
            print(f"  [edit] failed {step_id}.{field}: {e}", file=sys.stderr)

    return new_guidance, diff_log


# ===========================================================================
# Stage 5 — Guidance Validation
# ===========================================================================

try:  # reuse the runtime's regex matcher for consistency, if importable
    import importlib.util
    import pathlib as _pathlib
    _ss_path = _pathlib.Path(__file__).resolve().parent.parent / "skillsentry" / "skillsentry"
    if _ss_path.exists():
        _spec = importlib.util.spec_from_file_location(
            "skillsentry_matchers", _ss_path / "matchers.py")
        _matchers_mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_matchers_mod)
        _safe_search = _matchers_mod._safe_search
    else:
        _safe_search = None
except Exception:  # noqa: BLE001
    _safe_search = None


def _regex_matches_command(pattern: str, command: str) -> bool:
    if _safe_search:
        return _safe_search(pattern, command)
    try:
        return re.search(pattern, command) is not None
    except re.error:
        return False


def _signature_matches_tool_call(sig: dict[str, Any], tool: str,
                                 command: str | None, content: str | None) -> bool:
    if sig.get("tool") and sig["tool"] != tool:
        return False
    cmd_pat = sig.get("command_match")
    if cmd_pat:
        if not command or not _regex_matches_command(cmd_pat, command):
            return False
    im = sig.get("input_match", {})
    content_pat = im.get("content") if isinstance(im, dict) else None
    if content_pat:
        text = content or command or ""
        if not text or not _regex_matches_command(content_pat, text):
            return False
    return True


def check_logical_actions_reachable(
    new_action_patterns: list[dict[str, Any]],
    step_id: str,
    success_traces: list,
    global_success_tokens: dict | None = None,
) -> tuple[bool, str]:
    """Simulate whether the given logical-action signatures can be satisfied by at least one
    successful trace's tool calls (or a global memory token). Prevents an FSM-stuck step."""
    valid = [s for s in new_action_patterns if isinstance(s, dict)]
    if not valid:
        return True, "empty logical_actions — always reachable"

    for trace in success_traces:
        for sig in valid:
            for tc in trace.parsed.tool_calls:
                if _signature_matches_tool_call(sig, tc.tool, tc.command or "", tc.content_snippet or ""):
                    return True, "matched a current-round success trace"

    if global_success_tokens:
        for sig in valid:
            pattern = sig.get("command_match", "") or (sig.get("input_match") or {}).get("content", "")
            if not pattern:
                continue
            for token in global_success_tokens:
                try:
                    if re.search(pattern, token):
                        return True, f"matched global memory token '{token}'"
                except re.error:
                    pass

    return False, f"logical_actions matched 0/{len(success_traces)} traces — step '{step_id}' unreachable"


def guidance_validation(guidance: dict[str, Any]) -> list[str]:
    """Validate refined guidance against the DSL (paper §III-C stage 5):
    every action pattern is well-formed, each command-matching expression is a valid regex,
    and no field carries duplicate entries. Returns a list of error strings ([] when valid).
    """
    errors: list[str] = []
    known_ids = {s.get("stepId") for s in guidance.get("steps", [])}

    def _check_sig(sig, where: str) -> None:
        if not isinstance(sig, dict):
            errors.append(f"{where}: signature is not an object")
            return
        if not sig.get("tool"):
            errors.append(f"{where}: signature missing 'tool'")
        for key in ("command_match", "path_match"):
            pat = sig.get(key)
            if pat:
                try:
                    re.compile(pat)
                except re.error as e:
                    errors.append(f"{where}: invalid regex in {key}: {e}")
        im = sig.get("input_match")
        if isinstance(im, dict) and im.get("content"):
            try:
                re.compile(im["content"])
            except re.error as e:
                errors.append(f"{where}: invalid regex in input_match.content: {e}")

    for step in guidance.get("steps", []):
        sid = step.get("stepId", "?")
        # logical_actions
        seen_la: list = []
        for a, action in enumerate(step.get("logical_actions", [])):
            for p, sig in enumerate(action.get("patterns", [])):
                _check_sig(sig, f"{sid}.logical_actions[{a}].patterns[{p}]")
                if _is_duplicate(seen_la, sig):
                    errors.append(f"{sid}.logical_actions: duplicate pattern {sig}")
                else:
                    seen_la.append(sig)
        # failure_patterns (+ conflict with logical_actions)
        seen_fp: list = []
        for j, sig in enumerate(step.get("failure_patterns", [])):
            _check_sig(sig, f"{sid}.failure_patterns[{j}]")
            if _is_duplicate(seen_fp, sig):
                errors.append(f"{sid}.failure_patterns: duplicate pattern {sig}")
            else:
                seen_fp.append(sig)
            fp_cmd = sig.get("command_match", "") if isinstance(sig, dict) else ""
            for la in seen_la:
                la_cmd = la.get("command_match", "")
                if fp_cmd and la_cmd and (fp_cmd in la_cmd or la_cmd in fp_cmd):
                    errors.append(f"{sid}: failure_pattern '{fp_cmd}' conflicts with "
                                  f"logical_action '{la_cmd}'")

    for t in guidance.get("termination", []) or []:
        if t not in known_ids:
            errors.append(f"termination references unknown step '{t}'")

    return errors


# ===========================================================================
# Orchestrator
# ===========================================================================

def mine_experience(
    guidance: dict[str, Any],
    success_traces: list[Any],
    fail_traces: list[Any],
    memory: dict[str, Any],
    task_name: str,
    skill_name: str,
    skill_md: str = "",
    round_num: int = 0,
) -> tuple[dict[str, Any], list[dict]]:
    """Run stages 2–5 with the guidance-validation loop. Returns (refined_guidance, diff_log)."""
    workflow_steps = get_workflow_steps(guidance)

    # Stage 2: summarization (populates trace.structured_summary as a side-effect).
    for t in success_traces + fail_traces:
        trace_summarization(t, workflow_steps)

    # Stage 1 evidence + Stage 1 candidates.
    high_freq = current_round_patterns(success_traces)
    candidates = trace_pattern_extraction(memory, workflow_steps)

    # Stage 3: diagnosis.
    diagnosis = experience_field_diagnosis(
        task_name, round_num, guidance, high_freq, success_traces, fail_traces)

    # Stages 4–5: edition → guidance validation, looping on validation errors.
    refined, diff_log = guidance, []
    errors: list[str] = []
    for attempt in range(MAX_MINE_ATTEMPTS):
        edition = experience_field_edition(
            task_name, skill_name, skill_md, round_num, guidance, diagnosis, candidates,
            validation_errors=errors)
        refined, diff_log = apply_edits(
            guidance, edition, success_traces, fail_traces, memory)
        errors = guidance_validation(refined)
        if not errors:
            return refined, diff_log
        print(f"  [validation] attempt {attempt + 1}: {len(errors)} error(s), revising edits",
              file=sys.stderr)

    print(f"  [validation] returning best-effort guidance with {len(errors)} residual error(s)",
          file=sys.stderr)
    return refined, diff_log
