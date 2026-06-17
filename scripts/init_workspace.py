"""
init_workspace.py: Create a new standalone research workspace snapshot.

Usage:
    python scripts/init_workspace.py <name> [--path DIR] [update-check flags]

What it does:
    1. Validates the name is a valid slug
    2. Optionally checks whether the local toolkit checkout is behind the remote
       default branch
    3. Verifies the workspace does not already exist
    4. Copies the standalone runtime bundle to <path>/<name>/
    5. Updates config.json with the workspace name, metadata, and timestamps
    6. Prints a structured JSON status object to stdout

Architecture:
    - No LLM calls
    - Workspace creation itself is file I/O only; update checks may make a
      lightweight git remote query when enabled
    - Idempotent: refuses to overwrite an existing workspace
    - Exits 0 on success, 1 on error
    - JSON to stdout, errors to stderr
"""

from __future__ import annotations

import argparse
import sys
from contextlib import suppress
from pathlib import Path

# Make this script runnable as `python scripts/init_workspace.py ...`
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _common import (
    emit_error,
    emit_ok,
    is_valid_slug,
    load_workspace_config,
    save_workspace_config,
    utcnow_iso,
    workspace_path,
)
from runtime_bundle import (
    RUNTIME_MANIFEST_PATH,
    copy_runtime_bundle,
    runtime_bundle_version,
    standalone_workspace_metadata,
)
from toolkit_git import (
    build_toolkit_update_command,
    check_toolkit_freshness,
    format_short_commit,
)


def init_workspace(name: str, path: Path) -> dict:
    """Create a workspace named `name` inside `path`. Returns a status dict.

    Raises:
        ValueError: invalid name
        FileExistsError: workspace already exists
        FileNotFoundError: runtime bundle source missing
    """
    if not is_valid_slug(name):
        emit_error(
            "invalid_name",
            f"'{name}' is not a valid workspace name. Use lowercase letters, digits, and hyphens; 2-64 chars; start/end with a letter or digit.",
        )

    target = path / name
    if target.exists():
        emit_error(
            "workspace_exists",
            f"workspace '{name}' already exists at {target}. Use a different name or delete the existing workspace first.",
            extra={"workspace": str(target)},
        )

    try:
        copy_runtime_bundle(target)
    except FileExistsError:
        # Race condition: another process created it between our check and copy
        emit_error("workspace_exists", f"workspace '{name}' was created concurrently at {target}.")

    # Update config.json with the actual name, runtime metadata, and timestamps.
    config = load_workspace_config(target)
    config["name"] = name
    config.update(standalone_workspace_metadata())
    config["created_at"] = utcnow_iso()
    config["updated_at"] = utcnow_iso()
    save_workspace_config(target, config)

    return {
        "workspace": str(target),
        "name": name,
        "path": str(path),
        "runtime_manifest": str(RUNTIME_MANIFEST_PATH),
        "workspace_layout": config["workspace_layout"],
        "workspace_schema_version": config["workspace_schema_version"],
        "runtime_bundle_version": runtime_bundle_version(),
        "toolkit_commit_created_with": config.get("toolkit_commit_created_with"),
        "toolkit_build_number_created_with": config.get("toolkit_build_number_created_with"),
        "toolkit_ref_created_with": config.get("toolkit_ref_created_with"),
    }


def is_interactive_terminal() -> bool:
    """Return True when stdin/stdout are TTYs and prompting is safe."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def _console(message: str, *, prefer_console: bool = False) -> None:
    """Write a user-facing note, using the terminal directly only when requested."""
    if not prefer_console:
        print(message, file=sys.stderr)
        return

    console = _open_console_stream()
    if console is None:
        print(message, file=sys.stderr)
        return
    try:
        print(message, file=console)
    finally:
        console.close()


def _open_console_stream():
    """Open the controlling terminal for prompts when available."""
    console_path = "CON" if sys.platform.startswith("win") else "/dev/tty"
    with suppress(OSError):
        return open(console_path, "w", encoding="utf-8", buffering=1)
    return None


def _read_prompt(prompt: str) -> str:
    """Read one interactive response without writing the prompt to JSON stdout."""
    console = _open_console_stream()
    if console is None:
        try:
            return input(prompt)
        except EOFError:
            return ""
    try:
        print(prompt, end="", file=console, flush=True)
        line = sys.stdin.readline()
    finally:
        console.close()
    if not line:
        return ""
    return line.rstrip("\r\n")


def _describe_build(commit_sha: str | None, build_number: int | None) -> str:
    short_commit = format_short_commit(commit_sha)
    if build_number is None:
        return short_commit
    return f"{short_commit} (build {build_number})"


def _should_check_updates(args: argparse.Namespace, interactive: bool) -> bool:
    if args.skip_update_check:
        return False
    if args.check_updates or args.require_update_check or args.update_before_create:
        return True
    return interactive


def _update_command_from_freshness(freshness: dict) -> str:
    return build_toolkit_update_command(
        repo_url=freshness.get("installer_repo_url"),
        branch=freshness.get("default_branch"),
    )


def _warn_on_nonblocking_freshness_state(freshness: dict) -> None:
    status = freshness["status"]
    if status == "ahead":
        _console(
            "Toolkit update check: local checkout is ahead of the remote default branch; "
            "workspace creation will use the current local snapshot."
        )
        return
    if status == "diverged":
        _console(
            "Toolkit update check: local checkout has diverged from the remote default branch; "
            "workspace creation will use the current local snapshot."
        )
        return
    if status == "remote_newer_unknown_relationship":
        _console(
            "Toolkit update check: remote default branch has a newer commit, but the local checkout "
            "does not contain enough history to classify the relationship. Continuing with the current "
            "local snapshot."
        )
        return
    if status == "unknown":
        _console(
            "Toolkit update check: commit relationship could not be classified. Continuing with the "
            "current local snapshot."
        )


def maybe_check_for_toolkit_updates(args: argparse.Namespace) -> None:
    """Run the optional pre-create update check and prompt/exit when needed."""
    interactive = is_interactive_terminal()
    if not _should_check_updates(args, interactive):
        return

    freshness = check_toolkit_freshness()
    status = freshness["status"]
    if status == "unavailable":
        if args.require_update_check or args.update_before_create:
            emit_error(
                "update_check_failed",
                f"toolkit update check could not be completed: {freshness['message']}",
                extra={"workspace_created": False},
            )
        if interactive or args.check_updates:
            _console(f"Toolkit update check skipped: {freshness['message']}")
        return

    if status == "up_to_date":
        if args.check_updates:
            _console("Toolkit update check: local checkout is up to date with the remote default branch.")
        return

    if status == "behind":
        local_desc = _describe_build(
            freshness.get("local_commit"),
            freshness.get("local_build_number"),
        )
        latest_desc = _describe_build(
            freshness.get("latest_commit"),
            freshness.get("latest_build_number"),
        )
        behind_by = freshness.get("behind_by")
        behind_text = ""
        if behind_by is not None:
            behind_text = f" and is {behind_by} commit{'s' if behind_by != 1 else ''} behind"
        branch_name = freshness.get("default_branch") or "the remote default branch"
        message = (
            f"Toolkit update available: local {local_desc} is behind {branch_name} at {latest_desc}{behind_text}. "
            "Continuing will create the workspace from the current local toolkit snapshot."
        )
        if args.update_before_create:
            update_command = _update_command_from_freshness(freshness)
            emit_error(
                "update_required",
                f"{message} Run {update_command} from the toolkit root, then rerun init_workspace.py.",
                extra={
                    "workspace_created": False,
                    "update_command": update_command,
                },
            )
        if interactive:
            _console(message, prefer_console=True)
            response = _read_prompt("Update the toolkit before creating this workspace? [y/N]: ").strip().lower()
            if response in {"y", "yes"}:
                update_command = _update_command_from_freshness(freshness)
                emit_error(
                    "update_requested",
                    f"No workspace was created. Run {update_command} from the toolkit root, then rerun init_workspace.py.",
                    extra={
                        "workspace_created": False,
                        "update_command": update_command,
                    },
                )
            _console("Continuing with the current local toolkit snapshot.", prefer_console=True)
            return
        _console(message)
        return

    if args.update_before_create and status in {"remote_newer_unknown_relationship", "unknown"}:
        emit_error(
            "update_check_inconclusive",
            "toolkit update check could not determine whether the local checkout is stale; "
            "no workspace was created because --update-before-create was requested",
            extra={"workspace_created": False},
        )

    _warn_on_nonblocking_freshness_state(freshness)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create a new standalone Calixto research workspace snapshot.",
        prog="init_workspace",
    )
    parser.add_argument("name", help="Workspace name (lowercase, hyphens, 2-64 chars).")
    parser.add_argument(
        "--path",
        default="./workspaces",
        help="Parent directory for the new workspace. Default: ./workspaces",
    )
    update_group = parser.add_mutually_exclusive_group()
    update_group.add_argument(
        "--check-updates",
        action="store_true",
        help="Check whether the toolkit is behind the remote default branch before workspace creation.",
    )
    update_group.add_argument(
        "--skip-update-check",
        action="store_true",
        help="Skip the toolkit update check even in an interactive terminal.",
    )
    parser.add_argument(
        "--require-update-check",
        action="store_true",
        help="Fail before workspace creation if the update check cannot be completed.",
    )
    parser.add_argument(
        "--update-before-create",
        action="store_true",
        help="If the toolkit is behind, print the exact installer update command and exit before creating the workspace.",
    )
    args = parser.parse_args(argv)

    if args.skip_update_check and (args.require_update_check or args.update_before_create):
        emit_error(
            "invalid_arguments",
            "--skip-update-check cannot be combined with --require-update-check or --update-before-create.",
        )

    maybe_check_for_toolkit_updates(args)

    target_path = workspace_path(args.path)
    if not target_path.exists():
        try:
            target_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            emit_error("path_create_failed", f"could not create parent directory {target_path}: {e}")

    try:
        result = init_workspace(args.name, target_path)
    except SystemExit:
        raise
    except FileNotFoundError as e:
        emit_error("runtime_bundle_missing", str(e))
    except Exception as e:
        emit_error("init_failed", f"unexpected error: {e}")

    emit_ok(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
