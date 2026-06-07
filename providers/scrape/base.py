"""
scrape/base.py: Abstract ScrapeProvider interface.

This module defines the contract that all scrape providers must implement. A
ScrapeProvider turns a URL into clean markdown suitable for LLM consumption. It
does NOT search for URLs. Search is a separate layer (see
`providers/search/base.py`).

## Why a separate ScrapeProvider?

Separation lets us swap the entire scraping pipeline (e.g., Crawl4AI today,
something cheaper tomorrow) without touching search. It also keeps each layer
testable in isolation. See PHILOSOPHY.md Principle 3: Modular and Configurable.

## How to implement a new scrape provider

1. Subclass `ScrapeProvider` in `providers/scrape/<your_provider>.py`.
2. Implement the `scrape()` method to return a `ScrapeResult`.
3. Handle timeouts, paywalls, JS-rendering, and other failure modes internally
   and surface them via the result's `metadata` field or by raising `ScrapeError`.
4. Update `scripts/search_web.py` to use the new provider when selected.

## Example

    from providers.scrape.base import ScrapeProvider, ScrapeResult

    class MyProvider(ScrapeProvider):
        def scrape(self, url: str) -> ScrapeResult:
            markdown, meta = call_my_scraper(url)
            return ScrapeResult(
                url=url,
                title=meta.get("title", ""),
                markdown=markdown,
                word_count=len(markdown.split()),
                metadata=meta,
            )

## Failure modes (per requirements.md section 12.2)

- Paywall / blocked: set `metadata["error"] = "paywalled"`, return partial content
  if any.
- Timeout: raise `ScrapeError("timeout", retry_after=0)`.
- Crash: let the exception propagate; the calling script logs and continues.
- Non-HTML content: set `metadata["error"] = "unsupported_content_type"`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScrapeResult:
    """A scraped page returned by a ScrapeProvider.

    Attributes:
        url: The URL that was scraped. Echoed back so callers can correlate
            results with the original request.
        title: The page title extracted during scraping. May be empty.
        markdown: Clean, LLM-friendly markdown content. May be empty if the page
            could not be scraped (check `metadata` for the reason).
        word_count: Number of whitespace-separated tokens in `markdown`. Always
            populated, even when zero.
        metadata: Provider-specific extra data: publication date, author, error
            reason, etc. The convention is `metadata["error"]` for failure
            reasons ("paywalled", "timeout", "unsupported_content_type").
    """

    url: str
    title: str = ""
    markdown: str = ""
    word_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.word_count < 0:
            raise ValueError("word_count must be non-negative")
        # Keep word_count consistent with the actual markdown.
        if self.markdown and self.word_count == 0:
            self.word_count = len(self.markdown.split())


class ScrapeError(Exception):
    """Base exception for scrape provider failures.

    Attributes:
        error_type: Short machine-readable error code (e.g., "timeout",
            "paywalled", "unsupported_content_type").
        retry_after: Optional seconds hint for the caller. 0 means "no point
            retrying"; None means "unspecified".
    """

    def __init__(self, message: str, error_type: str = "scrape_failed", retry_after: int | None = None) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.retry_after = retry_after


class ScrapeProvider(ABC):
    """Abstract base class for all scrape providers.

    Implementations are responsible for:
    - Fetching the URL
    - Converting HTML/JS into clean markdown
    - Extracting page metadata (title, date, author)
    - Handling timeouts, paywalls, and other failure modes
    - Returning a normalized ScrapeResult
    """

    name: str = "base"
    timeout_seconds: int = 30

    @abstractmethod
    def scrape(self, url: str) -> ScrapeResult:
        """Scrape `url` and return its content as markdown.

        Args:
            url: The URL to scrape. Must be a valid http(s) URL.

        Returns:
            A `ScrapeResult` with markdown, title, word_count, and metadata.

        Raises:
            ValueError: If url is empty or malformed.
            ScrapeError: For recoverable provider failures.
        """
        raise NotImplementedError

    def validate_url(self, url: str) -> None:
        """Helper: raise ValueError if the URL is unusable."""
        if not url or not url.strip():
            raise ValueError("url must be a non-empty string")
        if not (url.startswith("http://") or url.startswith("https://")):
            raise ValueError(f"url must start with http:// or https://, got: {url}")
