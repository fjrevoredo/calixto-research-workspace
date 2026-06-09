#!/usr/bin/env bash
# install.sh: one-liner installer for Calixto Research Workspace.
#
# Fresh install and update intentionally use different safety rules:
# - fresh install copies the whole toolkit into a verified empty directory
# - update preserves user-owned data, repo metadata, and unknown files
#   unless managed-entry metadata proves the toolkit owns them

set -euo pipefail
shopt -s dotglob nullglob

TARGET_DIR="$(pwd)"
REPO_URL="${CALIXTO_REPO_URL:-https://github.com/calixto/calixto.git}"
REPO_BRANCH="${CALIXTO_REPO_BRANCH:-main}"
REPO_BRANCH_EXPLICIT=0
if [ -n "${CALIXTO_REPO_BRANCH:-}" ]; then
    REPO_BRANCH_EXPLICIT=1
fi
VERSION="${CALIXTO_VERSION:-}"
DRY_RUN=0
NONINTERACTIVE=0
SKIP_DEPS=0
TEST_MODE="${CALIXTO_TEST_MODE:-0}"
TEST_ARCHIVE_URL="${CALIXTO_TEST_ARCHIVE_URL:-}"
TEST_CA_CERT="${CALIXTO_TEST_CA_CERT:-}"

WORKSPACE_MARKERS=(
    "PHILOSOPHY.md"
    "requirements.md"
    "AGENTS.md"
    "runtime"
    "setup.sh"
    "setup.ps1"
    "templates"
    "scripts"
    "providers"
    "skills"
)

usage() {
    cat <<'EOF'
Calixto Research Workspace installer

Usage: install.sh [options]

Options:
  --dry-run            Print what would happen without making changes
  --non-interactive    Skip confirmation prompts
  --skip-deps          Skip running setup.sh / setup.ps1 afterwards
  --version TAG        Install a specific release tag
  --repo URL           Use a different GitHub repository URL
  --branch BRANCH      Install a specific branch (default: main)
  --help               Show this help and exit
EOF
}

log()  { printf '\n=== %s ===\n' "$*"; }
info() { printf '  -> %s\n' "$*"; }
warn() { printf '  !! %s\n' "$*" >&2; }
fail() { printf '  XX %s\n' "$*" >&2; exit 1; }

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run)         DRY_RUN=1; shift ;;
        --non-interactive) NONINTERACTIVE=1; shift ;;
        --skip-deps)       SKIP_DEPS=1; shift ;;
        --version)         VERSION="$2"; shift 2 ;;
        --repo)            REPO_URL="$2"; shift 2 ;;
        --branch)          REPO_BRANCH="$2"; REPO_BRANCH_EXPLICIT=1; shift 2 ;;
        --help|-h)         usage; exit 0 ;;
        *)                 warn "Unknown argument: $1"; usage; exit 1 ;;
    esac
done

command_exists() { command -v "$1" >/dev/null 2>&1; }

python_bin() {
    if command_exists python3; then
        printf '%s\n' python3
        return 0
    fi
    if command_exists python; then
        printf '%s\n' python
        return 0
    fi
    fail "Python 3.11+ is required to run the installer."
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

is_workspace() {
    local marker
    for marker in "${WORKSPACE_MARKERS[@]}"; do
        if [ ! -e "$TARGET_DIR/$marker" ]; then
            return 1
        fi
    done
    return 0
}

selected_ref() {
    if [ -n "$VERSION" ]; then
        printf '%s\n' "$VERSION"
    else
        printf '%s\n' "$REPO_BRANCH"
    fi
}

validate_selector_contract() {
    if [ -n "$VERSION" ] && [ "$REPO_BRANCH_EXPLICIT" -eq 1 ]; then
        fail "Specify either --branch or --version, not both."
    fi
    if [ -n "${CALIXTO_TEST_FAIL_AFTER_REPLACEMENTS:-}" ] && [ "$TEST_MODE" != "1" ]; then
        fail "CALIXTO_TEST_FAIL_AFTER_REPLACEMENTS requires CALIXTO_TEST_MODE=1."
    fi
    if [ -n "$TEST_ARCHIVE_URL" ] && [ "$TEST_MODE" != "1" ]; then
        fail "CALIXTO_TEST_ARCHIVE_URL requires CALIXTO_TEST_MODE=1."
    fi
    if [ -n "$TEST_CA_CERT" ] && [ "$TEST_MODE" != "1" ]; then
        fail "CALIXTO_TEST_CA_CERT requires CALIXTO_TEST_MODE=1."
    fi
}

normalize_repo_url() {
    case "$1" in
        https://github.com/*/*|https://github.com/*/*.git|https://github.com/*/*/)
            printf '%s\n' "${1%/}"
            ;;
        *)
            fail "Repo URL must be https://github.com/<owner>/<repo> (optionally ending in .git)."
            ;;
    esac
}

build_archive_base_url() {
    local repo
    repo="$(normalize_repo_url "$REPO_URL")"
    repo="${repo%.git}"
    printf '%s\n' "$repo"
}

build_source_url() {
    local ref
    ref="$(selected_ref)"
    if [ -n "$TEST_ARCHIVE_URL" ]; then
        printf 'tarball:%s\n' "$TEST_ARCHIVE_URL"
        return 0
    fi
    if command_exists git; then
        if [ "$TEST_MODE" = "1" ]; then
            printf 'git:%s:%s\n' "$REPO_URL" "$ref"
        else
            printf 'git:%s:%s\n' "$(normalize_repo_url "$REPO_URL")" "$ref"
        fi
        return 0
    fi
    if [ -n "$VERSION" ]; then
        printf 'tarball:%s/archive/refs/tags/%s.tar.gz\n' \
            "$(build_archive_base_url)" "$VERSION"
    else
        printf 'tarball:%s/archive/refs/heads/%s.tar.gz\n' \
            "$(build_archive_base_url)" "$REPO_BRANCH"
    fi
}

copy_installer_core() {
    local source_root="$1"
    local staging_dir="$2"
    local core_src="$source_root/scripts/installer_core.py"
    local core_copy="$staging_dir/installer-core.py"
    [ -f "$core_src" ] || fail "Downloaded source is missing scripts/installer_core.py."
    cp "$core_src" "$core_copy"
    printf '%s\n' "$core_copy"
}

run_installer_core() {
    local core_script="$1"
    shift
    local python
    python="$(python_bin)"
    "$python" "$core_script" "$@"
}

extract_archive_source() {
    local url="$1"
    local staging_dir="$2"
    local archive_path="$staging_dir/repo.tar.gz"
    local python
    python="$(python_bin)"
    local curl_args=(-fsSL)
    if [ -n "$TEST_CA_CERT" ]; then
        curl_args+=(--cacert "$TEST_CA_CERT")
    fi
    curl "${curl_args[@]}" "$url" -o "$archive_path"
    "$python" - "$archive_path" "$staging_dir" <<'PY'
import os
import posixpath
import re
import sys
import tarfile
from pathlib import Path

archive = Path(sys.argv[1])
staging = Path(sys.argv[2]).resolve(strict=False)

def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)

def normalize_member(name: str) -> str:
    if not name:
        fail("Archive contains an empty member name.")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in name):
        fail(f"Archive member contains control characters: {name!r}")
    normalized = posixpath.normpath(name)
    if normalized in {".", ""}:
        fail(f"Archive member is not a real path: {name!r}")
    if normalized.startswith("/") or normalized.startswith("\\"):
        fail(f"Archive member uses an absolute path: {name!r}")
    if normalized == ".." or normalized.startswith("../"):
        fail(f"Archive member escapes staging via '..': {name!r}")
    if re.match(r"^[A-Za-z]:", normalized):
        fail(f"Archive member uses a drive-qualified path: {name!r}")
    return normalized

with tarfile.open(archive, "r:gz") as tf:
    members = tf.getmembers()
    if not members:
        fail("Archive is empty.")
    for member in members:
        normalized = normalize_member(member.name)
        if member.issym() or member.islnk():
            link_target = member.linkname or ""
            if not link_target:
                fail(f"Archive link has no target: {member.name!r}")
            normalized_target = posixpath.normpath(
                posixpath.join(posixpath.dirname(normalized), link_target)
            )
            if normalized_target.startswith("/") or normalized_target.startswith("\\"):
                fail(
                    f"Archive link escapes staging via absolute target: "
                    f"{member.name!r} -> {link_target!r}"
                )
            if normalized_target == ".." or normalized_target.startswith("../"):
                fail(
                    f"Archive link escapes staging: "
                    f"{member.name!r} -> {link_target!r}"
                )
            if re.match(r"^[A-Za-z]:", normalized_target):
                fail(
                    f"Archive link uses a drive-qualified target: "
                    f"{member.name!r} -> {link_target!r}"
                )
    tf.extractall(staging)

candidates = []
for child in staging.iterdir():
    if child.name == archive.name:
        continue
    if child.is_dir():
        resolved = child.resolve(strict=False)
        try:
            resolved.relative_to(staging)
        except ValueError:
            fail(f"Extracted directory escapes staging: {child}")
        candidates.append(resolved)

if len(candidates) != 1:
    fail(
        "Archive extraction must produce exactly one top-level directory; "
        f"found {len(candidates)} candidates."
    )

print(str(candidates[0]))
PY
}

cleanup_path() {
    local path="$1"
    [ -e "$path" ] || return 0
    rm -rf "$path"
}

make_temp_staging_dir() {
    mktemp -d "${TMPDIR:-/tmp}/calixto-install.XXXXXX"
}

run_setup_if_requested() {
    local setup_script="$1"
    local context="$2"
    if [ "$SKIP_DEPS" -eq 1 ] || [ "$DRY_RUN" -eq 1 ]; then
        return 0
    fi
    chmod +x "$setup_script" 2>/dev/null || true
    if [ ! -x "$setup_script" ]; then
        return 0
    fi
    log "Running setup.sh"
    if ! (cd "$TARGET_DIR" && bash "$setup_script"); then
        fail "setup.sh failed during $context. Toolkit files are present, but the environment is not ready."
    fi
}

fresh_install() {
    log "Mode: fresh install"
    info "Target directory: $TARGET_DIR"
    info "Repository: $REPO_URL"

    if [ -n "$(ls -A "$TARGET_DIR" 2>/dev/null)" ]; then
        fail "Target directory is not empty. Use a new directory for fresh install."
    fi

    confirm "This will install Calixto Research Workspace into '$TARGET_DIR'. Continue?" || {
        info "Installation cancelled by user."
        exit 0
    }

    local src
    src="$(build_source_url)"
    info "Source: $src"

    if [ "$DRY_RUN" -eq 1 ]; then
        printf '   [dry-run] would fetch source into a staging directory and apply a fresh install\n'
        exit 0
    fi

    local staging
    staging="$(make_temp_staging_dir)"

    local source_root=""
    case "$src" in
        git:*)
            local url="${src#git:}"
            url="${url%:*}"
            local ref="${src##*:}"
            git clone --depth 1 --branch "$ref" "$url" "$staging/repo"
            source_root="$staging/repo"
            ;;
        tarball:*)
            local url="${src#tarball:}"
            source_root="$(extract_archive_source "$url" "$staging")"
            ;;
        *)
            cleanup_path "$staging"
            fail "Unknown source mode: $src"
            ;;
    esac

    local core_script
    core_script="$(copy_installer_core "$source_root" "$staging")"
    if ! run_installer_core \
        "$core_script" \
        apply-fresh \
        --source-root "$source_root" \
        --target-dir "$TARGET_DIR"
    then
        warn "Fresh install failed. Staging preserved at $staging for inspection."
        exit 1
    fi

    cleanup_path "$staging"
    run_setup_if_requested "$TARGET_DIR/setup.sh" "fresh install"

    log "Fresh install complete"
    info "To start: cd $TARGET_DIR && uv run python scripts/init_workspace.py my-research"
}

update_workspace() {
    log "Mode: toolkit update"
    info "Target directory: $TARGET_DIR"
    info "Repository: $REPO_URL"

    local missing=()
    local marker
    for marker in "${WORKSPACE_MARKERS[@]}"; do
        if [ ! -e "$TARGET_DIR/$marker" ]; then
            missing+=("$marker")
        fi
    done
    if [ "${#missing[@]}" -gt 0 ]; then
        fail "Directory looks like a partial Calixto toolkit root. Missing: ${missing[*]}"
    fi

    confirm "This will update Calixto Research Workspace in '$TARGET_DIR'. Continue?" || {
        info "Update cancelled by user."
        exit 0
    }

    local src
    src="$(build_source_url)"
    info "Source: $src"

    if [ "$DRY_RUN" -eq 1 ]; then
        printf '   [dry-run] would fetch source, validate it, and apply an update transaction to toolkit files only\n'
        exit 0
    fi

    local staging
    staging="$(make_temp_staging_dir)"

    local source_root=""
    case "$src" in
        git:*)
            local url="${src#git:}"
            url="${url%:*}"
            local ref="${src##*:}"
            git clone --depth 1 --branch "$ref" "$url" "$staging/repo"
            source_root="$staging/repo"
            ;;
        tarball:*)
            local url="${src#tarball:}"
            source_root="$(extract_archive_source "$url" "$staging")"
            ;;
        *)
            cleanup_path "$staging"
            fail "Unknown source mode: $src"
            ;;
    esac

    local core_script
    core_script="$(copy_installer_core "$source_root" "$staging")"

    if ! run_installer_core \
        "$core_script" \
        recover-transaction \
        --target-dir "$TARGET_DIR"
    then
        cleanup_path "$staging"
        exit 1
    fi

    if ! run_installer_core \
        "$core_script" \
        apply-update \
        --source-root "$source_root" \
        --target-dir "$TARGET_DIR"
    then
        cleanup_path "$staging"
        exit 1
    fi

    cleanup_path "$staging"

    if [ "$SKIP_DEPS" -eq 0 ]; then
        if confirm "Run setup.sh now to update dependencies?"; then
            run_setup_if_requested "$TARGET_DIR/setup.sh" "update"
        fi
    fi

    log "Update complete"
    info "Existing workspaces under $TARGET_DIR/workspaces were left untouched."
    info "To start: cd $TARGET_DIR && uv run python scripts/init_workspace.py my-research"
}

validate_selector_contract

log "Calixto Research Workspace installer"
info "Target: $TARGET_DIR"

if is_workspace; then
    update_workspace
else
    fresh_install
fi
