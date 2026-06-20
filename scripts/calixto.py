"""
calixto.py: top-level Calixto toolkit CLI.

Primary user flows:
- `calixto research "<question>" --agent none`
- `calixto open <workspace-or-slug> --agent codex`
- `calixto runtime list`
- `calixto runtime prune`
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from argparse import Namespace
from pathlib import Path
from typing import Any

# Make this script runnable as `python scripts/calixto.py ...`
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _common import is_valid_slug, load_workspace_config, save_workspace_config, slugify, workspace_path
from harnesses import (
    ensure_harness_available,
    get_harness,
    initial_handoff_prompt,
    launch_harness_process,
    project_skill_dirs_for,
    supported_harness_names,
)
from init_workspace import init_workspace, is_interactive_terminal, maybe_check_for_toolkit_updates
from managed_runtime import (
    current_runtime_spec,
    ensure_managed_runtime,
    is_managed_workspace_location,
    list_managed_runtimes,
    prune_managed_runtimes,
    runtime_environment_overrides,
    runtime_spec_for_workspace,
    select_runtime_for_workspace,
)
from runtime_bundle import REPO_ROOT


DEFAULT_WORKSPACES_DIR = REPO_ROOT / "workspaces"
CANONICAL_WORKSPACE_SKILLS_DIR = Path("skills")


class CalixtoError(RuntimeError):
    def __init__(self, error: str, message: str, *, extra: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.error = error
        self.message = message
        self.extra = extra or {}


def _emit_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _emit_human(text: str, *, stderr: bool = False) -> None:
    print(text, file=sys.stderr if stderr else sys.stdout)


def _fail(error: str, message: str, *, extra: dict[str, Any] | None = None) -> None:
    raise CalixtoError(error, message, extra=extra)


def _validate_question(question: str) -> str:
    question = question.strip()
    if not question:
        _fail("invalid_question", "research question must not be empty")
    return question


def _update_check_namespace(args: argparse.Namespace) -> Namespace:
    return Namespace(
        check_updates=args.check_updates,
        skip_update_check=args.skip_update_check,
        require_update_check=args.require_update_check,
        update_before_create=args.update_before_create,
    )


def _derived_workspace_name(question: str, parent: Path, explicit_name: str | None) -> str:
    if explicit_name:
        if not is_valid_slug(explicit_name):
            _fail(
                "invalid_name",
                f"'{explicit_name}' is not a valid workspace name. Use lowercase letters, digits, and hyphens; 2-64 chars; start/end with a letter or digit.",
            )
        return explicit_name

    base = slugify(question)
    if not is_valid_slug(base):
        _fail("name_derivation_failed", "could not derive a valid workspace name from the question")

    if not (parent / base).exists():
        return base

    suffix = 2
    while True:
        candidate = f"{base}-{suffix}"
        if len(candidate) > 64:
            trim_to = 64 - len(f"-{suffix}")
            candidate = f"{base[:trim_to].rstrip('-')}-{suffix}"
        if is_valid_slug(candidate) and not (parent / candidate).exists():
            return candidate
        suffix += 1


def _ensure_parent_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_question_to_workspace(workspace: Path, question: str) -> None:
    config = load_workspace_config(workspace)
    config["question"] = question
    save_workspace_config(workspace, config)


def _skill_directories(workspace: Path) -> list[Path]:
    skills_dir = workspace / CANONICAL_WORKSPACE_SKILLS_DIR
    if not skills_dir.exists():
        return []
    return sorted([path for path in skills_dir.iterdir() if path.is_dir()], key=lambda item: item.name)


def _generate_harness_skill_mirrors(workspace: Path, harness_name: str) -> list[str]:
    if harness_name == "none":
        return []
    generated: list[str] = []
    for relative_dir in project_skill_dirs_for(harness_name):
        mirror_root = workspace / relative_dir
        mirror_root.mkdir(parents=True, exist_ok=True)
        for canonical_skill_dir in _skill_directories(workspace):
            target_dir = mirror_root / canonical_skill_dir.name
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.copytree(canonical_skill_dir, target_dir)
            generated.append(str(target_dir))
    return generated


def _resolve_workspace_argument(raw: str) -> Path:
    candidate = Path(raw).expanduser()
    looks_like_path = candidate.is_absolute() or any(sep in raw for sep in ("/", "\\"))
    if looks_like_path:
        resolved = workspace_path(candidate)
        if not resolved.exists():
            _fail("workspace_not_found", f"workspace not found at {resolved}")
        return resolved

    slug = raw.strip()
    if not is_valid_slug(slug):
        _fail("invalid_workspace", f"'{raw}' is not a valid workspace slug or existing path")
    resolved = (DEFAULT_WORKSPACES_DIR / slug).resolve()
    if not resolved.exists():
        _fail("workspace_not_found", f"workspace '{slug}' not found under {DEFAULT_WORKSPACES_DIR}")
    return resolved


def _validate_workspace_root(workspace: Path) -> None:
    required = [
        workspace / "config.json",
        workspace / "pyproject.toml",
        workspace / "uv.lock",
        workspace / "AGENTS.md",
    ]
    missing = [str(path.name) for path in required if not path.exists()]
    if missing:
        joined = ", ".join(missing)
        _fail("invalid_workspace", f"workspace at {workspace} is missing required files: {joined}")


def _prepare_runtime_for_workspace(workspace: Path, *, setup_local: bool) -> dict[str, Any]:
    selection = select_runtime_for_workspace(workspace, allow_local_setup=setup_local)
    if selection.get("status") == "error":
        _fail(selection["error"], selection["message"], extra=selection)
    return selection


def _create_workspace(args: argparse.Namespace) -> dict[str, Any]:
    question = _validate_question(args.question)
    maybe_check_for_toolkit_updates(_update_check_namespace(args))

    parent = _ensure_parent_dir(workspace_path(args.path) if args.path else DEFAULT_WORKSPACES_DIR)
    name = _derived_workspace_name(question, parent, args.name)
    if args.agent != "none":
        ensure_harness_available(args.agent)

    created = init_workspace(name, parent)
    workspace = Path(created["workspace"])
    _write_question_to_workspace(workspace, question)

    integration_paths: list[str] = []
    if args.agent != "none":
        integration_paths = _generate_harness_skill_mirrors(workspace, args.agent)

    runtime_mode = "standalone_setup_required"
    runtime_key = runtime_spec_for_workspace(workspace).full_key
    runtime_display_key = runtime_spec_for_workspace(workspace).display_key
    runtime_details: dict[str, Any] = {
        "runtime_mode": runtime_mode,
        "runtime_key": runtime_key,
        "runtime_display_key": runtime_display_key,
    }
    if is_managed_workspace_location(workspace):
        runtime_details = ensure_managed_runtime()
        runtime_mode = runtime_details["runtime_mode"]
        runtime_key = runtime_details["runtime_key"]
        runtime_display_key = runtime_details["runtime_display_key"]

    return {
        "workspace": str(workspace),
        "workspace_name": name,
        "question": question,
        "runtime_mode": runtime_mode,
        "runtime_key": runtime_key,
        "runtime_display_key": runtime_display_key,
        "integration_paths": integration_paths,
        "open_command": f'calixto open {name} --agent {args.agent}' if parent == DEFAULT_WORKSPACES_DIR else f'calixto open "{workspace}" --agent {args.agent}',
        "created": created,
        "runtime_details": runtime_details,
    }


def _maybe_launch_agent(args: argparse.Namespace, created: dict[str, Any]) -> int:
    if args.agent == "none":
        return 0

    workspace = Path(created["workspace"])
    setup_local = args.setup_local
    if not setup_local and not is_managed_workspace_location(workspace) and is_interactive_terminal():
        response = input("This workspace is outside the toolkit-managed workspaces directory. Run workspace-local setup before launching? [y/N]: ").strip().lower()
        setup_local = response in {"y", "yes"}

    selection = _prepare_runtime_for_workspace(workspace, setup_local=setup_local)
    environment = runtime_environment_overrides(selection)
    prompt = initial_handoff_prompt(created["question"])

    try:
        process = launch_harness_process(
            args.agent,
            workspace=workspace,
            environment=environment,
            prompt=prompt,
        )
    except OSError as exc:
        _fail(
            "launch_failed",
            f"failed to launch {args.agent}: {exc}",
            extra={
                "workspace": str(workspace),
                "retry_command": created["open_command"],
            },
        )
    return process.wait()


def _research_command(args: argparse.Namespace) -> int:
    if args.json and args.agent != "none":
        _fail("invalid_arguments", "--json can only be used with --agent none")

    created = _create_workspace(args)
    if args.json:
        _emit_json(created)
        return 0

    _emit_human(f"Workspace created: {created['workspace']}")
    _emit_human(f"Runtime: {created['runtime_mode']} ({created['runtime_display_key']})")
    if created["integration_paths"]:
        _emit_human(f"Harness integration: {args.agent}")
    _emit_human(f"Next command: {created['open_command']}")
    return _maybe_launch_agent(args, created)


def _open_command(args: argparse.Namespace) -> int:
    if args.agent != "none":
        ensure_harness_available(args.agent)

    workspace = _resolve_workspace_argument(args.workspace)
    _validate_workspace_root(workspace)

    integration_paths: list[str] = []
    if args.prepare_harness and args.agent != "none":
        integration_paths = _generate_harness_skill_mirrors(workspace, args.agent)

    if args.agent == "none":
        selection = _prepare_runtime_for_workspace(workspace, setup_local=args.setup_local)
        _emit_human(f"Workspace ready: {workspace}")
        _emit_human(f"Runtime: {selection['runtime_mode']} ({selection['runtime_display_key']})")
        if integration_paths:
            _emit_human(f"Prepared harness integration for {args.agent}")
        return 0

    setup_local = args.setup_local
    if not setup_local and not is_managed_workspace_location(workspace) and is_interactive_terminal():
        response = input("No managed runtime is available for this workspace path. Run workspace-local setup before launching? [y/N]: ").strip().lower()
        setup_local = response in {"y", "yes"}

    selection = _prepare_runtime_for_workspace(workspace, setup_local=setup_local)
    environment = runtime_environment_overrides(selection)
    question = load_workspace_config(workspace).get("question", "")
    prompt = initial_handoff_prompt(question)
    try:
        process = launch_harness_process(
            args.agent,
            workspace=workspace,
            environment=environment,
            prompt=prompt,
        )
    except OSError as exc:
        _fail(
            "launch_failed",
            f"failed to launch {args.agent}: {exc}",
            extra={"workspace": str(workspace)},
        )
    return process.wait()


def _runtime_list_command() -> int:
    runtimes = list_managed_runtimes()
    if not runtimes:
        _emit_human("No managed runtimes are present.")
        return 0
    for runtime in runtimes:
        flags: list[str] = []
        if runtime["is_current_key"]:
            flags.append("current")
        if runtime["referenced_workspaces"]:
            flags.append(f"refs={len(runtime['referenced_workspaces'])}")
        flag_text = f" [{' '.join(flags)}]" if flags else ""
        _emit_human(
            f"{runtime['runtime_display_key']}{flag_text} size={runtime['apparent_size_bytes']}B valid={runtime['valid']}"
        )
    return 0


def _runtime_prune_command(args: argparse.Namespace) -> int:
    report = prune_managed_runtimes(
        selected_keys=args.key or [],
        force=args.force,
        dry_run=not args.apply,
    )
    mode = "Dry run" if report["dry_run"] else "Applied"
    _emit_human(f"{mode}:")
    if report["deleted"]:
        _emit_human(f"Delete: {', '.join(report['deleted'])}")
    if report["kept"]:
        _emit_human(f"Keep: {', '.join(report['kept'])}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calixto toolkit CLI for one-command workspace creation and reopening.",
        prog="calixto",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    research = subparsers.add_parser("research", help="Create a research workspace and optionally launch a harness.")
    research.add_argument("question", help="Research question to store in the new workspace.")
    research.add_argument("--name", help="Explicit workspace name slug.")
    research.add_argument(
        "--path",
        default=str(DEFAULT_WORKSPACES_DIR),
        help=f"Parent directory for the new workspace. Default: {DEFAULT_WORKSPACES_DIR}",
    )
    research.add_argument(
        "--agent",
        default="none",
        choices=supported_harness_names(),
        help="Coding-agent harness to prepare and optionally launch. Default: none",
    )
    research.add_argument(
        "--json",
        action="store_true",
        help="Emit one JSON object and do not launch an interactive harness.",
    )
    research.add_argument(
        "--setup-local",
        action="store_true",
        help="Allow workspace-local setup when the new workspace is outside the managed workspaces directory.",
    )
    update_group = research.add_mutually_exclusive_group()
    update_group.add_argument("--check-updates", action="store_true")
    update_group.add_argument("--skip-update-check", action="store_true")
    research.add_argument("--require-update-check", action="store_true")
    research.add_argument("--update-before-create", action="store_true")

    open_parser = subparsers.add_parser("open", help="Open an existing workspace with the selected harness.")
    open_parser.add_argument("workspace", help="Workspace slug under the toolkit root or an explicit workspace path.")
    open_parser.add_argument(
        "--agent",
        default="none",
        choices=supported_harness_names(),
        help="Coding-agent harness to launch. Default: none",
    )
    open_parser.add_argument(
        "--prepare-harness",
        action="store_true",
        help="Generate harness skill mirrors for an existing workspace before launch.",
    )
    open_parser.add_argument(
        "--setup-local",
        action="store_true",
        help="Allow running the workspace-local setup script when no compatible runtime is available yet.",
    )

    runtime_parser = subparsers.add_parser("runtime", help="Inspect or prune toolkit-managed runtimes.")
    runtime_subparsers = runtime_parser.add_subparsers(dest="runtime_command", required=True)
    runtime_subparsers.add_parser("list", help="List managed runtimes.")
    prune_parser = runtime_subparsers.add_parser("prune", help="Prune managed runtimes.")
    prune_parser.add_argument("--key", action="append", help="Runtime key or display key to target.")
    prune_parser.add_argument("--apply", action="store_true", help="Actually delete matching runtimes.")
    prune_parser.add_argument("--force", action="store_true", help="Allow pruning protected runtimes.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "research":
            return _research_command(args)
        if args.command == "open":
            return _open_command(args)
        if args.command == "runtime" and args.runtime_command == "list":
            return _runtime_list_command()
        if args.command == "runtime" and args.runtime_command == "prune":
            return _runtime_prune_command(args)
        _fail("unknown_command", f"unknown command: {args.command}")
    except CalixtoError as exc:
        if getattr(args, "json", False):
            _emit_json({"status": "error", "error": exc.error, "message": exc.message, **exc.extra})
        else:
            _emit_human(exc.message, stderr=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
