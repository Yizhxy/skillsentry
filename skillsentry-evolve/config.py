"""Global configuration — all env-var overrides live here."""
import os
from pathlib import Path

# LLM (for TDRR optimizer — runs outside container)
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
_PROJECT = Path("/YOUR/PATH/TO/project")

DATASET_ROOT    = Path(os.environ.get("DATASET_ROOT",
    str(_PROJECT / "skillsentry_tasks" / "dataset_for_validation")))
TASKS_ROOT      = Path(os.environ.get("TASKS_ROOT",
    str(_PROJECT / "skillsentry" / "tasks")))
RULES_REF_DIR   = Path(os.environ.get("RULES_REF_DIR",
    str(_PROJECT / "skillsentry" / "tasks")))
SKILLSENTRY_SRC = Path(os.environ.get("SKILLSENTRY_SRC",
    str(_PROJECT / "skillsentry" / "skillsentry")))
HOOKS_SRC       = Path(os.environ.get("HOOKS_SRC",
    str(_PROJECT / "skillsentry" / "hooks")))
OUTPUT_DIR      = Path(os.environ.get("OUTPUT_DIR",
    str(_PROJECT / "skillsentry-evolve" / "output_rules")))
PROMPTS_DIR     = Path(__file__).resolve().parent / "prompts"

# task → skill mapping file (canonical skill for each task in dataset_for_validation)
TASK_SKILL_MAP  = Path(os.environ.get("TASK_SKILL_MAP",
    str(_PROJECT / "skillsentry-evolve" / "task_skill_map.json")))

# TDRR tuning
PATTERN_MIN_FREQ         = int(os.environ.get("PATTERN_MIN_FREQ", "2"))
# Max tool calls to include per trace in LLM prompts (0 = no truncation)
MAX_TOOL_CALLS_IN_PROMPT = int(os.environ.get("MAX_TOOL_CALLS_IN_PROMPT", "0"))
