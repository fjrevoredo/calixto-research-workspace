"""Materialize the standalone workspace runtime bundle.

This module is used by the toolkit-side initializer and by tests that need a
single source of truth for the standalone workspace payload.
"""

from __future__ import annotations

import json
import shutil
import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_MANIFEST_PATH = REPO_ROOT / "runtime" / "workspace-manifest.json"


def load_runtime_manifest() -> dict[str, Any]:
    """Load and lightly validate the workspace runtime manifest."""
    with RUNTIME_MANIFEST_PATH.open("r", encoding="utf-8") as f:
        manifest = json.load(f)
    if not isinstance(manifest, dict):
        raise ValueError("workspace runtime manifest must be a JSON object")
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("workspace runtime manifest must contain a non-empty entries list")
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("workspace runtime manifest entries must be objects")
        kind = entry.get("kind")
        source = entry.get("source")
        destination = entry.get("destination")
        if kind not in {"file", "directory"}:
            raise ValueError(f"invalid manifest entry kind: {kind!r}")
        if not isinstance(source, str) or not source:
            raise ValueError("manifest entry source must be a non-empty string")
        if not isinstance(destination, str) or not destination:
            raise ValueError("manifest entry destination must be a non-empty string")
    return manifest


def toolkit_version() -> str:
    """Read the current toolkit version from the root pyproject."""
    pyproject_path = REPO_ROOT / "pyproject.toml"
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)
    return str(data["project"]["version"])


def runtime_bundle_version() -> str:
    """Version string recorded in standalone workspaces.

    For now, the runtime bundle version tracks the toolkit project version that
    produced it.
    """

    return toolkit_version()


def standalone_workspace_metadata() -> dict[str, Any]:
    """Return the metadata fields every standalone workspace must record."""
    manifest = load_runtime_manifest()
    return {
        "workspace_schema_version": manifest["workspace_schema_version"],
        "workspace_layout": manifest["workspace_layout"],
        "runtime_manifest_version": manifest["version"],
        "runtime_bundle_version": runtime_bundle_version(),
        "toolkit_version_created_with": toolkit_version(),
    }


def iter_runtime_entries() -> list[dict[str, str]]:
    """Return the manifest entries in declared copy order."""
    manifest = load_runtime_manifest()
    return list(manifest["entries"])


def copy_runtime_bundle(target_dir: Path) -> None:
    """Copy the standalone runtime bundle into `target_dir`.

    `target_dir` must not already exist.
    """

    if target_dir.exists():
        raise FileExistsError(f"workspace target already exists: {target_dir}")
    target_dir.mkdir(parents=True, exist_ok=False)

    for entry in iter_runtime_entries():
        source = REPO_ROOT / entry["source"]
        destination = target_dir / entry["destination"]
        if not source.exists():
            raise FileNotFoundError(f"runtime source entry not found: {source}")
        if entry["kind"] == "directory":
            shutil.copytree(source, destination, dirs_exist_ok=False)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

