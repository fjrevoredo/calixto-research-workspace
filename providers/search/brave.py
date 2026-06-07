"""
brave.py: Brave Search implementation of the SearchProvider interface.

Paid, requires an API key. Better quality than DuckDuckGo for many queries.

Usage:
    from providers.search.brave import BraveProvider
    p = BraveProvider(api_key="BSA...")
    results = p.search("python asyncio", max_results=10)

Environment:
    Set BRAVE_API_KEY to avoid passing the key explicitly.

Rate limiting:
    - 1 second delay between requests (Brave's free tier limit is generous)
    - 2000 requests/month free, 1 request/second
    - Track usage in self.usage["calls_this_month"] and warn at 80% of 2000
    - Exponential backoff on 429 (rate limited) responses, max 3 retries

Error handling:
    - 401/403: raise SearchError with error_type="auth_failed"
    - 429: retry with backoff, then raise SearchError("rate_limited", retry_after=...)
    - Other HTTP errors: raise SearchError
    - Network errors: raise SearchError("network_error")
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from .base import SearchError, SearchProvider, SearchResult

log = logging.getLogger(__name__)

DEFAULT_DELAY_SECONDS = 1.0
DEFAULT_MAX_RETRIES = 3
BRAVE_FREE_TIER_MONTHLY = 2000
WARNING_THRESHOLD = 0.8

API_URL = "https://api.search.brave.com/res/v1/web/search"


class BraveProvider(SearchProvider):
    """Search the web via the Brave Search API.

    Requires an API key. Get one at https://brave.com/search/api/.

    Args:
        api_key: Your Brave Search API subscription token. If omitted, reads
            from the BRAVE_API_KEY environment variable.
        delay_seconds: Minimum delay between API calls.
        max_retries: Maximum number of retries on transient failures.
        timeout: HTTP request timeout in seconds.
        monthly_quota: Soft quota for usage tracking (default: 2000 for free tier).
    """

    name = "brave"

    def __init__(
        self,
        api_key: str | None = None,
        delay_seconds: float = DEFAULT_DELAY_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout: float = 30.0,
        monthly_quota: int = BRAVE_FREE_TIER_MONTHLY,
    ) -> None:
        self.api_key = api_key or os.environ.get("BRAVE_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "Brave API key required. Pass api_key=... or set BRAVE_API_KEY env var."
            )
        self.delay_seconds = delay_seconds
        self.max_retries = max_retries
        self.timeout = timeout
        self.monthly_quota = monthly_quota
        self._last_request_time: float = 0.0
        self.usage: dict[str, int] = {"calls_this_session": 0, "quota_warned": 0}
        # Lazy import requests
        self._requests: Any = None

    def _get_requests(self) -> Any:
        if self._requests is None:
            try:
                import requests  # type: ignore
            except ImportError as e:
                raise SearchError(
                    f"requests package not installed. Run: pip install requests. ({e})"
                )
            self._requests = requests
        return self._requests

    def _respect_rate_limit(self) -> None:
        if self._last_request_time <= 0:
            return
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)

    def _track_usage(self) -> None:
        self.usage["calls_this_session"] += 1
        # Warn at 80% of quota
        if self.usage["calls_this_session"] >= self.monthly_quota * WARNING_THRESHOLD:
            if self.usage["quota_warned"] == 0:
                log.warning(
                    "Brave API usage at %d/%d (80%% of free tier). Consider upgrading or switching providers.",
                    self.usage["calls_this_session"],
                    self.monthly_quota,
                )
                self.usage["quota_warned"] = 1

    def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        self.validate_query(query)
        if max_results <= 0:
            return []

        requests = self._get_requests()
        self._respect_rate_limit()

        params = {"q": query, "count": min(max_results, 20)}  # Brave caps count at 20
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.api_key,
        }

        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.get(
                    API_URL,
                    params=params,
                    headers=headers,
                    timeout=self.timeout,
                )
                self._last_request_time = time.monotonic()
                self._track_usage()

                if response.status_code == 200:
                    data = response.json()
                    raw = data.get("web", {}).get("results", [])
                    return [
                        SearchResult(
                            url=r.get("url", ""),
                            title=r.get("title", ""),
                            snippet=r.get("description", ""),
                            score=0.0,
                            metadata={
                                "brave_age": r.get("age"),
                                "brave_profile": (r.get("profile") or {}).get("name", ""),
                            },
                        )
                        for r in raw
                        if r.get("url")
                    ]
                if response.status_code in (401, 403):
                    raise SearchError(
                        f"Brave API auth failed (HTTP {response.status_code}): {response.text[:200]}",
                        retry_after=None,
                    )
                if response.status_code == 429:
                    if attempt < self.max_retries:
                        backoff = 2 ** attempt
                        log.warning("Brave 429 on attempt %d, sleeping %ds", attempt, backoff)
                        time.sleep(backoff)
                        continue
                    raise SearchError(
                        "Brave rate limit hit after retries (HTTP 429)",
                        retry_after=60,
                    )
                # Other HTTP errors
                raise SearchError(
                    f"Brave API HTTP {response.status_code}: {response.text[:200]}"
                )
            except SearchError:
                raise
            except Exception as e:
                last_exc = e
                if attempt < self.max_retries:
                    backoff = 2 ** attempt
                    log.warning("Brave error on attempt %d, sleeping %ds: %s", attempt, backoff, e)
                    time.sleep(backoff)
                    continue
                raise SearchError(f"Brave search failed: {e}")

        if last_exc:
            raise SearchError(f"Brave search failed: {last_exc}")
        return []
