from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import installer_core  # noqa: E402


class TestProtectedSnapshots:
    def test_protected_snapshots_do_not_recurse_into_workspaces_directory(self, tmp_path: Path, monkeypatch) -> None:
        workspaces = tmp_path / "workspaces"
        nested = workspaces / "deep" / "nested"
        nested.mkdir(parents=True)
        (nested / "notes.md").write_text("large workspace payload\n", encoding="utf-8")

        calls: list[Path] = []
        original_hash_path = installer_core._hash_path

        def tracking_hash_path(path: Path) -> str:
            calls.append(path)
            return original_hash_path(path)

        monkeypatch.setattr(installer_core, "_hash_path", tracking_hash_path)

        snapshots = installer_core._protected_snapshots(tmp_path)

        assert "workspaces" in snapshots
        assert calls == []

    def test_protected_snapshots_still_hash_protected_files(self, tmp_path: Path, monkeypatch) -> None:
        config = tmp_path / "config.json"
        config.write_text('{"user": true}\n', encoding="utf-8")

        calls: list[Path] = []
        original_hash_path = installer_core._hash_path

        def tracking_hash_path(path: Path) -> str:
            calls.append(path)
            return original_hash_path(path)

        monkeypatch.setattr(installer_core, "_hash_path", tracking_hash_path)

        snapshots = installer_core._protected_snapshots(tmp_path)

        assert snapshots["config.json"]
        assert calls == [config]
