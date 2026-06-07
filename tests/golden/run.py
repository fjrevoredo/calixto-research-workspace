"""
tests/golden/run.py: Execute the full golden dataset workflow.

This script:
  1. Loads tests/golden/config.json
  2. Creates a new workspace (or uses an explicit name)
  3. Runs each search query in the config
  4. Saves the complete workspace to tests/golden/runs/<timestamp>/
  5. Runs workspace_info.py audit on the result
  6. Prints a summary

Usage:
    python tests/golden/run.py [--use-cache] [--clear-cache] [--workspace-name NAME]

If --workspace-name is omitted, a timestamped name is generated.

See tests/golden/README.md for the full specification.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure scripts/ and providers/ are importable
THIS_FILE = Path(__file__).resolve()
TESTS_DIR = THIS_FILE.parent
GOLDEN_DIR = TESTS_DIR
REPO_ROOT = TESTS_DIR.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

for p in (str(REPO_ROOT), str(SCRIPTS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)


def emit_error(error_type: str, message: str) -> None:
    print(
        json.dumps(
            {"status": "error", "error": error_type, "message": message},
            indent=2,
            ensure_ascii=False,
        ),
        file=sys.stderr,
    )
    sys.exit(1)


def emit_ok(payload: dict) -> None:
    print(json.dumps({"status": "ok", **payload}, indent=2, ensure_ascii=False))


def run_command(cmd: list[str], cwd: Path) -> dict:
    """Run a command, capture stdout, return parsed JSON or raise."""
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        # Try to parse stderr as JSON
        try:
            err = json.loads(proc.stderr)
        except json.JSONDecodeError:
            err = {"raw_stderr": proc.stderr.strip(), "raw_stdout": proc.stdout.strip()}
        raise RuntimeError(f"command failed (rc={proc.returncode}): {' '.join(cmd)}: {err}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"command output not JSON: {proc.stdout[:500]}") from e


def run_golden(
    config_path: Path,
    use_cache: bool,
    clear_cache: bool,
    workspace_name: str | None,
    python_bin: str,
) -> dict:
    """Execute the full golden dataset workflow."""
    if not config_path.exists():
        emit_error("config_missing", f"golden config not found at {config_path}")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    searches = config.get("searches", [])
    if not searches:
        emit_error("config_empty", "no searches defined in golden config")

    # Determine workspace name
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if not workspace_name:
        workspace_name = f"{config.get('workspace_prefix', 'golden')}-{timestamp}"
    workspace_path = REPO_ROOT / "workspaces" / workspace_name

    if clear_cache:
        cache_dir = REPO_ROOT / "tests" / "golden" / "cache"
        if cache_dir.exists():
            shutil.rmtree(cache_dir)

    # Step 1: create workspace
    print(f"[1/3] Creating workspace: {workspace_name}", file=sys.stderr)
    init_result = run_command(
        [python_bin, str(SCRIPTS_DIR / "init_workspace.py"), workspace_name],
        cwd=REPO_ROOT,
    )

    # Set the question
    cfg_file = workspace_path / "config.json"
    cfg_data = json.loads(cfg_file.read_text(encoding="utf-8"))
    cfg_data["question"] = config.get("question", "")
    cfg_file.write_text(json.dumps(cfg_data, indent=2), encoding="utf-8")

    # Step 2: run each search
    print(f"[2/3] Running {len(searches)} searches", file=sys.stderr)
    search_results: list[dict] = []
    for s in searches:
        provider = s.get("provider", "duckduckgo")
        query = s.get("query")
        max_results = s.get("max_results", 5)
        do_scrape = s.get("do_scrape", False)
        category = s.get("category")
        truncate = s.get("truncate", config.get("truncate", 10000))
        cmd = [
            python_bin,
        ]
        if provider == "arxiv":
            cmd += [
                str(SCRIPTS_DIR / "search_arxiv.py"),
                query,
                "--workspace",
                str(workspace_path),
                "--max-results",
                str(max_results),
            ]
            if use_cache:
                cmd.append("--use-cache")
            if clear_cache:
                cmd.append("--clear-cache")
            if category:
                cmd += ["--category", category]
        else:
            cmd += [
                str(SCRIPTS_DIR / "search_web.py"),
                query,
                "--workspace",
                str(workspace_path),
                "--max-results",
                str(max_results),
                "--truncate",
                str(truncate),
            ]
            if not do_scrape:
                cmd.append("--no-scrape")
            if use_cache:
                cmd.append("--use-cache")
            if clear_cache:
                cmd.append("--clear-cache")
        print(f"  - {provider}: {query!r}", file=sys.stderr)
        try:
            r = run_command(cmd, cwd=REPO_ROOT)
            search_results.append({"query": query, "provider": provider, "result": r})
        except Exception as e:
            search_results.append({"query": query, "provider": provider, "error": str(e)})

    # Step 3: audit
    print(f"[3/3] Auditing workspace", file=sys.stderr)
    audit_result = run_command(
        [python_bin, str(SCRIPTS_DIR / "workspace_info.py"), "audit", workspace_name],
        cwd=REPO_ROOT,
    )

    # Copy workspace to runs/<timestamp>/
    runs_dir = GOLDEN_DIR / "runs" / timestamp
    if runs_dir.exists():
        # Avoid clobbering an existing run dir
        i = 1
        while (GOLDEN_DIR / "runs" / f"{timestamp}-{i}").exists():
            i += 1
        runs_dir = GOLDEN_DIR / "runs" / f"{timestamp}-{i}"
    print(f"[+] Archiving workspace to {runs_dir.relative_to(REPO_ROOT)}", file=sys.stderr)
    shutil.copytree(workspace_path, runs_dir)

    # Summary
    total_added = sum(
        sr.get("result", {}).get("sources_added", 0) for sr in search_results
    )
    total_skipped = sum(
        sr.get("result", {}).get("sources_skipped", 0) for sr in search_results
    )
    summary = {
        "timestamp": timestamp,
        "workspace": workspace_name,
        "workspace_path": str(workspace_path),
        "run_archive": str(runs_dir),
        "config": str(config_path),
        "searches_run": len(search_results),
        "searches_failed": sum(1 for sr in search_results if "error" in sr),
        "total_sources_added": total_added,
        "total_sources_skipped": total_skipped,
        "audit": audit_result,
    }
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Execute the full golden dataset workflow.",
        prog="golden-run",
    )
    parser.add_argument("--config", default=str(GOLDEN_DIR / "config.json"), help="Path to the golden config JSON.")
    parser.add_argument("--use-cache", action="store_true", help="Use cached search results instead of live calls.")
    parser.add_argument("--clear-cache", action="store_true", help="Delete the search cache before running.")
    parser.add_argument("--workspace-name", default=None, help="Workspace name to use (default: timestamped).")
    parser.add_argument("--python", default=sys.executable, help="Python interpreter to use for child processes.")
    args = parser.parse_args(argv)

    config_path = Path(args.config).resolve()
    try:
        summary = run_golden(
            config_path=config_path,
            use_cache=args.use_cache,
            clear_cache=args.clear_cache,
            workspace_name=args.workspace_name,
            python_bin=args.python,
        )
    except SystemExit:
        raise
    except Exception as e:
        emit_error("golden_run_failed", str(e))

    emit_ok(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
