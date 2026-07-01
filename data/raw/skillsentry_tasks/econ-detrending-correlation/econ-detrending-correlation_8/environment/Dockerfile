FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Install python packages with pinned versions
RUN pip install --no-cache-dir \
    pandas==2.2.3 \
    numpy==1.26.4 \
    openpyxl==3.1.5 \
    xlrd==2.0.1 \
    scipy==1.14.1 \
    statsmodels==0.14.4

WORKDIR /root

# Copy data files
COPY CPI.xlsx /root/
COPY ERP-2025-table10.xls /root/
COPY ERP-2025-table12.xls /root/

# Copy skills to agent-specific locations
# Claude Code
COPY skills /root/.claude/skills
# Codex
COPY skills /root/.codex/skills
# OpenCode
COPY skills /root/.opencode/skill
# Goose
COPY skills /root/.goose/skills
# Factory
COPY skills /root/.factory/skills
# Goose/Amp (portable agents format)
COPY skills /root/.agents/skills
# Gemini
COPY skills /root/.gemini/skills


# Copy SWAG hook script and workflow_state module
COPY swag_hook.py /usr/local/bin/swag_hook.py
COPY workflow_state.py /usr/local/lib/python3.12/dist-packages/workflow_state.py

# Create Claude Code settings.json with PreToolUse hook
RUN mkdir -p /root/.claude/sessions && \
    echo '{"hooks":{"PreToolUse":[{"matcher":"","hooks":[{"type":"command","command":"python3 /usr/local/bin/swag_hook.py"}]}]}}' > /root/.claude/sessions/settings.json


# ============================================================================
# SWAG: Skill Workflow Adaptive Guard integration
# ============================================================================

# Copy SWAG hook script and workflow_state module
COPY swag_hook.py /usr/local/bin/swag_hook.py
COPY inject_settings.py /usr/local/bin/inject_settings.py
COPY workflow_state.py /usr/local/lib/python3.12/dist-packages/workflow_state.py

# Create startup script to inject settings.json with proper workflow spec
RUN echo '#!/bin/bash' > /usr/local/bin/swag_init.sh && \
    echo 'if [ "$SWAG_ENABLED" = "1" ] && [ -n "$SWAG_TASK_NAME" ] && [ -n "$SWAG_SESSION_ID" ]; then' >> /usr/local/bin/swag_init.sh && \
    echo '  CONFIG_DIR="${CLAUDE_CONFIG_DIR:-/root/.claude}"' >> /usr/local/bin/swag_init.sh && \
    echo '  python3 /usr/local/bin/inject_settings.py \' >> /usr/local/bin/swag_init.sh && \
    echo '    --config-dir "$CONFIG_DIR" \' >> /usr/local/bin/swag_init.sh && \
    echo '    --task-name "$SWAG_TASK_NAME" \' >> /usr/local/bin/swag_init.sh && \
    echo '    --session-id "$SWAG_SESSION_ID" \' >> /usr/local/bin/swag_init.sh && \
    echo '    ${SWAG_LOG_FILE:+--log-file "$SWAG_LOG_FILE"} >&2' >> /usr/local/bin/swag_init.sh && \
    echo 'fi' >> /usr/local/bin/swag_init.sh && \
    chmod +x /usr/local/bin/swag_init.sh

# Use BASH_ENV to run swag_init.sh for non-interactive shells
ENV BASH_ENV=/usr/local/bin/swag_init.sh

# ============================================================================
