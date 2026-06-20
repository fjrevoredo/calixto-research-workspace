"""
install_calixto_shim.py: install or refresh the lightweight `calixto` launcher shim.

The shim delegates to `uv run --project <toolkit-root> calixto ...` so users
do not need to remember the fallback command after running toolkit setup.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


def shim_directory() -> Path:
    return Path.home() / ".local" / "bin"


def windows_cmd_contents(toolkit_root: Path) -> str:
    return (
        "@echo off\r\n"
        f'uv run --project "{toolkit_root}" calixto %*\r\n'
    )


def posix_shim_contents(toolkit_root: Path) -> str:
    return (
        "#!/usr/bin/env bash\n"
        f'exec uv run --project "{toolkit_root}" calixto "$@"\n'
    )


def install_shims(toolkit_root: Path) -> dict[str, str | bool]:
    target_dir = shim_directory()
    target_dir.mkdir(parents=True, exist_ok=True)

    if sys.platform.startswith("win"):
        cmd_path = target_dir / "calixto.cmd"
        cmd_path.write_text(windows_cmd_contents(toolkit_root), encoding="utf-8", newline="\r\n")
        in_path = any(Path(part).resolve(strict=False) == target_dir.resolve(strict=False) for part in os.environ.get("PATH", "").split(os.pathsep) if part)
        return {
            "shim_dir": str(target_dir),
            "shim_path": str(cmd_path),
            "on_path": in_path,
        }

    shim_path = target_dir / "calixto"
    shim_path.write_text(posix_shim_contents(toolkit_root), encoding="utf-8", newline="\n")
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
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Install or refresh the lightweight calixto launcher shim.",
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
