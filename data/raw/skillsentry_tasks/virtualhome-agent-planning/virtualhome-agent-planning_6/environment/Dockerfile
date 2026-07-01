FROM ubuntu:24.04

# Install or copy over any environment dependencies here.

ENV DEBIAN_FRONTEND=noninteractive

# Install Python and essential tools
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    wget \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /app

# Install Python dependencies for citation verification
RUN pip3 install --break-system-packages \
    requests==2.32.3 \
    bibtexparser==1.4.2 \
    pyyaml==6.0.3 \
    numpy==2.4.1 \
    pyperplan==2.1 \
    unified_planning==1.3.0 \
    up-pyperplan==1.1.0

COPY problem.json /app/problem.json
COPY airport /app/airport
# COPY reference /app/reference
COPY skills /app/skills

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
# Portable agents format (Goose, Amp)
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
