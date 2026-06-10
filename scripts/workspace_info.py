"""
workspace_info.py: List, inspect, delete, and audit workspaces.

Subcommands:
    list    - List all workspaces in a parent directory
    show    - Show summary of a single workspace
    delete  - Remove a workspace (with confirmation)
    audit   - Verify the traceability chain (src > fnd > ins > report)
    sync-counters - Synchronize finding/insight counters from note contents
    review-source - Update one source review status in sources/index.json

All subcommands print structured JSON to stdout. Errors go to stderr.

Usage:
    python scripts/workspace_info.py list [--path ./workspaces]
    python scripts/workspace_info.py show <name> [--path ./workspaces]
    python scripts/workspace_info.py delete <name> [--path ./workspaces] [--force]
    python scripts/workspace_info.py audit <name> [--path ./workspaces]
    python scripts/workspace_info.py sync-counters <name> [--path ./workspaces]
    python scripts/workspace_info.py review-source <name> <src_NNN> <pending|discarded|used> [--note TEXT] [--path ./workspaces]
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
    REVIEW_STATUS_VALUES,
    SOURCE_ID_RE,
    WorkspaceStateCoordinator,
    emit_error,
    emit_ok,
    is_valid_slug,
    parse_frontmatter,
    utcnow_iso,
    workspace_path,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


PATH_QUALIFIED_SRC_RE = re.compile(r"\b(?:web|papers|code)/(src_(\d{3,}))\b")
SRC_ID_RE = re.compile(r"(?<![A-Za-z0-9_/])(src_(\d{3,}))\b")
FND_ID_RE = re.compile(r"\bfnd_(\d{3,})\b")
INS_ID_RE = re.compile(r"\bins_(\d{3,})\b")
MALFORMED_FND_ID_RE = re.compile(r"(?<![A-Za-z0-9_])(fnd\d{3,})\b")
MALFORMED_INS_ID_RE = re.compile(r"(?<![A-Za-z0-9_])(ins\d{3,})\b")


def _read_file(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _collect_source_references(text: str) -> tuple[set[str], list[str]]:
    """Return valid bare source refs plus malformed path-qualified refs."""
    refs = {match.group(1) for match in SRC_ID_RE.finditer(text)}
    malformed = sorted({match.group(0) for match in PATH_QUALIFIED_SRC_RE.finditer(text)})
    return refs, malformed


def _scan_workspace_source_files(workspace: Path) -> dict[str, Any]:
    """Scan sources/{web,papers,code} on disk and index them by file/id."""
    source_root = workspace / "sources"
    files_by_relpath: dict[str, dict[str, Any]] = {}
    ids_to_paths: dict[str, list[str]] = {}
    for source_type in ("web", "papers", "code"):
        for path in sorted((source_root / source_type).glob("*.md")):
            relpath = path.relative_to(source_root).as_posix()
            frontmatter, _ = parse_frontmatter(_read_file(path))
            source_id = str(frontmatter.get("id") or path.stem).strip()
            files_by_relpath[relpath] = {
                "path": path,
                "source_id": source_id,
                "frontmatter": frontmatter,
            }
            if source_id:
                ids_to_paths.setdefault(source_id, []).append(relpath)
    duplicate_ids = {
        source_id: sorted(paths)
        for source_id, paths in ids_to_paths.items()
        if len(paths) > 1
    }
    return {
        "files_by_relpath": files_by_relpath,
        "ids_to_paths": ids_to_paths,
        "duplicate_ids": duplicate_ids,
    }


def _highest_numbered_id(text: str, pattern: re.Pattern[str]) -> int:
    """Return the highest numeric suffix matched by `pattern`, or 0."""
    return max((int(match.group(1)) for match in pattern.finditer(text)), default=0)


def _counter_drift(actual_next_id: Any, highest_seen: int) -> dict[str, Any]:
    """Describe whether a next_* counter matches note contents."""
    expected = highest_seen + 1 if highest_seen > 0 else 1
    valid = isinstance(actual_next_id, int) and actual_next_id == expected
    return {
        "expected": expected,
        "actual": actual_next_id,
        "valid": valid,
    }


def _scope_limit_details(scope: Any, total_sources: int) -> dict[str, Any]:
    """Describe whether the workspace exceeded its configured soft source limit."""
    max_sources = None
    if isinstance(scope, dict):
        max_sources = scope.get("max_sources")
    if not isinstance(max_sources, int) or max_sources < 1:
        return {
            "max_sources": None,
            "total_sources": total_sources,
            "exceeded": False,
            "over_by": 0,
        }
    over_by = max(total_sources - max_sources, 0)
    return {
        "max_sources": max_sources,
        "total_sources": total_sources,
        "exceeded": over_by > 0,
        "over_by": over_by,
    }


def _review_status_for_entry(entry: dict[str, Any]) -> str:
    """Return the normalized review status for one source index entry."""
    status = str(entry.get("review_status", "")).strip()
    if status in REVIEW_STATUS_VALUES:
        return status
    return "pending"


def _review_status_counts(entries: list[dict[str, Any]]) -> dict[str, int]:
    """Count index entries by review status."""
    counts = {status: 0 for status in sorted(REVIEW_STATUS_VALUES)}
    for entry in entries:
        counts[_review_status_for_entry(entry)] += 1
    return counts


def _is_low_signal_or_error(entry: dict[str, Any]) -> bool:
    """Return True when an uncited source already carries a low-value signal."""
    if entry.get("low_signal") is True:
        return True
    if str(entry.get("content_quality", "")).strip() == "low_signal":
        return True
    if entry.get("snippet_only") is True:
        return True
    return bool(str(entry.get("error", "")).strip())


def _classify_orphaned_sources(
    orphaned_ids: set[str],
    index_entries_by_id: dict[str, list[dict[str, Any]]],
) -> dict[str, list[str]]:
    """Bucket uncited sources into actionable review categories."""
    buckets = {
        "pending": [],
        "discarded": [],
        "low_signal_or_error": [],
        "used_but_uncited": [],
    }
    for source_id in sorted(orphaned_ids):
        entries = index_entries_by_id.get(source_id, [])
        entry = entries[0] if entries else {}
        status = _review_status_for_entry(entry)
        if status == "discarded":
            buckets["discarded"].append(source_id)
        elif status == "used":
            buckets["used_but_uncited"].append(source_id)
        elif _is_low_signal_or_error(entry):
            buckets["low_signal_or_error"].append(source_id)
        else:
            buckets["pending"].append(source_id)
    return buckets


def _build_summary(
    *,
    status: str,
    invalid_reference_count: int,
    malformed_reference_count: int,
    malformed_identifier_count: int,
    unindexed_files: int,
    missing_index_files: int,
    duplicate_ids: int,
    counter_drift_count: int,
    orphaned_sources: int,
    scope_overrun_count: int,
) -> str:
    """Build a concise human-readable audit summary."""
    if status == "ok":
        return "OK: workspace index, files, citations, and counters are consistent"

    reasons: list[str] = []
    if invalid_reference_count:
        reasons.append(f"{invalid_reference_count} invalid reference(s)")
    if malformed_reference_count:
        reasons.append(f"{malformed_reference_count} malformed source citation(s)")
    if malformed_identifier_count:
        reasons.append(f"{malformed_identifier_count} malformed finding/insight id(s)")
    if unindexed_files:
        reasons.append(f"{unindexed_files} unindexed source file(s)")
    if missing_index_files:
        reasons.append(f"{missing_index_files} missing indexed file(s)")
    if duplicate_ids:
        reasons.append(f"{duplicate_ids} duplicate on-disk source id(s)")
    if counter_drift_count:
        reasons.append(f"{counter_drift_count} counter drift issue(s)")
    if scope_overrun_count:
        reasons.append(f"{scope_overrun_count} source(s) above configured max_sources")
    if status == "warning" and orphaned_sources:
        reasons.append(f"{orphaned_sources} orphaned source(s)")
    prefix = "ERROR" if status == "error" else "WARNING"
    return f"{prefix}: " + ", ".join(reasons)


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
        with WorkspaceStateCoordinator(workspace) as coordinator:
            cfg = coordinator.config
            idx = coordinator.index
            recovery = coordinator.recovery
            scanned = _scan_workspace_source_files(workspace)
    except (json.JSONDecodeError, OSError) as e:
        emit_error("workspace_corrupt", f"could not read workspace metadata: {e}")

    indexed_counts: dict[str, int] = {"web": 0, "papers": 0, "code": 0}
    for source in idx.get("sources", []):
        file_field = str(source.get("file", ""))
        source_type = file_field.split("/", 1)[0] if "/" in file_field else "other"
        indexed_counts[source_type] = indexed_counts.get(source_type, 0) + 1

    file_counts: dict[str, int] = {"web": 0, "papers": 0, "code": 0}
    for relpath in scanned["files_by_relpath"]:
        source_type = relpath.split("/", 1)[0]
        file_counts[source_type] = file_counts.get(source_type, 0) + 1

    indexed_files = {
        str(source.get("file", "")).strip()
        for source in idx.get("sources", [])
        if str(source.get("file", "")).strip()
    }
    unindexed_files = sorted(
        relpath
        for relpath in scanned["files_by_relpath"]
        if relpath not in indexed_files
    )
    missing_index_files = sorted(
        relpath
        for relpath in indexed_files
        if relpath not in scanned["files_by_relpath"]
    )
    total_sources = sum(indexed_counts.values())
    scope_limits = _scope_limit_details(cfg.get("scope", {}), total_sources)
    review_counts = _review_status_counts(idx.get("sources", []))

    return {
        "workspace": str(workspace),
        "name": cfg.get("name", workspace.name),
        "question": cfg.get("question", ""),
        "scope": cfg.get("scope", {}),
        "scope_limits": scope_limits,
        "providers": cfg.get("providers", {}),
        "source_counts": indexed_counts,
        "total_sources": total_sources,
        "source_file_counts": file_counts,
        "source_file_count": sum(file_counts.values()),
        "source_review_counts": review_counts,
        "search_count": len(cfg.get("searches", [])),
        "next_source_id": cfg.get("next_source_id", 1),
        "next_finding_id": cfg.get("next_finding_id", 1),
        "next_insight_id": cfg.get("next_insight_id", 1),
        "created_at": cfg.get("created_at", ""),
        "updated_at": cfg.get("updated_at", ""),
        "consistency": {
            "indexed_source_count": sum(indexed_counts.values()),
            "source_file_count": sum(file_counts.values()),
            "counts_match": sum(indexed_counts.values()) == sum(file_counts.values()),
            "unindexed_files": unindexed_files,
            "missing_index_files": missing_index_files,
            "duplicate_source_ids": scanned["duplicate_ids"],
            "recovered_transactions": recovery.get("recovered", []),
            "discarded_staged_transactions": recovery.get("discarded", []),
        },
    }


def cmd_sync_counters(workspace: Path) -> dict:
    """Synchronize finding/insight counters in config.json from note contents."""
    if not (workspace / "config.json").exists():
        emit_error("workspace_not_found", f"workspace not found at {workspace}")
    try:
        with WorkspaceStateCoordinator(workspace) as coordinator:
            cfg = coordinator.config
            idx = coordinator.index
            recovery = coordinator.recovery
            findings_text = _read_file(workspace / "notes" / "findings.md")
            summary_text = _read_file(workspace / "notes" / "summary.md")
            finding_expected = _highest_numbered_id(findings_text, FND_ID_RE) + 1
            insight_expected = _highest_numbered_id(summary_text, INS_ID_RE) + 1
            old_finding = cfg.get("next_finding_id", 1)
            old_insight = cfg.get("next_insight_id", 1)
            changed = (
                old_finding != finding_expected
                or old_insight != insight_expected
            )
            if changed:
                cfg["next_finding_id"] = finding_expected
                cfg["next_insight_id"] = insight_expected
                coordinator.commit(
                    config=cfg,
                    index=idx,
                    source_files=[],
                    transaction_label="sync_counters",
                )
    except (json.JSONDecodeError, OSError) as e:
        emit_error("workspace_corrupt", f"could not read workspace metadata: {e}")

    return {
        "workspace": str(workspace),
        "changed": changed,
        "counters": {
            "next_finding_id": {
                "old": old_finding,
                "new": finding_expected,
                "changed": old_finding != finding_expected,
            },
            "next_insight_id": {
                "old": old_insight,
                "new": insight_expected,
                "changed": old_insight != insight_expected,
            },
        },
        "recovered_transactions": recovery.get("recovered", []),
        "discarded_staged_transactions": recovery.get("discarded", []),
    }


def cmd_review_source(workspace: Path, source_id: str, review_status: str, note: str | None) -> dict:
    """Update one source's review metadata in sources/index.json."""
    if not (workspace / "config.json").exists():
        emit_error("workspace_not_found", f"workspace not found at {workspace}")
    source_id = source_id.strip()
    if not SOURCE_ID_RE.match(source_id):
        emit_error("invalid_source_id", f"source id must look like src_NNN, got: {source_id!r}")
    if review_status not in REVIEW_STATUS_VALUES:
        emit_error(
            "invalid_review_status",
            f"review status must be one of {sorted(REVIEW_STATUS_VALUES)}, got: {review_status!r}",
        )
    normalized_note = note.strip() if isinstance(note, str) else None
    if normalized_note == "":
        normalized_note = None

    try:
        with WorkspaceStateCoordinator(workspace) as coordinator:
            cfg = coordinator.config
            idx = coordinator.index
            recovery = coordinator.recovery
            matches = [
                entry
                for entry in idx.get("sources", [])
                if str(entry.get("id", "")).strip() == source_id
            ]
            if not matches:
                emit_error("source_not_found", f"source not found in index: {source_id}")
            if len(matches) > 1:
                emit_error(
                    "workspace_corrupt",
                    f"source id {source_id} appears multiple times in sources/index.json",
                )
            entry = matches[0]
            old_entry = dict(entry)
            entry["review_status"] = review_status
            if review_status == "pending":
                entry.pop("reviewed_at", None)
                if normalized_note is None:
                    entry.pop("review_note", None)
            else:
                entry["reviewed_at"] = utcnow_iso()
            if normalized_note is None:
                if review_status != "pending":
                    entry.pop("review_note", None)
            else:
                entry["review_note"] = normalized_note
            changed = entry != old_entry
            if changed:
                coordinator.commit(
                    config=cfg,
                    index=idx,
                    source_files=[],
                    transaction_label="review_source",
                )
    except (json.JSONDecodeError, OSError) as e:
        emit_error("workspace_corrupt", f"could not read workspace metadata: {e}")

    return {
        "workspace": str(workspace),
        "source_id": source_id,
        "changed": changed,
        "source": {
            "id": str(entry.get("id", "")).strip(),
            "file": str(entry.get("file", "")).strip(),
            "review_status": str(entry.get("review_status", "")).strip(),
            "review_note": entry.get("review_note"),
            "reviewed_at": entry.get("reviewed_at"),
        },
        "recovered_transactions": recovery.get("recovered", []),
        "discarded_staged_transactions": recovery.get("discarded", []),
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
    try:
        with WorkspaceStateCoordinator(workspace) as coordinator:
            cfg = coordinator.config
            idx = coordinator.index
            recovery = coordinator.recovery
            scanned = _scan_workspace_source_files(workspace)
            findings_text = _read_file(workspace / "notes" / "findings.md")
            summary_text = _read_file(workspace / "notes" / "summary.md")
            report_text = _read_file(workspace / "outputs" / "report.md")
    except (json.JSONDecodeError, OSError) as e:
        emit_error("workspace_corrupt", f"could not read workspace metadata: {e}")

    index_entries = idx.get("sources", [])
    known_src_ids = {
        str(entry.get("id", "")).strip()
        for entry in index_entries
        if str(entry.get("id", "")).strip()
    }
    index_entries_by_id: dict[str, list[dict[str, Any]]] = {}
    indexed_files: dict[str, dict[str, Any]] = {}
    for entry in index_entries:
        source_id = str(entry.get("id", "")).strip()
        file_relpath = str(entry.get("file", "")).strip()
        if source_id:
            index_entries_by_id.setdefault(source_id, []).append(entry)
        if file_relpath:
            indexed_files[file_relpath] = entry

    duplicate_index_ids = {
        source_id: sorted(str(entry.get("file", "")) for entry in entries)
        for source_id, entries in index_entries_by_id.items()
        if len(entries) > 1
    }
    unindexed_files = sorted(
        relpath
        for relpath in scanned["files_by_relpath"]
        if relpath not in indexed_files
    )
    missing_index_files = sorted(
        relpath
        for relpath in indexed_files
        if relpath not in scanned["files_by_relpath"]
    )
    frontmatter_id_mismatches: list[dict[str, str]] = []
    valid_source_ids: set[str] = set()
    for file_relpath, entry in indexed_files.items():
        on_disk = scanned["files_by_relpath"].get(file_relpath)
        if not on_disk:
            continue
        disk_id = str(on_disk["source_id"]).strip()
        index_id = str(entry.get("id", "")).strip()
        if disk_id and index_id and disk_id != index_id:
            frontmatter_id_mismatches.append(
                {
                    "file": file_relpath,
                    "index_id": index_id,
                    "frontmatter_id": disk_id,
                }
            )
            continue
        if index_id:
            valid_source_ids.add(index_id)

    known_fnd_ids = {f"fnd_{match.group(1)}" for match in re.finditer(r"^##\s+fnd_(\d{3,})\b", findings_text, re.MULTILINE)}
    known_ins_ids = {f"ins_{match.group(1)}" for match in re.finditer(r"^##\s+ins_(\d{3,})\b", summary_text, re.MULTILINE)}

    findings_src_refs: set[str] = set()
    malformed_findings_refs: list[str] = []
    for match in re.finditer(r"\*\*Source:\*\*\s*([^\n]+)", findings_text):
        refs, malformed = _collect_source_references(match.group(1))
        findings_src_refs.update(refs)
        malformed_findings_refs.extend(malformed)

    summary_fnd_refs: set[str] = set()
    malformed_summary_fnd_refs: list[str] = []
    for match in re.finditer(r"\*\*Based on:\*\*\s*([^\n]+)", summary_text):
        malformed_summary_fnd_refs.extend(
            malformed.group(1)
            for malformed in MALFORMED_FND_ID_RE.finditer(match.group(1))
        )
        for fid in FND_ID_RE.findall(match.group(1)):
            summary_fnd_refs.add(f"fnd_{fid}")

    report_src_refs, malformed_report_refs = _collect_source_references(report_text)
    malformed_finding_ids = sorted(
        {
            match.group(1)
            for match in re.finditer(r"^##\s+(fnd\d{3,})\b", findings_text, re.MULTILINE)
        }
    )
    malformed_insight_ids = sorted(
        {
            match.group(1)
            for match in re.finditer(r"^##\s+(ins\d{3,})\b", summary_text, re.MULTILINE)
        }
    )

    invalid_src_in_findings = findings_src_refs - valid_source_ids
    invalid_fnd_in_summary = summary_fnd_refs - known_fnd_ids
    invalid_src_in_report = report_src_refs - valid_source_ids
    orphaned_src = known_src_ids - (findings_src_refs | report_src_refs)
    orphaned_breakdown = _classify_orphaned_sources(orphaned_src, index_entries_by_id)

    highest_src = max((int(source_id.split("_", 1)[1]) for source_id in known_src_ids), default=0)
    source_counter = _counter_drift(idx.get("next_id", 1), highest_src)
    finding_counter = _counter_drift(cfg.get("next_finding_id", 1), _highest_numbered_id(findings_text, FND_ID_RE))
    insight_counter = _counter_drift(cfg.get("next_insight_id", 1), _highest_numbered_id(summary_text, INS_ID_RE))
    scope_limits = _scope_limit_details(cfg.get("scope", {}), len(known_src_ids))

    invalid_reference_count = (
        len(invalid_src_in_findings)
        + len(invalid_fnd_in_summary)
        + len(invalid_src_in_report)
    )
    malformed_reference_count = len(set(malformed_findings_refs)) + len(set(malformed_report_refs))
    malformed_identifier_count = (
        len(malformed_finding_ids)
        + len(malformed_insight_ids)
        + len(set(malformed_summary_fnd_refs))
    )
    counter_drift_count = sum(
        not counter["valid"]
        for counter in (source_counter, finding_counter, insight_counter)
    )
    hard_failure_count = (
        invalid_reference_count
        + malformed_reference_count
        + malformed_identifier_count
        + len(unindexed_files)
        + len(missing_index_files)
        + len(scanned["duplicate_ids"])
        + len(duplicate_index_ids)
        + len(frontmatter_id_mismatches)
        + counter_drift_count
    )
    if hard_failure_count:
        status = "error"
    elif orphaned_src or scope_limits["exceeded"]:
        status = "warning"
    else:
        status = "ok"

    remediation: dict[str, Any] = {}
    if not finding_counter["valid"] or not insight_counter["valid"]:
        remediation["sync_counters_command"] = f"python scripts/workspace_info.py sync-counters {workspace}"

    return {
        "workspace": str(workspace),
        "status": status,
        "sources_in_index": len(known_src_ids),
        "source_files_on_disk": len(scanned["files_by_relpath"]),
        "findings_count": len(known_fnd_ids),
        "insights_count": len(known_ins_ids),
        "sources_cited_in_findings": len(findings_src_refs),
        "sources_cited_in_report": len(report_src_refs),
        "findings_referenced_in_summary": len(summary_fnd_refs),
        "orphaned_sources": sorted(orphaned_src),
        "orphaned_source_breakdown": orphaned_breakdown,
        "source_review_counts": _review_status_counts(index_entries),
        "scope_limits": scope_limits,
        "filesystem_index_mismatches": {
            "unindexed_files": unindexed_files,
            "missing_index_files": missing_index_files,
            "frontmatter_id_mismatches": frontmatter_id_mismatches,
        },
        "duplicate_source_ids": {
            "on_disk": scanned["duplicate_ids"],
            "in_index": duplicate_index_ids,
        },
        "invalid_references": {
            "source_in_findings": sorted(invalid_src_in_findings),
            "finding_in_summary": sorted(invalid_fnd_in_summary),
            "source_in_report": sorted(invalid_src_in_report),
        },
        "malformed_references": {
            "source_in_findings": sorted(set(malformed_findings_refs)),
            "source_in_report": sorted(set(malformed_report_refs)),
        },
        "malformed_identifiers": {
            "finding_ids": malformed_finding_ids,
            "insight_ids": malformed_insight_ids,
            "finding_in_summary": sorted(set(malformed_summary_fnd_refs)),
        },
        "counters": {
            "source_index_next_id": source_counter,
            "next_finding_id": finding_counter,
            "next_insight_id": insight_counter,
        },
        "id_counter_valid": source_counter["valid"],
        "id_counter_expected": source_counter["expected"],
        "id_counter_actual": source_counter["actual"],
        "remediation": remediation,
        "recovered_transactions": recovery.get("recovered", []),
        "discarded_staged_transactions": recovery.get("discarded", []),
        "summary": _build_summary(
            status=status,
            invalid_reference_count=invalid_reference_count,
            malformed_reference_count=malformed_reference_count,
            malformed_identifier_count=malformed_identifier_count,
            unindexed_files=len(unindexed_files),
            missing_index_files=len(missing_index_files),
            duplicate_ids=len(scanned["duplicate_ids"]) + len(duplicate_index_ids),
            counter_drift_count=counter_drift_count,
            orphaned_sources=len(orphaned_src),
            scope_overrun_count=scope_limits["over_by"],
        ),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="List, inspect, audit, and maintain Calixto research workspaces.",
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

    sync_p = sub.add_parser("sync-counters", help="Synchronize finding/insight counters from note contents.")
    sync_p.add_argument("name", help="Workspace name or path.")
    sync_p.add_argument("--path", default="./workspaces", help="Parent directory (default: ./workspaces).")

    review_p = sub.add_parser("review-source", help="Update one source review status in sources/index.json.")
    review_p.add_argument("name", help="Workspace name or path.")
    review_p.add_argument("source_id", help="Source id to update (src_NNN).")
    review_p.add_argument("review_status", choices=sorted(REVIEW_STATUS_VALUES), help="New review status.")
    review_p.add_argument("--note", default=None, help="Optional review note.")
    review_p.add_argument("--path", default="./workspaces", help="Parent directory (default: ./workspaces).")

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
    elif args.command == "sync-counters":
        parent = workspace_path(args.path)
        workspace = _resolve_workspace(args.name, parent)
        if not (workspace / "config.json").exists():
            emit_error("workspace_not_found", f"workspace not found: {args.name} (looked in {parent})")
        result = cmd_sync_counters(workspace)
        emit_ok(result)
    elif args.command == "review-source":
        parent = workspace_path(args.path)
        workspace = _resolve_workspace(args.name, parent)
        if not (workspace / "config.json").exists():
            emit_error("workspace_not_found", f"workspace not found: {args.name} (looked in {parent})")
        result = cmd_review_source(workspace, args.source_id, args.review_status, args.note)
        emit_ok(result)
    else:
        emit_error("unknown_command", f"unknown command: {args.command}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
