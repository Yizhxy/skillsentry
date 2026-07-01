# SkillSentry: Skill-Oriented Runtime Assurance for Reliable LLM Agent Execution

SkillSentry is a skill-oriented runtime assurance framework that improves the reliability of LLM agent execution. It wraps around the agent execution loop to monitor and guide skill execution under a structured runtime guidance, and iteratively refines that guidance using newly collected traces.

> Paper: *SkillSentry: Skill-Oriented Runtime Assurance for Reliable LLM Agent Execution*

## Overview

![Overview](assert/overview.png)

SkillSentry consists of two stages:

**Initialization Stage**
1. **Skill Specification Extraction** — An LLM-based parser reads the skill document (SKILL.md) and extracts a structured skill specification: expected steps, step dependencies, constraints, and completion requirements. This is encoded in a domain-specific language (DSL) designed for skill-oriented runtime guidance.
2. **Execution Experience Mining** — An LLM-based miner analyzes historical successful and failed traces to extract validated action patterns, failure-associated actions, and step-level suggestions and warnings. The extracted experience is merged with the skill specification to produce the initial runtime guidance.

**Self-Evolving Stage**

3. **Step-Aware Runtime Assurance** — The agent executes new task queries under the current runtime guidance. A hook intercepts each planned action and passes it to:
   - **Procedure Checker**: monitors whether execution follows the skill procedure; delivers step-level hints and blocks failure-associated actions when detected.
   - **Termination Checker**: verifies that all required skill steps have been completed before accepting the final output; prompts the agent to continue if not.

   Resulting successful and failed traces are collected and fed back into Execution Experience Mining to update the runtime guidance, forming a self-evolving loop.

## Repository Structure

```
skillsentry/
├── LICENSE
├── README.md
│
├── assert/
│   └── overview.pdf                  # Architecture overview figure
│
├── data/
│   ├── raw/
│   │   └── skillsentry_tasks/        # Raw task environments (SKILL.md, tests, Dockerfiles)
│   └── results/
│       ├── dsl/                      # Runtime guidance (guidance.json) per model × skill
│       │   ├── haiku/                #   Claude Code + Claude-Haiku-4.5  (15 skills)
│       │   ├── opus/                 #   Claude Code + Claude-Opus-4.6   (15 skills)
│       │   ├── gpt-5.2/              #   Codex + GPT-5.2-medium          (15 skills)
│       │   └── gpt-5.4/              #   Codex + GPT-5.4                 (15 skills)
│       ├── evolve/                   # Self-evolving success-rate curves per model × skill
│       │   ├── haiku_4_5/            #   Per-skill success rate over 10 iterations (PNG + PDF)
│       │   ├── opus_4_6/             #   Per-skill success rate over 10 iterations (PNG + PDF)
│       │   ├── gpt_5_2/              #   Per-skill success rate over 10 iterations (PNG + PDF)
│       │   └── gpt_5_4/              #   Per-skill success rate over 10 iterations (PNG + PDF)
│       └── runtimes/                 # Runtime overhead breakdown per model (PNG + PDF)
│           ├── haiku_4_5_runtime_breakdown.*
│           ├── opus_4_6_runtime_breakdown.*
│           ├── gpt_5_2_runtime_breakdown.*
│           └── gpt_5_4_runtime_breakdown.*
│
├── skillsentry/
│   ├── skillsentry/                  # Core runtime assurance library
│   │   ├── fsm.py                    #   Finite-state machine: step tracking & transitions
│   │   ├── ir.py                     #   Internal representation of DSL guidance
│   │   ├── layers.py                 #   Procedure checker and termination checker logic
│   │   ├── matchers.py               #   Action pattern matching (command_match, path_match, etc.)
│   │   └── state.py                  #   Per-session runtime state
│   ├── hooks/
│   │   └── skillsentry_hook.py       # Hook entry point injected into the agent runtime
│   └── fix_codex/                    # Codex 0.135.0 hook-fix patch + Harbor integration
│       ├── agent.py                  #   PatchedCodexAgent for Harbor
│       ├── Dockerfile.base           #   Base Docker image with fixed codex binary
│       ├── setup.sh                  #   One-click install script
│       └── verify.sh                 #   Verify hooks are firing correctly
│
└── skillsentry-evolve/               # Initialization + self-evolving pipeline
    ├── main.py                       # Entry point (initialize / evolve / evaluate)
    ├── config.py                     # All configuration and env-var overrides
    ├── run.sh                        # Convenience wrapper around main.py
    ├── skill_spec_extraction.py      # §III-B: LLM-based skill specification extractor
    ├── experience_mining.py          # §III-C: LLM-based execution experience miner
    ├── task_skill_map.json           # Maps task names → skill names and skill directories
    ├── prompts/
    │   ├── dsl_reference.txt         #   Full DSL schema reference
    │   ├── skill_spec_extraction_sp.txt / _up.txt   # Spec extraction prompts
    │   ├── experience_diagnosis_sp.txt / _up.txt    # Experience diagnosis prompts
    │   └── experience_edition_sp.txt / _up.txt      # Guidance editing prompts
    └── utils/
        ├── llm.py                    #   LLM API client wrapper
        ├── runner.py                 #   Harbor trial runner and trace collector
        ├── trace.py                  #   Trace parsing and representation
        ├── task_data.py              #   Query and skill data loaders
        ├── memory.py                 #   Accumulated experience memory across iterations
        ├── state.py                  #   Evolve-stage iteration state persistence
        └── prepare_data.py           #   Converts raw task data → evolve/test split format
```

## Experimental Results

The `data/results/` directory contains all artifacts from the paper's evaluation across 4 model configurations (Claude Code + Claude-Haiku-4.5, Claude Code + Claude-Opus-4.6, Codex + GPT-5.2-medium, Codex + GPT-5.4) and 15 skills.

### Runtime Guidance (`data/results/dsl/`)

Each `guidance.json` is the runtime guidance for one skill under one model, combining the extracted skill specification with mined execution experience. These are used as the initial guidance fed into the self-evolving stage.

### Self-Evolving Success Rate Curves (`data/results/evolve/`)

Per-skill success rate over 10 self-evolving iterations for each model. Each PNG shows the baseline (iteration 1, guidance skeleton only) versus the evolving trajectory.

| | Claude-Haiku-4.5 | Claude-Opus-4.6 | GPT-5.2-medium | GPT-5.4 |
|---|---|---|---|---|
| Example (econ) | ![](data/results/evolve/haiku_4_5/haiku_4_5__timeseries-detrending.png) | ![](data/results/evolve/opus_4_6/opus_4_6__timeseries-detrending.png) | ![](data/results/evolve/gpt_5_2/gpt_5_2__timeseries-detrending.png) | ![](data/results/evolve/gpt_5_4/gpt_5_4__timeseries-detrending.png) |

All 15 per-skill curves are in the respective subdirectories under `data/results/evolve/`.

### Runtime Overhead (`data/results/runtimes/`)

Breakdown of SkillSentry's runtime overhead (procedure checking, termination checking, experience mining) per model.

| Claude-Haiku-4.5 | Claude-Opus-4.6 | GPT-5.2-medium | GPT-5.4 |
|---|---|---|---|
| ![](data/results/runtimes/haiku_4_5_runtime_breakdown.png) | ![](data/results/runtimes/opus_4_6_runtime_breakdown.png) | ![](data/results/runtimes/gpt_5_2_runtime_breakdown.png) | ![](data/results/runtimes/gpt_5_4_runtime_breakdown.png) |

## Installation

### Prerequisites

- **x86_64 Linux**
- **Docker**
- **Harbor >= 0.1.45**

```bash
uv tool install harbor
```

- **Python 3.10+** with standard packages (`openai`, `anthropic`, or compatible)

### Step 1: Install the Codex hook fix

SkillSentry relies on Codex hooks firing in `exec` mode. Codex 0.135.0 has a bug that silently drops all hooks in non-interactive mode. The patched binary is included in `skillsentry/fix_codex/`.

```bash
cd skillsentry/fix_codex
bash setup.sh
```

This builds the `codex-base:0.135.0` Docker image (~5 min on first run) and registers `PatchedCodexAgent` in Harbor's Python environment.

Verify the setup:

```bash
# Image exists
docker images | grep codex-base

# Binary works inside the image
docker run --rm codex-base:0.135.0 sh -c '. ~/.nvm/nvm.sh && codex --version'

# Python package importable
HARBOR_PYTHON=$(head -1 $(which harbor) | sed 's/^#!//')
$HARBOR_PYTHON -c "from fix_codex.agent import PatchedCodexAgent; print('OK')"
```

### Step 2: Prepare task data

```bash
cd skillsentry-evolve
python utils/prepare_data.py
```

This converts the raw tasks under `data/raw/` into the `data/evolve/<task>/` format expected by the evolve pipeline (80 queries per skill, split at runtime into Q\_evol / Q\_test).

## Running the Self-Evolving Pipeline

All commands are run from the `skillsentry-evolve/` directory.

### Environment variables

| Variable | Description | Example |
|---|---|---|
| `LLM_API_BASE` | API base URL for the guidance LLM (spec extractor / experience miner) | `https://api.example.com/v1` |
| `LLM_API_KEY` / `OPENAI_API_KEY` | API key for the guidance LLM | `sk-xxxxxxxx` |
| `LLM_MODEL` | Model used for guidance generation | `gpt-5.4` |
| `AGENT_API_BASE` | API base URL for the agent running inside Harbor containers | `https://api.example.com/v1` |
| `AGENT_API_KEY` | API key for the agent | `sk-xxxxxxxx` |
| `HARBOR_MODEL` | Model used by the Harbor agent | `gpt-5.4` |
| `HARBOR_AGENT` | Harbor agent type (`claude-code` or `codex`) | `claude-code` |
| `TASKS_ROOT` | Path to raw task environments | `data/raw/skillsentry_tasks` |
| `EVOLVE_ROOT` | Path to prepared query splits | `data/evolve` |
| `OUTPUT_DIR` | Output directory for evolved guidance and traces | `data/results/evolve` |
| `RULES_REF_DIR` | Directory containing initial DSL guidance skeletons | `data/results/dsl` |

Export before running:

```bash
export LLM_API_BASE="https://api.example.com/v1"
export LLM_API_KEY="sk-xxxxxxxx"
export OPENAI_API_KEY="sk-xxxxxxxx"
export LLM_MODEL="gpt-5.4"

export AGENT_API_BASE="https://api.example.com/v1"
export AGENT_API_KEY="sk-xxxxxxxx"
export HARBOR_MODEL="gpt-5.4"
export HARBOR_AGENT="claude-code"
```

### Stage 1 — Initialization

Extracts a DSL guidance skeleton from the skill document (SKILL.md). No agent traces needed.

```bash
bash run.sh econ-detrending-correlation initialize
```

Or directly:

```bash
python main.py --task econ-detrending-correlation --mode initialize
```

Output: `data/results/evolve/<skill>/guidance.json` (DSL skeleton, experience fields empty)

### Stage 2 — Self-Evolving

Runs the agent on Q\_evol queries, mines execution experience, and updates the guidance iteratively.

```bash
# 10 iterations, 5 queries per iteration (defaults from the paper)
bash run.sh econ-detrending-correlation evolve

# Custom settings
bash run.sh econ-detrending-correlation evolve --iterations 5 --queries-per-iter 3
```

Or directly:

```bash
python main.py --task econ-detrending-correlation --mode evolve --iterations 10 --queries-per-iter 5
```

Output per iteration: `data/results/evolve/<skill>/iter_<N>/guidance.json` and `diff_log.json`

## License

Apache License 2.0. See [LICENSE](LICENSE).
