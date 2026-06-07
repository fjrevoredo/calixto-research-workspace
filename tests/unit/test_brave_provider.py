"""Unit tests for the Brave search provider's auth check and lazy loading.

Does not exercise the network. Verifies the constructor validation, the env
variable fallback, and the rate-limit usage tracker.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from providers.search.brave import BraveProvider  # noqa: E402


class TestBraveProvider:
    def test_requires_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("BRAVE_API_KEY", raising=False)
        with pytest.raises(ValueError, match="API key"):
            BraveProvider()

    def test_explicit_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("BRAVE_API_KEY", raising=False)
        p = BraveProvider(api_key="test-key")
        assert p.api_key == "test-key"
        assert p.name == "brave"

    def test_env_var_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BRAVE_API_KEY", "env-key-123")
        p = BraveProvider()
        assert p.api_key == "env-key-123"

    def test_default_rate_limit(self) -> None:
        p = BraveProvider(api_key="k")
        assert p.delay_seconds == 1.0
        assert p.max_retries == 3
        assert p.monthly_quota == 2000

    def test_custom_rate_limit(self) -> None:
        p = BraveProvider(api_key="k", delay_seconds=0.5, max_retries=5, monthly_quota=100)
        assert p.delay_seconds == 0.5
        assert p.max_retries == 5
        assert p.monthly_quota == 100

    def test_usage_starts_zero(self) -> None:
        p = BraveProvider(api_key="k")
        assert p.usage["calls_this_session"] == 0
        assert p.usage["quota_warned"] == 0

    def test_track_usage_increments(self) -> None:
        p = BraveProvider(api_key="k")
        p._track_usage()
        p._track_usage()
        p._track_usage()
        assert p.usage["calls_this_session"] == 3

    def test_warns_at_80_percent(self) -> None:
        p = BraveProvider(api_key="k", monthly_quota=10)
        # 8 calls = 80% of 10
        for _ in range(8):
            p._track_usage()
        assert p.usage["calls_this_session"] == 8
        assert p.usage["quota_warned"] == 1
        # Subsequent calls do not re-warn
        p._track_usage()
        assert p.usage["quota_warned"] == 1

    def test_validate_query(self) -> None:
        p = BraveProvider(api_key="k")
        with pytest.raises(ValueError):
            p.validate_query("")

    def test_lazy_requests_import(self) -> None:
        """The `requests` package should not be imported until first search call."""
        p = BraveProvider(api_key="k")
        assert p._requests is None
        # Don't actually call search(); just verify lazy init behavior
