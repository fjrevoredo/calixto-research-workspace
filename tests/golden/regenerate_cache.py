"""Regenerate committed cache files for the golden dataset.

Reads the old cache files (which were keyed without arXiv category/sort_by)
and re-saves them under the new keys, so --use-cache works for the
committed cache.

This is a one-off migration. After it runs, the cache is keyed
consistently with the search_arxiv / search_web cache_key implementations.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from search_web import cache_key, cache_path_for

SAFE_CACHE_KEY = re.compile(r"^[0-9a-f]{16}$")
ALLOWED_CACHE_PROVIDERS = {"duckduckgo", "arxiv"}


def _validated_cache_path(cache_dir: Path, provider: str, key: str) -> Path:
    if provider not in ALLOWED_CACHE_PROVIDERS:
        raise ValueError(f"unsupported cache provider: {provider}")
    if not SAFE_CACHE_KEY.fullmatch(key):
        raise ValueError(f"unsafe cache key: {key!r}")
    provider_dir = (cache_dir / provider).resolve()
    path = cache_path_for(cache_dir, provider, key).resolve()
    if not path.is_relative_to(provider_dir):
        raise ValueError(f"cache path escapes provider directory: {path}")
    return path


def _read_old_duckduckgo_cache() -> list[dict]:
    """Read the four old duckduckgo cache files."""
    cache_dir = REPO_ROOT / "tests" / "golden" / "cache"
    files = sorted((cache_dir / "duckduckgo").glob("*.json"))
    out = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        # Re-save under the new key
        provider = data["provider"]
        query = data["query"]
        max_results = data["max_results"]
        new_key = cache_key(provider, query, max_results)
        out.append(
            {
                "provider": provider,
                "query": query,
                "max_results": max_results,
                "results": data["results"],
                "old_key": f.stem,
                "new_key": new_key,
            }
        )
    return out


def _read_old_arxiv_cache() -> list[dict]:
    cache_dir = REPO_ROOT / "tests" / "golden" / "cache"
    files = sorted((cache_dir / "arxiv").glob("*.json"))
    out = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        provider = "arxiv"
        query = data["query"]
        max_results = data["max_results"]
        # The golden config's arxiv query has category=cs.CL and default sort.
        category = data.get("params", {}).get("category") or "cs.CL"
        sort_by = data.get("params", {}).get("sort_by") or "relevance"
        new_key = cache_key(provider, query, max_results, category=category, sort_by=sort_by)
        out.append(
            {
                "provider": provider,
                "query": query,
                "max_results": max_results,
                "category": category,
                "sort_by": sort_by,
                "results": data["results"],
                "old_key": f.stem,
                "new_key": new_key,
            }
        )
    return out


def main() -> int:
    cache_dir = REPO_ROOT / "tests" / "golden" / "cache"

    # Migrate web cache
    for entry in _read_old_duckduckgo_cache():
        provider = entry["provider"]
        new_path = _validated_cache_path(cache_dir, provider, entry["new_key"])
        payload = {
            "provider": provider,
            "query": entry["query"],
            "max_results": entry["max_results"],
            "params": {},
            "timestamp": "2026-06-07T00:00:00Z",
            "result_count": len(entry["results"]),
            "results": entry["results"],
        }
        new_path.parent.mkdir(parents=True, exist_ok=True)
        new_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        old_path = _validated_cache_path(cache_dir, provider, entry["old_key"])
        if old_path != new_path and old_path.exists():
            old_path.unlink()
        print(f"web: {old_path.name} -> {new_path.name} ({len(entry['results'])} results)")

    # Migrate arxiv cache
    for entry in _read_old_arxiv_cache():
        provider = entry["provider"]
        new_path = _validated_cache_path(cache_dir, provider, entry["new_key"])
        payload = {
            "provider": provider,
            "query": entry["query"],
            "max_results": entry["max_results"],
            "params": {"category": entry["category"], "sort_by": entry["sort_by"]},
            "timestamp": "2026-06-07T00:00:00Z",
            "result_count": len(entry["results"]),
            "results": entry["results"],
        }
        new_path.parent.mkdir(parents=True, exist_ok=True)
        new_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        old_path = _validated_cache_path(cache_dir, provider, entry["old_key"])
        if old_path != new_path and old_path.exists():
            old_path.unlink()
        print(f"arxiv: {old_path.name} -> {new_path.name} ({len(entry['results'])} results)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
