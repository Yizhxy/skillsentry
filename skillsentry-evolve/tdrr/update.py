"""
Stage 4: Conservative Update.

Key improvements:
1. Semantic matching for UPDATE/REMOVE/REVERT via match_existing description.
2. PASS support — if gradient says decision=pass, returns unchanged rules.
3. Deduplication — prevents adding identical entries across rounds.
4. Overfit validation — rejects regex patterns with specific filenames/paths.
5. FSM reachability check — rejects must_call updates that would cause FSM stuck.
6. Pareto multi-objective filtering — selects updates by (FP_rate, FN_rate, coverage)
   instead of pure LLM confidence, avoiding degenerate solutions.
"""
from __future__ import annotations

import copy
import re
import sys
from typing import Any

import config
from tdrr.fsm_validator import check_must_call_reachable, _signature_matches_tool_call


# Patterns that indicate overfit content — reject if found in regex fields
_OVERFIT_PATTERNS = [
    r'\.[a-z]{2,4}$',          # specific file extensions like .xlsx .csv .txt
    r'/[a-z_]+/',               # specific paths
    r'[A-Z]{3,}\.',             # specific variable names like CPI. GDP.
]


def _is_overfit(regex_str: str) -> bool:
    """Heuristic check: does this regex look like it's overfit to specific data?"""
    for pat in _OVERFIT_PATTERNS:
        if re.search(pat, regex_str):
            return True
    return False


def _get_step(rules: dict, step_id: str) -> dict | None:
    for step in rules.get("steps", []):
        if step.get("stepId") == step_id or step.get("id") == step_id:
            return step
    return None


def _get_logical_action_patterns(step: dict) -> list[dict]:
    """Flatten all patterns from logical_actions for signature matching."""
    patterns = []
    for action in step.get("logical_actions", []):
        patterns.extend(action.get("patterns", []))
    return patterns


def _find_matching_index(entries: list, match_desc) -> int | None:
    """
    Semantically find the index of an entry that best matches match_desc.
    match_desc may be a string, list, or dict (LLM sometimes returns wrong type).
    """
    if not entries or not match_desc:
        return None
    # Normalize match_desc to string
    if isinstance(match_desc, (list, dict)):
        match_desc = str(match_desc)
    match_lower = str(match_desc).lower()
    match_words = set(re.findall(r'\w+', match_lower))

    best_idx, best_score = None, 0
    for i, entry in enumerate(entries):
        entry_str = str(entry).lower()
        entry_words = set(re.findall(r'\w+', entry_str))
        # Score: word overlap (words > 2 chars)
        overlap = {w for w in match_words & entry_words if len(w) > 2}
        score = len(overlap)
        if score > best_score:
            best_score = score
            best_idx = i

    # Lower threshold to 1 for must_call/forbidden fields where descriptions are short
    return best_idx if best_score >= 1 else None


def _is_duplicate(existing_list: list, new_entry: dict) -> bool:
    """Check if new_entry is already present by exact (tool, command_match, input_match) match."""
    if not isinstance(new_entry, dict):
        new_str = str(new_entry).lower()
        return any(str(e).lower() == new_str for e in existing_list)

    new_tool = new_entry.get("tool", "")
    new_cmd  = new_entry.get("command_match", "")
    new_im   = str(new_entry.get("input_match", ""))
    new_pm   = new_entry.get("path_match", "")

    for existing in existing_list:
        if not isinstance(existing, dict):
            continue
        if (existing.get("tool", "") == new_tool and
                existing.get("command_match", "") == new_cmd and
                str(existing.get("input_match", "")) == new_im and
                existing.get("path_match", "") == new_pm):
            return True
    return False


# ---------------------------------------------------------------------------
# Pareto multi-objective scoring
# ---------------------------------------------------------------------------

def _score_update(
    upd: dict[str, Any],
    current_rules: dict[str, Any],
    success_traces: list,
    fail_traces: list,
) -> dict[str, float]:
    """
    Compute a 3-objective score for a candidate field update:
      fp_rate:  fraction of success traces that would be incorrectly blocked
      fn_rate:  fraction of fail traces whose error would still be missed
      coverage: fraction of success traces that satisfy the new must_call

    Lower fp_rate and fn_rate is better; higher coverage is better.
    Returns {"fp_rate", "fn_rate", "coverage", "confidence"}.
    """
    field   = upd.get("field", "")
    content = upd.get("content")
    step_id = upd.get("step_id", "")
    conf    = float(upd.get("confidence", 0.5))

    # Only score logical_actions and failure_patterns updates; others use confidence only
    if field not in ("logical_actions", "failure_patterns") or not content:
        return {"fp_rate": 0.0, "fn_rate": 0.0, "coverage": 1.0, "confidence": conf}

    sigs = content if isinstance(content, list) else [content]
    # For logical_actions content can be an action dict {actionId, patterns} or a flat sig
    flat_sigs = []
    for s in sigs:
        if isinstance(s, dict) and "patterns" in s:
            flat_sigs.extend(s["patterns"])
        else:
            flat_sigs.append(s)

    if field == "logical_actions":
        # coverage: how many success traces have at least one tool call matching
        matched = sum(
            1 for t in success_traces
            if any(
                _signature_matches_tool_call(
                    sig, tc.tool, tc.command or "", tc.content_snippet or "")
                for sig in flat_sigs
                if isinstance(sig, dict)
                for tc in t.parsed.tool_calls
            )
        )
        coverage = matched / len(success_traces) if success_traces else 1.0
        return {"fp_rate": 0.0, "fn_rate": 0.0, "coverage": coverage, "confidence": conf}

    if field == "failure_patterns":
        # fp_rate: success traces that match the forbidden pattern (false positives)
        fp = sum(
            1 for t in success_traces
            if any(
                _signature_matches_tool_call(
                    sig, tc.tool, tc.command or "", tc.content_snippet or "")
                for sig in flat_sigs
                if isinstance(sig, dict)
                for tc in t.parsed.tool_calls
            )
        )
        fp_rate = fp / len(success_traces) if success_traces else 0.0

        # fn_rate: fail traces that do NOT match the forbidden pattern (still missed)
        fn = sum(
            1 for t in fail_traces
            if not any(
                _signature_matches_tool_call(
                    sig, tc.tool, tc.command or "", tc.content_snippet or "")
                for sig in flat_sigs
                if isinstance(sig, dict)
                for tc in t.parsed.tool_calls
            )
        )
        fn_rate = fn / len(fail_traces) if fail_traces else 0.0

        return {"fp_rate": fp_rate, "fn_rate": fn_rate, "coverage": 1.0, "confidence": conf}

    return {"fp_rate": 0.0, "fn_rate": 0.0, "coverage": 1.0, "confidence": conf}


def _pareto_select(
    scored_updates: list[tuple[dict, dict[str, float]]],
) -> list[dict]:
    """
    Select updates using Pareto-front filtering — no hard limit on count.

    Objectives (all to minimize): fp_rate, fn_rate, (1 - coverage).
    Returns all non-dominated updates, sorted by confidence descending.
    Dominated updates are appended after the front (also by confidence).
    """
    if not scored_updates:
        return []

    def dominates(a_scores: dict, b_scores: dict) -> bool:
        a = (a_scores["fp_rate"], a_scores["fn_rate"], 1 - a_scores["coverage"])
        b = (b_scores["fp_rate"], b_scores["fn_rate"], 1 - b_scores["coverage"])
        return all(ai <= bi for ai, bi in zip(a, b)) and any(ai < bi for ai, bi in zip(a, b))

    front, dominated_upds = [], []
    for i, (upd_i, scores_i) in enumerate(scored_updates):
        is_dominated = any(
            i != j and dominates(scores_j, scores_i)
            for j, (_, scores_j) in enumerate(scored_updates)
        )
        (dominated_upds if is_dominated else front).append((upd_i, scores_i))

    front.sort(key=lambda x: x[1]["confidence"], reverse=True)
    dominated_upds.sort(key=lambda x: x[1]["confidence"], reverse=True)
    return [upd for upd, _ in front + dominated_upds]


def _normalize_gradient(gradient: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize Stage 3 output to the internal field_updates format.

    Accepts both the new simplified 'changes' format:
      {"decision": "update", "changes": [{
        "step_id": "...",
        "failure_patterns_add": [...],
        "on_enter_update": {"suggestions": [...], "warnings": [...]},
        "logical_actions_add": [...],
      }]}

    And the legacy 'field_updates' format (pass-through unchanged).
    """
    if "field_updates" in gradient or "changes" not in gradient:
        return gradient  # already in internal format

    field_updates: list[dict] = []
    for change in gradient.get("changes", []):
        step_id = change.get("step_id", "")
        rationale = change.get("rationale", "")
        confidence = change.get("confidence", 0.7)

        # failure_patterns_add: each entry has {regex, tool, match_in, reason}
        for pat in change.get("failure_patterns_add", []):
            if not isinstance(pat, dict):
                continue
            regex = pat.get("regex", "")
            tool = pat.get("tool", "Bash")
            match_in = pat.get("match_in", "command")
            reason = pat.get("reason", "")
            # Convert to internal signature format
            if match_in == "content":
                sig = {"tool": tool, "input_match": {"content": regex}, "reason": reason}
            else:
                sig = {"tool": tool, "command_match": regex, "reason": reason}
            field_updates.append({
                "step_id": step_id,
                "field": "failure_patterns",
                "action": "ADD",
                "content": sig,
                "rationale": rationale,
                "confidence": confidence,
            })

        # logical_actions_add: each entry has {regex, tool, match_in}
        for pat in change.get("logical_actions_add", []):
            if not isinstance(pat, dict):
                continue
            regex = pat.get("regex", "")
            tool = pat.get("tool", "Bash")
            match_in = pat.get("match_in", "command")
            if match_in == "content":
                sig = {"tool": tool, "input_match": {"content": regex}}
            else:
                sig = {"tool": tool, "command_match": regex}
            # Wrap in an action dict so _score_update can flatten it
            field_updates.append({
                "step_id": step_id,
                "field": "logical_actions",
                "action": "ADD",
                "content": {"actionId": 999, "patterns": [sig]},
                "rationale": rationale,
                "confidence": confidence,
            })

        # on_enter_update: replaces entire on_enter
        if "on_enter_update" in change:
            on_enter = change["on_enter_update"]
            if isinstance(on_enter, dict) and (on_enter.get("suggestions") or on_enter.get("warnings")):
                field_updates.append({
                    "step_id": step_id,
                    "field": "on_enter",
                    "action": "UPDATE",
                    "content": on_enter,
                    "match_existing": "",
                    "rationale": rationale,
                    "confidence": confidence,
                })

    return {
        "decision": gradient.get("decision", "update"),
        "field_updates": field_updates,
    }


def apply(
    current_rules: dict[str, Any],
    gradient: dict[str, Any],
    success_traces: list | None = None,
    fail_traces: list | None = None,
    global_memory: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
    """
    Apply field updates. No hard limit on number of changes — all updates
    that pass Pareto filtering, FSM validation, and overfit checks are applied.

    Returns (new_rules, diff_log, was_pass).
    """
    # Normalize new 'changes' format to internal 'field_updates' format
    gradient = _normalize_gradient(gradient)

    # Respect the pass decision
    if gradient.get("decision") == "pass":
        reason = gradient.get("pass_reason", "no changes needed")
        print(f"  [pass] {reason}")
        return current_rules, [], True

    updates = gradient.get("field_updates", [])
    if not updates:
        print("  [pass] No field updates proposed")
        return current_rules, [], True

    # Pareto multi-objective selection — no hard limit
    s_traces = success_traces or []
    f_traces = fail_traces   or []
    if s_traces or f_traces:
        scored  = [(upd, _score_update(upd, current_rules, s_traces, f_traces))
                   for upd in updates]
        updates = _pareto_select(scored)
        print(f"  [pareto] {len(updates)}/{len(gradient['field_updates'])} updates after Pareto filter")
    else:
        # Fallback: confidence sort, no truncation
        updates = sorted(updates, key=lambda x: float(x.get("confidence", 0.5)), reverse=True)

    new_rules = copy.deepcopy(current_rules)
    diff_log  = []

    for upd in updates:
        step_id     = upd.get("step_id")
        field       = upd.get("field")
        action      = upd.get("action", "ADD")
        content     = upd.get("content")
        match_desc  = upd.get("match_existing", "")

        # Skip if content is None for non-REMOVE actions
        if content is None and action != "REMOVE":
            print(f"  [skip] {step_id}.{field}: content is None for action={action}",
                  file=sys.stderr)
            continue

        # Validate step exists
        step = _get_step(new_rules, step_id)
        if not step:
            print(f"  [warn] step_id '{step_id}' not found in rules, skipping",
                  file=sys.stderr)
            continue

        # Validate content for regex fields
        if content and field in ("logical_actions", "failure_patterns"):
            # Flatten logical_actions content to verify signature format
            if field == "logical_actions" and isinstance(content, dict) and "patterns" in content:
                sigs = content["patterns"]
            elif isinstance(content, list):
                sigs = []
                for item in content:
                    if isinstance(item, dict) and "patterns" in item:
                        sigs.extend(item["patterns"])
                    else:
                        sigs.append(item)
            else:
                sigs = [content]
            rejected = False
            for sig in sigs:
                if not isinstance(sig, dict):
                    continue
                # Validate failure_patterns format: must have tool + command_match or input_match
                if field == "failure_patterns":
                    has_tool = bool(sig.get("tool"))
                    has_match = bool(sig.get("command_match") or sig.get("input_match"))
                    if not has_tool or not has_match:
                        print(f"  [warn] Rejected malformed failure_pattern in {step_id}: "
                              f"missing 'tool' or 'command_match'/'input_match' — "
                              f"got keys: {list(sig.keys())}",
                              file=sys.stderr)
                        rejected = True
                        break
                # Check for logical_actions/failure_patterns contradiction
                if field == "failure_patterns":
                    cmd_pat = sig.get("command_match", "")
                    step_obj = _get_step(new_rules, step_id)
                    if step_obj and cmd_pat:
                        for mc in _get_logical_action_patterns(step_obj):
                            if isinstance(mc, dict):
                                mc_pat = mc.get("command_match", "")
                                if mc_pat and cmd_pat and (
                                    mc_pat in cmd_pat or cmd_pat in mc_pat
                                ):
                                    print(f"  [warn] Contradiction: {step_id}.failure_patterns "
                                          f"'{cmd_pat}' conflicts with logical_actions '{mc_pat}'",
                                          file=sys.stderr)
                regex = (sig.get("command_match") or
                         sig.get("input_match", {}).get("content", ""))
                if regex and _is_overfit(regex):
                    print(f"  [warn] Rejected overfit regex in {step_id}.{field}: {regex[:60]}",
                          file=sys.stderr)
                    rejected = True
                    break
            if rejected:
                continue

        # FSM reachability check for logical_actions ADD/UPDATE/REVERT
        if field == "logical_actions" and action in ("ADD", "UPDATE", "REVERT") and content:
            # Flatten newly added/updated patterns
            if isinstance(content, dict) and "patterns" in content:
                new_sigs = content["patterns"]
            elif isinstance(content, list):
                new_sigs = []
                for item in content:
                    if isinstance(item, dict) and "patterns" in item:
                        new_sigs.extend(item["patterns"])
                    else:
                        new_sigs.append(item)
            else:
                new_sigs = [content]
            if action == "ADD":
                candidate_sigs = _get_logical_action_patterns(step) + new_sigs
            else:
                candidate_sigs = new_sigs
            # Get global memory tokens for this step
            global_tokens = None
            if global_memory:
                global_tokens = global_memory.get("success_patterns", {}).get(step_id, {})
            reachable, reason = check_must_call_reachable(
                candidate_sigs, step_id,
                success_traces or [],
                global_success_tokens=global_tokens,
            )
            if not reachable:
                print(f"  [reject] FSM stuck: {reason}", file=sys.stderr)
                continue
            print(f"  [fsm-ok] {step_id}.logical_actions: {reason}")

        old_value = step.get(field)

        try:
            if action == "ADD":
                current_list = step.get(field, [])
                if isinstance(current_list, list):
                    # Deduplication check
                    if content and _is_duplicate(current_list, content):
                        print(f"  [skip] Duplicate entry for {step_id}.{field}, skipping")
                        continue
                    current_list = current_list + [content]
                    step[field] = current_list
                elif field == "on_enter" and current_list is None:
                    step[field] = content
                else:
                    step[field] = content

            elif action in ("UPDATE", "REVERT"):
                current_list = step.get(field)
                if isinstance(current_list, list):
                    idx = _find_matching_index(current_list, match_desc)
                    if idx is not None:
                        # Skip if content is identical to existing entry (no-op update)
                        if str(current_list[idx]) == str(content):
                            print(f"  [skip] {step_id}.{field} UPDATE has no effect "
                                  f"(old == new), skipping")
                            continue
                        current_list[idx] = content
                        step[field] = current_list
                    else:
                        print(f"  [warn] Could not find matching entry for "
                              f"{step_id}.{field} UPDATE (desc: {match_desc[:60]})",
                              file=sys.stderr)
                        continue
                else:
                    # For non-list fields, also check for no-op
                    if str(current_list) == str(content):
                        print(f"  [skip] {step_id}.{field} UPDATE has no effect "
                              f"(old == new), skipping")
                        continue
                    step[field] = content

            elif action == "REMOVE":
                current_list = step.get(field)
                if isinstance(current_list, list):
                    idx = _find_matching_index(current_list, match_desc)
                    if idx is not None:
                        current_list.pop(idx)
                        step[field] = current_list
                    else:
                        print(f"  [warn] Could not find matching entry for "
                              f"{step_id}.{field} REMOVE (desc: {match_desc[:60]})",
                              file=sys.stderr)
                        continue
                elif field == "on_enter":
                    step[field] = None

            new_value = step.get(field)
            diff_log.append({
                "step_id":    step_id,
                "field":      field,
                "action":     action,
                "old":        old_value,
                "new":        new_value,
                "rationale":  upd.get("rationale", ""),
                "confidence": upd.get("confidence", 0.5),
            })

        except Exception as e:
            print(f"  [warn] Failed to apply {step_id}.{field}: {e}", file=sys.stderr)

    was_pass = len(diff_log) == 0
    return new_rules, diff_log, was_pass
