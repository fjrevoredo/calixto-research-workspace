#!/usr/bin/env bash
# install.sh: One-liner installer for Calixto Research Workspace.
#
# Two modes:
#   1. Fresh install: runs in an empty directory. Clones the repo, copies files,
#      runs setup.sh.
#   2. Workspace update: runs inside an existing Calixto workspace. Backs up user
#      data (especially workspaces/), pulls latest changes, optionally runs setup.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/calixto/calixto/main/install.sh | bash
#   curl -fsSL https://...install.sh | bash -s -- --dry-run
#   curl -fsSL https://...install.sh | bash -s -- --version v0.1.0
#
# Safety:
#   - Never deletes user data without explicit confirmation
#   - Always prompts before making changes
#   - Backs up workspaces/ before updating
#   - Idempotent: safe to re-run
#   - Supports --dry-run for testing

set -euo pipefail

REPO_URL="${CALIXTO_REPO_URL:-https://github.com/calixto/calixto.git}"
REPO_BRANCH="${CALIXTO_REPO_BRANCH:-main}"
VERSION="${CALIXTO_VERSION:-}"
TARGET_DIR="$(pwd)"

# Files/dirs that signal "this is already a Calixto workspace"
WORKSPACE_MARKERS=(
    "PHILOSOPHY.md"
    "requirements.md"
    "AGENTS.md"
    "setup.sh"
    "setup.ps1"
    "templates"
    "scripts"
    "providers"
    "skills"
)

DRY_RUN=0
NONINTERACTIVE=0
SKIP_DEPS=0
BACKUP_DIR=""

usage() {
    cat <<'EOF'
Calixto Research Workspace installer

Usage: install.sh [options]

Options:
  --dry-run            Print what would happen without making changes
  --non-interactive    Skip all confirmation prompts (for automation)
  --skip-deps          Skip running setup.sh / setup.ps1 after install
  --version TAG        Install a specific version tag (default: default branch)
  --repo URL           Use a different repository URL
  --branch BRANCH      Use a different branch (default: main)
  --help               Show this help and exit

Examples:
  # Fresh install in a new directory
  curl -fsSL https://calixto.dev/install.sh | bash

  # Update an existing Calixto workspace
  cd workspaces/my-research && curl -fsSL https://calixto.dev/install.sh | bash

  # Dry run to see what would happen
  curl -fsSL https://calixto.dev/install.sh | bash -s -- --dry-run
EOF
}

log()  { printf '\n=== %s ===\n' "$*"; }
info() { printf '  -> %s\n' "$*"; }
warn() { printf '  !! %s\n' "$*" >&2; }
fail() { printf '  XX %s\n' "$*" >&2; exit 1; }

# Parse arguments
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run)         DRY_RUN=1; shift ;;
        --non-interactive) NONINTERACTIVE=1; shift ;;
        --skip-deps)       SKIP_DEPS=1; shift ;;
        --version)         VERSION="$2"; shift 2 ;;
        --repo)            REPO_URL="$2"; shift 2 ;;
        --branch)          REPO_BRANCH="$2"; shift 2 ;;
        --help|-h)         usage; exit 0 ;;
        *)                 warn "Unknown argument: $1"; usage; exit 1 ;;
    esac
done

run() {
    if [ "$DRY_RUN" -eq 1 ]; then
        printf '   [dry-run] %s\n' "$*"
    else
        "$@"
    fi
}

is_workspace() {
    local marker
    for marker in "${WORKSPACE_MARKERS[@]}"; do
        if [ ! -e "$TARGET_DIR/$marker" ]; then
            return 1
        fi
    done
    return 0
}

confirm() {
    local prompt="$1"
    if [ "$NONINTERACTIVE" -eq 1 ]; then
        info "[non-interactive] auto-confirming: $prompt"
        return 0
    fi
    if [ "$DRY_RUN" -eq 1 ]; then
        printf '   [dry-run] would prompt: %s\n' "$prompt"
        return 0
    fi
    read -r -p "  $prompt (y/n) " response
    case "$response" in
        y|Y|yes|YES) return 0 ;;
        *)           return 1 ;;
    esac
}

command_exists() { command -v "$1" >/dev/null 2>&1; }

# Decide the source we will fetch the repo from
build_source_url() {
    # Prefer git clone if git is available. Fall back to tarball download.
    if command_exists git; then
        if [ -n "$VERSION" ]; then
            echo "git:$REPO_URL:$VERSION"
        else
            echo "git:$REPO_URL:$REPO_BRANCH"
        fi
    else
        # Tarball: convert repo URL to codeload tarball URL
        local tarball_base
        case "$REPO_URL" in
            https://github.com/*) tarball_base="${REPO_URL%.git}/archive/refs/heads" ;;
            *) fail "Cannot derive tarball URL from: $REPO_URL. Install git or set CALIXTO_REPO_URL to a GitHub URL." ;;
        esac
        if [ -n "$VERSION" ]; then
            echo "tarball:${tarball_base}/${VERSION}.tar.gz"
        else
            echo "tarball:${tarball_base}/${REPO_BRANCH}.tar.gz"
        fi
    fi
}

# =================================================================
# Mode 1: Fresh install (current directory is empty)
# =================================================================
fresh_install() {
    log "Mode: fresh install"
    info "Target directory: $TARGET_DIR"
    info "Repository: $REPO_URL (branch: $REPO_BRANCH${VERSION:+, version: $VERSION})"

    # Safety: refuse to install into a non-empty directory
    if [ -n "$(ls -A "$TARGET_DIR" 2>/dev/null)" ]; then
        fail "Target directory is not empty. Use a new directory for fresh install, or run inside an existing Calixto workspace for update mode."
    fi

    confirm "This will clone Calixto Research Workspace into '$TARGET_DIR'. Continue?" || {
        info "Installation cancelled by user."
        exit 0
    }

    local src; src="$(build_source_url)"
    info "Source: $src"

    case "$src" in
        git:*)
            local url="${src#git:}"
            url="${url%:*}"
            local ref="${src##*:}"
            run git clone --depth 1 --branch "$ref" "$url" "$TARGET_DIR/.calixto-tmp"
            run mv "$TARGET_DIR/.calixto-tmp" "$TARGET_DIR/.calixto-stage"
            ;;
        tarball:*)
            local url="${src#tarball:}"
            run curl -fsSL "$url" -o "$TARGET_DIR/.calixto.tar.gz"
            run tar -xzf "$TARGET_DIR/.calixto.tar.gz" -C "$TARGET_DIR"
            # Tarballs extract into <repo>-<ref> directory; move contents up
            run sh -c "shopt -s dotglob && mv $TARGET_DIR/calixto-*/* $TARGET_DIR/ 2>/dev/null || true"
            run rm -rf "$TARGET_DIR/calixto-"*
            run rm -f "$TARGET_DIR/.calixto.tar.gz"
            ;;
    esac

    if [ "$DRY_RUN" -eq 0 ]; then
        # Cleanup the staging dir if we used git
        [ -d "$TARGET_DIR/.calixto-stage" ] && rm -rf "$TARGET_DIR/.calixto-stage"
    fi

    if [ "$SKIP_DEPS" -eq 0 ] && [ "$DRY_RUN" -eq 0 ]; then
        log "Running setup.sh to install dependencies"
        chmod +x "$TARGET_DIR/setup.sh" 2>/dev/null || true
        if [ -x "$TARGET_DIR/setup.sh" ]; then
            (cd "$TARGET_DIR" && bash ./setup.sh) || warn "setup.sh had issues. Re-run with ./setup.sh to retry."
        fi
    fi

    log "Fresh install complete"
    info "To start: cd $TARGET_DIR && python scripts/init_workspace.py my-research"
}

# =================================================================
# Mode 2: Workspace update (current directory is already a Calixto workspace)
# =================================================================
update_workspace() {
    log "Mode: workspace update"
    info "Target directory: $TARGET_DIR"
    info "Repository: $REPO_URL (branch: $REPO_BRANCH${VERSION:+, version: $VERSION})"

    # Verify compatibility: all required files/dirs must be present
    local missing=()
    local marker
    for marker in "${WORKSPACE_MARKERS[@]}"; do
        if [ ! -e "$TARGET_DIR/$marker" ]; then
            missing+=("$marker")
        fi
    done
    if [ ${#missing[@]} -gt 0 ]; then
        fail "Directory looks like a partial Calixto workspace. Missing: ${missing[*]}. Run from a complete Calixto workspace, or use a new directory for fresh install."
    fi

    confirm "This will update Calixto Research Workspace in '$TARGET_DIR'. User data (workspaces/, notes/, outputs/, config files) will be preserved. Continue?" || {
        info "Update cancelled by user."
        exit 0
    }

    # Backup user data
    local timestamp; timestamp="$(date +%Y%m%d-%H%M%S)"
    BACKUP_DIR="$TARGET_DIR/.calixto-backup-$timestamp"
    info "Backing up user data to $BACKUP_DIR"
    run mkdir -p "$BACKUP_DIR"
    for item in workspaces notes outputs config.json; do
        if [ -e "$TARGET_DIR/$item" ]; then
            run cp -r "$TARGET_DIR/$item" "$BACKUP_DIR/"
        fi
    done
    # templates/workspace is toolkit-owned, not user data; skip
    # Also back up any *.local config overrides
    run sh -c "cp $TARGET_DIR/*.local $BACKUP_DIR/ 2>/dev/null || true"

    # Fetch the latest source
    local src; src="$(build_source_url)"
    info "Source: $src"
    local staging="$TARGET_DIR/.calixto-update"
    run rm -rf "$staging"
    run mkdir -p "$staging"

    case "$src" in
        git:*)
            local url="${src#git:}"; url="${url%:*}"
            local ref="${src##*:}"
            run git clone --depth 1 --branch "$ref" "$url" "$staging/repo"
            run sh -c "shopt -s dotglob && cp -r $staging/repo/* $TARGET_DIR/ 2>/dev/null || true"
            ;;
        tarball:*)
            local url="${src#tarball:}"
            run curl -fsSL "$url" -o "$staging/repo.tar.gz"
            run tar -xzf "$staging/repo.tar.gz" -C "$staging"
            run sh -c "shopt -s dotglob && cp -r $staging/calixto-*/* $TARGET_DIR/ 2>/dev/null || true"
            ;;
    esac

    # Restore user data over the freshly installed files
    info "Restoring user data from backup"
    for item in workspaces notes outputs; do
        if [ -e "$BACKUP_DIR/$item" ]; then
            run rm -rf "$TARGET_DIR/$item"
            run cp -r "$BACKUP_DIR/$item" "$TARGET_DIR/"
        fi
    done
    # Note: templates/workspace is part of the toolkit, not user data

    # Cleanup staging
    if [ "$DRY_RUN" -eq 0 ]; then
        rm -rf "$staging"
    fi

    if [ "$SKIP_DEPS" -eq 0 ] && [ "$DRY_RUN" -eq 0 ]; then
        if confirm "Run setup.sh now to update dependencies?"; then
            log "Running setup.sh"
            chmod +x "$TARGET_DIR/setup.sh" 2>/dev/null || true
            (cd "$TARGET_DIR" && bash ./setup.sh) || warn "setup.sh had issues. Re-run with ./setup.sh to retry."
        fi
    fi

    log "Update complete"
    info "Backup preserved at: $BACKUP_DIR"
    info "To start: cd $TARGET_DIR && python scripts/init_workspace.py my-research"
}

# =================================================================
# Main
# =================================================================
log "Calixto Research Workspace installer"
info "Target: $TARGET_DIR"

if is_workspace; then
    update_workspace
else
    fresh_install
fi
