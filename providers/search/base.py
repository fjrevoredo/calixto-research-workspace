"""
search/base.py: Abstract SearchProvider interface.

This module defines the contract that all search providers must implement. The contract
is intentionally minimal: a search provider turns a query into a list of URLs. It
does NOT scrape or fetch content. Scraping is a separate layer (see
`providers/scrape/base.py`).

## Why a separate SearchProvider?

We separate search from scrape so that each layer is independently testable and
replaceable. A user can swap DuckDuckGo for Brave or Tavily without changing the
scraper, and vice versa. See PHILOSOPHY.md Principle 3: Modular and Configurable.

## How to implement a new search provider

1. Subclass `SearchProvider` in `providers/search/<your_provider>.py`.
2. Implement the `search()` method to return a list of `SearchResult` objects.
3. Handle rate limiting, retries, and provider-specific error semantics inside
   your implementation. The contract does not require this, but no silent failures.
4. Register the provider in `scripts/search_web.py` (look for the
   `--search-provider` argument dispatcher).

## Example

    from providers.search.base import SearchProvider, SearchResult

    class MyProvider(SearchProvider):
        def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
            results = call_my_search_api(query, max_results)
            return [
                SearchResult(url=r["url"], title=r["title"], snippet=r["snippet"], score=r["score"])
                for r in results
            ]

## Error handling

Providers should raise a subclass of `SearchError` for recoverable failures and
let unexpected exceptions propagate. Callers (the scripts) translate these into
the structured error output format described in requirements.md section 12.4.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SearchResult:
    """A single search result returned by a SearchProvider.

    Attributes:
        url: The canonical URL of the result. Must be non-empty.
        title: Human-readable title of the page. May be empty if the provider did
            not return one.
        snippet: Short text excerpt shown by the search provider. May be empty.
        score: Relevance or ranking score if the provider returns one. Higher is
            more relevant. Use 0.0 when not available.
        metadata: Provider-specific extra data (publication date, author, etc.).
            Not interpreted by the search layer.
    """

    url: str
    title: str = ""
    snippet: str = ""
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.url:
            raise ValueError("SearchResult.url must be a non-empty string")


class SearchError(Exception):
    """Base exception for search provider failures.

    Subclass this for specific failure modes (rate limited, network error, invalid
    API key, etc.). The HTTP-ish 'retry_after' attribute is honored by the search
    scripts to surface a structured retry hint to the agent.
    """

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class SearchProvider(ABC):
    """Abstract base class for all search providers.

    Implementations are responsible for:
    - Translating the query into a provider-specific request
    - Rate limiting (per the rate limit table in requirements.md section 15)
    - Retries with exponential backoff where appropriate
    - Returning SearchResult objects normalized to the contract
    """

    name: str = "base"

    @abstractmethod
    def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        """Search for `query` and return up to `max_results` results.

        Args:
            query: The search query string. Must be non-empty.
            max_results: Upper bound on the number of results to return. Providers
                may return fewer if the underlying API caps results.

        Returns:
            A list of `SearchResult` objects. Empty list if nothing was found.
            Order is implementation-defined but should be relevance-descending
            when a score is available.

        Raises:
            ValueError: If query is empty.
            SearchError: For recoverable provider failures.
        """
        raise NotImplementedError

    def validate_query(self, query: str) -> None:
        """Helper: raise ValueError if the query is unusable."""
        if not query or not query.strip():
            raise ValueError("query must be a non-empty string")
