"""End-to-end test of the committed golden cache workflow.

This test verifies that the cache files checked in to
tests/golden/cache/ cover every search in tests/golden/config.json
under the current cache_key contract. It is the contract guarantee
that `python tests/golden/run.py --use-cache` will work in CI without
any network access.

The test reads the golden config, computes the cache_key for each
configured search under the current implementation, and asserts that
a corresponding cache file exists on disk with valid contents.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GOLDEN_DIR = REPO_ROOT / "tests" / "golden"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))


def _load_golden_config() -> dict:
    return json.loads((GOLDEN_DIR / "config.json").read_text(encoding="utf-8"))


def _all_cache_keys() -> set[str]:
    """Read every cache file in tests/golden/cache/ and return its key (stem)."""
    keys: set[str] = set()
    for f in (GOLDEN_DIR / "cache").rglob("*.json"):
        keys.add(f.stem)
    return keys


def _key_for_search(search: dict) -> tuple[str, str]:
    """Return (provider, key) for a search entry in golden config."""
    from search_web import cache_key
    provider = search.get("provider", "duckduckgo")
    query = search.get("query", "")
    max_results = search.get("max_results", 5)
    if provider == "arxiv":
        category = search.get("category")
        sort_by = "relevance"  # default
        return provider, cache_key(provider, query, max_results, category=category, sort_by=sort_by)
    return provider, cache_key(provider, query, max_results)


def _key_for_legacy_arxiv(search: dict) -> str:
    """Compute the cache key as the legacy arxiv path did (no category, no sort_by)."""
    from search_web import cache_key
    provider = "arxiv"
    query = search.get("query", "")
    max_results = search.get("max_results", 5)
    return cache_key(provider, query, max_results)


class TestCommittedCache:
    """The committed cache must satisfy the contract in requirements.md 10.2:

    - Every search in the golden config has a corresponding cache file
    - The cache file's key matches the current cache_key implementation
    - The cache file's content is valid (provider, query, max_results, results)
    """

    def test_all_golden_searches_have_cache_entries(self) -> None:
        """Each search in tests/golden/config.json must have a committed cache file."""
        config = _load_golden_config()
        on_disk = _all_cache_keys()
        missing: list[tuple[str, str, str]] = []
        for search in config["searches"]:
            provider, key = _key_for_search(search)
            if key not in on_disk:
                missing.append((provider, search.get("query", ""), key))
        assert not missing, (
            f"missing cache entries for {len(missing)} searches: {missing}. "
            "Either re-run a live golden run to repopulate the cache or "
            "update the cache key computation to match the committed files."
        )

    def test_cache_entries_match_their_keys(self) -> None:
        """Cache file contents must agree with the current cache_key derivation."""
        config = _load_golden_config()
        for search in config["searches"]:
            provider, key = _key_for_search(search)
            cache_file = GOLDEN_DIR / "cache" / provider / f"{key}.json"
            if not cache_file.exists():
                # Test 1 above already covers the missing case; skip here.
                continue
            payload = json.loads(cache_file.read_text(encoding="utf-8"))
            # The committed file must declare the same provider and query.
            assert payload.get("provider") == provider, cache_file
            assert payload.get("query") == search.get("query", ""), cache_file
            assert payload.get("max_results") == search.get("max_results", 5), cache_file
            # And it must contain at least one result so a --use-cache run
            # actually populates a workspace.
            assert payload.get("results"), f"empty results in {cache_file}"

    def test_legacy_arxiv_key_is_stale(self) -> None:
        """The previous arxiv cache key (no params) must NOT match the current key.

        This regression guard documents the migration: the old key
        (e97ea4c6719f07c0) was used before category/sort_by were part
        of the key. After the migration, that file no longer exists,
        because the new key (with params) replaced it.
        """
        config = _load_golden_config()
        arxiv_searches = [s for s in config["searches"] if s.get("provider") == "arxiv"]
        if not arxiv_searches:
            pytest.skip("no arxiv searches in golden config")
        legacy = _key_for_legacy_arxiv(arxiv_searches[0])
        on_disk = _all_cache_keys()
        assert legacy not in on_disk, (
            f"legacy arxiv key {legacy} is still on disk. The cache must be "
            "keyed by category/sort_by; the old key was a bug."
        )

    def test_cache_files_have_new_payload_format(self) -> None:
        """Every cache file must include a `params` field (the new format)."""
        for f in (GOLDEN_DIR / "cache").rglob("*.json"):
            payload = json.loads(f.read_text(encoding="utf-8"))
            assert "params" in payload, (
                f"cache file {f.name} is missing the params field. "
                "All cache files must record the params that produced the key, "
                "so future cache_key changes can be detected and migrated."
            )

    def test_cached_searches_produce_sources(self) -> None:
        """End-to-end: a --use-cache run against the committed cache must produce
        sources. We invoke run_search in-process with a stub workspace and the
        committed cache directory.
        """
        import search_web
        config = _load_golden_config()
        # Use the first duckduckgo search in the config; that one is
        # guaranteed to have a cache entry.
        web_searches = [s for s in config["searches"] if s.get("provider") != "arxiv"]
        if not web_searches:
            pytest.skip("no web searches in golden config")
        search = web_searches[0]
        # Build an isolated workspace for the call
        import tempfile
        from _common import save_workspace_config
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "cached-ws"
            (ws / "sources" / "web").mkdir(parents=True)
            (ws / "sources" / "papers").mkdir(parents=True)
            (ws / "notes").mkdir(parents=True)
            (ws / "outputs").mkdir(parents=True)
            save_workspace_config(ws, {
                "name": "cached-ws",
                "question": search.get("query", ""),
                "providers": {"search": "duckduckgo", "scrape": "crawl4ai"},
                "searches": [],
                "next_source_id": 1,
                "created_at": "2026-06-07T00:00:00Z",
                "updated_at": "2026-06-07T00:00:00Z",
            })
            (ws / "sources" / "index.json").write_text(
                json.dumps({"next_id": 1, "sources": []}), encoding="utf-8"
            )
            # Use a stub search provider that should never be called when
            # the cache is read first.
            from providers.search.base import SearchResult

            class _MustNotBeCalled:
                name = "duckduckgo"

                def search(self, query, max_results=10):  # type: ignore[override]
                    raise AssertionError("provider called despite --use-cache hit")

            import search_web as sw
            sw.get_search_provider = lambda name, **kwargs: _MustNotBeCalled()
            result = sw.run_search(
                query=search["query"],
                workspace=ws,
                max_results=search.get("max_results", 5),
                search_provider_name="duckduckgo",
                scrape_provider_name="crawl4ai",
                do_scrape=False,
                truncate=10000,
                use_cache=True,
                clear_cache_first=False,
                cache_dir=GOLDEN_DIR / "cache",
            )
            assert result["sources_added"] >= 1, result
