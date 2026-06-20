from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import managed_runtime  # noqa: E402
import init_workspace  # noqa: E402


class TestManagedRuntimeSpecs:
    def test_generated_workspace_uses_current_runtime_key(self, tmp_path: Path) -> None:
        init_workspace.init_workspace("runtime-spec", tmp_path)
        workspace = tmp_path / "runtime-spec"
        assert managed_runtime.runtime_spec_for_workspace(workspace) == managed_runtime.current_runtime_spec()

    def test_list_managed_runtimes_reports_workspace_references(self, tmp_path: Path) -> None:
        toolkit_root = tmp_path / "toolkit"
        (toolkit_root / "workspaces").mkdir(parents=True)
        init_workspace.init_workspace("referenced", toolkit_root / "workspaces")
        workspace = toolkit_root / "workspaces" / "referenced"
        spec = managed_runtime.runtime_spec_for_workspace(workspace)

        runtime_dir = managed_runtime.managed_runtimes_dir(toolkit_root) / spec.display_key
        runtime_dir.mkdir(parents=True, exist_ok=True)
        metadata = {
            "metadata_version": managed_runtime.METADATA_VERSION,
            "runtime_key": spec.full_key,
            "runtime_display_key": spec.display_key,
            "platform": spec.platform_name,
            "architecture": spec.architecture,
            "python_version": spec.python_version,
            "workspace_pyproject_sha256": spec.pyproject_sha256,
            "workspace_uv_lock_sha256": spec.lockfile_sha256,
        }
        (runtime_dir / managed_runtime.MANAGED_RUNTIME_METADATA_FILENAME).write_text(
            json.dumps(metadata, indent=2),
            encoding="utf-8",
        )

        listed = managed_runtime.list_managed_runtimes(toolkit_root)
        assert len(listed) == 1
        assert listed[0]["referenced_workspaces"] == ["referenced"]

    def test_workspace_setup_argv_prefers_pwsh_on_windows(self, monkeypatch) -> None:
        workspace = Path(r"D:\Repos\calixto-research-workspace\workspaces\sample")

        monkeypatch.setattr(managed_runtime.sys, "platform", "win32")
        monkeypatch.setattr(
            managed_runtime.shutil,
            "which",
            lambda name: r"C:\Program Files\PowerShell\7\pwsh.exe" if name == "pwsh" else None,
        )

        argv = managed_runtime._workspace_setup_argv(workspace)

        assert argv == [
            r"C:\Program Files\PowerShell\7\pwsh.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(workspace / "setup.ps1"),
        ]
