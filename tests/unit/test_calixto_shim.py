from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import install_calixto_shim  # noqa: E402


def _create_toolkit_root(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "AGENTS.md").write_text("agents\n", encoding="utf-8")
    (path / "PHILOSOPHY.md").write_text("philosophy\n", encoding="utf-8")
    (path / "requirements.md").write_text("requirements\n", encoding="utf-8")
    (path / "scripts").mkdir(exist_ok=True)
    (path / "runtime").mkdir(exist_ok=True)
    return path


class TestCalixtoShim:
    def test_find_toolkit_root_uses_nearest_ancestor(self, tmp_path: Path) -> None:
        root_a = _create_toolkit_root(tmp_path / "toolkit-a")
        _create_toolkit_root(tmp_path / "toolkit-b")
        start = root_a / "workspaces" / "demo" / "notes"
        start.mkdir(parents=True)

        resolved = install_calixto_shim.find_toolkit_root(start, {})

        assert resolved == root_a.resolve()

    def test_find_toolkit_root_honors_explicit_override(self, tmp_path: Path) -> None:
        root_a = _create_toolkit_root(tmp_path / "toolkit-a")
        root_b = _create_toolkit_root(tmp_path / "toolkit-b")
        start = root_a / "workspaces" / "demo"
        start.mkdir(parents=True)

        resolved = install_calixto_shim.find_toolkit_root(
            start,
            {"CALIXTO_TOOLKIT_ROOT": str(root_b)},
        )

        assert resolved == root_b.resolve()

    def test_launcher_contents_are_generic_not_checkout_bound(self, tmp_path: Path) -> None:
        toolkit_root = _create_toolkit_root(tmp_path / "toolkit-a")

        posix = install_calixto_shim.posix_shim_contents()
        windows_cmd = install_calixto_shim.windows_cmd_contents()
        windows_ps1 = install_calixto_shim.windows_ps1_contents()

        for content in (posix, windows_cmd, windows_ps1):
            assert str(toolkit_root) not in content
        assert "CALIXTO_TOOLKIT_ROOT" in posix
        assert "CALIXTO_TOOLKIT_ROOT" in windows_ps1
