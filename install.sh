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
#
# This script is shebang'd for bash. It uses bash builtins (shopt, [[ ]],
# mapfile, arrays) directly; it does NOT invoke `sh -c` to run bash
# fragments, and it does not rely on `/bin/sh` being bash. Every command
# that mutates state is checked for nonzero exit under `set -e`.

set -euo pipefail

# Enable dotglob for the current shell so patterns like `mv staging/* target/`
# include dotfiles. This is the documented bash 4+ way; we avoid the
# historical `sh -c 'shopt -s dotglob && ...'` workaround.
shopt -s dotglob nullglob


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

# move_staging_contents: move every entry from $1 into $2 (including dotfiles).
# Uses nullglob + dotglob (enabled at script top) to avoid subshells.
move_staging_contents() {
    local src="$1"
    local dst="$2"
    if [ ! -d "$src" ]; then
        return 0
    fi
    # Iterate entries, including hidden ones. nullglob turns "no match" into
    # the empty list rather than a literal pattern.
    local entry
    for entry in "$src"/* "$src"/.[!.]*; do
        [ -e "$entry" ] || continue
        # -f to overwrite existing files, since a previous partial install
        # may have left them in place.
        mv -f "$entry" "$dst/"
    done
}

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
            # Move cloned contents (including dotfiles) up to TARGET_DIR.
            # This is a bash-native loop; no `sh -c` indirection, no `|| true`
            # suppression. If the staging dir is missing the loop is a no-op,
            # and the marker check below will catch the empty install.
            move_staging_contents "$TARGET_DIR/.calixto-tmp" "$TARGET_DIR"
            ;;
        tarball:*)
            local url="${src#tarball:}"
            run curl -fsSL "$url" -o "$TARGET_DIR/.calixto.tar.gz"
            run tar -xzf "$TARGET_DIR/.calixto.tar.gz" -C "$TARGET_DIR"
            # Tarballs extract into <repo>-<ref>/ directory. Find it and
            # move its contents up.
            local extracted_dir=""
            # The pattern `calixto-*/` matches a single directory. If
            # multiple exist (shouldn't happen), the first wins.
            for entry in calixto-*/; do
                [ -d "$entry" ] || continue
                extracted_dir="$entry"
                break
            done
            if [ -z "$extracted_dir" ]; then
                fail "Tarball extraction did not produce an expected calixto-* directory."
            fi
            move_staging_contents "$TARGET_DIR/$extracted_dir" "$TARGET_DIR"
            # Cleanup tarball artifacts
            run rm -rf "$TARGET_DIR/calixto-"*
            run rm -f "$TARGET_DIR/.calixto.tar.gz"
            ;;
    esac

    if [ "$DRY_RUN" -eq 0 ]; then
        # Verify the install actually populated the target before cleaning up.
        # If required workspace markers are missing, fail and preserve the
        # staging directory so the user can inspect it.
        local missing=()
        local marker
        for marker in "${WORKSPACE_MARKERS[@]}"; do
            if [ ! -e "$TARGET_DIR/$marker" ]; then
                missing+=("$marker")
            fi
        done
        if [ ${#missing[@]} -gt 0 ]; then
            warn "Fresh install appears incomplete. Missing markers: ${missing[*]}"
            warn "Staging preserved at $TARGET_DIR/.calixto-tmp for inspection."
            fail "Fresh install did not produce a valid Calixto workspace."
        fi
        # All markers present: clean up staging and any leftover tarball
        [ -d "$TARGET_DIR/.calixto-tmp" ] && rm -rf "$TARGET_DIR/.calixto-tmp"
        [ -d "$TARGET_DIR/calixto-"* ] && rm -rf "$TARGET_DIR/calixto-"*
        [ -f "$TARGET_DIR/.calixto.tar.gz" ] && rm -f "$TARGET_DIR/.calixto.tar.gz"
    fi

    if [ "$SKIP_DEPS" -eq 0 ] && [ "$DRY_RUN" -eq 0 ]; then
        log "Running setup.sh to install dependencies"
        chmod +x "$TARGET_DIR/setup.sh" 2>/dev/null || true
        if [ -x "$TARGET_DIR/setup.sh" ]; then
            # Track whether setup.sh succeeded. The fresh-install
            # contract is "after this script exits 0, the environment
            # is usable"; a failed setup must not leave the user with
            # a "Fresh install complete" message.
            local setup_ok=0
            (cd "$TARGET_DIR" && bash ./setup.sh) && setup_ok=1
            if [ "$setup_ok" -ne 1 ]; then
                fail "setup.sh failed. Toolkit files are installed at $TARGET_DIR, but the Python environment is not usable. Re-run $TARGET_DIR/setup.sh manually to diagnose, or re-run this installer with --skip-deps to install files without setting up the environment."
            fi
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

    # Backup user data. We back up the same set on every platform:
    # workspaces/, notes/, outputs/, config.json, and any *.local override
    # files in the root. These are all "user-owned"; toolkit files
    # (templates/, scripts/, etc.) are not.
    local timestamp; timestamp="$(date +%Y%m%d-%H%M%S)"
    BACKUP_DIR="$TARGET_DIR/.calixto-backup-$timestamp"
    info "Backing up user data to $BACKUP_DIR"
    run mkdir -p "$BACKUP_DIR"
    for item in workspaces notes outputs config.json; do
        if [ -e "$TARGET_DIR/$item" ]; then
            run cp -r "$TARGET_DIR/$item" "$BACKUP_DIR/"
        fi
    done
    # Also back up any *.local config overrides. nullglob turns the
    # pattern into the empty list when no match; the for loop is then a
    # no-op (no `|| true` needed because there is no failing command).
    for entry in "$TARGET_DIR"/*.local; do
        [ -e "$entry" ] || continue
        run cp "$entry" "$BACKUP_DIR/"
    done

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
            move_staging_contents "$staging/repo" "$TARGET_DIR"
            ;;
        tarball:*)
            local url="${src#tarball:}"
            run curl -fsSL "$url" -o "$staging/repo.tar.gz"
            run tar -xzf "$staging/repo.tar.gz" -C "$staging"
            local extracted_dir=""
            for entry in "$staging"/calixto-*/; do
                [ -d "$entry" ] || continue
                extracted_dir="$entry"
                break
            done
            if [ -z "$extracted_dir" ]; then
                fail "Tarball extraction did not produce an expected calixto-* directory."
            fi
            move_staging_contents "$extracted_dir" "$TARGET_DIR"
            ;;
    esac

    # Restore user data over the freshly installed files. config.json
    # and *.local overrides are restored along with the data dirs so
    # user-owned config survives the update.
    info "Restoring user data from backup"
    for item in workspaces notes outputs config.json; do
        if [ -e "$BACKUP_DIR/$item" ]; then
            run rm -rf "$TARGET_DIR/$item"
            run cp -r "$BACKUP_DIR/$item" "$TARGET_DIR/"
        fi
    done
    for entry in "$BACKUP_DIR"/*.local; do
        [ -e "$entry" ] || continue
        run cp "$entry" "$TARGET_DIR/"
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
            # Track setup success: a failed setup must not leave the
            # user with "Update complete". The user's data is safe
            # (restored from $BACKUP_DIR) but the environment is not
            # in a known-good state.
            local setup_ok=0
            (cd "$TARGET_DIR" && bash ./setup.sh) && setup_ok=1
            if [ "$setup_ok" -ne 1 ]; then
                fail "setup.sh failed during update. Toolkit files were updated and user data restored from $BACKUP_DIR, but the Python environment is not usable. Re-run $TARGET_DIR/setup.sh manually to diagnose, or re-run this installer with --skip-deps to apply files without touching the environment."
            fi
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
