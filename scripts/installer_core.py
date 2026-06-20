"""installer_core.py: shared install/update application logic.

This helper is invoked by both one-liner installers after they have fetched a
candidate source tree into staging. It owns the filesystem contracts that must
behave identically on Unix and Windows:

- fresh installs copy the complete toolkit into an empty target
- updates preserve protected user data and repo metadata
- unknown collisions abort before mutation
- managed-entry metadata controls removal of obsolete toolkit entries
- updates roll back replaced toolkit entries on failure

The module intentionally uses only the Python standard library so the
installers can rely on it before project dependencies are installed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import traceback
from pathlib import Path

WORKSPACE_MARKERS = (
    "PHILOSOPHY.md",
    "requirements.md",
    "AGENTS.md",
    "runtime",
    "setup.sh",
    "setup.ps1",
    "templates",
    "scripts",
    "providers",
    "skills",
)

PROTECTED_UPDATE_NAMES = {
    ".git",
    "workspaces",
    "notes",
    "outputs",
    "config.json",
}

FRESH_REJECTED_SOURCE_DIRS = {"workspaces", "notes", "outputs"}

MANAGED_ENTRIES_FILENAME = ".calixto-managed-entries"
TOOLKIT_INSTALL_METADATA_FILENAME = ".calixto-toolkit-install.json"
TRANSACTION_DIRNAME = ".calixto-update-transaction"
STATE_FILENAME = "state"
APPLIED_FILENAME = "applied.txt"
REPLACED_FILENAME = "replaced.txt"
ADDED_FILENAME = "added.txt"
DIAGNOSTICS_DIRNAME = "diagnostics"
SOURCE_DIRNAME = "source"
ROLLBACK_DIRNAME = "rollback"

LEGACY_MANAGED_ALLOWLIST = {
    ".gitignore",
    ".python-version",
    "AGENTS.md",
    "LICENSE",
    "PHILOSOPHY.md",
    "README.md",
    "adapters",
    "docs",
    "examples",
    "install.ps1",
    "install.sh",
    "providers",
    "pyproject.toml",
    "requirements.md",
    "runtime",
    "scripts",
    "setup.ps1",
    "setup.sh",
    "skills",
    "templates",
    "tests",
}

TEST_MODE_ENV = "CALIXTO_TEST_MODE"
TEST_FAIL_AFTER_ENV = "CALIXTO_TEST_FAIL_AFTER_REPLACEMENTS"


class InstallerError(RuntimeError):
    """Raised when installer application logic cannot continue safely."""


def _is_test_mode() -> bool:
    return os.environ.get(TEST_MODE_ENV) == "1"


def _contains_control_characters(name: str) -> bool:
    return any(ord(ch) < 32 or ord(ch) == 127 for ch in name)


def _validate_entry_name(name: str) -> None:
    if not name:
        raise InstallerError("Encountered an empty top-level entry name.")
    if "\n" in name or "\r" in name or _contains_control_characters(name):
        raise InstallerError(
            f"Entry name {name!r} contains control characters and is not supported."
        )


def _path_within(root: Path, candidate: Path) -> bool:
    root_resolved = root.resolve(strict=False)
    candidate_resolved = candidate.resolve(strict=False)
    try:
        candidate_resolved.relative_to(root_resolved)
        return True
    except ValueError:
        return False


def _is_reparse_point(path: Path) -> bool:
    attrs = getattr(path.lstat(), "st_file_attributes", 0)
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(flag and attrs & flag)


def _validate_link(root: Path, path: Path) -> None:
    if _is_reparse_point(path) and not path.is_symlink():
        raise InstallerError(
            f"Unsupported Windows reparse point in staged source: {path}"
        )
    target = os.readlink(path)
    if not target:
        raise InstallerError(f"Symlink without a target in staged source: {path}")
    if _contains_control_characters(target):
        raise InstallerError(f"Symlink target for {path} contains control characters.")
    resolved_target = (path.parent / target).resolve(strict=False)
    if not _path_within(root, resolved_target):
        raise InstallerError(
            f"Symlink escapes the staged source tree: {path} -> {target}"
        )


def _validate_source_tree(root: Path) -> None:
    if not root.is_dir():
        raise InstallerError(f"Staged source root does not exist: {root}")
    root = root.resolve(strict=False)
    stack = [root]
    while stack:
        current = stack.pop()
        for entry in sorted(current.iterdir(), key=lambda item: item.name):
            _validate_entry_name(entry.name)
            if entry.is_symlink():
                _validate_link(root, entry)
                continue
            if _is_reparse_point(entry):
                raise InstallerError(
                    f"Unsupported Windows reparse point in staged source: {entry}"
                )
            mode = entry.lstat().st_mode
            if stat.S_ISDIR(mode):
                stack.append(entry)
                continue
            if stat.S_ISREG(mode):
                continue
            if stat.S_ISLNK(mode):
                _validate_link(root, entry)
                continue
            raise InstallerError(
                f"Unsupported special file in staged source: {entry}"
            )


def _missing_workspace_markers(root: Path) -> list[str]:
    return [name for name in WORKSPACE_MARKERS if not (root / name).exists()]


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _append_line(path: Path, value: str) -> None:
    _validate_entry_name(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"{value}\n")


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    values = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        _validate_entry_name(line)
        values.append(line)
    return values


def _top_level_entries(root: Path) -> list[Path]:
    return sorted(root.iterdir(), key=lambda item: item.name)


def _iter_root_local_overrides(root: Path) -> list[Path]:
    return sorted(
        [
            path
            for path in root.iterdir()
            if path.is_file() and path.name.endswith(".local")
        ],
        key=lambda item: item.name,
    )


def _managed_names_from_source_root(source_root: Path) -> list[str]:
    managed = []
    for entry in _top_level_entries(source_root):
        name = entry.name
        if name in {".git", MANAGED_ENTRIES_FILENAME, TRANSACTION_DIRNAME}:
            continue
        if name in PROTECTED_UPDATE_NAMES or name.endswith(".local"):
            continue
        managed.append(name)
    return managed


def _write_managed_entries(target_dir: Path, names: list[str]) -> None:
    cleaned = sorted(dict.fromkeys(names))
    for name in cleaned:
        _validate_entry_name(name)
    payload = "".join(f"{name}\n" for name in cleaned)
    _write_text(target_dir / MANAGED_ENTRIES_FILENAME, payload)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    _write_text(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def _load_previous_managed_entries(target_dir: Path) -> set[str]:
    managed_path = target_dir / MANAGED_ENTRIES_FILENAME
    if managed_path.exists():
        return set(_read_lines(managed_path))
    return set(LEGACY_MANAGED_ALLOWLIST)


def _git_output(repo_root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _source_git_commit(source_root: Path) -> str | None:
    return _git_output(source_root, "rev-parse", "HEAD")


def _source_git_ref_name(source_root: Path) -> str | None:
    return _git_output(source_root, "symbolic-ref", "--short", "-q", "HEAD")


def _source_git_history_mode(source_root: Path) -> str:
    shallow = _git_output(source_root, "rev-parse", "--is-shallow-repository")
    if shallow == "true":
        return "shallow"
    if shallow == "false":
        return "full"
    return "unavailable"


def _source_git_build_number(source_root: Path, history_mode: str) -> int | None:
    if history_mode != "full":
        return None
    raw = _git_output(source_root, "rev-list", "--count", "HEAD")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _toolkit_install_metadata_payload(
    source_root: Path,
    *,
    repo_url: str,
    selector_kind: str,
    selector_value: str | None,
) -> dict[str, object]:
    history_mode = _source_git_history_mode(source_root)
    return {
        "metadata_version": 1,
        "repo_url": repo_url,
        "selector_kind": selector_kind,
        "selector_value": selector_value or None,
        "toolkit_commit": _source_git_commit(source_root),
        "toolkit_ref_name": _source_git_ref_name(source_root),
        "toolkit_build_number": _source_git_build_number(source_root, history_mode),
        "source_history": history_mode,
    }


def _write_toolkit_install_metadata(
    source_root: Path,
    target_dir: Path,
    *,
    repo_url: str,
    selector_kind: str,
    selector_value: str | None,
) -> None:
    payload = _toolkit_install_metadata_payload(
        source_root,
        repo_url=repo_url,
        selector_kind=selector_kind,
        selector_value=selector_value,
    )
    _write_json(target_dir / TOOLKIT_INSTALL_METADATA_FILENAME, payload)


def _validate_source_contract(source_root: Path, mode: str) -> None:
    missing = _missing_workspace_markers(source_root)
    if missing:
        joined = ", ".join(missing)
        raise InstallerError(
            f"Staged source is missing required toolkit markers: {joined}"
        )
    if (source_root / MANAGED_ENTRIES_FILENAME).exists():
        raise InstallerError(
            "Downloaded source includes .calixto-managed-entries, but that file "
            "must be generated by the installer."
        )
    if (source_root / TOOLKIT_INSTALL_METADATA_FILENAME).exists():
        raise InstallerError(
            "Downloaded source includes .calixto-toolkit-install.json, but that file "
            "must be generated by the installer."
        )
    if (source_root / TRANSACTION_DIRNAME).exists():
        raise InstallerError(
            "Downloaded source includes .calixto-update-transaction, which is "
            "reserved installer state."
        )
    for directory_name in sorted(FRESH_REJECTED_SOURCE_DIRS):
        path = source_root / directory_name
        if path.exists():
            raise InstallerError(
                f"Downloaded source contains protected user data directory: {directory_name}"
            )
    local_overrides = _iter_root_local_overrides(source_root)
    if local_overrides:
        names = ", ".join(path.name for path in local_overrides)
        raise InstallerError(
            f"Downloaded source contains root *.local overrides, which are user-owned: {names}"
        )
    _validate_source_tree(source_root)
    if mode == "fresh":
        return
    for protected in ("workspaces", "notes", "outputs"):
        if (source_root / protected).exists():
            raise InstallerError(
                f"Downloaded update source unexpectedly includes {protected}/."
            )


def _hash_bytes(path: Path) -> bytes:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.digest()


def _hash_path(path: Path) -> str:
    hasher = hashlib.sha256()

    def update_entry(current: Path, relative: Path) -> None:
        if current.is_symlink():
            target = os.readlink(current)
            hasher.update(b"L")
            hasher.update(str(relative).encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(target.encode("utf-8", errors="surrogateescape"))
            return
        mode = current.lstat().st_mode
        if stat.S_ISDIR(mode):
            hasher.update(b"D")
            hasher.update(str(relative).encode("utf-8"))
            hasher.update(b"\0")
            for child in sorted(current.iterdir(), key=lambda item: item.name):
                update_entry(child, relative / child.name)
            return
        if stat.S_ISREG(mode):
            hasher.update(b"F")
            hasher.update(str(relative).encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(_hash_bytes(current))
            return
        raise InstallerError(f"Cannot hash unsupported filesystem entry: {current}")

    update_entry(path, Path(path.name))
    return hasher.hexdigest()


def _directory_identity_snapshot(path: Path) -> str:
    stat_result = path.lstat()
    return "|".join(
        [
            "dir",
            path.name,
            str(getattr(stat_result, "st_dev", "")),
            str(getattr(stat_result, "st_ino", "")),
            str(stat_result.st_mode),
            str(stat_result.st_mtime_ns),
        ]
    )


def _protected_path_snapshot(path: Path) -> str:
    if path.is_symlink():
        return f"link|{path.name}|{os.readlink(path)}"
    mode = path.lstat().st_mode
    if stat.S_ISDIR(mode):
        # Protected directories such as workspaces/ and .git/ can be large.
        # The installer never mutates their contents, so a shallow identity
        # snapshot is sufficient to detect accidental replacement/removal
        # without turning updates into an O(total workspace bytes) hash walk.
        return _directory_identity_snapshot(path)
    return _hash_path(path)


def _protected_snapshots(target_dir: Path) -> dict[str, str]:
    snapshots: dict[str, str] = {}
    for name in sorted(PROTECTED_UPDATE_NAMES):
        path = target_dir / name
        if path.exists():
            snapshots[name] = _protected_path_snapshot(path)
    for override in _iter_root_local_overrides(target_dir):
        snapshots[override.name] = _protected_path_snapshot(override)
    return snapshots


def _assert_protected_unchanged(
    target_dir: Path, before: dict[str, str], label: str
) -> None:
    after = _protected_snapshots(target_dir)
    if before != after:
        raise InstallerError(
            f"{label} changed protected user data or repo metadata during update."
        )


def _move_path(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))


def _remove_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
        return
    path.unlink()


def _build_update_plan(source_root: Path, target_dir: Path) -> dict[str, list[str]]:
    previous_managed = _load_previous_managed_entries(target_dir)
    source_entries = {
        entry.name: entry
        for entry in _top_level_entries(source_root)
        if entry.name not in {".git", MANAGED_ENTRIES_FILENAME, TRANSACTION_DIRNAME}
        and entry.name not in PROTECTED_UPDATE_NAMES
        and not entry.name.endswith(".local")
    }
    conflicts: list[str] = []
    replacements: list[str] = []
    additions: list[str] = []
    removals: list[str] = []

    for name in sorted(source_entries):
        target_path = target_dir / name
        if target_path.exists() or target_path.is_symlink():
            if name in previous_managed:
                replacements.append(name)
            else:
                conflicts.append(name)
        else:
            additions.append(name)

    for name in sorted(previous_managed):
        target_path = target_dir / name
        if name in source_entries:
            continue
        if name in PROTECTED_UPDATE_NAMES:
            continue
        if name in {MANAGED_ENTRIES_FILENAME, TRANSACTION_DIRNAME}:
            continue
        if target_path.exists() or target_path.is_symlink():
            removals.append(name)

    return {
        "replacements": replacements,
        "additions": additions,
        "removals": removals,
        "conflicts": conflicts,
        "managed_next": sorted(source_entries),
        "apply_order": sorted(replacements + additions),
    }


def _transaction_paths(target_dir: Path) -> dict[str, Path]:
    transaction_dir = target_dir / TRANSACTION_DIRNAME
    return {
        "transaction": transaction_dir,
        "state": transaction_dir / STATE_FILENAME,
        "source": transaction_dir / SOURCE_DIRNAME,
        "rollback": transaction_dir / ROLLBACK_DIRNAME,
        "diagnostics": transaction_dir / DIAGNOSTICS_DIRNAME,
        "applied": transaction_dir / APPLIED_FILENAME,
        "replaced": transaction_dir / REPLACED_FILENAME,
        "added": transaction_dir / ADDED_FILENAME,
    }


def _prepare_generated_metadata_for_update(paths: dict[str, Path], target_dir: Path) -> None:
    metadata_path = target_dir / TOOLKIT_INSTALL_METADATA_FILENAME
    if metadata_path.exists():
        _move_path(metadata_path, paths["rollback"] / TOOLKIT_INSTALL_METADATA_FILENAME)
        _append_line(paths["replaced"], TOOLKIT_INSTALL_METADATA_FILENAME)


def _write_state(state_path: Path, phase: str) -> None:
    _write_text(state_path, f"phase={phase}\n")


def _read_state_phase(state_path: Path) -> str | None:
    if not state_path.exists():
        return None
    for line in state_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("phase="):
            return line.split("=", 1)[1].strip()
    return None


def _write_diagnostic(paths: dict[str, Path], message: str) -> None:
    paths["diagnostics"].mkdir(parents=True, exist_ok=True)
    _write_text(paths["diagnostics"] / "error.txt", message)


def _rollback_transaction(
    target_dir: Path,
    *,
    phase_label: str,
    leave_diagnostics: bool,
) -> None:
    paths = _transaction_paths(target_dir)
    transaction_dir = paths["transaction"]
    rollback_dir = paths["rollback"]
    if not transaction_dir.exists():
        return
    applied_names = _read_lines(paths["applied"])
    for name in reversed(applied_names):
        _remove_path(target_dir / name)
    if rollback_dir.exists():
        for entry in sorted(rollback_dir.iterdir(), key=lambda item: item.name):
            _move_path(entry, target_dir / entry.name)
    _write_state(paths["state"], phase_label)
    if not leave_diagnostics:
        shutil.rmtree(transaction_dir)


def recover_incomplete_transaction(target_dir: Path) -> None:
    paths = _transaction_paths(target_dir)
    transaction_dir = paths["transaction"]
    if not transaction_dir.exists():
        return
    phase = _read_state_phase(paths["state"])
    if phase in {"prepared", "replacing", "rolling_back"}:
        _rollback_transaction(
            target_dir,
            phase_label="restored_pending_inspection",
            leave_diagnostics=True,
        )
        raise InstallerError(
            "Recovered an incomplete update transaction. Inspect "
            ".calixto-update-transaction, then re-run the installer."
        )
    if phase == "restored_pending_inspection":
        raise InstallerError(
            "An earlier interrupted update was already restored. Inspect "
            ".calixto-update-transaction, then remove it before retrying."
        )
    raise InstallerError(
        "Found an incomplete or ambiguous .calixto-update-transaction directory. "
        "Stop and inspect it before retrying."
    )


def _maybe_inject_failure(applied_count: int) -> None:
    if not _is_test_mode():
        return
    raw = os.environ.get(TEST_FAIL_AFTER_ENV)
    if not raw:
        return
    try:
        threshold = int(raw)
    except ValueError as exc:
        raise InstallerError(
            f"{TEST_FAIL_AFTER_ENV} must be an integer when test mode is enabled."
        ) from exc
    if threshold < 0:
        raise InstallerError(
            f"{TEST_FAIL_AFTER_ENV} must be non-negative when test mode is enabled."
        )
    if applied_count >= threshold:
        raise InstallerError(
            f"Injected test failure after {applied_count} replacements."
        )


def apply_fresh_install(
    source_root: Path,
    target_dir: Path,
    *,
    repo_url: str,
    selector_kind: str,
    selector_value: str | None,
) -> None:
    if any(target_dir.iterdir()):
        raise InstallerError(
            "Fresh install target is not empty. Refusing to overwrite it."
        )
    _validate_source_contract(source_root, mode="fresh")
    managed_names = _managed_names_from_source_root(source_root)
    for entry in _top_level_entries(source_root):
        if entry.name in {".git", MANAGED_ENTRIES_FILENAME, TRANSACTION_DIRNAME}:
            continue
        _move_path(entry, target_dir / entry.name)
    missing = _missing_workspace_markers(target_dir)
    if missing:
        joined = ", ".join(missing)
        raise InstallerError(
            f"Fresh install did not produce a valid toolkit root. Missing: {joined}"
        )
    _write_toolkit_install_metadata(
        source_root,
        target_dir,
        repo_url=repo_url,
        selector_kind=selector_kind,
        selector_value=selector_value,
    )
    _write_managed_entries(target_dir, managed_names)


def apply_update(
    source_root: Path,
    target_dir: Path,
    *,
    repo_url: str,
    selector_kind: str,
    selector_value: str | None,
) -> None:
    recover_incomplete_transaction(target_dir)
    _validate_source_contract(source_root, mode="update")
    plan = _build_update_plan(source_root, target_dir)
    if plan["conflicts"]:
        joined = ", ".join(plan["conflicts"])
        raise InstallerError(
            "Update would overwrite unknown top-level entries. Resolve these "
            f"conflicts first: {joined}"
        )

    protected_before = _protected_snapshots(target_dir)
    paths = _transaction_paths(target_dir)
    transaction_dir = paths["transaction"]
    transaction_dir.mkdir(parents=True, exist_ok=False)
    paths["source"].mkdir(parents=True, exist_ok=True)
    paths["rollback"].mkdir(parents=True, exist_ok=True)
    paths["diagnostics"].mkdir(parents=True, exist_ok=True)
    _write_state(paths["state"], "prepared")
    _prepare_generated_metadata_for_update(paths, target_dir)

    for name in plan["apply_order"]:
        _move_path(source_root / name, paths["source"] / name)

    managed_path = target_dir / MANAGED_ENTRIES_FILENAME

    try:
        _write_state(paths["state"], "replacing")
        if managed_path.exists():
            _move_path(managed_path, paths["rollback"] / MANAGED_ENTRIES_FILENAME)
            _append_line(paths["replaced"], MANAGED_ENTRIES_FILENAME)

        applied_count = 0
        for name in plan["apply_order"]:
            target_path = target_dir / name
            staged_path = paths["source"] / name
            if target_path.exists() or target_path.is_symlink():
                _move_path(target_path, paths["rollback"] / name)
                _append_line(paths["replaced"], name)
            else:
                _append_line(paths["added"], name)
            _move_path(staged_path, target_path)
            _append_line(paths["applied"], name)
            applied_count += 1
            _maybe_inject_failure(applied_count)

        for name in plan["removals"]:
            target_path = target_dir / name
            if target_path.exists() or target_path.is_symlink():
                _move_path(target_path, paths["rollback"] / name)
                _append_line(paths["replaced"], name)

        missing = _missing_workspace_markers(target_dir)
        if missing:
            joined = ", ".join(missing)
            raise InstallerError(
                f"Updated toolkit root is missing required markers: {joined}"
            )
        _assert_protected_unchanged(
            target_dir,
            protected_before,
            "Installer",
        )
        _write_managed_entries(target_dir, plan["managed_next"])
        _write_toolkit_install_metadata(
            source_root,
            target_dir,
            repo_url=repo_url,
            selector_kind=selector_kind,
            selector_value=selector_value,
        )
        _append_line(paths["applied"], TOOLKIT_INSTALL_METADATA_FILENAME)
        _write_state(paths["state"], "files_committed")
    except Exception as exc:
        details = "".join(traceback.format_exception(exc))
        _write_diagnostic(paths, details)
        try:
            _rollback_transaction(
                target_dir,
                phase_label="restored_pending_inspection",
                leave_diagnostics=True,
            )
        except Exception as rollback_exc:  # pragma: no cover - best-effort path
            raise InstallerError(
                f"{exc}\nRollback also failed: {rollback_exc}\n"
                "Inspect .calixto-update-transaction manually."
            ) from rollback_exc
        raise InstallerError(str(exc)) from exc

    _assert_protected_unchanged(
        target_dir,
        protected_before,
        "Post-commit validation",
    )
    try:
        shutil.rmtree(transaction_dir)
    except Exception as exc:
        raise InstallerError(
            "Update committed, but cleanup of .calixto-update-transaction failed. "
            "Inspect and remove it manually."
        ) from exc


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    fresh = subparsers.add_parser("apply-fresh")
    fresh.add_argument("--source-root", required=True)
    fresh.add_argument("--target-dir", required=True)
    fresh.add_argument("--repo-url", required=True)
    fresh.add_argument("--selector-kind", required=True)
    fresh.add_argument("--selector-value")

    update = subparsers.add_parser("apply-update")
    update.add_argument("--source-root", required=True)
    update.add_argument("--target-dir", required=True)
    update.add_argument("--repo-url", required=True)
    update.add_argument("--selector-kind", required=True)
    update.add_argument("--selector-value")

    recover = subparsers.add_parser("recover-transaction")
    recover.add_argument("--target-dir", required=True)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    try:
        if args.command == "apply-fresh":
            apply_fresh_install(
                Path(args.source_root).resolve(strict=False),
                Path(args.target_dir).resolve(strict=False),
                repo_url=args.repo_url,
                selector_kind=args.selector_kind,
                selector_value=args.selector_value,
            )
            return 0
        if args.command == "apply-update":
            apply_update(
                Path(args.source_root).resolve(strict=False),
                Path(args.target_dir).resolve(strict=False),
                repo_url=args.repo_url,
                selector_kind=args.selector_kind,
                selector_value=args.selector_value,
            )
            return 0
        if args.command == "recover-transaction":
            recover_incomplete_transaction(
                Path(args.target_dir).resolve(strict=False)
            )
            return 0
        raise InstallerError(f"Unknown command: {args.command}")
    except InstallerError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
