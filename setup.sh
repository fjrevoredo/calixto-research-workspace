#!/usr/bin/env bash
# setup.sh: One-shot environment setup for Calixto Research Workspace.
# Idempotent. Safe to re-run. Prints every step clearly.
#
# Usage: ./setup.sh
# Requires: Python 3.11+, internet, ~500MB disk for Playwright/Chromium.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

log()  { printf '\n=== %s ===\n' "$*"; }
info() { printf '  -> %s\n' "$*"; }
warn() { printf '  !! %s\n' "$*" >&2; }
fail() { printf '  XX %s\n' "$*" >&2; exit 1; }

command_exists() { command -v "$1" >/dev/null 2>&1; }
repair_incomplete_venv() {
    local venv_dir="$REPO_ROOT/.venv"
    local venv_python="$venv_dir/bin/python"
    if [ -d "$venv_dir" ] && [ ! -x "$venv_python" ]; then
        warn "Detected incomplete virtual environment at '$venv_dir'. Removing it before uv sync."
        rm -rf "$venv_dir" || fail "Failed to remove incomplete virtual environment at '$venv_dir'"
    fi
}

# 1. Verify Python 3.11+
log "Step 1/7: Verifying Python"
if ! command_exists python3 && ! command_exists python; then
    fail "Python not found. Install Python 3.11+: https://www.python.org/downloads/"
fi
PYTHON_BIN="$(command_exists python3 && echo python3 || echo python)"
PY_VERSION="$("$PYTHON_BIN" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
info "Found Python $PY_VERSION"
PY_MAJOR="$(echo "$PY_VERSION" | cut -d. -f1)"
PY_MINOR="$(echo "$PY_VERSION" | cut -d. -f2)"
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    fail "Python 3.11+ required, found $PY_VERSION. Upgrade at https://www.python.org/downloads/"
fi

# 2. Install uv if missing
log "Step 2/7: Installing uv (Python package manager)"
if ! command_exists uv; then
    info "uv not found, installing via official installer..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # shellcheck disable=SC1091
    if [ -f "$HOME/.cargo/env" ]; then source "$HOME/.cargo/env"; fi
    if ! command_exists uv; then
        fail "uv install failed. See https://docs.astral.sh/uv/getting-started/installation/"
    fi
fi
UV_VERSION="$(uv --version)"
info "uv ready: $UV_VERSION"

# 3. Sync dependencies via uv
log "Step 3/7: Installing Python dependencies"
info "This installs: crawl4ai (~50MB), ddgs (~5MB, renamed from duckduckgo-search), arxiv (~1MB), pyyaml (~1MB)"
repair_incomplete_venv
if ! uv sync --locked; then
    fail "uv sync failed. Check network and Python version."
fi
info "Python dependencies installed"

# 4. Verify the root toolkit environment itself.
log "Step 4/7: Verifying toolkit dependencies"
VERIFY_OUTPUT="$(uv run python -c 'import crawl4ai, ddgs, arxiv, yaml; print("ok")' 2>&1)" || {
    fail "Verification import failed: $VERIFY_OUTPUT"
}
info "All required packages importable: $VERIFY_OUTPUT"

# 5. Prepare the shared managed workspace runtime.
log "Step 5/7: Preparing managed workspace runtime"
info "This prepares the shared workspace runtime once and installs Chromium only when missing"
MANAGED_OUTPUT="$(uv run python scripts/managed_runtime.py prepare 2>&1)" || {
    fail "Managed runtime preparation failed: $MANAGED_OUTPUT"
}
info "Managed runtime ready"

# 6. Install the lightweight launcher shim.
log "Step 6/7: Installing calixto launcher"
SHIM_OUTPUT="$(uv run python scripts/install_calixto_shim.py --toolkit-root "$REPO_ROOT" 2>&1)" || {
    fail "Launcher shim installation failed: $SHIM_OUTPUT"
}
info "Launcher shim ready"
if printf '%s' "$SHIM_OUTPUT" | grep -q 'PATH_MISSING::'; then
    SHIM_DIR="$(printf '%s' "$SHIM_OUTPUT" | sed -n 's/^PATH_MISSING:://p')"
    warn "The launcher directory is not currently on PATH: $SHIM_DIR"
    warn "Add it to PATH or use the fallback command: uv run --project \"$REPO_ROOT\" calixto ..."
fi

# 7. Print summary
log "Step 7/7: Setup complete"
info "Total installed: ~500MB (mostly Chromium browser)"
info ""
info "Quick start:"
info "  calixto research 'your question' --agent none"
info "Fallback if the launcher is not on PATH:"
info "  uv run --project \"$REPO_ROOT\" calixto research 'your question' --agent none"
info ""
info "Run the golden dataset to validate:"
info "  python tests/golden/run.py --use-cache"
info ""
info "See AGENTS.md for full documentation."
