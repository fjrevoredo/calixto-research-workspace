---
name: integrate-tool
description: Teaches an agent how to add a new search provider, scrape backend, or data source to Calixto Research Workspace. Use when the user asks to add support for Brave, Tavily, Google Scholar, Semantic Scholar, PubMed, GitHub, a custom API, or any new data source. Covers the SearchProvider and ScrapeProvider interfaces, registration in the script dispatchers, optional dependency groups, testing, and documentation. Also useful for adding new CLI scripts.
license: MIT
compatibility: Requires Python 3.11+, Calixto Research Workspace installed, familiarity with the providers/ and scripts/ directories in the Calixto repo.
metadata:
  category: meta
  mode: developer
  version: "0.1.0"
---

# Integrate a New Tool or Provider (Meta-Skill)

Teaches an agent how to add a new search provider, scrape backend, data source, or CLI script to Calixto.

## When to Use

- The user asks to add support for a new search provider (Brave, Tavily, Google Scholar, Semantic Scholar, etc.)
- The user wants to integrate a new scrape backend
- The user wants to add a new data source (PubMed, GitHub, Stack Overflow, etc.)
- The user wants to write a new CLI script in `scripts/`

Do NOT use this skill for one-off scripts outside the toolkit, or for adding new skills (use `create-skill` instead).

## Goal

Add a new tool or provider to Calixto by:

1. Implementing the appropriate interface (`SearchProvider`, `ScrapeProvider`, or a new one)
2. Registering the new tool in the relevant script dispatcher
3. Documenting the new tool so future agents can use it
4. Testing the new tool against the golden dataset

The goal is that an agent reading only the existing docs (AGENTS.md, the provider interface, this skill) can add a new provider without asking the user for clarification.

## Provider Interface Contracts

### SearchProvider

Located at `providers/search/base.py`.

```python
from providers.search.base import SearchProvider, SearchResult, SearchError

class MyProvider(SearchProvider):
    name = "my_provider"

    def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        self.validate_query(query)
        # ... call the underlying API ...
        return [
            SearchResult(url=..., title=..., snippet=..., score=..., metadata={...})
            for r in raw_results
        ]
```

Required:

- `name` class attribute (lowercase, unique)
- `search()` method returning `list[SearchResult]`
- Rate limiting with backoff and retries
- Raise `SearchError` for recoverable failures
- Let unexpected exceptions propagate

### ScrapeProvider

Located at `providers/scrape/base.py`.

```python
from providers.scrape.base import ScrapeProvider, ScrapeResult, ScrapeError

class MyScraper(ScrapeProvider):
    name = "my_scraper"
    timeout_seconds = 30

    def scrape(self, url: str) -> ScrapeResult:
        self.validate_url(url)
        # ... fetch and convert ...
        return ScrapeResult(
            url=url, title=..., markdown=..., word_count=..., metadata={...}
        )
```

Failure handling (per requirements.md section 12.2):

- Paywall: set `metadata["error"] = "paywalled"`, return partial content if any
- Timeout: raise `ScrapeError("timeout")`
- Non-HTML content: set `metadata["error"] = "unsupported_content_type"`
- Crash: let the exception propagate

## Step-by-Step: Adding a New Search Provider

### 1. Create the provider file

`providers/search/my_provider.py`:

```python
"""
my_provider.py: <Description>

Usage:
    from providers.search.my_provider import MyProvider
    p = MyProvider(api_key="...")
    results = p.search("query", max_results=10)

Rate limiting:
    - <Describe how rate limits are handled>

Error handling:
    - <Describe what raises SearchError>
"""

from __future__ import annotations

import logging
import time

from .base import SearchError, SearchProvider, SearchResult

log = logging.getLogger(__name__)


class MyProvider(SearchProvider):
    name = "my_provider"

    def __init__(self, api_key: str, delay_seconds: float = 1.0, max_retries: int = 3):
        if not api_key:
            raise ValueError("api_key is required")
        self.api_key = api_key
        self.delay_seconds = delay_seconds
        self.max_retries = max_retries
        self._last_request_time = 0.0

    def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        self.validate_query(query)
        if max_results <= 0:
            return []

        elapsed = time.monotonic() - self._last_request_time
        if self._last_request_time > 0 and elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)

        for attempt in range(1, self.max_retries + 1):
            try:
                response = call_my_api(self.api_key, query, max_results)
                self._last_request_time = time.monotonic()
                return [
                    SearchResult(
                        url=r["url"],
                        title=r.get("title", ""),
                        snippet=r.get("snippet", ""),
                        score=r.get("score", 0.0),
                    )
                    for r in response.get("results", [])
                ]
            except Exception as e:
                if "rate limit" in str(e).lower() and attempt < self.max_retries:
                    backoff = 2 ** attempt
                    log.warning("rate limited, sleeping %ds: %s", backoff, e)
                    time.sleep(backoff)
                    continue
                raise SearchError(f"my_provider failed: {e}")

        return []


def call_my_api(api_key: str, query: str, max_results: int) -> dict:
    """Wrapper around the actual API call. Replace with real implementation."""
    return {"results": []}
```

### 2. Register the provider in the script dispatcher

Edit `scripts/search_web.py`:

```python
def get_search_provider(name: str, **kwargs: Any) -> Any:
    name = name.lower()
    if name == "duckduckgo":
        from providers.search.duckduckgo import DuckDuckGoProvider
        return DuckDuckGoProvider(**kwargs)
    if name == "brave":
        from providers.search.brave import BraveProvider
        return BraveProvider(**kwargs)
    if name == "my_provider":
        from providers.search.my_provider import MyProvider
        api_key = kwargs.pop("api_key", None) or os.environ.get("MY_PROVIDER_API_KEY")
        return MyProvider(api_key=api_key, **kwargs)
    raise ValueError(f"unknown search provider: {name}")
```

### 3. Add optional dependency

If the provider requires a Python package, add it to `pyproject.toml`:

```toml
[project.optional-dependencies]
my_provider = ["my-provider-sdk>=1.0"]
```

Users opt in with: `pip install 'calixto-research-workspace[my_provider]'` or `uv sync --extra my_provider`.

### 4. Document

- Add a module docstring with usage example
- Add a row to the "Optional Search Providers" table in `requirements.md` section 5.3
- Update `AGENTS.md` if the provider ships by default

### 5. Test

```bash
# Smoke test
python -c "from providers.search.my_provider import MyProvider; p = MyProvider(api_key='test'); print('importable')"

# End-to-end test
python scripts/search_web.py "test query" --workspace workspaces/test --max-results 3 --search-provider my_provider --no-scrape
```

## Step-by-Step: Adding a New Scrape Provider

Same pattern as search, but the file goes in `providers/scrape/`, the interface is `ScrapeProvider`, and you register in `scripts/search_web.py`'s `get_scrape_provider` function.

## Step-by-Step: Adding a New Data Source

A "data source" is anything beyond web search and arXiv (e.g., Semantic Scholar, PubMed, GitHub). It is essentially a specialized search provider with a custom data model.

Approach:

1. Create `providers/search/semantic_scholar.py` (etc.)
2. Implement the `SearchProvider` interface, mapping the source's data model into `SearchResult`
3. Save results to `sources/code/` or `sources/papers/` depending on the type
4. Modify `scripts/search_web.py` (or add a new script) to dispatch to the new provider
5. Add a flag like `--source-type` to the script

Alternatively, create a new top-level script `scripts/search_semantic_scholar.py` if the data source has unique behavior.

## Step-by-Step: Adding a New CLI Script

When you need a new script that is not just "another provider":

1. Create `scripts/<script_name>.py`
2. Add `sys.path.insert(0, str(Path(__file__).resolve().parent))` at the top so `_common` imports work
3. Use `_common.emit_ok()`, `_common.emit_error()`, `_common.emit_partial()` for structured output
4. Use `_common.load_workspace_config()`, `save_workspace_config()`, `load_source_index()`, `save_source_index()` for workspace I/O
5. Register a console entry point in `pyproject.toml` under `[project.scripts]`
6. Document the script in `AGENTS.md` "Scripts Reference"
7. Add unit tests under `tests/`

## Testing New Providers

### Unit test (recommended)

```python
# tests/test_my_provider.py
from providers.search.my_provider import MyProvider

def test_search_returns_results():
    p = MyProvider(api_key="test-key")
    results = p.search("python", max_results=3)
    assert len(results) <= 3
    assert all(r.url for r in results)
```

### Integration test

```bash
# Fresh workspace
python scripts/init_workspace.py test-my-provider

# Run the search
python scripts/search_web.py "test query" --workspace workspaces/test-my-provider --max-results 3 --search-provider my_provider --no-scrape

# Verify
python scripts/workspace_info.py show test-my-provider
python scripts/workspace_info.py audit test-my-provider
```

### Golden dataset test

Add a new search to `tests/golden/config.json` and verify the run is reproducible.

## Updating Documentation

After adding a provider:

1. Update `AGENTS.md` "Scripts Reference" if applicable
2. Add a row to `requirements.md` section 5.3 (search providers) or section 5.4 (scrape providers)
3. Create or update `providers/<type>/README.md` with the new provider's usage
4. If the provider required a non-trivial design decision, create an ADR in `docs/adr/`
5. Add an entry to `docs/initial-implementation-plan-decision-log.md` for any non-obvious choice

## Reference Implementations

Use the existing providers as references:

- `providers/search/duckduckgo.py`: free, no API key, simple rate limiting
- `providers/search/brave.py`: paid, requires API key, more sophisticated rate limit tracking
- `providers/scrape/crawl4ai_provider.py`: the only scrape provider, async wrapped in sync

## Common Pitfalls

- **Forgetting to register the provider**: a new provider is invisible until it appears in the script's dispatcher
- **Hardcoding the API key**: read from env or pass as a constructor arg; never commit
- **Not handling rate limits**: every external API has them; check the API docs and bake the limits into the provider
- **Returning raw dicts instead of SearchResult**: the script layer depends on the dataclass
- **Inconsistent error types**: always raise `SearchError` / `ScrapeError`, not generic `Exception`
- **Skipping tests**: even a 5-line smoke test catches the obvious bugs

## See Also

- `providers/search/base.py`: SearchProvider interface
- `providers/scrape/base.py`: ScrapeProvider interface
- `skills/create-skill/SKILL.md`: how to add a new skill
- `requirements.md` section 5.5: Adding New Providers
- `docs/adr/001-choose-crawl4ai.md`: example ADR
