#!/usr/bin/env bash
# verify.sh — Verify that fix_codex is installed correctly
# Usage:
#   bash verify.sh                          # Run only checks that don't need an API key (1, 2)
#   V_API_KEY=sk-xxx bash verify.sh --full  # Run all checks (including actual task execution)
#
# Outputs: All checks passed. when everything passes.

set -euo pipefail

FIX_CODEX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FULL=${1:-}
PASS=0
FAIL=0

green() { echo -e "\033[32m✓ $*\033[0m"; }
red()   { echo -e "\033[31m✗ $*\033[0m"; }

check() {
    local desc="$1"; shift
    if "$@" &>/dev/null; then
        green "$desc"
        ((PASS++)) || true
    else
        red "$desc"
        ((FAIL++)) || true
    fi
}

echo "=== fix_codex Installation Verification ==="
echo "Directory: $FIX_CODEX_DIR"
echo ""

# ── Check 1: Basic files ──────────────────────────────────────────────────────────
echo "[ 1/4 ] Basic files"
check "codex-fixed exists"       test -f "$FIX_CODEX_DIR/codex-fixed"
check "codex-fixed is executable" test -x "$FIX_CODEX_DIR/codex-fixed"
check "Dockerfile.base exists"   test -f "$FIX_CODEX_DIR/Dockerfile.base"
check "agent.py exists"          test -f "$FIX_CODEX_DIR/agent.py"
check "setup.sh exists"          test -f "$FIX_CODEX_DIR/setup.sh"
echo ""

# ── Check 2: Docker image and Python package ──────────────────────────────────
echo "[ 2/4 ] Docker image & Python package"
check "docker available"            docker info
check "codex-base:0.135.0 image exists" docker image inspect codex-base:0.135.0

HARBOR_PYTHON=$(head -1 "$(command -v harbor)" | sed 's/^#!//' 2>/dev/null || echo "")
if [[ -n "$HARBOR_PYTHON" ]]; then
    check "harbor Python found" test -x "$HARBOR_PYTHON"
    check "PatchedCodexAgent importable" \
        "$HARBOR_PYTHON" -c "from fix_codex.agent import PatchedCodexAgent"
else
    red "harbor not installed, skipping Python package check"
    ((FAIL++)) || true
fi

check "codex works inside image" \
    docker run --rm codex-base:0.135.0 sh -c '. ~/.nvm/nvm.sh && codex --version'
echo ""

# ── Checks 3 & 4: Full task run (requires API key) ──────────────────────────────────
if [[ "$FULL" != "--full" ]]; then
    echo "[ 3/4 ] Full task run (skipped; add --full and set V_API_KEY to run)"
    echo "[ 4/4 ] Hooks fire verification (skipped)"
    echo ""
else
    API_KEY="${V_API_KEY:-${OPENAI_API_KEY:-}}"
    if [[ -z "$API_KEY" ]]; then
        red "V_API_KEY not set, skipping task run verification"
        ((FAIL++)) || true
    else
        # Generate temporary job yamls (replace placeholders)
        TMP_JOB=$(mktemp /tmp/fix_codex_verify_XXXXXX.yaml)
        TMP_HOOKS_JOB=$(mktemp /tmp/fix_codex_verify_hooks_XXXXXX.yaml)
        JOBS_DIR=$(mktemp -d /tmp/fix_codex_jobs_XXXXXX)

        sed \
            -e "s|REPLACE_WITH_YOUR_API_KEY|$API_KEY|g" \
            -e "s|REPLACE_WITH_FIX_CODEX_DIR|$FIX_CODEX_DIR|g" \
            -e "s|jobs_dir:.*|jobs_dir: $JOBS_DIR|g" \
            -e "s|job_name:.*|job_name: verify-econ|g" \
            "$FIX_CODEX_DIR/example/job_econ_iter0.yaml" > "$TMP_JOB"

        sed \
            -e "s|REPLACE_WITH_YOUR_API_KEY|$API_KEY|g" \
            -e "s|REPLACE_WITH_FIX_CODEX_DIR|$FIX_CODEX_DIR|g" \
            -e "s|jobs_dir:.*|jobs_dir: $JOBS_DIR|g" \
            -e "s|job_name:.*|job_name: verify-hooks|g" \
            "$FIX_CODEX_DIR/example/job_hooks_test.yaml" > "$TMP_HOOKS_JOB"

        echo "[ 3/4 ] Full task run (about 3 minutes)"
        # Build task image
        docker build -q -t hb__task-econ-iter0 \
            "$FIX_CODEX_DIR/task_econ_iter0/environment/" &>/dev/null
        check "task image built successfully" docker image inspect hb__task-econ-iter0

        # Run task, check reward=1.0
        HARBOR_OUT=$(harbor run -c "$TMP_JOB" 2>&1 || true)
        if echo "$HARBOR_OUT" | grep -q "reward = 1.0"; then
            green "Task run succeeded (reward = 1.0)"
            ((PASS++)) || true
        else
            red "Task run failed or reward != 1.0"
            echo "$HARBOR_OUT" | tail -20
            ((FAIL++)) || true
        fi
        echo ""

        echo "[ 4/4 ] Hooks fire verification (about 3 minutes)"
        HARBOR_OUT2=$(harbor run -c "$TMP_HOOKS_JOB" 2>&1 || true)
        HOOK_LOG=$(find "$JOBS_DIR/verify-hooks" -name "hook.log" 2>/dev/null | head -1)

        if [[ -n "$HOOK_LOG" ]] && grep -q "session_start" "$HOOK_LOG" \
            && grep -q "pre_tool_use" "$HOOK_LOG" \
            && grep -q "stop" "$HOOK_LOG"; then
            green "Hooks firing correctly (session_start / pre_tool_use / stop all recorded)"
            ((PASS++)) || true
            echo "  hook.log contents (first 10 lines):"
            head -10 "$HOOK_LOG" | sed 's/^/    /'
        else
            red "Hooks not firing or log missing"
            [[ -n "$HOOK_LOG" ]] && cat "$HOOK_LOG" || echo "  hook.log does not exist"
            ((FAIL++)) || true
        fi

        rm -f "$TMP_JOB" "$TMP_HOOKS_JOB"
        rm -rf "$JOBS_DIR"
        echo ""
    fi
fi

# ── Summary ──────────────────────────────────────────────────────────────────────
echo "=== Results ==="
echo "Passed: $PASS  Failed: $FAIL"
echo ""
if [[ $FAIL -eq 0 ]]; then
    green "All checks passed."
    exit 0
else
    red "$FAIL check(s) failed. See README.md for troubleshooting."
    exit 1
fi
