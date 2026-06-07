"""Unit tests for the search and scrape provider interfaces.

These tests cover the abstract base classes: SearchProvider / SearchResult /
SearchError and ScrapeProvider / ScrapeResult / ScrapeError. They verify
contract behaviors (validation, dataclass post-checks) and that concrete
implementations adhere to the interface.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make repo root and providers importable
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from providers.scrape.base import (  # noqa: E402
    ScrapeError,
    ScrapeProvider,
    ScrapeResult,
)
from providers.search.base import (  # noqa: E402
    SearchError,
    SearchProvider,
    SearchResult,
)


# --- SearchResult dataclass ---


class TestSearchResult:
    def test_minimal(self) -> None:
        r = SearchResult(url="https://x.com")
        assert r.url == "https://x.com"
        assert r.title == ""
        assert r.snippet == ""
        assert r.score == 0.0
        assert r.metadata == {}

    def test_full(self) -> None:
        r = SearchResult(
            url="https://x.com",
            title="Title",
            snippet="snippet",
            score=0.5,
            metadata={"key": "value"},
        )
        assert r.url == "https://x.com"
        assert r.title == "Title"
        assert r.score == 0.5

    def test_empty_url_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            SearchResult(url="")


# --- ScrapeResult dataclass ---


class TestScrapeResult:
    def test_minimal(self) -> None:
        r = ScrapeResult(url="https://x.com")
        assert r.url == "https://x.com"
        assert r.title == ""
        assert r.markdown == ""
        assert r.word_count == 0
        assert r.metadata == {}

    def test_word_count_auto_computed(self) -> None:
        r = ScrapeResult(url="https://x.com", markdown="one two three four")
        assert r.word_count == 4

    def test_explicit_word_count_respected(self) -> None:
        r = ScrapeResult(url="https://x.com", markdown="one two", word_count=999)
        # The post-init guard only re-computes if markdown is non-empty and word_count is 0
        assert r.word_count == 999

    def test_negative_word_count_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            ScrapeResult(url="https://x.com", word_count=-1)


# --- SearchError ---


class TestSearchError:
    def test_basic(self) -> None:
        e = SearchError("boom")
        assert str(e) == "boom"
        assert e.retry_after is None

    def test_with_retry_after(self) -> None:
        e = SearchError("rate limited", retry_after=60)
        assert e.retry_after == 60


# --- ScrapeError ---


class TestScrapeError:
    def test_defaults(self) -> None:
        e = ScrapeError("boom")
        assert e.error_type == "scrape_failed"
        assert e.retry_after is None

    def test_custom_type(self) -> None:
        e = ScrapeError("timed out", error_type="timeout", retry_after=30)
        assert e.error_type == "timeout"
        assert e.retry_after == 30


# --- SearchProvider abstract class ---


class TestSearchProviderContract:
    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            SearchProvider()  # type: ignore[abstract]

    def test_validate_query_rejects_empty(self) -> None:
        class P(SearchProvider):
            name = "p"

            def search(self, query: str, max_results: int = 10):
                return []

        p = P()
        with pytest.raises(ValueError, match="non-empty"):
            p.validate_query("")

    def test_validate_query_rejects_whitespace(self) -> None:
        class P(SearchProvider):
            name = "p"

            def search(self, query: str, max_results: int = 10):
                return []

        p = P()
        with pytest.raises(ValueError, match="non-empty"):
            p.validate_query("   \t  ")

    def test_concrete_subclass_works(self) -> None:
        class P(SearchProvider):
            name = "stub"

            def search(self, query: str, max_results: int = 10):
                self.validate_query(query)
                return [SearchResult(url="https://x.com")]

        results = P().search("hello")
        assert len(results) == 1
        assert results[0].url == "https://x.com"


# --- ScrapeProvider abstract class ---


class TestScrapeProviderContract:
    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            ScrapeProvider()  # type: ignore[abstract]

    def test_validate_url_rejects_empty(self) -> None:
        class S(ScrapeProvider):
            name = "s"

            def scrape(self, url: str):
                return ScrapeResult(url=url)

        s = S()
        with pytest.raises(ValueError, match="non-empty"):
            s.validate_url("")

    def test_validate_url_rejects_non_http(self) -> None:
        class S(ScrapeProvider):
            name = "s"

            def scrape(self, url: str):
                return ScrapeResult(url=url)

        s = S()
        with pytest.raises(ValueError, match="http"):
            s.validate_url("ftp://example.com")

    def test_validate_url_accepts_http_and_https(self) -> None:
        class S(ScrapeProvider):
            name = "s"

            def scrape(self, url: str):
                return ScrapeResult(url=url)

        s = S()
        s.validate_url("http://x.com")  # should not raise
        s.validate_url("https://x.com")  # should not raise

    def test_concrete_subclass_works(self) -> None:
        class S(ScrapeProvider):
            name = "stub"
            timeout_seconds = 30

            def scrape(self, url: str):
                self.validate_url(url)
                return ScrapeResult(url=url, markdown="hello world", title="Hi")

        result = S().scrape("https://x.com")
        assert result.markdown == "hello world"
        assert result.word_count == 2
