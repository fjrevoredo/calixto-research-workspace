"""
runtime_probe.py: verify a Calixto research runtime can execute the default scraper path.

This script is intentionally workspace-safe. It is bundled into standalone
workspaces and also used from the toolkit root to validate managed runtimes.

It verifies:
- the required Python packages import successfully
- Playwright Chromium can launch using the default runtime path

The script prints one JSON object to stdout and exits 0 on success, 1 on
failure. It does not install anything itself.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def _ok(payload: dict[str, Any]) -> int:
    print(json.dumps({"status": "ok", **payload}, indent=2, ensure_ascii=False))
    return 0


def _error(error_type: str, message: str, *, extra: dict[str, Any] | None = None) -> int:
    payload: dict[str, Any] = {
        "status": "error",
        "error": error_type,
        "message": message,
    }
    if extra:
        payload.update(extra)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 1


def _classify_browser_error(message: str) -> str:
    lowered = (message or "").lower()
    if "executable doesn't exist" in lowered:
        return "missing_browser"
    if "browser type has been closed" in lowered:
        return "browser_launch_failed"
    if "playwright" in lowered and "install" in lowered:
        return "missing_browser"
    if "failed to launch" in lowered:
        return "browser_launch_failed"
    return "browser_probe_failed"


def probe_runtime(*, imports_only: bool = False) -> tuple[int, dict[str, Any]]:
    try:
        import crawl4ai  # noqa: F401
        import ddgs  # noqa: F401
        import arxiv  # noqa: F401
        import yaml  # noqa: F401
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        return 1, {
            "error": "missing_dependency",
            "message": f"required runtime dependency is missing: {exc}",
            "imports_ok": False,
            "browser_ready": False,
        }

    if imports_only:
        return 0, {
            "imports_ok": True,
            "browser_ready": False,
            "probe_mode": "imports_only",
        }

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            browser.close()
    except Exception as exc:  # pragma: no cover - error type depends on host/browser state
        return 1, {
            "error": _classify_browser_error(str(exc)),
            "message": str(exc),
            "imports_ok": True,
            "browser_ready": False,
        }

    return 0, {
        "imports_ok": True,
        "browser_ready": True,
        "probe_mode": "full",
        "browser_backend": "playwright-chromium",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify a Calixto research runtime can import its dependencies and launch Chromium.",
        prog="runtime_probe",
    )
    parser.add_argument(
        "--imports-only",
        action="store_true",
        help="Only verify required Python imports, not browser launch.",
    )
    args = parser.parse_args(argv)

    rc, payload = probe_runtime(imports_only=args.imports_only)
    if rc == 0:
        return _ok(payload)
    return _error(payload["error"], payload["message"], extra=payload)


if __name__ == "__main__":
    raise SystemExit(main())
