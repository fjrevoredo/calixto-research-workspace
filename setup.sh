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

# 1. Verify Python 3.11+
log "Step 1/6: Verifying Python"
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
log "Step 2/6: Installing uv (Python package manager)"
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
log "Step 3/6: Installing Python dependencies"
info "This installs: crawl4ai (~50MB), ddgs (~5MB, renamed from duckduckgo-search), arxiv (~1MB), pyyaml (~1MB)"
if ! uv sync; then
    fail "uv sync failed. Check network and Python version."
fi
info "Python dependencies installed"

# 4. Install Playwright browser via crawl4ai-setup
log "Step 4/6: Installing Playwright + Chromium for Crawl4AI"
info "This downloads Chromium (~450MB) and may take a few minutes"
chromium_ok=0
if uv run crawl4ai-setup 2>/dev/null; then
    chromium_ok=1
else
    warn "crawl4ai-setup encountered an issue; falling back to playwright install chromium"
    if uv run python -m playwright install chromium; then
        chromium_ok=1
    else
        warn "Playwright Chromium install failed. Web scraping may not work until fixed."
        warn "See https://playwright.dev/python/docs/intro for manual install."
    fi
fi

# 5. Verify the install. We verify the live `ddgs` module name.
log "Step 5/6: Verifying installation"
VERIFY_OUTPUT="$(uv run python -c 'import crawl4ai, ddgs, arxiv, yaml; print("ok")' 2>&1)" || {
    fail "Verification import failed: $VERIFY_OUTPUT"
}
info "All required packages importable: $VERIFY_OUTPUT"

# 5b. Verify Chromium is installed and launchable. The default
# scraping provider (Crawl4AI / Playwright) needs a working browser
# to actually fetch pages; without it, search_web.py --no-scrape
# still works, but the default mode (with scraping) is unusable.
# A missing browser is therefore a setup failure, not a warning.
if [ "$chromium_ok" -ne 1 ]; then
    fail "Chromium was not installed successfully. Web scraping is the default mode; without Chromium, search_web.py will not be able to fetch pages. Re-run with explicit: uv run python -m playwright install chromium"
fi
# Browser launch check: ask Playwright where Chromium lives, then
# try to launch it headless and verify the executable responds. We
# use a 30s timeout because the first launch can be slow.
LAUNCH_OUTPUT="$(uv run python -c "
from playwright.sync_api import sync_playwright
import sys
try:
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, args=['--no-sandbox'])
        b.close()
    print('ok')
except Exception as e:
    print(f'launch_failed: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1)" || {
    fail "Chromium install completed but the browser failed to launch: $LAUNCH_OUTPUT"
}
info "Chromium launch check passed"

# 6. Print summary
log "Step 6/6: Setup complete"
info "Total installed: ~500MB (mostly Chromium browser)"
info ""
info "Quick start:"
info "  uv run python scripts/init_workspace.py my-research"
info "  cd workspaces/my-research"
info "  ./setup.sh"
info "  uv run python scripts/search_web.py 'your query' --workspace ."
info ""
info "Run the golden dataset to validate:"
info "  python tests/golden/run.py --use-cache"
info ""
info "See AGENTS.md for full documentation."
