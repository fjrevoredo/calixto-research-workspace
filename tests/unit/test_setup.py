"""Tests for the setup scripts (setup.sh, setup.ps1).

These tests verify the setup scripts verify the correct package name
(`ddgs`, not the legacy `duckduckgo_search`) and use proper exit code
checking.

The tests are split by platform:
- setup.sh: bash-only, runs on Unix
- setup.ps1: PowerShell-only, runs on Windows

Both are skipped on the wrong platform to avoid false negatives.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SETUP_SH = REPO_ROOT / "setup.sh"
SETUP_PS1 = REPO_ROOT / "setup.ps1"


def _is_windows() -> bool:
    return sys.platform == "win32"


def _have_bash() -> bool:
    return shutil.which("bash") is not None


def _have_pwsh() -> bool:
    return shutil.which("pwsh") is not None


# ---------------------------------------------------------------------------
# setup.sh tests
# ---------------------------------------------------------------------------


class TestSetupShPackageCheck:
    """setup.sh must verify `ddgs`, not the legacy `duckduckgo_search`."""

    def test_setup_sh_verifies_ddgs(self) -> None:
        if not _have_bash():
            pytest.skip("bash not available")
        text = SETUP_SH.read_text(encoding="utf-8")
        # The script's verification step must import ddgs
        assert "import ddgs" in text, (
            "setup.sh verification step must import `ddgs` (the current "
            "name of the duckduckgo-search package)."
        )

    def test_setup_sh_does_not_verify_legacy_module(self) -> None:
        if not _have_bash():
            pytest.skip("bash not available")
        text = SETUP_SH.read_text(encoding="utf-8")
        # The script's verification step must not import the
        # unmaintained `duckduckgo_search` name. We allow it in
        # comments.
        for line in text.splitlines():
            stripped = line.split("#", 1)[0]  # strip trailing comment
            if "import duckduckgo_search" in stripped:
                pytest.fail(
                    f"setup.sh imports the legacy `duckduckgo_search` "
                    f"module on a non-comment line: {line!r}"
                )

    def test_setup_sh_lists_ddgs_in_install_message(self) -> None:
        """The progress message about what's being installed should also reflect the new name."""
        if not _have_bash():
            pytest.skip("bash not available")
        text = SETUP_SH.read_text(encoding="utf-8")
        # The install-step progress message should mention ddgs, not
        # the legacy name.
        assert "ddgs" in text
        # And the legacy name should not appear outside of rename-context
        # comments. We allow any line that contains the word "renamed",
        # OR is within 2 lines of a line that does.
        lines = text.splitlines()
        renamed_lines = {
            i for i, line in enumerate(lines) if "renamed" in line
        }
        legacy_violations: list[tuple[int, str]] = []
        for i, line in enumerate(lines):
            if "duckduckgo-search" not in line:
                continue
            if any(abs(i - r) <= 2 for r in renamed_lines):
                continue
            legacy_violations.append((i + 1, line))
        assert not legacy_violations, (
            f"setup.sh has {len(legacy_violations)} duckduckgo-search "
            f"references outside rename context: {legacy_violations}. "
            "The package is now `ddgs`."
        )

    def test_setup_sh_syntax(self) -> None:
        if not _have_bash():
            pytest.skip("bash not available")
        result = subprocess.run(
            ["bash", "-n", str(SETUP_SH)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"setup.sh has a syntax error: {result.stderr}"
        )


# ---------------------------------------------------------------------------
# setup.ps1 tests
# ---------------------------------------------------------------------------


class TestSetupPs1NativeExitCodes:
    """setup.ps1 must check $LASTEXITCODE after every required native command."""

    def test_setup_ps1_syntax(self) -> None:
        if not _have_pwsh():
            pytest.skip("pwsh not available")
        result = subprocess.run(
            [
                "pwsh", "-NoProfile", "-Command",
                f"$null = [System.Management.Automation.PSParser]::Tokenize("
                f"(Get-Content -Raw '{SETUP_PS1}'), [ref]$null); 'OK'"
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"setup.ps1 has a syntax error: {result.stderr}"
        )

    def test_setup_ps1_verifies_ddgs(self) -> None:
        if not _have_pwsh():
            pytest.skip("pwsh not available")
        text = SETUP_PS1.read_text(encoding="utf-8")
        assert "import ddgs" in text, (
            "setup.ps1 verification step must import `ddgs` (the current "
            "name of the duckduckgo-search package)."
        )

    def test_setup_ps1_does_not_import_legacy_module(self) -> None:
        if not _have_pwsh():
            pytest.skip("pwsh not available")
        text = SETUP_PS1.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.split("#", 1)[0]
            if "import duckduckgo_search" in stripped:
                pytest.fail(
                    f"setup.ps1 imports the legacy `duckduckgo_search` "
                    f"module on a non-comment line: {line!r}"
                )

    def test_setup_ps1_checks_last_exit_code_for_uv_sync(self) -> None:
        """After `uv sync`, the script must check $LASTEXITCODE explicitly.

        PowerShell's try/catch does NOT reliably catch native
        executable nonzero exits, so a missing $LASTEXITCODE check
        would let setup silently print "Python dependencies
        installed" even when uv sync failed.
        """
        if not _have_pwsh():
            pytest.skip("pwsh not available")
        text = SETUP_PS1.read_text(encoding="utf-8")
        # Find the `uv sync` line and assert a $LASTEXITCODE check
        # appears within the next ~10 lines.
        lines = text.splitlines()
        for i, line in enumerate(lines):
            stripped = line.split("#", 1)[0]
            if "uv sync" in stripped and "if " not in stripped:
                # Look ahead for $LASTEXITCODE check
                window = lines[i : i + 12]
                window_text = "\n".join(window)
                assert "LASTEXITCODE" in window_text, (
                    f"`uv sync` at line {i+1} is not followed by a "
                    f"$LASTEXITCODE check within the next 12 lines. "
                    f"Setup can silently succeed even when uv fails."
                )

    def test_setup_ps1_checks_last_exit_code_for_crawl4ai(self) -> None:
        """After `crawl4ai-setup`, the script must check $LASTEXITCODE."""
        if not _have_pwsh():
            pytest.skip("pwsh not available")
        text = SETUP_PS1.read_text(encoding="utf-8")
        lines = text.splitlines()
        for i, line in enumerate(lines):
            stripped = line.split("#", 1)[0]
            if "crawl4ai-setup" in stripped:
                window = lines[i : i + 12]
                window_text = "\n".join(window)
                assert "LASTEXITCODE" in window_text, (
                    f"`crawl4ai-setup` at line {i+1} is not followed "
                    f"by a $LASTEXITCODE check."
                )

    def test_setup_ps1_lists_ddgs_in_install_message(self) -> None:
        if not _have_pwsh():
            pytest.skip("pwsh not available")
        text = SETUP_PS1.read_text(encoding="utf-8")
        assert "ddgs" in text
        lines = text.splitlines()
        renamed_lines = {
            i for i, line in enumerate(lines) if "renamed" in line
        }
        legacy_violations: list[tuple[int, str]] = []
        for i, line in enumerate(lines):
            if "duckduckgo-search" not in line:
                continue
            if any(abs(i - r) <= 2 for r in renamed_lines):
                continue
            legacy_violations.append((i + 1, line))
        assert not legacy_violations, (
            f"setup.ps1 has {len(legacy_violations)} duckduckgo-search "
            f"references outside rename context: {legacy_violations}. "
            "The package is now `ddgs`."
        )
