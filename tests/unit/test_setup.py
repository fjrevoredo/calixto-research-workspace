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

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SETUP_SH = REPO_ROOT / "setup.sh"
SETUP_PS1 = REPO_ROOT / "setup.ps1"
RUNTIME_SETUP_SH = REPO_ROOT / "runtime" / "workspace" / "setup.sh"
RUNTIME_SETUP_PS1 = REPO_ROOT / "runtime" / "workspace" / "setup.ps1"


def _iter_imported_modules(text: str) -> list[str]:
    modules: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0]
        if "import " not in line:
            continue
        _, _, tail = line.partition("import ")
        import_clause = tail.split(";", 1)[0]
        for chunk in import_clause.split(","):
            token = chunk.strip().split()
            if not token:
                continue
            modules.append(token[0].strip("'\""))
    return modules


def _imports_module(text: str, module: str) -> bool:
    return module in _iter_imported_modules(text)


def _legacy_import_lines(text: str, module: str) -> list[str]:
    matches: list[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.split("#", 1)[0]
        if module in _iter_imported_modules(stripped):
            matches.append(raw_line)
    return matches


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
        assert _imports_module(text, "ddgs"), (
            "setup.sh verification step must import `ddgs` (the current "
            "name of the duckduckgo-search package). Did not find an "
            "import of ddgs in setup.sh."
        )

    def test_setup_sh_does_not_verify_legacy_module(self) -> None:
        if not _have_bash():
            pytest.skip("bash not available")
        text = SETUP_SH.read_text(encoding="utf-8")
        violations = _legacy_import_lines(text, "duckduckgo_search")
        assert not violations, (
            "setup.sh imports the legacy `duckduckgo_search` "
            f"module on non-comment lines: {violations!r}"
        )

    def test_setup_sh_lists_ddgs_in_install_message(self) -> None:
        """The progress message about what's being installed should also reflect the new name."""
        if not _have_bash():
            pytest.skip("bash not available")
        text = SETUP_SH.read_text(encoding="utf-8")
        assert "ddgs" in text
        # The legacy name may appear ONLY in comments that explain the
        # rename. We accept any line that itself says "renamed" or
        # is within 2 lines of a line that does.
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
        bash_path = shutil.which("bash")
        # If the bash on PATH is the WSL launcher (C:\Windows\System32\bash.exe)
        # and no WSL distribution is installed, `bash -c "..."` will
        # fail with an "rpc" error before running any commands. Detect
        # that condition up front and skip.
        if bash_path and "system32" in bash_path.lower():
            launcher_check = subprocess.run(
                [bash_path, "-c", "echo READY"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if launcher_check.returncode != 0 or "rpc" in launcher_check.stderr.lower():
                pytest.skip(
                    "bash is the WSL launcher but no WSL distribution "
                    "is installed; syntax check is not meaningful here"
                )
        # Pass the script path via the CALIXTO_SCRIPT_PATH env var.
        # We avoid backslash-in-command problems entirely by writing
        # the bash snippet to a temp file and executing it. The temp
        # file's name has no colons or backslashes, so MSYS2 path
        # translation is harmless.
        import tempfile
        snippet = (
            "# Syntax-check the script at $CALIXTO_SCRIPT_PATH\n"
            'bash -n "$CALIXTO_SCRIPT_PATH"\n'
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", delete=False, encoding="utf-8"
        ) as f:
            f.write(snippet)
            snippet_path = f.name
        try:
            result = subprocess.run(
                ["bash", snippet_path],
                env={**os.environ, "CALIXTO_SCRIPT_PATH": str(SETUP_SH)},
                capture_output=True,
                text=True,
            )
        finally:
            os.unlink(snippet_path)
        if result.returncode != 0 and (
            "no such file" in result.stderr.lower()
            or "cannot access" in result.stderr.lower()
        ):
            pytest.skip(
                f"bash cannot access {SETUP_SH} on this host "
                f"(stderr={result.stderr!r}); skipping syntax check"
            )
        assert result.returncode == 0, (
            f"setup.sh has a syntax error: {result.stderr}"
        )

    def test_runtime_setup_sh_verifies_ddgs(self) -> None:
        if not _have_bash():
            pytest.skip("bash not available")
        text = RUNTIME_SETUP_SH.read_text(encoding="utf-8")
        assert _imports_module(text, "ddgs"), (
            "runtime/workspace/setup.sh verification step must import `ddgs`."
        )

    def test_runtime_setup_sh_syntax(self) -> None:
        if not _have_bash():
            pytest.skip("bash not available")
        if _is_windows():
            launcher_check = subprocess.run(
                ["bash", "-lc", ":"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            stdout_lower = launcher_check.stdout.lower()
            stderr_lower = launcher_check.stderr.lower()
            if (
                launcher_check.returncode != 0
                or "rpc" in stderr_lower
                or "windows subsystem for linux" in stdout_lower
            ):
                pytest.skip(
                    "bash is the WSL launcher but no WSL distribution "
                    "is installed; syntax check is not meaningful here"
                )
        import tempfile
        snippet = (
            "# Syntax-check the script at $CALIXTO_SCRIPT_PATH\n"
            'bash -n "$CALIXTO_SCRIPT_PATH"\n'
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", delete=False, encoding="utf-8"
        ) as f:
            f.write(snippet)
            snippet_path = f.name
        try:
            result = subprocess.run(
                ["bash", snippet_path],
                env={**os.environ, "CALIXTO_SCRIPT_PATH": str(RUNTIME_SETUP_SH)},
                capture_output=True,
                text=True,
            )
        finally:
            os.unlink(snippet_path)
        if result.returncode != 0 and (
            "no such file" in result.stderr.lower()
            or "cannot access" in result.stderr.lower()
        ):
            pytest.skip(
                f"bash cannot access {RUNTIME_SETUP_SH} on this host "
                f"(stderr={result.stderr!r}); skipping syntax check"
            )
        assert result.returncode == 0, (
            f"runtime/workspace/setup.sh has a syntax error: {result.stderr}"
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
        assert _imports_module(text, "ddgs"), (
            "setup.ps1 verification step must import `ddgs` (the current "
            "name of the duckduckgo-search package). Did not find an "
            "import of ddgs in setup.ps1."
        )

    def test_setup_ps1_does_not_import_legacy_module(self) -> None:
        if not _have_pwsh():
            pytest.skip("pwsh not available")
        text = SETUP_PS1.read_text(encoding="utf-8")
        violations = _legacy_import_lines(text, "duckduckgo_search")
        assert not violations, (
            "setup.ps1 imports the legacy `duckduckgo_search` "
            f"module on non-comment lines: {violations!r}"
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

    def test_runtime_setup_ps1_syntax(self) -> None:
        if not _have_pwsh():
            pytest.skip("pwsh not available")
        result = subprocess.run(
            [
                "pwsh", "-NoProfile", "-Command",
                f"$null = [System.Management.Automation.PSParser]::Tokenize("
                f"(Get-Content -Raw '{RUNTIME_SETUP_PS1}'), [ref]$null); 'OK'"
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"runtime/workspace/setup.ps1 has a syntax error: {result.stderr}"
        )

    def test_runtime_setup_ps1_verifies_ddgs(self) -> None:
        if not _have_pwsh():
            pytest.skip("pwsh not available")
        text = RUNTIME_SETUP_PS1.read_text(encoding="utf-8")
        assert _imports_module(text, "ddgs"), (
            "runtime/workspace/setup.ps1 verification step must import `ddgs`."
        )
