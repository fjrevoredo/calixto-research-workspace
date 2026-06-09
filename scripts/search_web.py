"""
search_web.py: Search the web and scrape results into a workspace.

This script composes a SearchProvider (finds URLs) with a ScrapeProvider
(fetches content) to collect web sources for research. Each result is assigned
a sequential `src_NNN` ID and saved to the workspace with full frontmatter
metadata. Sources are deduplicated by normalized URL.

Usage:
    python scripts/search_web.py "query" --workspace <path>
        [--max-results 10]
        [--search-provider duckduckgo|brave]
        [--scrape-provider crawl4ai]
        [--no-scrape]                      # save snippets only, skip scraping
        [--truncate 10000]                 # max words per source (0 = no limit)
        [--use-cache]                      # use cached search results (golden runs)
        [--clear-cache]                    # delete cache before running
        [--cache-dir <path>]               # default: <workspace>/.calixto/cache

Output (stdout): JSON with status, sources_added, sources_skipped, source_ids,
errors (if any), workspace path.

Architecture:
    1. Load workspace config and source index
    2. Initialize search provider and (optionally) scrape provider
    3. Call search provider for URLs
    4. Deduplicate by normalized URL via sources/index.json
    5. For each new URL: scrape (unless --no-scrape), assign ID, save markdown
    6. Update index.json and config.json
    7. Print final JSON status

See:
    - providers/search/base.py: SearchProvider interface
    - providers/scrape/base.py: ScrapeProvider interface
    - skills/deep-research/SKILL.md: toolkit-side handoff into a workspace
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

# Make `providers` importable when this script is run directly (python scripts/search_web.py ...)
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
# Also ensure the scripts dir is on path so `_common` imports work
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _common import (
    emit_error,
    emit_ok,
    emit_partial,
    load_source_index,
    load_workspace_config,
    normalize_url,
    render_frontmatter,
    save_source_index,
    save_workspace_config,
    source_id_for,
    truncate_markdown,
    utcnow_iso,
    word_count,
    workspace_path,
)

log = logging.getLogger(__name__)


def default_cache_dir(workspace: Path) -> Path:
    """Return the default cache directory for a standalone workspace."""
    return workspace / ".calixto" / "cache"


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------


def get_search_provider(name: str, **kwargs: Any) -> Any:
    """Return an instance of the named search provider.

    Lazy imports to keep startup fast when the provider is not used.
    """
    name = name.lower()
    if name == "duckduckgo":
        from providers.search.duckduckgo import DuckDuckGoProvider
        return DuckDuckGoProvider(**kwargs)
    if name == "brave":
        from providers.search.brave import BraveProvider
        return BraveProvider(**kwargs)
    raise ValueError(f"unknown search provider: {name}")


def get_scrape_provider(name: str, **kwargs: Any) -> Any:
    """Return an instance of the named scrape provider."""
    name = name.lower()
    if name == "crawl4ai":
        from providers.scrape.crawl4ai_provider import Crawl4AIProvider
        return Crawl4AIProvider(**kwargs)
    raise ValueError(f"unknown scrape provider: {name}")


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------


def cache_key(provider: str, query: str, max_results: int, **params: Any) -> str:
    """Compute a deterministic cache key for a search call.

    `params` is a free-form dict of result-affecting inputs (category, sort
    order, language filter, etc.). Including every input in the hash
    prevents two logically distinct searches from sharing a cache entry.
    Keys are stable across runs because params are sorted before hashing.
    """
    parts = [f"provider={provider}", f"query={query}", f"max_results={max_results}"]
    for k in sorted(params):
        v = params[k]
        if v is None or v == "":
            continue
        parts.append(f"{k}={v}")
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def cache_path_for(cache_dir: Path, provider: str, key: str) -> Path:
    """Return the path where cached results for a given key live."""
    return cache_dir / provider / f"{key}.json"


def load_cache(cache_dir: Path, provider: str, query: str, max_results: int, **params: Any) -> list[dict] | None:
    """Return cached results for the given call, or None on miss.

    `params` mirrors cache_key: any result-affecting input that should be
    part of the key (category, sort_by, language, etc.) must be passed
    through here so the lookup matches.
    """
    key = cache_key(provider, query, max_results, **params)
    path = cache_path_for(cache_dir, provider, key)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "results" not in data:
            return None
        return data["results"]
    except (json.JSONDecodeError, OSError):
        return None


def save_cache(
    cache_dir: Path, provider: str, query: str, max_results: int, results: list[dict], **params: Any
) -> None:
    """Persist search results to the cache.

    Cache writes happen on every successful live call (regardless of whether
    `--use-cache` was passed). `--use-cache` controls whether a cache hit
    is *required* (and a miss is an error), not whether cache writes
    occur. This matches the contract in requirements.md section 10.2:
    "first run caches, subsequent runs use cache".
    """
    key = cache_key(provider, query, max_results, **params)
    path = cache_path_for(cache_dir, provider, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "provider": provider,
        "query": query,
        "max_results": max_results,
        "params": {k: v for k, v in params.items() if v is not None and v != ""},
        "timestamp": utcnow_iso(),
        "result_count": len(results),
        "results": results,
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def clear_cache(cache_dir: Path) -> int:
    """Delete all cached search files. Returns the number of files removed."""
    if not cache_dir.exists():
        return 0
    count = 0
    for f in cache_dir.rglob("*.json"):
        f.unlink()
        count += 1
    return count


# ---------------------------------------------------------------------------
# ID assignment and persistence
# ---------------------------------------------------------------------------


def existing_url_set(index: dict) -> set[str]:
    """Return the set of normalized URLs already in the index."""
    return {
        (s.get("url_normalized") or normalize_url(s.get("url", "")))
        for s in index.get("sources", [])
        if s.get("url")
    }


def write_source(
    workspace: Path,
    source_id: str,
    frontmatter: dict[str, Any],
    body: str,
) -> Path:
    """Save a source's markdown file to sources/web/<id>.md and return its path."""
    target_dir = workspace / "sources" / "web"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{source_id}.md"
    target.write_text(render_frontmatter(frontmatter, body), encoding="utf-8")
    return target


def add_to_index(
    workspace: Path,
    index: dict,
    source_id: str,
    url: str,
    file_relpath: str,
    query: str,
    source_word_count: int,
    extras: dict[str, Any] | None = None,
) -> dict:
    """Append a new source entry to the index (in memory). Returns the new entry."""
    entry: dict[str, Any] = {
        "id": source_id,
        "url": url,
        "url_normalized": normalize_url(url),
        "file": file_relpath,
        "added_at": utcnow_iso(),
        "query": query,
        "word_count": source_word_count,
    }
    if extras:
        entry.update(extras)
    index.setdefault("sources", []).append(entry)
    return entry


# ---------------------------------------------------------------------------
# Main search flow
# ---------------------------------------------------------------------------


def run_search(
    query: str,
    workspace: Path,
    max_results: int,
    search_provider_name: str,
    scrape_provider_name: str,
    do_scrape: bool,
    truncate: int,
    use_cache: bool,
    clear_cache_first: bool,
    cache_dir: Path,
) -> dict:
    """Execute the full search-and-persist flow. Returns a status dict."""
    # Validate workspace
    if not workspace.exists() or not (workspace / "config.json").exists():
        emit_error(
            "workspace_not_found",
            f"workspace not found at {workspace}. Run init_workspace.py first.",
        )

    config = load_workspace_config(workspace)
    index = load_source_index(workspace)

    # Optional: provider overrides from workspace config
    if not search_provider_name:
        search_provider_name = config.get("providers", {}).get("search", "duckduckgo")
    if not scrape_provider_name:
        scrape_provider_name = config.get("providers", {}).get("scrape", "crawl4ai")

    # Clear cache if requested
    if clear_cache_first and cache_dir.exists():
        removed = clear_cache(cache_dir)
        log.info("cleared %d cache files", removed)

    # Cache lookup must happen BEFORE provider initialization. The cache is
    # the cheaper path and avoids paying the cost of importing the search
    # package (e.g. ddgs, requests) when we already have a stored result.
    cache_dir.mkdir(parents=True, exist_ok=True)
    raw_results: list[dict] | None = None
    if use_cache:
        raw_results = load_cache(cache_dir, search_provider_name, query, max_results)
        if raw_results is not None:
            log.info("using cached results: %d items", len(raw_results))
        else:
            # Reproducible mode: a cache miss must fail loudly rather than
            # silently falling back to a live network call. This matches
            # the contract in requirements.md section 10.2: cache hits are
            # used, cache misses during a reproducible run are errors.
            emit_error(
                "cache_miss",
                f"no cached result for provider={search_provider_name!r} "
                f"query={query!r} max_results={max_results}. "
                "Refusing to call the network in --use-cache mode; "
                "re-run without --use-cache to populate the cache.",
            )

    # Provider is only needed when we will actually call the network.
    if raw_results is None:
        search_provider = get_search_provider(search_provider_name)
        try:
            search_results = search_provider.search(query, max_results=max_results)
        except Exception as e:
            from providers.search.base import SearchError
            if isinstance(e, SearchError):
                emit_error(
                    "search_failed",
                    str(e),
                    retry_after=getattr(e, "retry_after", None),
                )
            emit_error("search_failed", f"search provider error: {e}")
        raw_results = [
            {
                "url": r.url,
                "title": r.title,
                "snippet": r.snippet,
                "score": r.score,
                "metadata": r.metadata,
            }
            for r in search_results
        ]
        # Always write the cache after a successful live call so subsequent
        # --use-cache runs can replay it. This decouples cache writes from
        # the --use-cache flag, which now means "require cache hit".
        save_cache(cache_dir, search_provider_name, query, max_results, raw_results)

    # Deduplicate
    seen = existing_url_set(index)
    new_results: list[dict] = []
    skipped = 0
    for r in raw_results:
        norm = normalize_url(r["url"])
        if not norm or norm in seen:
            skipped += 1
            continue
        seen.add(norm)
        new_results.append(r)

    if not new_results:
        # Record the search attempt and exit cleanly
        config.setdefault("searches", []).append(
            {
                "query": query,
                "provider": search_provider_name,
                "timestamp": utcnow_iso(),
                "results_count": len(raw_results),
                "urls_found": [r["url"] for r in raw_results],
                "sources_added": 0,
                "sources_skipped": skipped,
            }
        )
        config["next_source_id"] = index.get("next_id", 1)
        save_workspace_config(workspace, config)
        save_source_index(workspace, index)
        return {
            "sources_added": 0,
            "sources_skipped": skipped,
            "source_ids": [],
            "workspace": str(workspace),
            "query": query,
        }

    # Scrape (unless --no-scrape)
    scrape_provider = None
    if do_scrape:
        try:
            scrape_provider = get_scrape_provider(scrape_provider_name)
        except Exception as e:
            emit_error("scrape_init_failed", f"could not initialize scrape provider: {e}")

    added_ids: list[str] = []
    errors: list[dict] = []
    next_id = index.get("next_id", 1)

    for r in new_results:
        url = r["url"]
        title = r.get("title", "")
        snippet = r.get("snippet", "")

        source_id = source_id_for(next_id)
        next_id += 1

        frontmatter: dict[str, Any] = {
            "id": source_id,
            "url": url,
            "title": title,
            "date_crawled": utcnow_iso(),
            "provider": scrape_provider_name if do_scrape else "none",
            "search_provider": search_provider_name,
            "query": query,
            "word_count": 0,
            "truncated": False,
        }

        body = ""

        if do_scrape and scrape_provider is not None:
            try:
                scrape_result = scrape_provider.scrape(url)
                frontmatter["title"] = scrape_result.title or title
                # If scrape failed, keep the snippet as the body
                if scrape_result.markdown:
                    body = scrape_result.markdown
                    frontmatter["word_count"] = scrape_result.word_count
                else:
                    err = scrape_result.metadata.get("error", "no_content")
                    frontmatter["error"] = err
                    body = _snippet_only_body(snippet, url)
                    frontmatter["word_count"] = word_count(body)
                # Pass through any interesting scrape metadata
                for k in ("description", "author"):
                    if scrape_result.metadata.get(k):
                        frontmatter[k] = scrape_result.metadata[k]
            except Exception as e:
                from providers.scrape.base import ScrapeError
                if isinstance(e, ScrapeError):
                    frontmatter["error"] = e.error_type
                    errors.append({"url": url, "error": e.error_type, "message": str(e)})
                else:
                    frontmatter["error"] = "scrape_exception"
                    errors.append({"url": url, "error": "scrape_exception", "message": str(e)})
                body = _snippet_only_body(snippet, url)
                frontmatter["word_count"] = word_count(body)
        else:
            body = _snippet_only_body(snippet, url)
            frontmatter["word_count"] = word_count(body)
            frontmatter["snippet_only"] = True

        # Truncation
        if truncate and truncate > 0 and frontmatter["word_count"] > truncate:
            original_wc = frontmatter["word_count"]
            body = truncate_markdown(body, truncate)
            frontmatter["word_count"] = word_count(body)
            frontmatter["truncated"] = True
            frontmatter["original_word_count"] = original_wc

        relpath = f"web/{source_id}.md"
        write_source(workspace, source_id, frontmatter, body)
        add_to_index(
            workspace,
            index,
            source_id,
            url,
            relpath,
            query,
            frontmatter["word_count"],
            extras={
                "title": frontmatter.get("title", ""),
                "search_provider": search_provider_name,
            },
        )
        added_ids.append(source_id)
        # Polite delay between scrapes
        if do_scrape and len(new_results) > 1:
            time.sleep(1.0)

    # Update index next_id
    index["next_id"] = next_id

    # Record search
    config.setdefault("searches", []).append(
        {
            "query": query,
            "provider": search_provider_name,
            "scrape_provider": scrape_provider_name if do_scrape else None,
            "timestamp": utcnow_iso(),
            "results_count": len(raw_results),
            "urls_found": [r["url"] for r in raw_results],
            "sources_added": len(added_ids),
            "sources_skipped": skipped,
            "source_ids": added_ids,
        }
    )
    config["next_source_id"] = next_id
    save_workspace_config(workspace, config)
    save_source_index(workspace, index)

    result = {
        "sources_added": len(added_ids),
        "sources_skipped": skipped,
        "source_ids": added_ids,
        "workspace": str(workspace),
        "query": query,
    }
    if errors:
        result["sources_failed"] = len(errors)
        result["errors"] = errors
    return result


def _snippet_only_body(snippet: str, url: str) -> str:
    """Build a placeholder body for snippet-only sources (--no-scrape or scrape failure)."""
    if not snippet:
        snippet = "(no snippet available; scraping was skipped or failed)"
    return f"# Snippet Only\n\nSource: {url}\n\n{snippet}\n\n*This source was not fully scraped. Run `search_web.py` again with the scrape enabled, or visit the URL directly for full content.*\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Search the web and scrape results into a workspace.",
        prog="search_web",
    )
    parser.add_argument("query", help="Search query string.")
    parser.add_argument("--workspace", required=True, help="Path to the workspace directory.")
    parser.add_argument("--max-results", type=int, default=10, help="Maximum search results to fetch (default: 10).")
    parser.add_argument("--search-provider", default=None, help="Search provider name (default: from config).")
    parser.add_argument("--scrape-provider", default=None, help="Scrape provider name (default: from config).")
    parser.add_argument("--no-scrape", action="store_true", help="Skip scraping; save URL + snippet only.")
    parser.add_argument("--truncate", type=int, default=10000, help="Truncate sources to N words (0=no limit, default: 10000).")
    parser.add_argument("--use-cache", action="store_true", help="Use cached search results if present (for golden runs).")
    parser.add_argument("--clear-cache", action="store_true", help="Delete cached search results before running.")
    parser.add_argument("--cache-dir", default=None, help="Cache directory (default: <workspace>/.calixto/cache).")
    args = parser.parse_args(argv)

    if not args.query or not args.query.strip():
        emit_error("invalid_query", "query must be a non-empty string")

    workspace = workspace_path(args.workspace)
    cache_dir = Path(args.cache_dir).resolve() if args.cache_dir else default_cache_dir(workspace)

    if args.truncate < 0:
        emit_error("invalid_truncate", "--truncate must be >= 0")

    try:
        result = run_search(
            query=args.query.strip(),
            workspace=workspace,
            max_results=args.max_results,
            search_provider_name=args.search_provider,
            scrape_provider_name=args.scrape_provider,
            do_scrape=not args.no_scrape,
            truncate=args.truncate,
            use_cache=args.use_cache,
            clear_cache_first=args.clear_cache,
            cache_dir=cache_dir,
        )
    except SystemExit:
        raise
    except Exception as e:
        emit_error("search_failed", f"unexpected error: {e}")

    if result.get("sources_failed", 0) > 0 and result.get("sources_added", 0) > 0:
        emit_partial(result)
    else:
        emit_ok(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
