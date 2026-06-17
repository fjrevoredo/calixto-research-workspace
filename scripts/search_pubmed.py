"""
search_pubmed.py: Search PubMed and save biomedical paper metadata to a workspace.

This script complements search_arxiv.py for biomedical, pharmacology, and
clinical questions where PubMed/MEDLINE is usually the better scholarly source.
It uses the official NCBI E-utilities HTTP API, assigns sequential src_NNN IDs
shared with the workspace source index, and writes paper metadata into
sources/papers/.

Usage:
    python scripts/search_pubmed.py "<query>" --workspace <path>
        [--max-results 10]
        [--email you@example.com]
        [--api-key <key>]
        [--use-cache]
        [--clear-cache]
        [--cache-dir <path>]

Output: structured JSON to stdout.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = Path(__file__).resolve().parent.parent
for p in (str(_REPO_ROOT), str(_SCRIPTS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from _common import (
    WorkspaceStateCoordinator,
    classify_source_quality,
    emit_error,
    emit_ok,
    load_source_index,
    load_workspace_config,
    render_frontmatter,
    source_id_for,
    utcnow_iso,
    word_count,
    workspace_path,
)
from search_web import clear_cache, load_cache, save_cache

log = logging.getLogger(__name__)

PUBMED_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
PUBMED_DELAY_NO_KEY_SECONDS = 0.34
PUBMED_DELAY_WITH_KEY_SECONDS = 0.11


def default_cache_dir(workspace: Path) -> Path:
    """Return the default cache directory for a standalone workspace."""
    return workspace / ".calixto" / "cache"


def _request_bytes(url: str, params: dict[str, Any], delay_seconds: float) -> bytes:
    """Perform one HTTP GET against NCBI and return raw bytes."""
    query = urllib.parse.urlencode(
        {key: value for key, value in params.items() if value not in (None, "")}
    )
    request_url = f"{url}?{query}"
    try:
        with urllib.request.urlopen(request_url, timeout=30) as response:
            payload = response.read()
    except Exception as exc:
        emit_error("pubmed_search_failed", f"PubMed request failed: {exc}", retry_after=5)
    if delay_seconds > 0:
        time.sleep(delay_seconds)
    return payload


def _text(node: ET.Element | None, xpath: str) -> str:
    """Return stripped text from the first matching child element."""
    if node is None:
        return ""
    match = node.find(xpath)
    if match is None or match.text is None:
        return ""
    return match.text.strip()


def _collect_text(node: ET.Element | None, xpath: str) -> list[str]:
    """Return stripped text values from matching child elements."""
    if node is None:
        return []
    values: list[str] = []
    for match in node.findall(xpath):
        text = "".join(match.itertext()).strip()
        if text:
            values.append(text)
    return values


def _parse_pubmed_articles(xml_payload: bytes) -> list[dict[str, Any]]:
    """Parse PubMed efetch XML into plain JSON-serializable records."""
    try:
        root = ET.fromstring(xml_payload)
    except ET.ParseError as exc:
        emit_error("pubmed_parse_failed", f"could not parse PubMed XML: {exc}")

    results: list[dict[str, Any]] = []
    for article in root.findall(".//PubmedArticle"):
        medline = article.find("MedlineCitation")
        article_meta = medline.find("Article") if medline is not None else None
        pubmed_data = article.find("PubmedData")
        pubmed_id = _text(medline, "PMID")
        if not pubmed_id:
            continue

        authors: list[str] = []
        for author in article.findall(".//AuthorList/Author"):
            collective_name = _text(author, "CollectiveName")
            if collective_name:
                authors.append(collective_name)
                continue
            last_name = _text(author, "LastName")
            fore_name = _text(author, "ForeName")
            initials = _text(author, "Initials")
            if last_name and fore_name:
                authors.append(f"{fore_name} {last_name}")
            elif last_name and initials:
                authors.append(f"{initials} {last_name}")
            elif last_name:
                authors.append(last_name)

        pub_date = ""
        journal_issue = article_meta.find("Journal/JournalIssue/PubDate") if article_meta is not None else None
        year = _text(journal_issue, "Year")
        month = _text(journal_issue, "Month")
        day = _text(journal_issue, "Day")
        if year:
            pub_date = "-".join(part for part in (year, month, day) if part)
        medline_date = _text(journal_issue, "MedlineDate")
        if not pub_date and medline_date:
            pub_date = medline_date

        article_ids = article.findall(".//ArticleIdList/ArticleId")
        doi = ""
        for article_id in article_ids:
            if article_id.attrib.get("IdType") == "doi" and (article_id.text or "").strip():
                doi = article_id.text.strip()
                break

        abstract_parts = _collect_text(article_meta, "Abstract/AbstractText")
        title = "".join(article_meta.findtext("ArticleTitle", default="").splitlines()).strip() if article_meta is not None else ""
        journal = _text(article_meta, "Journal/Title")
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/"
        result = {
            "pubmed_id": pubmed_id,
            "url": url,
            "title": title,
            "abstract": "\n\n".join(abstract_parts).strip(),
            "authors": authors,
            "journal": journal,
            "date_published": pub_date,
            "doi": doi,
            "mesh_terms": _collect_text(medline, "MeshHeadingList/MeshHeading/DescriptorName"),
            "publication_types": _collect_text(article_meta, "PublicationTypeList/PublicationType"),
            "pmc_id": "",
        }
        for article_id in article_ids:
            if article_id.attrib.get("IdType") == "pmc" and (article_id.text or "").strip():
                result["pmc_id"] = article_id.text.strip()
                break
        results.append(result)
    return results


def _fetch_pubmed_results(
    query: str,
    max_results: int,
    email: str | None,
    api_key: str | None,
) -> list[dict[str, Any]]:
    """Search PubMed live and return normalized result dicts."""
    delay_seconds = PUBMED_DELAY_WITH_KEY_SECONDS if api_key else PUBMED_DELAY_NO_KEY_SECONDS
    common_params = {
        "db": "pubmed",
        "tool": "calixto-research-workspace",
        "email": email,
        "api_key": api_key,
    }
    search_payload = _request_bytes(
        PUBMED_SEARCH_URL,
        {
            **common_params,
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance",
        },
        delay_seconds,
    )
    try:
        search_data = json.loads(search_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        emit_error("pubmed_parse_failed", f"could not parse PubMed JSON: {exc}")
    id_list = search_data.get("esearchresult", {}).get("idlist", [])
    if not isinstance(id_list, list) or not id_list:
        return []

    fetch_payload = _request_bytes(
        PUBMED_FETCH_URL,
        {
            **common_params,
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "xml",
        },
        delay_seconds,
    )
    return _parse_pubmed_articles(fetch_payload)


def run_pubmed_search(
    query: str,
    workspace: Path,
    max_results: int,
    use_cache: bool,
    clear_cache_first: bool,
    cache_dir: Path,
    email: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Execute the full PubMed search-and-persist flow."""
    if not workspace.exists() or not (workspace / "config.json").exists():
        emit_error(
            "workspace_not_found",
            f"workspace not found at {workspace}. Run init_workspace.py first.",
        )

    load_workspace_config(workspace)
    initial_index = load_source_index(workspace)

    if clear_cache_first and cache_dir.exists():
        removed = clear_cache(cache_dir)
        log.info("cleared %d cache files", removed)

    cache_dir.mkdir(parents=True, exist_ok=True)
    raw_results: list[dict[str, Any]] | None = None
    if use_cache:
        raw_results = load_cache(
            cache_dir,
            "pubmed",
            query,
            max_results,
        )
        if raw_results is None:
            emit_error(
                "cache_miss",
                f"no cached PubMed result for query={query!r} max_results={max_results}. "
                "Refusing to call the network in --use-cache mode; re-run without --use-cache to populate the cache.",
            )

    if raw_results is None:
        raw_results = _fetch_pubmed_results(query, max_results, email, api_key)
        save_cache(cache_dir, "pubmed", query, max_results, raw_results)

    initial_pubmed_ids = {
        str(source.get("pubmed_id", "")).strip()
        for source in initial_index.get("sources", [])
        if str(source.get("pubmed_id", "")).strip()
    }
    candidate_results: list[dict[str, Any]] = []
    seen_pubmed_ids: set[str] = set()
    skipped_preexisting = 0
    for result in raw_results:
        pubmed_id = str(result.get("pubmed_id", "")).strip()
        if not pubmed_id or pubmed_id in seen_pubmed_ids:
            skipped_preexisting += 1
            continue
        seen_pubmed_ids.add(pubmed_id)
        if pubmed_id in initial_pubmed_ids:
            skipped_preexisting += 1
            continue
        candidate_results.append(result)

    added_ids: list[str] = []
    skipped_committed = 0

    with WorkspaceStateCoordinator(workspace) as coordinator:
        config = coordinator.config
        index = coordinator.index
        current_pubmed_ids = {
            str(source.get("pubmed_id", "")).strip()
            for source in index.get("sources", [])
            if str(source.get("pubmed_id", "")).strip()
        }
        next_id = index.get("next_id", 1)
        source_files: list[dict[str, str]] = []

        for result in candidate_results:
            pubmed_id = str(result.get("pubmed_id", "")).strip()
            if not pubmed_id or pubmed_id in current_pubmed_ids:
                skipped_committed += 1
                continue

            source_id = source_id_for(next_id)
            next_id += 1
            body_lines = [
                f"# {result.get('title') or 'Untitled'}",
                "",
                f"**Authors:** {', '.join(result.get('authors', [])) or 'Unknown'}",
                "",
                f"**Journal:** {result.get('journal') or 'Unknown'}",
                "",
                f"**Date published:** {result.get('date_published') or 'Unknown'}",
                "",
                f"**PubMed ID:** {pubmed_id}",
                "",
                f"**URL:** {result['url']}",
            ]
            if result.get("doi"):
                body_lines.extend(["", f"**DOI:** {result['doi']}"])
            if result.get("pmc_id"):
                body_lines.extend(["", f"**PMC ID:** {result['pmc_id']}"])
            if result.get("publication_types"):
                body_lines.extend(["", f"**Publication types:** {', '.join(result['publication_types'])}"])
            if result.get("mesh_terms"):
                body_lines.extend(["", f"**MeSH terms:** {', '.join(result['mesh_terms'])}"])
            body_lines.extend(["", "## Abstract", "", result.get("abstract") or "(no abstract returned)"])
            body = "\n".join(body_lines)
            wc = word_count(body)
            quality_metadata = classify_source_quality(
                url=result["url"],
                provider="pubmed",
                search_provider="pubmed",
                title=str(result.get("title", "")),
                metadata={"pubmed_id": pubmed_id, "doi": result.get("doi", "")},
            )
            frontmatter: dict[str, Any] = {
                "id": source_id,
                "url": result["url"],
                "title": result.get("title", ""),
                "date_crawled": utcnow_iso(),
                "date_published": result.get("date_published", ""),
                "provider": "pubmed",
                "search_provider": "pubmed",
                "query": query,
                "pubmed_id": pubmed_id,
                "pmc_id": result.get("pmc_id", ""),
                "authors": result.get("authors", []),
                "journal": result.get("journal", ""),
                "doi": result.get("doi", ""),
                "mesh_terms": result.get("mesh_terms", []),
                "publication_types": result.get("publication_types", []),
                "word_count": wc,
                "truncated": False,
                **quality_metadata,
            }
            relpath = f"papers/{source_id}.md"
            source_files.append(
                {
                    "relpath": f"sources/{relpath}",
                    "content": render_frontmatter(frontmatter, body),
                }
            )
            index.setdefault("sources", []).append(
                {
                    "id": source_id,
                    "url": result["url"],
                    "file": relpath,
                    "added_at": utcnow_iso(),
                    "query": query,
                    "word_count": wc,
                    "review_status": "pending",
                    "title": result.get("title", ""),
                    "authors": result.get("authors", []),
                    "journal": result.get("journal", ""),
                    "date_published": result.get("date_published", ""),
                    "doi": result.get("doi", ""),
                    "pubmed_id": pubmed_id,
                    "pmc_id": result.get("pmc_id", ""),
                    "mesh_terms": result.get("mesh_terms", []),
                    "publication_types": result.get("publication_types", []),
                    "search_provider": "pubmed",
                    **quality_metadata,
                }
            )
            current_pubmed_ids.add(pubmed_id)
            added_ids.append(source_id)

        index["next_id"] = next_id
        config.setdefault("searches", []).append(
            {
                "query": query,
                "provider": "pubmed",
                "timestamp": utcnow_iso(),
                "results_count": len(raw_results),
                "sources_added": len(added_ids),
                "sources_skipped": skipped_preexisting + skipped_committed,
                "source_ids": added_ids,
            }
        )
        config["next_source_id"] = next_id
        coordinator.commit(
            config=config,
            index=index,
            source_files=source_files,
            transaction_label="search_pubmed",
        )

    warnings: list[str] = []
    if not api_key:
        warnings.append(
            "PubMed was queried without an NCBI API key. This is supported, but rate limits are lower."
        )

    return {
        "sources_added": len(added_ids),
        "sources_skipped": skipped_preexisting + skipped_committed,
        "source_ids": added_ids,
        "workspace": str(workspace),
        "query": query,
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Search PubMed for biomedical papers and save them to a workspace.",
        prog="search_pubmed",
    )
    parser.add_argument("query", help="Search query string.")
    parser.add_argument("--workspace", required=True, help="Path to the workspace directory.")
    parser.add_argument("--max-results", type=int, default=10, help="Maximum results (default: 10).")
    parser.add_argument("--email", default=None, help="Optional contact email for the NCBI API.")
    parser.add_argument("--api-key", default=None, help="Optional NCBI API key for higher rate limits.")
    parser.add_argument("--use-cache", action="store_true", help="Use cached search results if present.")
    parser.add_argument("--clear-cache", action="store_true", help="Delete cached search results before running.")
    parser.add_argument("--cache-dir", default=None, help="Cache directory (default: <workspace>/.calixto/cache).")
    args = parser.parse_args(argv)

    if not args.query or not args.query.strip():
        emit_error("invalid_query", "query must be a non-empty string")

    workspace = workspace_path(args.workspace)
    cache_dir = Path(args.cache_dir).resolve() if args.cache_dir else default_cache_dir(workspace)

    try:
        result = run_pubmed_search(
            query=args.query.strip(),
            workspace=workspace,
            max_results=args.max_results,
            use_cache=args.use_cache,
            clear_cache_first=args.clear_cache,
            cache_dir=cache_dir,
            email=args.email,
            api_key=args.api_key,
        )
    except SystemExit:
        raise
    except Exception as exc:
        emit_error("search_failed", f"unexpected error: {exc}")

    emit_ok(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
