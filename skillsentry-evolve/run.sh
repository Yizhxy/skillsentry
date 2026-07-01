#!/usr/bin/env bash
# Run guidance generation (initialization stage) on a task using baseline traces.
# Keys and API config sourced from the environment.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

# --------------------------------------------------------------------
# API keys (same as fuzzer.sh / baseline_run.sh)
# --------------------------------------------------------------------
export LLM_API_BASE="YOUR_API_BASE_URL"
export OPENAI_API_KEY="YOUR_API_KEY"
export LLM_API_KEY="${OPENAI_API_KEY}"
export LLM_MODEL="${LLM_MODEL:-gpt-5.4}"
export LLM_TIMEOUT_SEC="${LLM_TIMEOUT_SEC:-120}"
export FUZZ_JSON_MODE="1"

# --------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------
export DATASET_ROOT="/YOUR/PATH/TO/skillsentry_tasks/dataset_for_validation"
export TASKS_ROOT="/YOUR/PATH/TO/skillsentry/tasks"
export RULES_REF_DIR="/YOUR/PATH/TO/rules"
export SKILLSENTRY_SRC="/YOUR/PATH/TO/skillsentry/skillsentry"
export HOOKS_SRC="/YOUR/PATH/TO/skillsentry/hooks"
export OUTPUT_DIR="${SCRIPT_DIR}/output_rules"

# --------------------------------------------------------------------
# Mining tuning
# --------------------------------------------------------------------
export PATTERN_MIN_FREQ="${PATTERN_MIN_FREQ:-1}"
export MAX_TOOL_CALLS_IN_PROMPT="${MAX_TOOL_CALLS_IN_PROMPT:-30}"

# --------------------------------------------------------------------
# Run
# --------------------------------------------------------------------
TASK="${1:-econ-detrending-correlation}"
MODE="${2:-initialize}"

LOG_DIR="${SCRIPT_DIR}/logs"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/${TASK}_${MODE}_$(date +%Y%m%d_%H%M%S).log"

echo "[skillsentry] task        = ${TASK}"
echo "[skillsentry] mode        = ${MODE}"
echo "[skillsentry] llm_model   = ${LLM_MODEL}"
echo "[skillsentry] api_base    = ${LLM_API_BASE}"
echo "[skillsentry] output_dir  = ${OUTPUT_DIR}"
echo "[skillsentry] log_file    = ${LOG_FILE}"
echo ""

python3 "${SCRIPT_DIR}/main.py" \
    --task "${TASK}" \
    --mode "${MODE}" \
    "${@:3}" 2>&1 | tee "${LOG_FILE}"
