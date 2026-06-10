"""
duckduckgo.py: DuckDuckGo implementation of the SearchProvider interface.

Free, no API key required. Default search provider.

Usage:
    from providers.search.duckduckgo import DuckDuckGoProvider
    p = DuckDuckGoProvider()
    results = p.search("python asyncio", max_results=10)

Rate limiting:
    - 3 second delay between consecutive search() calls (per requirements.md 15)
    - Exponential backoff on 429 / rate limit errors, max 3 retries
    - On persistent failure, raises SearchError with retry_after hint

Error handling:
    - Empty result list is returned (not an error) when DuckDuckGo has no hits
    - Network errors raise SearchError with error_type="network_error"
    - Rate limit errors raise SearchError with error_type="rate_limited"

Note: The underlying package was renamed from `duckduckgo-search` to `ddgs` in
2025. We import from `ddgs` (preferred) and fall back to `duckduckgo_search` for
older installs. The user-visible behavior is identical.
"""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlparse

from .base import SearchError, SearchProvider, SearchResult

log = logging.getLogger(__name__)

# Default rate limit delay between requests (seconds)
DEFAULT_DELAY_SECONDS = 3.0
# Maximum number of retries on transient failures
DEFAULT_MAX_RETRIES = 3
# Backoff base in seconds (2 -> 4 -> 8 between attempts)
BACKOFF_BASE_SECONDS = 2.0


def _is_supported_result_url(url: str) -> bool:
    """Return True when a DDG result URL is directly scrapeable."""
    if not url or not url.startswith(("http://", "https://")):
        return False
    parsed = urlparse(url)
    if not parsed.netloc:
        return False
    if parsed.path == "/clev" and "startpageresultclick" in parsed.query.lower():
        return False
    return True


class DuckDuckGoProvider(SearchProvider):
    """Search the web via DuckDuckGo, no API key required.

    Uses the `ddgs` Python package (renamed from `duckduckgo-search`). The
    package is imported lazily so the import is fast when this provider is
    not used.
    """

    name = "duckduckgo"

    def __init__(
        self,
        delay_seconds: float = DEFAULT_DELAY_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout: float = 30.0,
    ) -> None:
        self.delay_seconds = delay_seconds
        self.max_retries = max_retries
        self.timeout = timeout
        self._last_request_time: float = 0.0
        # Lazy import: only load ddgs when search() is called
        self._ddgs = None

    def _get_ddgs(self) -> Any:
        if self._ddgs is not None:
            return self._ddgs
        # Prefer the new name; fall back to the old one for legacy installs
        DDGS = None
        import_error: Exception | None = None
        try:
            from ddgs import DDGS as _DDGS  # type: ignore
            DDGS = _DDGS
        except ImportError as e:
            import_error = e
            try:
                from duckduckgo_search import DDGS as _DDGS  # type: ignore
                DDGS = _DDGS
            except ImportError as e2:
                raise SearchError(
                    f"ddgs (or duckduckgo-search) package not installed. Run: pip install ddgs. "
                    f"({import_error}; {e2})"
                )
        self._ddgs = DDGS(timeout=self.timeout)
        return self._ddgs

    def _respect_rate_limit(self) -> None:
        """Sleep if needed to honor the configured delay between requests."""
        if self._last_request_time <= 0:
            return
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)

    def _is_rate_limit_error(self, exc: Exception) -> bool:
        """Return True if the exception looks like a rate limit or transient block."""
        msg = str(exc).lower()
        indicators = [
            "ratelimit",
            "rate limit",
            "429",
            "too many requests",
            "blocked",
            "captcha",
            "please try again",
        ]
        return any(ind in msg for ind in indicators)

    def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        """Search DuckDuckGo for `query` and return up to `max_results` results.

        Args:
            query: The search query string. Must be non-empty.
            max_results: Upper bound on the number of results. DuckDuckGo may
                return fewer.

        Returns:
            A list of SearchResult objects. Empty list if nothing was found.

        Raises:
            ValueError: If query is empty.
            SearchError: For recoverable provider failures.
        """
        self.validate_query(query)
        if max_results <= 0:
            return []

        ddgs = self._get_ddgs()
        self._respect_rate_limit()

        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                # duckduckgo_search returns an iterator of dicts
                raw_results = list(ddgs.text(query, max_results=max_results))
                self._last_request_time = time.monotonic()
                results: list[SearchResult] = []
                for r in raw_results:
                    url = r.get("href") or r.get("url") or ""
                    if not _is_supported_result_url(url):
                        continue
                    title = r.get("title") or ""
                    snippet = r.get("body") or r.get("snippet") or ""
                    results.append(
                        SearchResult(
                            url=url,
                            title=title,
                            snippet=snippet,
                            score=0.0,
                            metadata={"duckduckgo_rank": len(results) + 1},
                        )
                    )
                return results
            except Exception as e:
                last_exc = e
                if self._is_rate_limit_error(e) and attempt < self.max_retries:
                    backoff = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                    log.warning(
                        "DuckDuckGo rate limit on attempt %d/%d, sleeping %.1fs: %s",
                        attempt,
                        self.max_retries,
                        backoff,
                        e,
                    )
                    time.sleep(backoff)
                    continue
                # Non-rate-limit error or retries exhausted
                if self._is_rate_limit_error(e):
                    raise SearchError(
                        f"DuckDuckGo rate limit hit after {self.max_retries} retries: {e}",
                        retry_after=int(self.delay_seconds * self.max_retries),
                    )
                raise SearchError(f"DuckDuckGo search failed: {e}")

        # Should not reach here, but for type safety
        if last_exc:
            raise SearchError(f"DuckDuckGo search failed: {last_exc}")
        return []
