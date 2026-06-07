"""
init_workspace.py: Create a new research workspace from the template.

Usage:
    python scripts/init_workspace.py <name> [--path DIR]

What it does:
    1. Validates the name is a valid slug
    2. Verifies the workspace does not already exist
    3. Copies templates/workspace/ to <path>/<name>/
    4. Updates config.json with the workspace name and current timestamp
    5. Prints a structured JSON status object to stdout

Architecture:
    - Pure file I/O, no network, no LLM calls
    - Idempotent: refuses to overwrite an existing workspace
    - Exits 0 on success, 1 on error
    - JSON to stdout, errors to stderr
"""

from __future__ import annotations

import argparse
import json
import sys
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

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "templates" / "workspace"


def copy_template(src: Path, dst: Path) -> None:
    """Recursively copy the workspace template from src to dst."""
    if not src.exists():
        raise FileNotFoundError(f"workspace template not found at {src}")
    dst.mkdir(parents=True, exist_ok=False)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            copy_template(item, target)
        else:
            # Read text and write to preserve newlines
            text = item.read_text(encoding="utf-8")
            target.write_text(text, encoding="utf-8")


def init_workspace(name: str, path: Path) -> dict:
    """Create a workspace named `name` inside `path`. Returns a status dict.

    Raises:
        ValueError: invalid name
        FileExistsError: workspace already exists
        FileNotFoundError: template missing
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
        copy_template(TEMPLATE_DIR, target)
    except FileExistsError:
        # Race condition: another process created it between our check and copy
        emit_error("workspace_exists", f"workspace '{name}' was created concurrently at {target}.")

    # Update config.json with the actual name and timestamps
    config_path = target / "config.json"
    config = load_workspace_config(target)
    config["name"] = name
    config["created_at"] = utcnow_iso()
    config["updated_at"] = utcnow_iso()
    save_workspace_config(target, config)

    return {
        "workspace": str(target),
        "name": name,
        "path": str(path),
        "template": str(TEMPLATE_DIR),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create a new Calixto research workspace from the template.",
        prog="init_workspace",
    )
    parser.add_argument("name", help="Workspace name (lowercase, hyphens, 2-64 chars).")
    parser.add_argument(
        "--path",
        default="./workspaces",
        help="Parent directory for the new workspace. Default: ./workspaces",
    )
    args = parser.parse_args(argv)

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
        emit_error("template_missing", str(e))
    except Exception as e:
        emit_error("init_failed", f"unexpected error: {e}")

    emit_ok(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
