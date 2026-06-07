"""
crawl4ai_provider.py: Crawl4AI implementation of the ScrapeProvider interface.

This is the only scrape provider in the core toolkit. It wraps Crawl4AI's
AsyncWebCrawler behind a sync `scrape()` method that scripts can call directly.

Usage:
    import asyncio
    from providers.scrape.crawl4ai_provider import Crawl4AIProvider
    p = Crawl4AIProvider()
    result = p.scrape("https://example.com")
    print(result.markdown[:200])

Architecture:
    - Crawl4AI is async under the hood
    - The sync `scrape()` method runs the async code via `asyncio.run`
    - Each `scrape()` call creates and tears down its own event loop
    - For long-running batch jobs, prefer `scrape_many()` which uses one event loop

Failure modes (per requirements.md 12.2):
    - Paywall / blocked: result.metadata["error"] = "paywalled", markdown may be empty
    - Timeout (>30s): raises ScrapeError("timeout")
    - Crash: exception propagates; callers log and continue
    - Non-HTML content: result.metadata["error"] = "unsupported_content_type"

See:
    - providers/scrape/base.py: ScrapeProvider interface
    - docs/adr/001-choose-crawl4ai.md: why we chose Crawl4AI
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .base import ScrapeError, ScrapeProvider, ScrapeResult

log = logging.getLogger(__name__)

# Default timeout for a single scrape (seconds)
DEFAULT_TIMEOUT_SECONDS = 30.0


class Crawl4AIProvider(ScrapeProvider):
    """Scrape web pages into LLM-friendly markdown using Crawl4AI.

    Requires:
        - crawl4ai package installed
        - Playwright browser installed (run: crawl4ai-setup or playwright install chromium)
    """

    name = "crawl4ai"
    timeout_seconds: int = 30

    def __init__(self, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self.timeout_seconds = timeout_seconds
        # Lazy import: don't load crawl4ai at module import time
        self._async_webcrawler_cls: Any = None
        self._browser_config_cls: Any = None
        self._crawler_run_config_cls: Any = None

    def _ensure_imports(self) -> None:
        """Lazily import Crawl4AI components."""
        if self._async_webcrawler_cls is not None:
            return
        try:
            from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig  # type: ignore
        except ImportError as e:
            raise ScrapeError(
                f"crawl4ai package not installed. Run: pip install crawl4ai. ({e})",
                error_type="missing_dependency",
            )
        self._async_webcrawler_cls = AsyncWebCrawler
        self._browser_config_cls = BrowserConfig
        self._crawler_run_config_cls = CrawlerRunConfig

    def _check_browser(self) -> None:
        """Best-effort check that a Playwright browser is available.

        Does not raise if the check cannot be performed, but logs a warning
        so misconfigured environments get a clear hint.
        """
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except ImportError:
            log.warning("playwright not installed; run: pip install playwright && playwright install chromium")
            return
        try:
            with sync_playwright() as p:
                # Don't actually launch; just check that the binary is present
                _ = p.chromium.executable_path
        except Exception as e:
            log.warning(
                "playwright chromium not installed. Run: crawl4ai-setup or playwright install chromium. (%s)",
                e,
            )

    def scrape(self, url: str) -> ScrapeResult:
        """Scrape a single URL synchronously.

        Args:
            url: The URL to scrape. Must be http(s).

        Returns:
            A ScrapeResult with markdown, title, word_count, and metadata.

        Raises:
            ValueError: If url is invalid.
            ScrapeError: For recoverable failures (timeout, dependency missing).
        """
        self.validate_url(url)
        self._ensure_imports()
        return asyncio.run(self._async_scrape(url))

    async def _async_scrape(self, url: str) -> ScrapeResult:
        """The async implementation. One call -> one event loop."""
        try:
            browser_config = self._browser_config_cls(headless=True)
            run_config = self._crawler_run_config_cls(
                page_timeout=int(self.timeout_seconds * 1000),
            )
            async with self._async_webcrawler_cls(config=browser_config) as crawler:
                try:
                    crawl_result = await asyncio.wait_for(
                        crawler.arun(url=url, config=run_config),
                        timeout=self.timeout_seconds,
                    )
                except asyncio.TimeoutError:
                    raise ScrapeError(
                        f"scrape timed out after {self.timeout_seconds}s for {url}",
                        error_type="timeout",
                    )
        except ScrapeError:
            raise
        except Exception as e:
            raise ScrapeError(f"crawl4ai crashed on {url}: {e}", error_type="scrape_failed")

        # crawl_result.success is a boolean indicating whether the crawl succeeded
        if not getattr(crawl_result, "success", False):
            error_message = getattr(crawl_result, "error_message", "unknown error") or "unknown error"
            return ScrapeResult(
                url=url,
                title="",
                markdown="",
                word_count=0,
                metadata={
                    "error": _classify_scrape_error(error_message),
                    "error_message": error_message,
                },
            )

        # Extract content. Crawl4AI exposes a few fields; we prefer the cleaned
        # markdown that is LLM-friendly.
        markdown = (
            getattr(crawl_result, "markdown_v2", None)
            or getattr(crawl_result, "markdown", None)
            or ""
        )
        # markdown_v2 can be a MarkdownGenerationResult object with a .raw_markdown attribute
        if hasattr(markdown, "raw_markdown"):
            markdown = markdown.raw_markdown or ""
        if not isinstance(markdown, str):
            markdown = str(markdown) if markdown is not None else ""
        title = ""
        meta_obj = getattr(crawl_result, "meta", None) or {}
        if isinstance(meta_obj, dict):
            title = meta_obj.get("title", "") or ""
        if not title:
            title = (
                getattr(crawl_result, "title", None)
                or meta_obj.get("og:title", "")
                if isinstance(meta_obj, dict)
                else ""
            )

        metadata: dict[str, Any] = {
            "provider": "crawl4ai",
        }
        if isinstance(meta_obj, dict):
            for k in ("description", "author", "keywords", "og:description"):
                if meta_obj.get(k):
                    metadata[k] = meta_obj[k]

        word_count = len(markdown.split()) if markdown else 0
        return ScrapeResult(
            url=url,
            title=title or "",
            markdown=markdown,
            word_count=word_count,
            metadata=metadata,
        )

    def scrape_many(self, urls: list[str]) -> list[ScrapeResult]:
        """Scrape multiple URLs in one event loop. Faster than calling scrape() in a loop."""
        if not urls:
            return []
        self._ensure_imports()
        return asyncio.run(self._async_scrape_many(urls))

    async def _async_scrape_many(self, urls: list[str]) -> list[ScrapeResult]:
        """Internal: run arun_many across all URLs in a single event loop."""
        for u in urls:
            self.validate_url(u)
        browser_config = self._browser_config_cls(headless=True)
        run_config = self._crawler_run_config_cls(
            page_timeout=int(self.timeout_seconds * 1000),
        )
        results: list[ScrapeResult] = []
        try:
            async with self._async_webcrawler_cls(config=browser_config) as crawler:
                # arun_many may not exist in all versions; fall back to sequential
                arun_many = getattr(crawler, "arun_many", None)
                if arun_many is not None:
                    crawl_results = await arun_many(urls=urls, config=run_config)
                    crawl_results_list = crawl_results if isinstance(crawl_results, list) else [crawl_results]
                else:
                    crawl_results_list = []
                    for u in urls:
                        try:
                            cr = await asyncio.wait_for(
                                crawler.arun(url=u, config=run_config),
                                timeout=self.timeout_seconds,
                            )
                            crawl_results_list.append(cr)
                        except Exception as e:
                            crawl_results_list.append(_error_crawl_result(u, e))
        except Exception as e:
            raise ScrapeError(f"crawl4ai batch scrape crashed: {e}", error_type="scrape_failed")

        for url, crawl_result in zip(urls, crawl_results_list):
            results.append(_crawl_result_to_scrape_result(url, crawl_result))
        return results


def _classify_scrape_error(message: str) -> str:
    """Map a Crawl4AI error message to a short error code."""
    m = (message or "").lower()
    if "paywall" in m or "subscriber" in m:
        return "paywalled"
    if "timeout" in m:
        return "timeout"
    if "forbidden" in m or "403" in m:
        return "blocked"
    if "not found" in m or "404" in m:
        return "not_found"
    return "scrape_failed"


def _error_crawl_result(url: str, exc: Exception) -> Any:
    """Build a minimal fake crawl result representing an error."""

    class _Fake:
        pass

    fake = _Fake()
    fake.success = False
    fake.error_message = str(exc)
    fake.markdown = ""
    fake.markdown_v2 = None
    fake.meta = {}
    fake.title = ""
    return fake


def _crawl_result_to_scrape_result(url: str, crawl_result: Any) -> ScrapeResult:
    """Convert a Crawl4AI result object into a ScrapeResult."""
    if not getattr(crawl_result, "success", False):
        error_message = getattr(crawl_result, "error_message", "unknown error") or "unknown error"
        return ScrapeResult(
            url=url,
            title="",
            markdown="",
            word_count=0,
            metadata={"error": _classify_scrape_error(error_message), "error_message": error_message},
        )
    markdown = (
        getattr(crawl_result, "markdown_v2", None)
        or getattr(crawl_result, "markdown", None)
        or ""
    )
    if hasattr(markdown, "raw_markdown"):
        markdown = markdown.raw_markdown or ""
    if not isinstance(markdown, str):
        markdown = str(markdown) if markdown is not None else ""
    title = ""
    meta_obj = getattr(crawl_result, "meta", None) or {}
    if isinstance(meta_obj, dict):
        title = meta_obj.get("title", "") or ""
    if not title:
        title = getattr(crawl_result, "title", "") or ""
    metadata: dict[str, Any] = {"provider": "crawl4ai"}
    if isinstance(meta_obj, dict):
        for k in ("description", "author", "keywords", "og:description"):
            if meta_obj.get(k):
                metadata[k] = meta_obj[k]
    return ScrapeResult(
        url=url,
        title=title,
        markdown=markdown,
        word_count=len(markdown.split()) if markdown else 0,
        metadata=metadata,
    )
