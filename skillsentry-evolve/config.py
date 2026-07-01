"""Global configuration — all env-var overrides live here."""
import os
from pathlib import Path

# LLM (for the generation-side parser/miner — runs outside the container)
LLM_API_BASE   = os.environ.get("LLM_API_BASE", os.environ.get("ANTHROPIC_BASE_URL", "YOUR_API_BASE_URL"))
LLM_API_KEY    = os.environ.get("LLM_API_KEY", os.environ.get("ANTHROPIC_AUTH_TOKEN", os.environ.get("OPENAI_API_KEY", "")))
LLM_MODEL      = os.environ.get("LLM_MODEL", "gpt-5.4")

# Agent (for harbor trials — runs inside container)
AGENT_API_BASE = os.environ.get("AGENT_API_BASE", os.environ.get("ANTHROPIC_BASE_URL", "YOUR_API_BASE_URL"))
AGENT_API_KEY  = os.environ.get("AGENT_API_KEY", os.environ.get("ANTHROPIC_AUTH_TOKEN", os.environ.get("OPENAI_API_KEY", "")))
LLM_TIMEOUT    = int(os.environ.get("LLM_TIMEOUT_SEC", "300"))
JSON_MODE      = os.environ.get("FUZZ_JSON_MODE", "1") != "0"

# Harbor
HARBOR_BIN     = os.environ.get("HARBOR_BIN", "harbor")
HARBOR_AGENT   = os.environ.get("HARBOR_AGENT", "claude-code")
HARBOR_MODEL   = os.environ.get("HARBOR_MODEL", "gpt-5.4")
HARBOR_TIMEOUT = int(os.environ.get("HARBOR_TIMEOUT", "900"))

# Paths
# _PROJECT: repo root (.../skillsentry/), auto-detected from this file's location.
# skillsentry-evolve/config.py → parent = skillsentry-evolve/ → parent = skillsentry/
_PROJECT = Path(os.environ.get("SKILLSENTRY_PROJECT",
    str(Path(__file__).resolve().parent.parent)))

# data/evolve/<skill>/{evolve,test,baseline}/ — prepared by utils/prepare_data.py
# Q_evol queries live under EVOLVE_ROOT/<skill>/evolve/
# Q_test  queries live under EVOLVE_ROOT/<skill>/test/
# Baseline traces  under EVOLVE_ROOT/<skill>/baseline/
EVOLVE_ROOT  = Path(os.environ.get("EVOLVE_ROOT",
    str(_PROJECT / "data" / "evolve")))

# Raw task directories (environment/, skills/, tests/, etc.)
# Used for SKILL.md extraction and harbor environment setup.
TASKS_ROOT   = Path(os.environ.get("TASKS_ROOT",
    str(_PROJECT / "data" / "raw" / "skillsentry_tasks")))

RULES_REF_DIR = Path(os.environ.get("RULES_REF_DIR",
    str(_PROJECT / "data" / "results" / "dsl")))

SKILLSENTRY_SRC = Path(os.environ.get("SKILLSENTRY_SRC",
    str(_PROJECT / "skillsentry" / "skillsentry")))
HOOKS_SRC       = Path(os.environ.get("HOOKS_SRC",
    str(_PROJECT / "skillsentry" / "hooks")))

# Output: evolved runtime guidance
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR",
    str(_PROJECT / "data" / "results" / "evolve")))

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# task → skill mapping
TASK_SKILL_MAP = Path(os.environ.get("TASK_SKILL_MAP",
    str(Path(__file__).resolve().parent / "task_skill_map.json")))

# Mining tuning
PATTERN_MIN_FREQ         = int(os.environ.get("PATTERN_MIN_FREQ", "2"))
MAX_TOOL_CALLS_IN_PROMPT = int(os.environ.get("MAX_TOOL_CALLS_IN_PROMPT", "0"))
