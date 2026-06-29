#!/usr/bin/env bash
# setup.sh — one-shot setup for fix_codex on a new machine
# Run from the fix_codex directory: bash setup.sh
set -euo pipefail

FIX_CODEX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "[setup] fix_codex dir: $FIX_CODEX_DIR"

# ── 0. Architecture check ─────────────────────────────────────────────────────
ARCH=$(uname -m)
if [[ "$ARCH" != "x86_64" ]]; then
    echo "[ERROR] codex-fixed is compiled for x86_64. Current arch: $ARCH"
    echo "        ARM / other architectures are not supported by this pre-built binary."
    echo "        You need to recompile from source: see fix_codex/README.md"
    exit 1
fi
echo "[setup] arch: $ARCH OK"

# ── 1. Check prerequisites ────────────────────────────────────────────────────
echo "[setup] checking prerequisites..."

if ! command -v docker &>/dev/null; then
    echo "[ERROR] docker not found. Install Docker first."
    exit 1
fi

if ! command -v harbor &>/dev/null; then
    echo "[ERROR] harbor not found. Install with: uv tool install harbor"
    exit 1
fi

HARBOR_PYTHON=$(head -1 "$(command -v harbor)" | sed 's/^#!//')
if [[ -z "$HARBOR_PYTHON" ]]; then
    echo "[ERROR] cannot determine harbor Python interpreter"
    exit 1
fi
echo "[setup] harbor Python: $HARBOR_PYTHON"

# ── 2. Register fix_codex as a Python package in harbor's environment ─────────
SITE_PACKAGES=$("$HARBOR_PYTHON" -c "import site; print(site.getsitepackages()[0])")
LINK="$SITE_PACKAGES/fix_codex"

if [[ -L "$LINK" && "$(readlink "$LINK")" == "$FIX_CODEX_DIR" ]]; then
    echo "[setup] fix_codex already registered in harbor Python env"
else
    echo "[setup] registering fix_codex in harbor Python env: $LINK -> $FIX_CODEX_DIR"
    ln -sf "$FIX_CODEX_DIR" "$LINK"
fi

# Verify import works
"$HARBOR_PYTHON" -c "from fix_codex.agent import PatchedCodexAgent; print('[setup] import OK')"

# ── 3. Build base Docker image ────────────────────────────────────────────────
# CODEX_BINARY: name of the patched binary file (default: codex-fixed)
CODEX_BINARY="${CODEX_BINARY:-codex-fixed}"

if [[ ! -f "$FIX_CODEX_DIR/$CODEX_BINARY" ]]; then
    echo "[ERROR] patched binary not found: $FIX_CODEX_DIR/$CODEX_BINARY"
    echo "        Set CODEX_BINARY=<filename> if your file has a different name."
    exit 1
fi
echo "[setup] using patched binary: $CODEX_BINARY"

if docker image inspect codex-base:0.135.0 &>/dev/null; then
    echo "[setup] codex-base:0.135.0 already exists, skipping build"
else
    echo "[setup] building codex-base:0.135.0 (this takes ~5 min on first run)..."
    docker build \
        --build-arg CODEX_BINARY="$CODEX_BINARY" \
        -f "$FIX_CODEX_DIR/Dockerfile.base" \
        -t codex-base:0.135.0 \
        "$FIX_CODEX_DIR"
    echo "[setup] codex-base:0.135.0 built successfully"
fi

# ── 4. Verify base image ──────────────────────────────────────────────────────
echo "[setup] verifying base image..."
docker run --rm codex-base:0.135.0 sh -c \
    '. ~/.nvm/nvm.sh && codex --version && echo "[setup] codex OK in image"'

echo ""
echo "✓ Setup complete. Usage:"
echo ""
echo "  # Run a task (edit job yaml to set V_API_KEY and task path):"
echo "  harbor run -c $FIX_CODEX_DIR/example/job_econ_iter0.yaml"
echo ""
echo "  # Run with hooks enabled:"
echo "  CODEX_HOOKS_CONFIG=$FIX_CODEX_DIR/example/hooks.json \\"
echo "  harbor run -c $FIX_CODEX_DIR/example/job_econ_iter0.yaml"
echo ""
echo "  # Build a task image (FROM codex-base:0.135.0):"
echo "  docker build -t hb__<task-name> /path/to/task/environment/"
