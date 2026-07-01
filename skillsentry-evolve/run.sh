#!/usr/bin/env bash
# Run SkillSentry guidance generation.
#
# Usage:
#   bash run.sh <task-name> initialize                    # Initialization Stage
#   bash run.sh <task-name> evolve                        # Self-evolving (10 iterations default)
#   bash run.sh <task-name> evolve --iterations 5         # Custom iteration count
#   bash run.sh <task-name> evolve --queries-per-iter 3   # Custom queries per iteration
#   bash run.sh <task-name> evaluate                      # Evaluate on Q_test
#
# Before the first run, prepare the data split:
#   python utils/prepare_data.py              # converts raw → data/evolve/iter_* format

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${SCRIPT_DIR}"

# --------------------------------------------------------------------
# API keys
# --------------------------------------------------------------------
export LLM_API_BASE="YOUR_API_BASE_URL"
export OPENAI_API_KEY="YOUR_API_KEY"
export LLM_API_KEY="${OPENAI_API_KEY}"
export LLM_MODEL="${LLM_MODEL:-gpt-5.4}"
export LLM_TIMEOUT_SEC="${LLM_TIMEOUT_SEC:-180}"
export FUZZ_JSON_MODE="1"

# --------------------------------------------------------------------
# Paths (auto-resolved from repo root; override via env vars if needed)
# --------------------------------------------------------------------
# Raw task data (environment, skills, tests)
export TASKS_ROOT="${REPO_ROOT}/data/raw/skillsentry_tasks"
# Prepared split data (evolve/test/baseline queries)
export EVOLVE_ROOT="${REPO_ROOT}/data/evolve"
# Evolved runtime guidance output
export OUTPUT_DIR="${REPO_ROOT}/data/results/evolve"
# DSL skeleton output (from initialization stage)
export RULES_REF_DIR="${REPO_ROOT}/data/results/dsl"

export SKILLSENTRY_SRC="${REPO_ROOT}/skillsentry/skillsentry"
export HOOKS_SRC="${REPO_ROOT}/skillsentry/hooks"

# --------------------------------------------------------------------
# Tuning
# --------------------------------------------------------------------
export PATTERN_MIN_FREQ="${PATTERN_MIN_FREQ:-1}"
export MAX_TOOL_CALLS_IN_PROMPT="${MAX_TOOL_CALLS_IN_PROMPT:-0}"

# --------------------------------------------------------------------
# Run
# --------------------------------------------------------------------
TASK="${1:-econ-detrending-correlation}"
MODE="${2:-initialize}"

LOG_DIR="${REPO_ROOT}/data/results/evolve/logs"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/${TASK}_${MODE}_$(date +%Y%m%d_%H%M%S).log"

echo "[skillsentry] task        = ${TASK}"
echo "[skillsentry] mode        = ${MODE}"
echo "[skillsentry] llm_model   = ${LLM_MODEL}"
echo "[skillsentry] tasks_root  = ${TASKS_ROOT}"
echo "[skillsentry] evolve_root = ${EVOLVE_ROOT}"
echo "[skillsentry] output_dir  = ${OUTPUT_DIR}"
echo "[skillsentry] log_file    = ${LOG_FILE}"
echo ""

python3 "${SCRIPT_DIR}/main.py" \
    --task "${TASK}" \
    --mode "${MODE}" \
    "${@:3}" 2>&1 | tee "${LOG_FILE}"
