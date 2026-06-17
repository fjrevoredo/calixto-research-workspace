# Bibliography

All sources with quality ratings. Mirror the structure of `sources/index.json` with human-readable annotations.
Populate this before handoff so a future agent or reviewer can see which
sources were kept, how strong they are, and why they matter.

## Format

```markdown
- **src_NNN** - [Article Title](https://example.com/article) - Tier: authoritative - Quality: high - Conflict: none - Notes: peer-reviewed source
- **src_MMM** - [Another Article](https://example.com/another) - Tier: affiliate_or_vendor - Quality: medium - Conflict: needs corroboration - Notes: blog post, useful for context
```

## Quality Criteria

- high: authoritative, primary source, recent, peer-reviewed (if applicable)
- medium: reputable secondary source, useful but not definitive
- low: useful for context only, opinion piece, marketing content, or undated

## Tier Guidance

- `authoritative`: public-health, regulatory, or primary institutional source
- `scholarly`: journal or preprint record
- `established_media`: major newsroom or outlet
- `commercial`: company or product page
- `affiliate_or_vendor`: sales, supplement, affiliate, or vendor-led page
- `low_signal`: scrape failure, thin content, or otherwise weak evidence
- `unknown`: no strong deterministic signal
