#!/usr/bin/env bash
# setup.sh: bootstrap a standalone Calixto research workspace.

set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$WORKSPACE_ROOT"

log()  { printf '\n=== %s ===\n' "$*"; }
info() { printf '  -> %s\n' "$*"; }
warn() { printf '  !! %s\n' "$*" >&2; }
fail() { printf '  XX %s\n' "$*" >&2; exit 1; }

command_exists() { command -v "$1" >/dev/null 2>&1; }

log "Step 1/5: Verifying Python"
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

log "Step 2/5: Installing uv"
if ! command_exists uv; then
    info "uv not found, installing via official installer..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # shellcheck disable=SC1091
    if [ -f "$HOME/.cargo/env" ]; then source "$HOME/.cargo/env"; fi
    if ! command_exists uv; then
        fail "uv install failed. See https://docs.astral.sh/uv/getting-started/installation/"
    fi
fi
info "uv ready: $(uv --version)"

log "Step 3/5: Syncing workspace dependencies"
if ! uv sync; then
    fail "uv sync failed. Check network access and Python version."
fi
info "Workspace dependencies installed"

log "Step 4/5: Installing Playwright Chromium"
chromium_ok=0
if uv run crawl4ai-setup 2>/dev/null; then
    chromium_ok=1
else
    warn "crawl4ai-setup encountered an issue; falling back to playwright install chromium"
    if uv run python -m playwright install chromium; then
        chromium_ok=1
    else
        warn "Playwright Chromium install failed. Web scraping will not work until fixed."
        warn "See https://playwright.dev/python/docs/intro for manual install."
    fi
fi

log "Step 5/5: Verifying workspace runtime"
VERIFY_OUTPUT="$(uv run python -c 'import crawl4ai, ddgs, arxiv, yaml; print("ok")' 2>&1)" || {
    fail "Verification import failed: $VERIFY_OUTPUT"
}
info "All required packages importable: $VERIFY_OUTPUT"
if [ "$chromium_ok" -ne 1 ]; then
    fail "Chromium was not installed successfully. Web scraping is the default mode; without Chromium, search_web.py will not be able to fetch pages. Re-run with explicit: uv run python -m playwright install chromium"
fi

log "Workspace ready"
info "Next steps:"
info "  update config.json with your research question"
info "  uv run python scripts/search_web.py 'your query' --workspace ."
info "  uv run python scripts/workspace_info.py audit ."
