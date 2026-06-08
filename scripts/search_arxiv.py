"""
search_arxiv.py: Search arXiv for academic papers and save them to a workspace.

This script is the arXiv counterpart to search_web.py. It uses the official
`arxiv` Python package, assigns sequential src_NNN IDs (shared with web sources
via the same index.json counter), and saves paper metadata as markdown in
sources/papers/.

Usage:
    python scripts/search_arxiv.py "<query>" --workspace <path>
        [--max-results 10]
        [--category cs.AI]                  # arXiv subject category
        [--sort-by relevance|submitted]     # sort criterion
        [--use-cache]                       # use cached results (golden runs)
        [--clear-cache]                     # delete cache before running
        [--cache-dir tests/golden/cache]

Output: structured JSON to stdout.

Architecture:
    - arXiv is queried via the `arxiv` Python package (rate limit 1 req / 3s)
    - 3.5s delay between queries per requirements.md section 15
    - Dedup by arXiv ID (stable, unique, not URL)
    - Saves to sources/papers/<src_NNN>.md
    - Shares the same index.json and config.json with web searches, so IDs are
      sequential across the workspace

See:
    - requirements.md section 15: rate limits
    - scripts/search_web.py: the web counterpart
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Ensure providers, _common are importable when run as a script
_SCRIPTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = Path(__file__).resolve().parent.parent
for p in (str(_REPO_ROOT), str(_SCRIPTS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from _common import (
    emit_error,
    emit_ok,
    emit_partial,
    load_source_index,
    load_workspace_config,
    render_frontmatter,
    save_source_index,
    save_workspace_config,
    source_id_for,
    utcnow_iso,
    word_count,
    workspace_path,
)
# Re-use the caching helpers from search_web so behavior is consistent
from search_web import (
    cache_key,
    cache_path_for,
    clear_cache,
    load_cache,
    save_cache,
)

log = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = _REPO_ROOT / "tests" / "golden" / "cache"

# arXiv's official rate limit guideline
ARXIV_DELAY_SECONDS = 3.5


def _ensure_arxiv_client() -> Any:
    try:
        import arxiv as arxiv_pkg  # type: ignore
    except ImportError as e:
        emit_error("missing_dependency", f"arxiv package not installed. Run: pip install arxiv. ({e})")
    return arxiv_pkg


def _arxiv_id_from_entry_id(entry_id: str) -> str:
    """Extract the canonical arXiv ID from an entry_id URL.

    Example: 'http://arxiv.org/abs/2401.01234v2' -> '2401.01234'
    """
    if not entry_id:
        return ""
    # Strip protocol and host
    if "://" in entry_id:
        entry_id = entry_id.split("://", 1)[1]
    if "/" in entry_id:
        entry_id = entry_id.split("/", 1)[1]
    # Drop "abs/" prefix
    if entry_id.startswith("abs/"):
        entry_id = entry_id[4:]
    # Drop version suffix (e.g., v1, v2)
    if "v" in entry_id:
        # Only drop the trailing vN, not the v in the middle (e.g., 2401.01234v2)
        last_v = entry_id.rfind("v")
        # If the part after the last v is all digits, drop it
        suffix = entry_id[last_v + 1:]
        if suffix.isdigit():
            entry_id = entry_id[:last_v]
    return entry_id


def _format_authors(authors) -> str:
    """Format an arxiv.Result.authors list into a comma-separated string."""
    if not authors:
        return ""
    return ", ".join(getattr(a, "name", str(a)) for a in authors)


def _date_to_iso(dt: Any) -> str:
    """Convert a datetime to YYYY-MM-DD; pass strings through."""
    if dt is None:
        return ""
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d")
    return str(dt)[:10]


def run_arxiv_search(
    query: str,
    workspace: Path,
    max_results: int,
    category: str | None,
    sort_by: str,
    use_cache: bool,
    clear_cache_first: bool,
    cache_dir: Path,
) -> dict:
    """Execute the full arXiv search-and-persist flow. Returns a status dict."""
    if not workspace.exists() or not (workspace / "config.json").exists():
        emit_error(
            "workspace_not_found",
            f"workspace not found at {workspace}. Run init_workspace.py first.",
        )

    config = load_workspace_config(workspace)
    index = load_source_index(workspace)

    if clear_cache_first and cache_dir.exists():
        removed = clear_cache(cache_dir)
        log.info("cleared %d cache files", removed)

    # Cache lookup must happen BEFORE the arxiv client is constructed.
    # The arxiv client pays a connection cost on import; for cached
    # reproducible runs we should not pay it at all.
    cache_dir.mkdir(parents=True, exist_ok=True)
    raw_results: list[dict] | None = None
    cache_provider = f"arxiv"
    if use_cache:
        raw_results = load_cache(
            cache_dir, cache_provider, query, max_results, category=category, sort_by=sort_by
        )
        if raw_results is not None:
            log.info("using cached arxiv results: %d items", len(raw_results))
        else:
            # Reproducible mode: a cache miss must fail loudly rather than
            # silently falling back to a live network call.
            emit_error(
                "cache_miss",
                f"no cached arxiv result for query={query!r} max_results={max_results} "
                f"category={category!r} sort_by={sort_by!r}. "
                "Refusing to call the network in --use-cache mode; "
                "re-run without --use-cache to populate the cache.",
            )

    if raw_results is None:
        arxiv_pkg = _ensure_arxiv_client()
        # Build the arxiv Search
        search_kwargs: dict[str, Any] = {
            "query": query,
            "max_results": max_results,
        }
        if category:
            search_kwargs["query"] = f"cat:{category} AND ({query})"
        if sort_by == "date":
            search_kwargs["sort_by"] = arxiv_pkg.SortCriterion.SubmittedDate
        else:
            search_kwargs["sort_by"] = arxiv_pkg.SortCriterion.Relevance

        client = arxiv_pkg.Client(page_size=min(max_results, 50), delay_seconds=ARXIV_DELAY_SECONDS, num_retries=3)
        try:
            results_gen = client.results(arxiv_pkg.Search(**search_kwargs))
            results_list = list(results_gen)
        except Exception as e:
            emit_error("arxiv_search_failed", f"arXiv API error: {e}", retry_after=10)

        raw_results = []
        for r in results_list:
            entry_id = _arxiv_id_from_entry_id(getattr(r, "entry_id", ""))
            url = getattr(r, "entry_id", "") or f"https://arxiv.org/abs/{entry_id}"
            pdf_url = getattr(r, "pdf_url", "") or f"https://arxiv.org/pdf/{entry_id}"
            authors = _format_authors(getattr(r, "authors", []))
            raw_results.append(
                {
                    "arxiv_id": entry_id,
                    "url": url,
                    "pdf_url": pdf_url,
                    "title": (getattr(r, "title", "") or "").strip().replace("\n", " "),
                    "summary": (getattr(r, "summary", "") or "").strip(),
                    "authors": authors,
                    "date_published": _date_to_iso(getattr(r, "published", None)),
                    "categories": list(getattr(r, "categories", []) or []),
                    "primary_category": getattr(r, "primary_category", "") or "",
                }
            )

        # Save the cache unconditionally after a successful live call.
        # `--use-cache` controls whether a cache *hit* is required, not
        # whether cache *writes* occur: every successful live search
        # should populate the cache so future reproducible runs can
        # replay it. This decouples cache writes from the --use-cache
        # flag, matching the contract in requirements.md section 10.2.
        save_cache(
            cache_dir, cache_provider, query, max_results, raw_results,
            category=category, sort_by=sort_by,
        )

    # Dedup by arxiv_id
    existing_arxiv_ids = {
        s.get("arxiv_id")
        for s in index.get("sources", [])
        if s.get("arxiv_id")
    }
    new_results: list[dict] = []
    skipped = 0
    for r in raw_results:
        arxiv_id = r.get("arxiv_id", "")
        if not arxiv_id or arxiv_id in existing_arxiv_ids:
            skipped += 1
            continue
        existing_arxiv_ids.add(arxiv_id)
        new_results.append(r)

    if not new_results:
        # Record the search and exit cleanly
        config.setdefault("searches", []).append(
            {
                "query": query,
                "provider": "arxiv",
                "timestamp": utcnow_iso(),
                "results_count": len(raw_results),
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

    next_id = index.get("next_id", 1)
    added_ids: list[str] = []

    for r in new_results:
        arxiv_id = r["arxiv_id"]
        source_id = source_id_for(next_id)
        next_id += 1

        # Build the markdown body
        body_lines: list[str] = []
        body_lines.append(f"# {r['title'] or 'Untitled'}")
        body_lines.append("")
        body_lines.append(f"**Authors:** {r['authors']}")
        body_lines.append("")
        body_lines.append(f"**Date published:** {r['date_published']}")
        body_lines.append("")
        body_lines.append(f"**arXiv ID:** {arxiv_id}")
        body_lines.append("")
        body_lines.append(f"**URL:** {r['url']}")
        if r.get("pdf_url"):
            body_lines.append(f"**PDF:** {r['pdf_url']}")
        body_lines.append("")
        if r.get("categories"):
            body_lines.append(f"**Categories:** {', '.join(r['categories'])}")
            body_lines.append("")
        body_lines.append("## Abstract")
        body_lines.append("")
        body_lines.append(r.get("summary", "(no summary)"))
        body = "\n".join(body_lines)
        wc = word_count(body)

        frontmatter: dict[str, Any] = {
            "id": source_id,
            "url": r["url"],
            "title": r["title"],
            "date_crawled": utcnow_iso(),
            "date_published": r["date_published"],
            "provider": "arxiv",
            "search_provider": "arxiv",
            "query": query,
            "arxiv_id": arxiv_id,
            "authors": r["authors"],
            "categories": r.get("categories", []),
            "word_count": wc,
            "truncated": False,
        }

        relpath = f"papers/{source_id}.md"
        target = workspace / "sources" / "papers" / f"{source_id}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_frontmatter(frontmatter, body), encoding="utf-8")

        index.setdefault("sources", []).append(
            {
                "id": source_id,
                "url": r["url"],
                "file": relpath,
                "added_at": utcnow_iso(),
                "query": query,
                "word_count": wc,
                "title": r["title"],
                "arxiv_id": arxiv_id,
                "authors": r["authors"],
                "date_published": r["date_published"],
                "categories": r.get("categories", []),
                "search_provider": "arxiv",
            }
        )
        added_ids.append(source_id)

    index["next_id"] = next_id

    config.setdefault("searches", []).append(
        {
            "query": query,
            "provider": "arxiv",
            "category": category,
            "timestamp": utcnow_iso(),
            "results_count": len(raw_results),
            "sources_added": len(added_ids),
            "sources_skipped": skipped,
            "source_ids": added_ids,
        }
    )
    config["next_source_id"] = next_id
    save_workspace_config(workspace, config)
    save_source_index(workspace, index)

    return {
        "sources_added": len(added_ids),
        "sources_skipped": skipped,
        "source_ids": added_ids,
        "workspace": str(workspace),
        "query": query,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Search arXiv for academic papers and save to a workspace.",
        prog="search_arxiv",
    )
    parser.add_argument("query", help="Search query string.")
    parser.add_argument("--workspace", required=True, help="Path to the workspace directory.")
    parser.add_argument("--max-results", type=int, default=10, help="Maximum results (default: 10).")
    parser.add_argument("--category", default=None, help="arXiv subject category (e.g., cs.AI, cs.LG).")
    parser.add_argument("--sort-by", choices=["relevance", "date"], default="relevance", help="Sort criterion (default: relevance).")
    parser.add_argument("--use-cache", action="store_true", help="Use cached search results if present.")
    parser.add_argument("--clear-cache", action="store_true", help="Delete cached search results before running.")
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR), help="Cache directory.")
    args = parser.parse_args(argv)

    if not args.query or not args.query.strip():
        emit_error("invalid_query", "query must be a non-empty string")

    workspace = workspace_path(args.workspace)
    cache_dir = Path(args.cache_dir).resolve()

    try:
        result = run_arxiv_search(
            query=args.query.strip(),
            workspace=workspace,
            max_results=args.max_results,
            category=args.category,
            sort_by=args.sort_by,
            use_cache=args.use_cache,
            clear_cache_first=args.clear_cache,
            cache_dir=cache_dir,
        )
    except SystemExit:
        raise
    except Exception as e:
        emit_error("search_failed", f"unexpected error: {e}")

    emit_ok(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
