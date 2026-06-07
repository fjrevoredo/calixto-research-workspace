"""
workspace_info.py: List, inspect, delete, and audit workspaces.

Subcommands:
    list    - List all workspaces in a parent directory
    show    - Show summary of a single workspace
    delete  - Remove a workspace (with confirmation)
    audit   - Verify the traceability chain (src > fnd > ins > report)

All subcommands print structured JSON to stdout. Errors go to stderr.

Usage:
    python scripts/workspace_info.py list [--path ./workspaces]
    python scripts/workspace_info.py show <name> [--path ./workspaces]
    python scripts/workspace_info.py delete <name> [--path ./workspaces] [--force]
    python scripts/workspace_info.py audit <name> [--path ./workspaces]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Make _common importable when this script is run directly
_SCRIPTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = Path(__file__).resolve().parent.parent
for p in (str(_REPO_ROOT), str(_SCRIPTS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from _common import (
    emit_error,
    emit_ok,
    is_valid_slug,
    parse_frontmatter,
    workspace_path,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


SRC_ID_RE = re.compile(r"\bsrc_(\d{3,})\b")
FND_ID_RE = re.compile(r"\bfnd_(\d{3,})\b")
INS_ID_RE = re.compile(r"\bins_(\d{3,})\b")


def _read_file(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _resolve_workspace(name_or_path: str, default_parent: Path) -> Path:
    """Resolve a workspace argument.

    If the argument is an existing path, use it. Otherwise, treat it as a name
    inside default_parent.
    """
    candidate = Path(name_or_path)
    if candidate.exists() and (candidate / "config.json").exists():
        return candidate.resolve()
    if is_valid_slug(name_or_path):
        full = default_parent / name_or_path
        if full.exists() and (full / "config.json").exists():
            return full.resolve()
    # Fall through; let the caller produce a structured error
    return (default_parent / name_or_path).resolve()


def _resolve_workspace_for_delete(name_or_path: str, default_parent: Path) -> Path:
    """Resolve a workspace target for deletion, with strict safety checks.

    The resolved path MUST:
    - Exist on disk
    - Contain a config.json marker
    - Be strictly inside the resolved default_parent (no traversal)
    - Not equal default_parent or any filesystem root

    These checks happen immediately before any destructive operation, so a
    misuse like `delete ..` cannot escape the workspaces parent directory.
    """
    parent = default_parent.resolve()
    if not parent.exists() or not parent.is_dir():
        emit_error("parent_not_found", f"workspace parent directory does not exist: {parent}")

    # Reject filesystem roots early; nothing under "/" is a workspace.
    parent_str = str(parent)
    if parent_str == "/" or (len(parent_str) >= 3 and parent_str[1] == ":" and parent_str.endswith("\\")):
        emit_error("invalid_parent", f"refusing to operate on filesystem root: {parent}")

    # Treat the argument strictly as a name; reject absolute paths and path
    # traversal segments. Slug-only inputs are the documented contract.
    if Path(name_or_path).is_absolute():
        emit_error(
            "invalid_target",
            f"delete target must be a workspace slug, not an absolute path: {name_or_path!r}",
        )
    if not is_valid_slug(name_or_path):
        emit_error(
            "invalid_target",
            f"delete target must be a valid workspace slug: {name_or_path!r}. "
            "Use lowercase letters, digits, and hyphens; 2-64 chars; start/end with a letter or digit.",
        )

    target = (parent / name_or_path).resolve()

    # Strict containment: target must be a child of parent, never parent itself.
    try:
        target.relative_to(parent)
    except ValueError:
        emit_error(
            "invalid_target",
            f"delete target {target} is not inside the workspace parent {parent}",
        )

    if target == parent:
        emit_error(
            "invalid_target",
            f"refusing to delete the workspace parent directory: {parent}",
        )

    if not target.exists() or not target.is_dir():
        emit_error("workspace_not_found", f"workspace not found at {target}")

    if not (target / "config.json").is_file():
        emit_error(
            "not_a_workspace",
            f"target {target} is not a Calixto workspace (missing config.json). "
            "Refusing to delete a non-workspace directory.",
        )

    return target


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def cmd_list(parent: Path) -> dict:
    """List all workspaces under `parent`."""
    if not parent.exists():
        emit_error("parent_not_found", f"workspaces directory does not exist: {parent}")
    workspaces: list[dict] = []
    for entry in sorted(parent.iterdir()):
        if not entry.is_dir():
            continue
        if not (entry / "config.json").exists():
            continue
        try:
            with (entry / "config.json").open("r", encoding="utf-8") as f:
                cfg = json.load(f)
        except (json.JSONDecodeError, OSError):
            cfg = {}
        # Count sources
        index_path = entry / "sources" / "index.json"
        source_count = 0
        if index_path.exists():
            try:
                with index_path.open("r", encoding="utf-8") as f:
                    idx = json.load(f)
                source_count = len(idx.get("sources", []))
            except (json.JSONDecodeError, OSError):
                pass
        # Count source files on disk
        files_count = sum(
            1 for d in ("web", "papers", "code") for _ in (entry / "sources" / d).glob("*.md")
        )
        # Last modified
        try:
            mtime = entry.stat().st_mtime
            last_modified = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
        except OSError:
            last_modified = "unknown"
        workspaces.append(
            {
                "name": entry.name,
                "path": str(entry),
                "question": cfg.get("question", ""),
                "source_count": source_count,
                "file_count": files_count,
                "last_modified": last_modified,
                "created_at": cfg.get("created_at", ""),
                "updated_at": cfg.get("updated_at", ""),
            }
        )
    return {"workspaces": workspaces, "count": len(workspaces), "parent": str(parent)}


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------


def cmd_show(workspace: Path) -> dict:
    """Show a single workspace's summary."""
    if not (workspace / "config.json").exists():
        emit_error("workspace_not_found", f"workspace not found at {workspace}")
    try:
        with (workspace / "config.json").open("r", encoding="utf-8") as f:
            cfg = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        emit_error("config_corrupt", f"could not read config.json: {e}")

    index_path = workspace / "sources" / "index.json"
    sources_by_type: dict[str, int] = {"web": 0, "papers": 0, "code": 0}
    if index_path.exists():
        try:
            with index_path.open("r", encoding="utf-8") as f:
                idx = json.load(f)
            for s in idx.get("sources", []):
                file_field = s.get("file", "")
                t = file_field.split("/", 1)[0] if "/" in file_field else "other"
                sources_by_type[t] = sources_by_type.get(t, 0) + 1
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "workspace": str(workspace),
        "name": cfg.get("name", workspace.name),
        "question": cfg.get("question", ""),
        "scope": cfg.get("scope", {}),
        "providers": cfg.get("providers", {}),
        "source_counts": sources_by_type,
        "total_sources": sum(sources_by_type.values()),
        "search_count": len(cfg.get("searches", [])),
        "next_source_id": cfg.get("next_source_id", 1),
        "next_finding_id": cfg.get("next_finding_id", 1),
        "next_insight_id": cfg.get("next_insight_id", 1),
        "created_at": cfg.get("created_at", ""),
        "updated_at": cfg.get("updated_at", ""),
    }


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


def cmd_delete(workspace: Path, force: bool) -> dict:
    """Delete a workspace. Requires --force or interactive confirmation.

    The caller is responsible for resolving `workspace` through
    `_resolve_workspace_for_delete`, which enforces that the target is a
    verified workspace inside the configured parent. This function only handles
    the confirmation prompt and the actual removal.
    """
    if not force:
        try:
            answer = input(f"Delete workspace at {workspace}? This cannot be undone. (y/n) ")
        except EOFError:
            emit_error("confirmation_required", "deletion requires --force flag in non-interactive mode")
        if answer.strip().lower() not in ("y", "yes"):
            emit_error("cancelled", "deletion cancelled by user")

    # Final belt-and-suspenders: the target must still look like a workspace
    # at the moment of removal. This guards against races where the directory
    # was replaced or the marker was deleted between resolution and removal.
    if not (workspace / "config.json").is_file():
        emit_error(
            "not_a_workspace",
            f"target {workspace} no longer contains a config.json. Aborting delete.",
        )

    try:
        shutil.rmtree(workspace)
    except OSError as e:
        emit_error("delete_failed", f"could not remove {workspace}: {e}")
    return {"workspace": str(workspace), "deleted": True}


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------


def cmd_audit(workspace: Path) -> dict:
    """Verify the traceability chain: src > fnd > ins > report.

    Checks (per requirements.md section 16.3.1):
    - All source IDs cited in findings.md exist in sources/index.json
    - All finding IDs cited in summary.md exist in findings.md
    - All source IDs cited in report.md exist in sources/index.json
    - Count orphaned sources (collected but never cited)
    - Count invalid references
    """
    if not (workspace / "config.json").exists():
        emit_error("workspace_not_found", f"workspace not found at {workspace}")

    # Load the source index
    index_path = workspace / "sources" / "index.json"
    known_src_ids: set[str] = set()
    if index_path.exists():
        try:
            with index_path.open("r", encoding="utf-8") as f:
                idx = json.load(f)
            known_src_ids = {s.get("id") for s in idx.get("sources", []) if s.get("id")}
        except (json.JSONDecodeError, OSError) as e:
            emit_error("index_corrupt", f"could not read index.json: {e}")

    # Read findings, summary, report
    findings_text = _read_file(workspace / "notes" / "findings.md")
    summary_text = _read_file(workspace / "notes" / "summary.md")
    report_text = _read_file(workspace / "outputs" / "report.md")

    # Extract finding IDs by `## fnd_NNN` headers
    known_fnd_ids: set[str] = set()
    for m in re.finditer(r"^##\s+fnd_(\d{3,})\b", findings_text, re.MULTILINE):
        known_fnd_ids.add(f"fnd_{m.group(1)}")

    # Source IDs referenced in findings (from **Source:** lines)
    findings_src_refs: set[str] = set()
    for m in re.finditer(r"\*\*Source:\*\*\s*([^\n]+)", findings_text):
        for sid in SRC_ID_RE.findall(m.group(1)):
            findings_src_refs.add(f"src_{sid}")

    # Finding IDs referenced in summary
    summary_fnd_refs: set[str] = set()
    for m in re.finditer(r"\*\*Based on:\*\*\s*([^\n]+)", summary_text):
        for fid in FND_ID_RE.findall(m.group(1)):
            summary_fnd_refs.add(f"fnd_{fid}")

    # Source IDs cited in report
    report_src_refs: set[str] = set()
    for sid in SRC_ID_RE.findall(report_text):
        report_src_refs.add(f"src_{sid}")

    # Compute orphans and invalid references
    invalid_src_in_findings = findings_src_refs - known_src_ids
    invalid_fnd_in_summary = summary_fnd_refs - known_fnd_ids
    invalid_src_in_report = report_src_refs - known_src_ids

    all_cited = findings_src_refs | report_src_refs
    orphaned_src = known_src_ids - all_cited

    # Check next_id matches count
    next_id_expected = (max((int(sid.split("_", 1)[1]) for sid in known_src_ids), default=0)) + 1
    next_id_in_index = idx.get("next_id", 1) if index_path.exists() else 1
    id_counter_valid = next_id_expected == next_id_in_index

    # Status
    total_errors = (
        len(invalid_src_in_findings) + len(invalid_fnd_in_summary) + len(invalid_src_in_report)
    )
    if total_errors == 0 and id_counter_valid:
        status = "ok"
    elif total_errors == 0:
        status = "warning"  # orphans or id counter issue, no broken refs
    else:
        status = "error"

    return {
        "workspace": str(workspace),
        "status": status,
        "sources_in_index": len(known_src_ids),
        "findings_count": len(known_fnd_ids),
        "sources_cited_in_findings": len(findings_src_refs),
        "sources_cited_in_report": len(report_src_refs),
        "findings_referenced_in_summary": len(summary_fnd_refs),
        "orphaned_sources": sorted(orphaned_src),
        "invalid_references": {
            "source_in_findings": sorted(invalid_src_in_findings),
            "finding_in_summary": sorted(invalid_fnd_in_summary),
            "source_in_report": sorted(invalid_src_in_report),
        },
        "id_counter_valid": id_counter_valid,
        "id_counter_expected": next_id_expected,
        "id_counter_actual": next_id_in_index,
        "summary": _audit_summary(
            len(known_src_ids),
            len(findings_src_refs),
            len(report_src_refs),
            len(orphaned_src),
            total_errors,
        ),
    }


def _audit_summary(
    total: int,
    cited_in_findings: int,
    cited_in_report: int,
    orphans: int,
    invalid_count: int,
) -> str:
    """Build a human-readable one-line audit summary."""
    if total == 0:
        return "No sources yet"
    if invalid_count > 0:
        return f"FAIL: {invalid_count} invalid reference(s) detected"
    if orphans == 0 and cited_in_report == total:
        return f"OK: {total} sources, all cited"
    return f"OK with warnings: {total} sources, {orphans} orphaned, {cited_in_report} cited in report"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="List, show, delete, or audit Calixto research workspaces.",
        prog="workspace_info",
    )
    sub = p.add_subparsers(dest="command", required=True, metavar="COMMAND")

    list_p = sub.add_parser("list", help="List all workspaces under --path.")
    list_p.add_argument("--path", default="./workspaces", help="Parent directory to scan (default: ./workspaces).")

    show_p = sub.add_parser("show", help="Show summary of a single workspace.")
    show_p.add_argument("name", help="Workspace name or path.")
    show_p.add_argument("--path", default="./workspaces", help="Parent directory (default: ./workspaces).")

    del_p = sub.add_parser("delete", help="Delete a workspace.")
    del_p.add_argument("name", help="Workspace name or path.")
    del_p.add_argument("--path", default="./workspaces", help="Parent directory (default: ./workspaces).")
    del_p.add_argument("--force", action="store_true", help="Skip the confirmation prompt.")

    audit_p = sub.add_parser("audit", help="Verify traceability chain.")
    audit_p.add_argument("name", help="Workspace name or path.")
    audit_p.add_argument("--path", default="./workspaces", help="Parent directory (default: ./workspaces).")

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "list":
        parent = workspace_path(args.path)
        result = cmd_list(parent)
        emit_ok(result)
    elif args.command == "show":
        parent = workspace_path(args.path)
        workspace = _resolve_workspace(args.name, parent)
        if not (workspace / "config.json").exists():
            emit_error("workspace_not_found", f"workspace not found: {args.name} (looked in {parent})")
        result = cmd_show(workspace)
        emit_ok(result)
    elif args.command == "delete":
        parent = workspace_path(args.path)
        workspace = _resolve_workspace_for_delete(args.name, parent)
        result = cmd_delete(workspace, force=args.force)
        emit_ok(result)
    elif args.command == "audit":
        parent = workspace_path(args.path)
        workspace = _resolve_workspace(args.name, parent)
        result = cmd_audit(workspace)
        emit_ok(result)
    else:
        emit_error("unknown_command", f"unknown command: {args.command}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
