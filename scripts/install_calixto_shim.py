"""
install_calixto_shim.py: install or refresh the lightweight `calixto` launcher.

The installed launcher is intentionally generic. It discovers the active
toolkit root from the current working directory (or `CALIXTO_TOOLKIT_ROOT`)
before delegating to `uv run --project <toolkit-root> calixto ...`.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Mapping


REQUIRED_TOOLKIT_MARKERS = (
    "AGENTS.md",
    "PHILOSOPHY.md",
    "requirements.md",
    "scripts",
    "runtime",
)


def shim_directory() -> Path:
    return Path.home() / ".local" / "bin"


def is_toolkit_root(path: Path) -> bool:
    return all((path / marker).exists() for marker in REQUIRED_TOOLKIT_MARKERS)


def find_toolkit_root(start_dir: Path, env: Mapping[str, str] | None = None) -> Path | None:
    explicit = (env or os.environ).get("CALIXTO_TOOLKIT_ROOT")
    if explicit:
        candidate = Path(explicit).expanduser().resolve(strict=False)
        return candidate if is_toolkit_root(candidate) else None

    current = start_dir.resolve(strict=False)
    while True:
        if is_toolkit_root(current):
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def windows_cmd_contents() -> str:
    return (
        "@echo off\n"
        "setlocal\n"
        "set \"CALIXTO_LAUNCHER_PS1=%~dp0calixto.ps1\"\n"
        "if not exist \"%CALIXTO_LAUNCHER_PS1%\" (\n"
        "  echo calixto: missing launcher helper \"%CALIXTO_LAUNCHER_PS1%\" 1>&2\n"
        "  exit /b 1\n"
        ")\n"
        "pwsh -NoProfile -ExecutionPolicy Bypass -File \"%CALIXTO_LAUNCHER_PS1%\" %*\n"
        "if errorlevel 1 powershell -NoProfile -ExecutionPolicy Bypass -File \"%CALIXTO_LAUNCHER_PS1%\" %*\n"
        "exit /b %ERRORLEVEL%\n"
    )


def windows_ps1_contents() -> str:
    return (
        "$ErrorActionPreference = 'Stop'\n"
        "$resolvedRoot = $env:CALIXTO_TOOLKIT_ROOT\n"
        "if ($resolvedRoot) {\n"
        "    $candidate = [System.IO.Path]::GetFullPath($resolvedRoot)\n"
        "    $required = @('AGENTS.md', 'PHILOSOPHY.md', 'requirements.md', 'scripts', 'runtime')\n"
        "    foreach ($entry in $required) {\n"
        "        if (-not (Test-Path -LiteralPath (Join-Path $candidate $entry))) {\n"
        "            Write-Error \"calixto: CALIXTO_TOOLKIT_ROOT does not point to a valid Calixto toolkit root: $candidate\"\n"
        "            exit 1\n"
        "        }\n"
        "    }\n"
        "    $resolvedRoot = $candidate\n"
        "} else {\n"
        "    $required = @('AGENTS.md', 'PHILOSOPHY.md', 'requirements.md', 'scripts', 'runtime')\n"
        "    $dir = (Get-Location).Path\n"
        "    while ($dir) {\n"
        "        $matches = $true\n"
        "        foreach ($entry in $required) {\n"
        "            if (-not (Test-Path -LiteralPath (Join-Path $dir $entry))) {\n"
        "                $matches = $false\n"
        "                break\n"
        "            }\n"
        "        }\n"
        "        if ($matches) {\n"
        "            $resolvedRoot = $dir\n"
        "            break\n"
        "        }\n"
        "        $parent = Split-Path -LiteralPath $dir -Parent\n"
        "        if (-not $parent -or $parent -eq $dir) {\n"
        "            break\n"
        "        }\n"
        "        $dir = $parent\n"
        "    }\n"
        "}\n"
        "if (-not $resolvedRoot) {\n"
        "    Write-Error 'calixto: could not locate a Calixto toolkit root from the current directory. Run this command inside a toolkit checkout/install root or set CALIXTO_TOOLKIT_ROOT.'\n"
        "    exit 1\n"
        "}\n"
        "& uv run --project $resolvedRoot calixto @args\n"
        "exit $LASTEXITCODE\n"
    )


def posix_shim_contents() -> str:
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'required=(AGENTS.md PHILOSOPHY.md requirements.md scripts runtime)\n'
        'is_toolkit_root() {\n'
        '  local candidate="$1"\n'
        '  local entry\n'
        '  for entry in "${required[@]}"; do\n'
        '    if [ ! -e "$candidate/$entry" ]; then\n'
        '      return 1\n'
        '    fi\n'
        '  done\n'
        '  return 0\n'
        '}\n'
        'if [ -n "${CALIXTO_TOOLKIT_ROOT:-}" ]; then\n'
        '  resolved_root="$(cd "$CALIXTO_TOOLKIT_ROOT" 2>/dev/null && pwd -P)" || {\n'
        '    printf "calixto: CALIXTO_TOOLKIT_ROOT is not accessible: %s\\n" "$CALIXTO_TOOLKIT_ROOT" >&2\n'
        '    exit 1\n'
        '  }\n'
        '  if ! is_toolkit_root "$resolved_root"; then\n'
        '    printf "calixto: CALIXTO_TOOLKIT_ROOT does not point to a valid Calixto toolkit root: %s\\n" "$resolved_root" >&2\n'
        '    exit 1\n'
        '  fi\n'
        'else\n'
        '  resolved_root="$PWD"\n'
        '  while true; do\n'
        '    if is_toolkit_root "$resolved_root"; then\n'
        '      break\n'
        '    fi\n'
        '    parent="$(dirname "$resolved_root")"\n'
        '    if [ "$parent" = "$resolved_root" ]; then\n'
        '      printf "calixto: could not locate a Calixto toolkit root from the current directory. Run this command inside a toolkit checkout/install root or set CALIXTO_TOOLKIT_ROOT.\\n" >&2\n'
        '      exit 1\n'
        '    fi\n'
        '    resolved_root="$parent"\n'
        '  done\n'
        'fi\n'
        'exec uv run --project "$resolved_root" calixto "$@"\n'
    )


def install_shims(toolkit_root: Path) -> dict[str, str | bool]:
    target_dir = shim_directory()
    target_dir.mkdir(parents=True, exist_ok=True)

    if sys.platform.startswith("win"):
        cmd_path = target_dir / "calixto.cmd"
        ps1_path = target_dir / "calixto.ps1"
        cmd_path.write_text(windows_cmd_contents(), encoding="utf-8", newline="\r\n")
        ps1_path.write_text(windows_ps1_contents(), encoding="utf-8", newline="\r\n")
        in_path = any(Path(part).resolve(strict=False) == target_dir.resolve(strict=False) for part in os.environ.get("PATH", "").split(os.pathsep) if part)
        return {
            "shim_dir": str(target_dir),
            "shim_path": str(cmd_path),
            "shim_helper_path": str(ps1_path),
            "on_path": in_path,
            "fallback_command": f'uv run --project "{toolkit_root}" calixto ...',
        }

    shim_path = target_dir / "calixto"
    shim_path.write_text(posix_shim_contents(), encoding="utf-8", newline="\n")
    shim_path.chmod(shim_path.stat().st_mode | 0o111)
    in_path = shutil.which("calixto") is not None or any(
        Path(part).resolve(strict=False) == target_dir.resolve(strict=False)
        for part in os.environ.get("PATH", "").split(os.pathsep)
        if part
    )
    return {
        "shim_dir": str(target_dir),
        "shim_path": str(shim_path),
        "on_path": in_path,
        "fallback_command": f'uv run --project "{toolkit_root}" calixto ...',
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Install or refresh the context-aware calixto launcher.",
        prog="install_calixto_shim",
    )
    parser.add_argument(
        "--toolkit-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Toolkit root to target. Default: this repository root.",
    )
    args = parser.parse_args(argv)

    result = install_shims(Path(args.toolkit_root).resolve())
    print(result["shim_path"])
    if not result["on_path"]:
        print(f"PATH_MISSING::{result['shim_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
