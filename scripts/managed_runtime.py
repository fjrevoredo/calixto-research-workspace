"""
managed_runtime.py: toolkit-local managed runtime lifecycle for Calixto workspaces.

The managed runtime cache is owned by one toolkit root under `.calixto/`.
Each runtime key is content-addressed from the bundled workspace dependency
files plus host compatibility dimensions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# Make this script runnable as `python scripts/managed_runtime.py ...`
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _common import emit_error, emit_ok, is_valid_slug, utcnow_iso
from runtime_bundle import REPO_ROOT
from toolkit_git import toolkit_build_metadata


STATE_DIR_NAME = ".calixto"
MANAGED_RUNTIMES_DIRNAME = "runtimes"
MANAGED_RUNTIME_METADATA_FILENAME = "runtime.json"
MANAGED_RUNTIME_ENV_DIRNAME = ".venv"
MANAGED_RUNTIME_LOCK_DIRNAME = "locks"
LOCK_STALE_AFTER_SECONDS = 15 * 60
LOCK_ACQUIRE_TIMEOUT_SECONDS = 120.0
LOCK_POLL_INTERVAL_SECONDS = 0.2
METADATA_VERSION = 1
DISPLAY_KEY_LENGTH = 12

TOOLKIT_RUNTIME_PROJECT = REPO_ROOT / "runtime" / "workspace"
TOOLKIT_RUNTIME_PYPROJECT = TOOLKIT_RUNTIME_PROJECT / "pyproject.toml"
TOOLKIT_RUNTIME_LOCKFILE = TOOLKIT_RUNTIME_PROJECT / "uv.lock"
TOOLKIT_RUNTIME_PROBE = REPO_ROOT / "scripts" / "runtime_probe.py"


@dataclass(frozen=True)
class RuntimeSpec:
    full_key: str
    display_key: str
    platform_name: str
    architecture: str
    python_version: str
    pyproject_sha256: str
    lockfile_sha256: str


def _state_dir(toolkit_root: Path = REPO_ROOT) -> Path:
    return toolkit_root / STATE_DIR_NAME


def managed_runtimes_dir(toolkit_root: Path = REPO_ROOT) -> Path:
    return _state_dir(toolkit_root) / MANAGED_RUNTIMES_DIRNAME


def managed_runtime_locks_dir(toolkit_root: Path = REPO_ROOT) -> Path:
    return managed_runtimes_dir(toolkit_root) / MANAGED_RUNTIME_LOCK_DIRNAME


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _current_python_version() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def _platform_name() -> str:
    return platform.system().lower()


def _architecture() -> str:
    return platform.machine().lower()


def _build_runtime_key(pyproject_bytes: bytes, lockfile_bytes: bytes) -> RuntimeSpec:
    pyproject_sha = _sha256_bytes(pyproject_bytes)
    lockfile_sha = _sha256_bytes(lockfile_bytes)
    payload = {
        "platform": _platform_name(),
        "architecture": _architecture(),
        "python_version": _current_python_version(),
        "pyproject_sha256": pyproject_sha,
        "lockfile_sha256": lockfile_sha,
    }
    full_key = _sha256_bytes(json.dumps(payload, sort_keys=True).encode("utf-8"))
    return RuntimeSpec(
        full_key=full_key,
        display_key=full_key[:DISPLAY_KEY_LENGTH],
        platform_name=payload["platform"],
        architecture=payload["architecture"],
        python_version=payload["python_version"],
        pyproject_sha256=pyproject_sha,
        lockfile_sha256=lockfile_sha,
    )


def current_runtime_spec() -> RuntimeSpec:
    return _build_runtime_key(_read_bytes(TOOLKIT_RUNTIME_PYPROJECT), _read_bytes(TOOLKIT_RUNTIME_LOCKFILE))


def runtime_spec_for_workspace(workspace: Path) -> RuntimeSpec:
    pyproject_path = workspace / "pyproject.toml"
    lockfile_path = workspace / "uv.lock"
    return _build_runtime_key(_read_bytes(pyproject_path), _read_bytes(lockfile_path))


def runtime_dir_for_spec(spec: RuntimeSpec, toolkit_root: Path = REPO_ROOT) -> Path:
    return managed_runtimes_dir(toolkit_root) / spec.display_key


def runtime_metadata_path(runtime_dir: Path) -> Path:
    return runtime_dir / MANAGED_RUNTIME_METADATA_FILENAME


def runtime_environment_path(runtime_dir: Path) -> Path:
    return runtime_dir / MANAGED_RUNTIME_ENV_DIRNAME


def _runtime_metadata_for_spec(spec: RuntimeSpec) -> dict[str, Any]:
    metadata = {
        "metadata_version": METADATA_VERSION,
        "runtime_key": spec.full_key,
        "runtime_display_key": spec.display_key,
        "platform": spec.platform_name,
        "architecture": spec.architecture,
        "python_version": spec.python_version,
        "workspace_pyproject_sha256": spec.pyproject_sha256,
        "workspace_uv_lock_sha256": spec.lockfile_sha256,
        "prepared_at": utcnow_iso(),
        "environment_dirname": MANAGED_RUNTIME_ENV_DIRNAME,
    }
    metadata.update(toolkit_build_metadata())
    return metadata


def load_runtime_metadata(runtime_dir: Path) -> dict[str, Any] | None:
    path = runtime_metadata_path(runtime_dir)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def runtime_metadata_matches_spec(metadata: dict[str, Any], spec: RuntimeSpec) -> bool:
    return (
        metadata.get("metadata_version") == METADATA_VERSION
        and metadata.get("runtime_key") == spec.full_key
        and metadata.get("runtime_display_key") == spec.display_key
        and metadata.get("platform") == spec.platform_name
        and metadata.get("architecture") == spec.architecture
        and metadata.get("python_version") == spec.python_version
        and metadata.get("workspace_pyproject_sha256") == spec.pyproject_sha256
        and metadata.get("workspace_uv_lock_sha256") == spec.lockfile_sha256
    )


def _runtime_lock_dir(spec: RuntimeSpec, toolkit_root: Path = REPO_ROOT) -> Path:
    return managed_runtime_locks_dir(toolkit_root) / f"{spec.display_key}.lock"


@contextmanager
def _runtime_lock(spec: RuntimeSpec, toolkit_root: Path = REPO_ROOT):
    lock_dir = _runtime_lock_dir(spec, toolkit_root)
    lock_dir.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    while True:
        try:
            lock_dir.mkdir()
            break
        except FileExistsError:
            try:
                age_seconds = time.time() - lock_dir.stat().st_mtime
            except OSError:
                age_seconds = 0
            if age_seconds >= LOCK_STALE_AFTER_SECONDS:
                shutil.rmtree(lock_dir, ignore_errors=True)
                continue
            if time.monotonic() - started >= LOCK_ACQUIRE_TIMEOUT_SECONDS:
                raise TimeoutError(f"timed out waiting for managed runtime lock {lock_dir}")
            time.sleep(LOCK_POLL_INTERVAL_SECONDS)
    try:
        yield
    finally:
        shutil.rmtree(lock_dir, ignore_errors=True)


def _uv_environment(environment_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["UV_PROJECT_ENVIRONMENT"] = str(environment_path)
    env["UV_NO_SYNC"] = "1"
    return env


def _run(
    argv: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _parse_probe_result(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    output = (result.stdout or "").strip()
    try:
        payload = json.loads(output) if output else {}
    except json.JSONDecodeError:
        payload = {
            "status": "error",
            "error": "probe_failed",
            "message": output or (result.stderr or "").strip() or "runtime probe produced invalid output",
        }
    if not isinstance(payload, dict):
        payload = {
            "status": "error",
            "error": "probe_failed",
            "message": "runtime probe did not return a JSON object",
        }
    if result.returncode != 0 and payload.get("status") != "error":
        payload["status"] = "error"
        payload.setdefault("error", "probe_failed")
        payload.setdefault("message", (result.stderr or "").strip() or "runtime probe failed")
    return payload


def probe_environment(project_path: Path, environment_path: Path, probe_script: Path) -> dict[str, Any]:
    result = _run(
        [
            "uv",
            "run",
            "--project",
            str(project_path),
            "--no-sync",
            "python",
            str(probe_script),
        ],
        cwd=project_path,
        env=_uv_environment(environment_path),
    )
    return _parse_probe_result(result)


def _install_browser_assets(project_path: Path, environment_path: Path) -> subprocess.CompletedProcess[str]:
    return _run(
        [
            "uv",
            "run",
            "--project",
            str(project_path),
            "--no-sync",
            "python",
            "-m",
            "playwright",
            "install",
            "chromium",
        ],
        cwd=project_path,
        env=_uv_environment(environment_path),
    )


def _runtime_valid(runtime_dir: Path, spec: RuntimeSpec, *, probe_script: Path = TOOLKIT_RUNTIME_PROBE) -> bool:
    metadata = load_runtime_metadata(runtime_dir)
    environment_path = runtime_environment_path(runtime_dir)
    if not metadata or not runtime_metadata_matches_spec(metadata, spec):
        return False
    if not environment_path.exists():
        return False
    probe = probe_environment(TOOLKIT_RUNTIME_PROJECT, environment_path, probe_script)
    return probe.get("status") == "ok" and probe.get("browser_ready") is True


def _prepare_staging_environment(staging_dir: Path) -> Path:
    env_path = runtime_environment_path(staging_dir)
    sync_env = os.environ.copy()
    sync_env["UV_PROJECT_ENVIRONMENT"] = str(env_path)
    sync = _run(
        [
            "uv",
            "sync",
            "--locked",
            "--project",
            str(TOOLKIT_RUNTIME_PROJECT),
        ],
        cwd=REPO_ROOT,
        env=sync_env,
    )
    if sync.returncode != 0:
        raise RuntimeError(
            f"managed runtime dependency sync failed: {(sync.stderr or sync.stdout).strip()}"
        )

    probe = probe_environment(TOOLKIT_RUNTIME_PROJECT, env_path, TOOLKIT_RUNTIME_PROBE)
    if probe.get("status") == "error" and probe.get("error") == "missing_browser":
        install = _install_browser_assets(TOOLKIT_RUNTIME_PROJECT, env_path)
        if install.returncode != 0:
            raise RuntimeError(
                f"managed runtime browser install failed: {(install.stderr or install.stdout).strip()}"
            )
        probe = probe_environment(TOOLKIT_RUNTIME_PROJECT, env_path, TOOLKIT_RUNTIME_PROBE)
    if probe.get("status") != "ok" or probe.get("browser_ready") is not True:
        raise RuntimeError(f"managed runtime probe failed: {probe.get('message', probe)}")
    return env_path


def ensure_managed_runtime(toolkit_root: Path = REPO_ROOT) -> dict[str, Any]:
    spec = current_runtime_spec()
    runtimes_dir = managed_runtimes_dir(toolkit_root)
    runtime_dir = runtime_dir_for_spec(spec, toolkit_root)
    runtimes_dir.mkdir(parents=True, exist_ok=True)

    if _runtime_valid(runtime_dir, spec):
        return {
            "runtime_mode": "managed",
            "runtime_key": spec.full_key,
            "runtime_display_key": spec.display_key,
            "runtime_dir": str(runtime_dir),
            "environment_path": str(runtime_environment_path(runtime_dir)),
            "prepared": False,
        }

    with _runtime_lock(spec, toolkit_root):
        if _runtime_valid(runtime_dir, spec):
            return {
                "runtime_mode": "managed",
                "runtime_key": spec.full_key,
                "runtime_display_key": spec.display_key,
                "runtime_dir": str(runtime_dir),
                "environment_path": str(runtime_environment_path(runtime_dir)),
                "prepared": False,
            }

        if runtime_dir.exists():
            shutil.rmtree(runtime_dir, ignore_errors=True)

        staging_dir = runtimes_dir / f".staging-{spec.display_key}-{uuid.uuid4().hex[:8]}"
        try:
            staging_dir.mkdir(parents=True, exist_ok=False)
            _prepare_staging_environment(staging_dir)
            runtime_metadata_path(staging_dir).write_text(
                json.dumps(_runtime_metadata_for_spec(spec), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            staging_dir.replace(runtime_dir)
        finally:
            if staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)

    return {
        "runtime_mode": "managed",
        "runtime_key": spec.full_key,
        "runtime_display_key": spec.display_key,
        "runtime_dir": str(runtime_dir),
        "environment_path": str(runtime_environment_path(runtime_dir)),
        "prepared": True,
    }


def is_managed_workspace_location(workspace: Path, toolkit_root: Path = REPO_ROOT) -> bool:
    workspaces_root = (toolkit_root / "workspaces").resolve(strict=False)
    workspace_resolved = workspace.resolve(strict=False)
    try:
        workspace_resolved.relative_to(workspaces_root)
    except ValueError:
        return False
    return True


def validate_local_workspace_runtime(workspace: Path) -> dict[str, Any]:
    env_path = workspace / ".venv"
    if not env_path.exists():
        return {
            "status": "error",
            "error": "workspace_runtime_missing",
            "message": f"workspace-local runtime is missing at {env_path}",
        }
    probe_script = workspace / "scripts" / "runtime_probe.py"
    return probe_environment(workspace, env_path, probe_script)


def _workspace_setup_argv(workspace: Path) -> list[str]:
    if sys.platform.startswith("win"):
        shell_host = shutil.which("pwsh") or shutil.which("powershell") or "powershell"
        return [
            shell_host,
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(workspace / "setup.ps1"),
        ]
    return ["bash", str(workspace / "setup.sh")]


def setup_local_workspace_runtime(workspace: Path) -> dict[str, Any]:
    result = _run(_workspace_setup_argv(workspace), cwd=workspace, env=os.environ.copy())
    if result.returncode != 0:
        return {
            "status": "error",
            "error": "workspace_setup_failed",
            "message": (result.stderr or result.stdout).strip() or "workspace setup failed",
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    return validate_local_workspace_runtime(workspace)


def select_runtime_for_workspace(
    workspace: Path,
    *,
    allow_local_setup: bool = False,
) -> dict[str, Any]:
    runtime_spec = runtime_spec_for_workspace(workspace)
    if is_managed_workspace_location(workspace):
        runtime_dir = runtime_dir_for_spec(runtime_spec)
        metadata = load_runtime_metadata(runtime_dir)
        if metadata and runtime_metadata_matches_spec(metadata, runtime_spec):
            probe = probe_environment(
                TOOLKIT_RUNTIME_PROJECT,
                runtime_environment_path(runtime_dir),
                TOOLKIT_RUNTIME_PROBE,
            )
            if probe.get("status") == "ok" and probe.get("browser_ready") is True:
                return {
                    "runtime_mode": "managed",
                    "runtime_key": runtime_spec.full_key,
                    "runtime_display_key": runtime_spec.display_key,
                    "runtime_dir": str(runtime_dir),
                    "environment_path": str(runtime_environment_path(runtime_dir)),
                    "reason": "exact_managed_runtime_match",
                }

    local_probe = validate_local_workspace_runtime(workspace)
    if local_probe.get("status") == "ok" and local_probe.get("browser_ready") is True:
        return {
            "runtime_mode": "local",
            "runtime_key": runtime_spec.full_key,
            "runtime_display_key": runtime_spec.display_key,
            "runtime_dir": str(workspace / ".venv"),
            "environment_path": str(workspace / ".venv"),
            "reason": "valid_workspace_local_runtime",
        }

    if allow_local_setup:
        setup_probe = setup_local_workspace_runtime(workspace)
        if setup_probe.get("status") == "ok" and setup_probe.get("browser_ready") is True:
            return {
                "runtime_mode": "local",
                "runtime_key": runtime_spec.full_key,
                "runtime_display_key": runtime_spec.display_key,
                "runtime_dir": str(workspace / ".venv"),
                "environment_path": str(workspace / ".venv"),
                "reason": "workspace_local_setup_completed",
            }
        return {
            "status": "error",
            "error": setup_probe.get("error", "workspace_setup_failed"),
            "message": setup_probe.get("message", "workspace setup failed"),
        }

    return {
        "status": "error",
        "error": local_probe.get("error", "runtime_unavailable"),
        "message": local_probe.get(
            "message",
            "no compatible managed runtime or valid workspace-local runtime is available",
        ),
        "runtime_key": runtime_spec.full_key,
        "runtime_display_key": runtime_spec.display_key,
    }


def runtime_environment_overrides(selection: dict[str, Any]) -> dict[str, str]:
    env = os.environ.copy()
    env["UV_PROJECT_ENVIRONMENT"] = selection["environment_path"]
    env["UV_NO_SYNC"] = "1"
    env["CALIXTO_RUNTIME_MODE"] = selection["runtime_mode"]
    env["CALIXTO_RUNTIME_KEY"] = selection["runtime_key"]
    return env


def _workspace_runtime_key_or_none(workspace: Path) -> str | None:
    try:
        return runtime_spec_for_workspace(workspace).full_key
    except (FileNotFoundError, OSError):
        return None


def _iter_workspace_dirs(toolkit_root: Path = REPO_ROOT) -> list[Path]:
    workspaces_root = toolkit_root / "workspaces"
    if not workspaces_root.exists():
        return []
    return sorted([path for path in workspaces_root.iterdir() if path.is_dir()], key=lambda item: item.name)


def referenced_workspace_map(toolkit_root: Path = REPO_ROOT) -> dict[str, list[str]]:
    references: dict[str, list[str]] = {}
    for workspace in _iter_workspace_dirs(toolkit_root):
        config_path = workspace / "config.json"
        if not config_path.exists():
            continue
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if config.get("workspace_layout") != "standalone":
            continue
        runtime_key = _workspace_runtime_key_or_none(workspace)
        if not runtime_key:
            continue
        references.setdefault(runtime_key, []).append(workspace.name)
    return references


def _directory_size(path: Path) -> int:
    total = 0
    if not path.exists():
        return total
    for current in path.rglob("*"):
        if current.is_file():
            total += current.stat().st_size
    return total


def list_managed_runtimes(toolkit_root: Path = REPO_ROOT) -> list[dict[str, Any]]:
    runtimes_root = managed_runtimes_dir(toolkit_root)
    references = referenced_workspace_map(toolkit_root)
    current_spec = current_runtime_spec()
    entries: list[dict[str, Any]] = []
    if not runtimes_root.exists():
        return entries
    for entry in sorted(runtimes_root.iterdir(), key=lambda item: item.name):
        if not entry.is_dir():
            continue
        if entry.name.startswith(".staging-") or entry.name == MANAGED_RUNTIME_LOCK_DIRNAME:
            continue
        metadata = load_runtime_metadata(entry)
        runtime_key = metadata.get("runtime_key") if metadata else None
        valid = bool(metadata and runtime_metadata_matches_spec(metadata, RuntimeSpec(
            full_key=str(metadata.get("runtime_key", "")),
            display_key=str(metadata.get("runtime_display_key", "")),
            platform_name=str(metadata.get("platform", "")),
            architecture=str(metadata.get("architecture", "")),
            python_version=str(metadata.get("python_version", "")),
            pyproject_sha256=str(metadata.get("workspace_pyproject_sha256", "")),
            lockfile_sha256=str(metadata.get("workspace_uv_lock_sha256", "")),
        )))
        entries.append(
            {
                "runtime_display_key": entry.name,
                "runtime_key": runtime_key,
                "runtime_dir": str(entry),
                "is_current_key": runtime_key == current_spec.full_key,
                "valid": valid,
                "apparent_size_bytes": _directory_size(entry),
                "referenced_workspaces": references.get(runtime_key or "", []),
            }
        )
    return entries


def prune_managed_runtimes(
    *,
    toolkit_root: Path = REPO_ROOT,
    selected_keys: list[str] | None = None,
    force: bool = False,
    dry_run: bool = True,
) -> dict[str, Any]:
    entries = list_managed_runtimes(toolkit_root)
    selected = set(selected_keys or [])
    deleted: list[str] = []
    kept: list[str] = []
    reasons: dict[str, str] = {}

    for entry in entries:
        key = entry["runtime_key"] or entry["runtime_display_key"]
        is_selected = not selected or key in selected or entry["runtime_display_key"] in selected
        if not is_selected:
            kept.append(entry["runtime_display_key"])
            reasons[entry["runtime_display_key"]] = "not_selected"
            continue
        if entry["is_current_key"] and not force:
            kept.append(entry["runtime_display_key"])
            reasons[entry["runtime_display_key"]] = "current_key_protected"
            continue
        if entry["referenced_workspaces"] and not force:
            kept.append(entry["runtime_display_key"])
            reasons[entry["runtime_display_key"]] = "referenced_workspace_protected"
            continue
        if dry_run:
            deleted.append(entry["runtime_display_key"])
            reasons[entry["runtime_display_key"]] = "dry_run_candidate"
            continue
        shutil.rmtree(Path(entry["runtime_dir"]), ignore_errors=True)
        deleted.append(entry["runtime_display_key"])
        reasons[entry["runtime_display_key"]] = "deleted"

    return {
        "dry_run": dry_run,
        "force": force,
        "deleted": deleted,
        "kept": kept,
        "reasons": reasons,
    }


def _prepare_command() -> int:
    emit_ok(ensure_managed_runtime())
    return 0


def _list_command() -> int:
    emit_ok({"runtimes": list_managed_runtimes()})
    return 0


def _prune_command(args: argparse.Namespace) -> int:
    emit_ok(
        prune_managed_runtimes(
            selected_keys=args.key or [],
            force=args.force,
            dry_run=not args.apply,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect and prepare Calixto managed runtimes.",
        prog="managed_runtime",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("prepare", help="Prepare the current managed runtime key.")
    subparsers.add_parser("list", help="List managed runtimes.")

    prune_parser = subparsers.add_parser("prune", help="Prune managed runtimes.")
    prune_parser.add_argument("--key", action="append", help="Runtime key or display key to prune.")
    prune_parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete matching runtimes. Default is dry-run only.",
    )
    prune_parser.add_argument(
        "--force",
        action="store_true",
        help="Allow pruning referenced/current runtimes when keys are explicitly selected.",
    )

    args = parser.parse_args(argv)
    if args.command == "prepare":
        return _prepare_command()
    if args.command == "list":
        return _list_command()
    if args.command == "prune":
        return _prune_command(args)
    emit_error("unknown_command", f"unknown command: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
