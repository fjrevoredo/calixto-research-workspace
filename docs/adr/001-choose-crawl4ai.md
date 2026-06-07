# ADR 001: Choose Crawl4AI as the Web Scraping Backend

## Status

Accepted. 2026-06-06.

## Context

Calixto Research Workspace needs to turn arbitrary web pages into clean, LLM-friendly markdown. This is a core dependency of the research workflow: every web source in a workspace is the output of a scrape call.

We evaluated four candidates for this role:

1. **Scrapy**: Mature Python scraping framework. Excellent for large crawl jobs, but its output is raw HTML or custom item pipelines. It does not produce LLM-friendly markdown out of the box, and the user would have to build a markdown extraction layer on top. Overkill for a single-page-at-a-time research tool.

2. **BeautifulSoup**: Lightweight HTML parser. Easy to learn, very small footprint. But it does not handle JavaScript-rendered pages at all, and produces HTML, not markdown. The agent would have to do the HTML-to-markdown conversion and miss anything rendered by JavaScript, which is most modern web content.

3. **Playwright direct**: The browser automation library. Maximum flexibility: full JavaScript execution, full DOM access. But it returns raw HTML/DOM, and writing a clean markdown extractor on top is significant work. Also, it is lower-level than we need: we want a "URL to markdown" function, not "browser to DOM".

4. **Firecrawl**: Hosted service with a generous free tier. Excellent output quality, well-maintained, designed for exactly this use case. But it is a hosted service that requires an API key and an account, which violates our "zero API keys required" goal and our "no servers or daemons" non-negotiable.

5. **Crawl4AI** (chosen): Open-source Python library purpose-built for "URL to LLM-friendly markdown". Supports JavaScript rendering via Playwright, extracts metadata, handles many common edge cases (tables, code blocks, headings), and runs entirely locally. ~50MB for the library plus ~450MB for Playwright/Chromium.

## Decision

We use **Crawl4AI** as the default and currently only scrape provider. The contract is defined in `providers/scrape/base.py` so that the provider can be swapped if a better alternative emerges.

## Consequences

Positive:

- No API keys required, no accounts, no hosted dependency
- JavaScript-rendered pages are handled correctly
- LLM-friendly markdown output by default
- Self-hosted, fits our "no servers or daemons" non-negotiable (we still depend on Playwright, which is local)
- Active open-source project with good documentation

Negative:

- ~500MB total install (Crawl4AI + Playwright + Chromium). This is significant. We document it prominently in `setup.sh`, `setup.ps1`, `requirements.md`, and `PHILOSOPHY.md` per the Honest Complexity principle.
- Crawl4AI's API has been evolving; we may need to track breaking changes between versions
- On Windows, Playwright browser install can have quirks. `setup.ps1` includes fallback handling for this
- We are dependent on Chromium staying compatible with modern web content. If Chromium falls behind, our scraper falls behind

Operational:

- Setup time on a clean machine is dominated by the Chromium download
- The dependency budget table in `PHILOSOPHY.md` Principle 4 captures this

## Alternatives Considered (Summary)

| Alternative | Why not |
|---|---|
| Scrapy | Overkill, no LLM-friendly output by default |
| BeautifulSoup | No JS rendering, raw HTML output |
| Playwright direct | Lower level, more work for same outcome |
| Firecrawl | Hosted, requires API key, violates our non-negotiables |
| Crawl4AI (chosen) | Best fit for self-hosted, LLM-friendly, JS-aware scraping |

## References

- `providers/scrape/base.py`: ScrapeProvider interface
- `providers/scrape/crawl4ai_provider.py`: Implementation
- `PHILOSOPHY.md` Principle 4: Honest Complexity (dependency budget)
- `requirements.md` section 3.4: Dependencies
- `requirements.md` section 5.4: Scrape provider
