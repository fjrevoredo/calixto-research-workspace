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
        [--retry-failed]                  # retry only failed URLs from the latest web search
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
    4. Prepare scrape results outside the workspace mutation lock
    5. Re-deduplicate and assign IDs under a shared workspace coordinator
    6. Commit source files, sources/index.json, and config.json as one staged transaction
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
import os
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
    WorkspaceStateCoordinator,
    classify_source_quality,
    emit_error,
    emit_ok,
    emit_partial,
    load_source_index,
    load_workspace_config,
    normalize_url,
    render_frontmatter,
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


def maybe_test_precommit_delay() -> None:
    """Deterministic test hook for concurrent-search regression coverage."""
    delay_ms = os.environ.get("CALIXTO_TEST_PRE_COMMIT_DELAY_MS", "").strip()
    if not delay_ms:
        return
    try:
        delay_value = int(delay_ms)
    except ValueError:
        return
    if delay_value > 0:
        time.sleep(delay_value / 1000.0)


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


def existing_url_map(index: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Map normalized URLs to the index entries that already use them."""
    mapping: dict[str, list[dict[str, Any]]] = {}
    for entry in index.get("sources", []):
        url = str(entry.get("url", "")).strip()
        normalized = str(entry.get("url_normalized") or normalize_url(url)).strip()
        if not normalized:
            continue
        mapping.setdefault(normalized, []).append(entry)
    return mapping


def duplicate_detail(url: str, matching_entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Describe a duplicate URL match for stdout/config history."""
    return {
        "url": url,
        "url_normalized": normalize_url(url),
        "existing_source_ids": sorted(
            str(entry.get("id", "")).strip()
            for entry in matching_entries
            if str(entry.get("id", "")).strip()
        ),
    }


def index_entry_for_source(
    source_id: str,
    url: str,
    file_relpath: str,
    query: str,
    source_word_count: int,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a normalized source-index entry."""
    entry: dict[str, Any] = {
        "id": source_id,
        "url": url,
        "url_normalized": normalize_url(url),
        "file": file_relpath,
        "added_at": utcnow_iso(),
        "query": query,
        "word_count": source_word_count,
        "review_status": "pending",
    }
    if extras:
        entry.update(extras)
    return entry


def latest_failed_web_search(config: dict[str, Any]) -> dict[str, Any] | None:
    """Return the most recent web-search record that still has retryable failures."""
    for search in reversed(config.get("searches", [])):
        failures = search.get("failures", [])
        provider = str(search.get("provider", "")).strip()
        if provider and provider != "arxiv" and isinstance(failures, list) and failures:
            return search
    return None


def failure_entries_to_results(search_record: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert persisted failure metadata into raw-result shaped records."""
    results: list[dict[str, Any]] = []
    for failure in search_record.get("failures", []):
        url = str(failure.get("url", "")).strip()
        if not url:
            continue
        results.append(
            {
                "url": url,
                "title": failure.get("title", ""),
                "snippet": failure.get("snippet", ""),
                "score": 0.0,
                "metadata": {
                    "retry_source_id": failure.get("source_id"),
                    "retry_error": failure.get("error"),
                },
            }
        )
    return results


def metadata_passthrough(metadata: dict[str, Any]) -> dict[str, Any]:
    """Return provider metadata fields worth persisting into source state."""
    passthrough: dict[str, Any] = {}
    for key, value in metadata.items():
        if key == "provider" or value in (None, ""):
            continue
        if isinstance(value, (str, int, float, bool, list, dict)):
            passthrough[key] = value
    return passthrough


def build_source_frontmatter(
    *,
    source_id: str,
    url: str,
    title: str,
    query: str,
    scrape_provider_name: str,
    search_provider_name: str,
    word_count_value: int,
    extra_metadata: dict[str, Any],
) -> dict[str, Any]:
    """Create the frontmatter payload for a saved web source."""
    frontmatter: dict[str, Any] = {
        "id": source_id,
        "url": url,
        "title": title,
        "date_crawled": utcnow_iso(),
        "provider": scrape_provider_name,
        "search_provider": search_provider_name,
        "query": query,
        "word_count": word_count_value,
        "truncated": False,
    }
    frontmatter.update(extra_metadata)
    return frontmatter


def prepare_candidate_source(
    result: dict[str, Any],
    *,
    query: str,
    do_scrape: bool,
    scrape_provider_name: str,
    search_provider_name: str,
    truncate: int,
    scrape_provider: Any | None,
) -> dict[str, Any]:
    """Scrape or format one search result before the final locked commit."""
    url = str(result.get("url", "")).strip()
    title = str(result.get("title", "")).strip()
    snippet = str(result.get("snippet", "")).strip()
    prepared: dict[str, Any] = {
        "url": url,
        "normalized_url": normalize_url(url),
        "search_title": title,
        "snippet": snippet,
        "retry_source_id": result.get("metadata", {}).get("retry_source_id"),
    }

    extra_metadata: dict[str, Any] = {}
    body = ""
    failure: dict[str, Any] | None = None

    if do_scrape and scrape_provider is not None:
        try:
            scrape_result = scrape_provider.scrape(url)
            extra_metadata.update(metadata_passthrough(scrape_result.metadata))
            title = scrape_result.title or title
            if scrape_result.markdown:
                body = scrape_result.markdown
            else:
                error_type = str(scrape_result.metadata.get("error", "no_content"))
                failure = {
                    "url": url,
                    "title": title,
                    "snippet": snippet,
                    "error": error_type,
                    "message": str(scrape_result.metadata.get("error_message") or error_type),
                    "retryable": True,
                }
                extra_metadata["error"] = error_type
                extra_metadata["snippet_only"] = True
                body = _snippet_only_body(snippet, url)
        except Exception as exc:
            from providers.scrape.base import ScrapeError

            if isinstance(exc, ScrapeError):
                error_type = exc.error_type
            else:
                error_type = "scrape_exception"
            failure = {
                "url": url,
                "title": title,
                "snippet": snippet,
                "error": error_type,
                "message": str(exc),
                "retryable": True,
            }
            extra_metadata["error"] = error_type
            extra_metadata["snippet_only"] = True
            body = _snippet_only_body(snippet, url)
    else:
        body = _snippet_only_body(snippet, url)
        extra_metadata["snippet_only"] = True

    word_count_value = word_count(body)
    if truncate and truncate > 0 and word_count_value > truncate:
        original_wc = word_count_value
        body = truncate_markdown(body, truncate)
        word_count_value = word_count(body)
        extra_metadata["truncated"] = True
        extra_metadata["original_word_count"] = original_wc

    quality_metadata = classify_source_quality(
        url=url,
        provider=scrape_provider_name if do_scrape else "snippet_only",
        search_provider=search_provider_name,
        title=title,
        content_quality=str(extra_metadata.get("content_quality", "")),
        low_signal=bool(extra_metadata.get("low_signal")),
        snippet_only=bool(extra_metadata.get("snippet_only")),
        error=str(extra_metadata.get("error", "")),
        metadata=extra_metadata,
    )
    extra_metadata.update(quality_metadata)

    prepared["title"] = title
    prepared["body"] = body
    prepared["word_count"] = word_count_value
    prepared["frontmatter_extra"] = extra_metadata
    prepared["index_extra"] = {
        "title": title,
        "search_provider": search_provider_name,
        **metadata_passthrough(extra_metadata),
    }
    if failure is not None:
        prepared["failure"] = failure
    return prepared


# ---------------------------------------------------------------------------
# Main search flow
# ---------------------------------------------------------------------------


def run_search(
    query: str | None,
    workspace: Path,
    max_results: int,
    search_provider_name: str,
    scrape_provider_name: str,
    do_scrape: bool,
    truncate: int,
    use_cache: bool,
    clear_cache_first: bool,
    cache_dir: Path,
    retry_failed: bool = False,
) -> dict:
    """Execute the full search-and-persist flow. Returns a status dict."""
    if not workspace.exists() or not (workspace / "config.json").exists():
        emit_error(
            "workspace_not_found",
            f"workspace not found at {workspace}. Run init_workspace.py first.",
        )

    initial_config = load_workspace_config(workspace)
    initial_index = load_source_index(workspace)

    if not search_provider_name:
        search_provider_name = initial_config.get("providers", {}).get("search", "duckduckgo")
    if not scrape_provider_name:
        scrape_provider_name = initial_config.get("providers", {}).get("scrape", "crawl4ai")

    retry_context: dict[str, Any] | None = None
    raw_results: list[dict[str, Any]] | None = None

    if retry_failed:
        retry_search = latest_failed_web_search(initial_config)
        if retry_search is None:
            emit_error(
                "no_failed_results",
                "no previous web-search failures were found in this workspace",
            )
        raw_results = failure_entries_to_results(retry_search)
        if not raw_results:
            emit_error(
                "no_failed_results",
                "the latest failed web-search record does not contain retryable URLs",
            )
        query = str(retry_search.get("query", "")).strip()
        if not query:
            emit_error(
                "invalid_retry_record",
                "the latest failed web-search record is missing its original query",
            )
        search_provider_name = search_provider_name or str(retry_search.get("provider", "")).strip()
        retry_context = {
            "query": retry_search.get("query", ""),
            "timestamp": retry_search.get("timestamp", ""),
        }
    elif not query or not query.strip():
        emit_error("invalid_query", "query must be a non-empty string")
    else:
        query = query.strip()

    if clear_cache_first and cache_dir.exists():
        removed = clear_cache(cache_dir)
        log.info("cleared %d cache files", removed)

    cache_dir.mkdir(parents=True, exist_ok=True)
    if raw_results is None and use_cache:
        raw_results = load_cache(cache_dir, search_provider_name, query, max_results)
        if raw_results is not None:
            log.info("using cached results: %d items", len(raw_results))
        else:
            emit_error(
                "cache_miss",
                f"no cached result for provider={search_provider_name!r} "
                f"query={query!r} max_results={max_results}. "
                "Refusing to call the network in --use-cache mode; "
                "re-run without --use-cache to populate the cache.",
            )

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
        save_cache(cache_dir, search_provider_name, query, max_results, raw_results)

    initial_url_map = existing_url_map(initial_index)
    candidates_to_prepare: list[dict[str, Any]] = []
    best_effort_duplicates: list[dict[str, Any]] = []
    seen_candidate_urls: set[str] = set()
    for result in raw_results:
        url = str(result.get("url", "")).strip()
        normalized = normalize_url(url)
        if not normalized or normalized in seen_candidate_urls:
            best_effort_duplicates.append(duplicate_detail(url, initial_url_map.get(normalized, [])))
            continue
        seen_candidate_urls.add(normalized)
        if not retry_failed and normalized in initial_url_map:
            best_effort_duplicates.append(duplicate_detail(url, initial_url_map[normalized]))
            continue
        candidates_to_prepare.append(result)

    scrape_provider = None
    if do_scrape:
        try:
            scrape_provider = get_scrape_provider(scrape_provider_name)
        except Exception as e:
            emit_error("scrape_init_failed", f"could not initialize scrape provider: {e}")

    prepared_candidates: list[dict[str, Any]] = []
    for pos, raw_result in enumerate(candidates_to_prepare):
        prepared_candidates.append(
            prepare_candidate_source(
                raw_result,
                query=query,
                do_scrape=do_scrape,
                scrape_provider_name=scrape_provider_name if do_scrape else "none",
                search_provider_name=search_provider_name,
                truncate=truncate,
                scrape_provider=scrape_provider,
            )
        )
        if do_scrape and pos < (len(candidates_to_prepare) - 1):
            time.sleep(1.0)

    added_ids: list[str] = []
    updated_ids: list[str] = []
    duplicate_matches: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    maybe_test_precommit_delay()

    with WorkspaceStateCoordinator(workspace) as coordinator:
        config = coordinator.config
        index = coordinator.index
        url_map = existing_url_map(index)
        next_id = index.get("next_id", 1)
        source_files: list[dict[str, str]] = []

        for prepared in prepared_candidates:
            normalized = prepared["normalized_url"]
            existing_entries = url_map.get(normalized, [])
            retry_source_id = str(prepared.get("retry_source_id") or "").strip()

            if retry_source_id:
                target_entry = next(
                    (entry for entry in existing_entries if str(entry.get("id", "")).strip() == retry_source_id),
                    None,
                )
                if target_entry is not None:
                    if prepared.get("failure"):
                        failure = dict(prepared["failure"])
                        failure["source_id"] = retry_source_id
                        failures.append(failure)
                        continue

                    frontmatter = build_source_frontmatter(
                        source_id=retry_source_id,
                        url=prepared["url"],
                        title=prepared["title"],
                        query=query,
                        scrape_provider_name=scrape_provider_name if do_scrape else "none",
                        search_provider_name=search_provider_name,
                        word_count_value=prepared["word_count"],
                        extra_metadata=prepared["frontmatter_extra"],
                    )
                    relpath = f"sources/{target_entry['file']}"
                    source_files.append(
                        {
                            "relpath": relpath,
                            "content": render_frontmatter(frontmatter, prepared["body"]),
                        }
                    )
                    target_entry.update(
                        {
                            "url": prepared["url"],
                            "url_normalized": normalized,
                            "query": query,
                            "word_count": prepared["word_count"],
                            "title": prepared["title"],
                            "search_provider": search_provider_name,
                            "retried_at": utcnow_iso(),
                        }
                    )
                    target_entry.setdefault("review_status", "pending")
                    target_entry.pop("error", None)
                    for key, value in prepared["index_extra"].items():
                        if value in (None, ""):
                            target_entry.pop(key, None)
                        else:
                            target_entry[key] = value
                    updated_ids.append(retry_source_id)
                    continue

            if existing_entries:
                duplicate_matches.append(duplicate_detail(prepared["url"], existing_entries))
                continue

            source_id = source_id_for(next_id)
            next_id += 1
            frontmatter = build_source_frontmatter(
                source_id=source_id,
                url=prepared["url"],
                title=prepared["title"],
                query=query,
                scrape_provider_name=scrape_provider_name if do_scrape else "none",
                search_provider_name=search_provider_name,
                word_count_value=prepared["word_count"],
                extra_metadata=prepared["frontmatter_extra"],
            )
            relpath = f"web/{source_id}.md"
            source_files.append(
                {
                    "relpath": f"sources/{relpath}",
                    "content": render_frontmatter(frontmatter, prepared["body"]),
                }
            )
            entry = index_entry_for_source(
                source_id,
                prepared["url"],
                relpath,
                query,
                prepared["word_count"],
                extras=prepared["index_extra"],
            )
            index.setdefault("sources", []).append(entry)
            url_map.setdefault(normalized, []).append(entry)
            added_ids.append(source_id)
            if prepared.get("failure"):
                failure = dict(prepared["failure"])
                failure["source_id"] = source_id
                failures.append(failure)

        index["next_id"] = next_id

        deduped_duplicates = {
            json.dumps(detail, sort_keys=True): detail
            for detail in (best_effort_duplicates + duplicate_matches)
        }
        duplicate_matches = sorted(
            deduped_duplicates.values(),
            key=lambda detail: (detail.get("url_normalized", ""), detail.get("url", "")),
        )

        search_record: dict[str, Any] = {
            "query": query,
            "provider": search_provider_name,
            "scrape_provider": scrape_provider_name if do_scrape else None,
            "timestamp": utcnow_iso(),
            "results_count": len(raw_results),
            "urls_found": [r["url"] for r in raw_results],
            "sources_added": len(added_ids),
            "sources_updated": len(updated_ids),
            "sources_skipped": len(duplicate_matches),
            "source_ids": added_ids + updated_ids,
            "duplicate_matches": duplicate_matches,
        }
        if failures:
            search_record["failures"] = failures
        if retry_context:
            search_record["retry_of"] = retry_context

        config.setdefault("searches", []).append(search_record)
        config["next_source_id"] = index["next_id"]
        coordinator.commit(
            config=config,
            index=index,
            source_files=source_files,
            transaction_label="search_web",
        )

    result = {
        "sources_added": len(added_ids),
        "sources_updated": len(updated_ids),
        "sources_skipped": len(duplicate_matches),
        "source_ids": added_ids,
        "updated_source_ids": updated_ids,
        "duplicate_matches": duplicate_matches,
        "workspace": str(workspace),
        "query": query,
    }
    if failures:
        result["sources_failed"] = len(failures)
        result["errors"] = failures
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
    parser.add_argument("query", nargs="?", help="Search query string.")
    parser.add_argument("--workspace", required=True, help="Path to the workspace directory.")
    parser.add_argument("--max-results", type=int, default=10, help="Maximum search results to fetch (default: 10).")
    parser.add_argument("--search-provider", default=None, help="Search provider name (default: from config).")
    parser.add_argument("--scrape-provider", default=None, help="Scrape provider name (default: from config).")
    parser.add_argument("--no-scrape", action="store_true", help="Skip scraping; save URL + snippet only.")
    parser.add_argument("--retry-failed", action="store_true", help="Retry only the failed URLs from the latest web-search record in this workspace.")
    parser.add_argument("--truncate", type=int, default=10000, help="Truncate sources to N words (0=no limit, default: 10000).")
    parser.add_argument("--use-cache", action="store_true", help="Use cached search results if present (for golden runs).")
    parser.add_argument("--clear-cache", action="store_true", help="Delete cached search results before running.")
    parser.add_argument("--cache-dir", default=None, help="Cache directory (default: <workspace>/.calixto/cache).")
    args = parser.parse_args(argv)

    if not args.retry_failed and (not args.query or not args.query.strip()):
        emit_error("invalid_query", "query must be a non-empty string")
    if args.retry_failed and args.no_scrape:
        emit_error("invalid_retry_mode", "--retry-failed requires scraping to be enabled")

    workspace = workspace_path(args.workspace)
    cache_dir = Path(args.cache_dir).resolve() if args.cache_dir else default_cache_dir(workspace)

    if args.truncate < 0:
        emit_error("invalid_truncate", "--truncate must be >= 0")

    try:
        result = run_search(
            query=args.query.strip() if args.query else None,
            workspace=workspace,
            max_results=args.max_results,
            search_provider_name=args.search_provider,
            scrape_provider_name=args.scrape_provider,
            do_scrape=not args.no_scrape,
            truncate=args.truncate,
            use_cache=args.use_cache,
            clear_cache_first=args.clear_cache,
            cache_dir=cache_dir,
            retry_failed=args.retry_failed,
        )
    except SystemExit:
        raise
    except Exception as e:
        emit_error("search_failed", f"unexpected error: {e}")

    if result.get("sources_failed", 0) > 0:
        emit_partial(result)
    else:
        emit_ok(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
