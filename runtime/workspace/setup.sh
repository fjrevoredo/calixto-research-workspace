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
repair_incomplete_venv() {
    local venv_dir="$WORKSPACE_ROOT/.venv"
    local venv_python="$venv_dir/bin/python"
    if [ -d "$venv_dir" ] && [ ! -x "$venv_python" ]; then
        warn "Detected incomplete virtual environment at '$venv_dir'. Removing it before uv sync."
        rm -rf "$venv_dir" || fail "Failed to remove incomplete virtual environment at '$venv_dir'"
    fi
}

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
repair_incomplete_venv
if ! uv sync --locked; then
    fail "uv sync failed. Check network access and Python version."
fi
info "Workspace dependencies installed"

log "Step 4/5: Verifying workspace runtime"
PROBE_OUTPUT="$(uv run python scripts/runtime_probe.py 2>&1)" || true
if printf '%s' "$PROBE_OUTPUT" | grep -Eq '"browser_ready"[[:space:]]*:[[:space:]]*true'; then
    info "Workspace runtime already has a working browser"
else
    if printf '%s' "$PROBE_OUTPUT" | grep -q '"error": "missing_browser"'; then
        info "Chromium is missing; installing it for this standalone workspace"
        INSTALL_OUTPUT="$(uv run python -m playwright install chromium 2>&1)" || {
            fail "Chromium install failed: $INSTALL_OUTPUT"
        }
        PROBE_OUTPUT="$(uv run python scripts/runtime_probe.py 2>&1)" || {
            fail "Workspace runtime probe still failed after browser install: $PROBE_OUTPUT"
        }
    else
        fail "Workspace runtime probe failed: $PROBE_OUTPUT"
    fi
fi

log "Step 5/5: Workspace ready"

info "Next steps:"
info "  If this workspace lives under the creating toolkit root, you can reopen it with calixto open from there."
info "  If it was copied elsewhere, this local .venv is now the supported runtime."
info "  update config.json with your research question"
info "  uv run python scripts/search_web.py 'your query' --workspace ."
info "  uv run python scripts/workspace_info.py audit ."
