"""
_common.py: Shared utilities used by all Calixto CLI scripts.

This module provides:
- `emit_ok`: print a structured success JSON object to stdout
- `emit_error`: print a structured error JSON object to stderr, exit 1
- `emit_partial`: print a structured partial-success JSON object to stdout
- `load_workspace_config`: load and validate a workspace's config.json
- `save_workspace_config`: atomic write of a workspace's config.json
- `load_source_index`: load and validate a workspace's sources/index.json
- `save_source_index`: atomic write of a workspace's sources/index.json
- `normalize_url`: strip protocol, www, trailing slashes, tracking params for dedup
- `parse_frontmatter`: extract YAML frontmatter from a markdown file
- `slugify`: convert a string to a valid workspace name slug

All scripts follow the same I/O contract: structured JSON to stdout on success,
structured JSON to stderr on failure, exit code 0 on success, 1 on error.

See requirements.md section 12.4 for the error output format.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import yaml


# ---------------------------------------------------------------------------
# Structured output helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return current UTC time in ISO 8601 format with Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def emit_ok(payload: dict[str, Any]) -> None:
    """Print a structured success JSON object to stdout and exit 0."""
    out = {"status": "ok", **payload}
    print(json.dumps(out, indent=2, ensure_ascii=False))


def emit_partial(payload: dict[str, Any]) -> None:
    """Print a structured partial-success JSON object to stdout and exit 0."""
    out = {"status": "partial", **payload}
    print(json.dumps(out, indent=2, ensure_ascii=False))


def emit_error(
    error_type: str,
    message: str,
    retry_after: int | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Print a structured error JSON object to stderr and exit 1."""
    out: dict[str, Any] = {
        "status": "error",
        "error": error_type,
        "message": message,
    }
    if retry_after is not None:
        out["retry_after"] = retry_after
    if extra:
        out.update(extra)
    print(json.dumps(out, indent=2, ensure_ascii=False), file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Workspace I/O
# ---------------------------------------------------------------------------


def workspace_path(workspace: str | Path) -> Path:
    """Resolve a workspace path string to an absolute Path.

    Accepts either an absolute path or a path relative to the current directory.
    Does not check existence; callers verify.
    """
    p = Path(workspace).expanduser()
    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()
    return p


def load_workspace_config(workspace: Path) -> dict[str, Any]:
    """Load and validate a workspace's config.json.

    Raises FileNotFoundError or json.JSONDecodeError on failure. Callers should
    catch and convert to structured errors.
    """
    config_path = workspace / "config.json"
    with config_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_workspace_config(workspace: Path, config: dict[str, Any]) -> None:
    """Atomically write a workspace's config.json.

    Atomic means: write to a temp file, then rename. A crash mid-write does not
    corrupt the existing config.json.
    """
    config["updated_at"] = _now_iso()
    config_path = workspace / "config.json"
    _atomic_write_json(config_path, config)


def load_source_index(workspace: Path) -> dict[str, Any]:
    """Load a workspace's sources/index.json. Returns a fresh empty index if the file is missing."""
    index_path = workspace / "sources" / "index.json"
    if not index_path.exists():
        return {"next_id": 1, "sources": []}
    with index_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_source_index(workspace: Path, index: dict[str, Any]) -> None:
    """Atomically write a workspace's sources/index.json."""
    index_path = workspace / "sources" / "index.json"
    _atomic_write_json(index_path, index)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON to path atomically (temp file + rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = f".{uuid.uuid4().hex}.tmp"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        delete=False,
        dir=str(path.parent),
        prefix=path.name + ".",
        suffix=suffix,
    ) as tmp:
        json.dump(payload, tmp, indent=2, ensure_ascii=False)
        tmp_path = Path(tmp.name)
    try:
        tmp_path.replace(path)
    except OSError:
        # On Windows, rename fails if the destination exists; use a fallback.
        if path.exists():
            path.unlink()
        tmp_path.replace(path)


# ---------------------------------------------------------------------------
# URL normalization for deduplication
# ---------------------------------------------------------------------------


_TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
}


def normalize_url(url: str) -> str:
    """Normalize a URL for deduplication matching.

    Strips:
    - protocol (http/https)
    - leading "www."
    - trailing slashes
    - common tracking query parameters
    - fragment (the # part)

    Returns a canonical form suitable for string equality comparison. Note that
    this is intentionally lossy. Two URLs that differ only in tracking params
    or in http vs https will be considered duplicates.
    """
    if not url:
        return ""
    parsed = urlparse(url.strip())
    # Drop www.
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    # Drop tracking params
    query_pairs = [
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS
    ]
    query = urlencode(query_pairs)
    # Normalize path: drop trailing slash (except for root)
    path = parsed.path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    # Rebuild without scheme or fragment
    normalized = f"{host}{path}"
    if query:
        normalized = f"{normalized}?{query}"
    return normalized.lower()


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split a markdown document into (frontmatter_dict, body).

    Returns ({}, text) if no frontmatter is present.
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
        if not isinstance(meta, dict):
            meta = {"_raw_frontmatter": str(meta)}
    except yaml.YAMLError:
        meta = {}
    return meta, m.group(2)


def render_frontmatter(meta: dict[str, Any], body: str) -> str:
    """Render a markdown document with YAML frontmatter.

    The body is appended verbatim. The frontmatter keys are sorted for
    deterministic output.
    """
    if not meta:
        return body
    yaml_str = yaml.safe_dump(meta, sort_keys=True, allow_unicode=True, default_flow_style=False).strip()
    return f"---\n{yaml_str}\n---\n\n{body}"


# ---------------------------------------------------------------------------
# Slug validation
# ---------------------------------------------------------------------------


_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")


def is_valid_slug(name: str) -> bool:
    """Return True if `name` is a valid workspace slug.

    Valid slugs:
    - lowercase letters, digits, and hyphens
    - 2-64 characters long
    - must start and end with a letter or digit
    """
    if not name or len(name) < 2 or len(name) > 64:
        return False
    return bool(_SLUG_RE.match(name))


def slugify(text: str) -> str:
    """Convert arbitrary text to a workspace slug."""
    text = text.lower().strip()
    # Replace non-alphanumeric with hyphens
    text = re.sub(r"[^a-z0-9]+", "-", text)
    # Collapse multiple hyphens
    text = re.sub(r"-+", "-", text)
    # Strip leading/trailing hyphens
    text = text.strip("-")
    if len(text) > 64:
        text = text[:64].rstrip("-")
    if len(text) < 2:
        text = (text + "-x")[:2]
    return text


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------


def source_id_for(next_id: int) -> str:
    """Format a numeric ID as the standard src_NNN form."""
    return f"src_{next_id:03d}"


def word_count(text: str) -> int:
    """Count whitespace-separated words in a string."""
    if not text:
        return 0
    return len(text.split())


def utcnow_iso() -> str:
    """Public alias for _now_iso."""
    return _now_iso()


# ---------------------------------------------------------------------------
# Markdown truncation (preserves heading structure)
# ---------------------------------------------------------------------------


def truncate_markdown(text: str, max_words: int) -> str:
    """Truncate a markdown document to at most `max_words` words.

    Preserves heading structure by keeping the first N words of each section
    (split on ATX headings, i.e., lines starting with `#`). The intent is to
    keep the table of contents and a useful excerpt of every section, not
    to cut mid-section at a fixed word boundary.

    Algorithm:
        1. Split the text into sections at lines starting with `#`
        2. For each section, take the heading line plus the first K words of
           the body, where K is chosen to keep the total <= max_words while
           ensuring every section gets at least 1/8 of the per-section budget
        3. Reassemble with a "..." marker if any section was truncated

    Args:
        text: The markdown body to truncate.
        max_words: Target word count. Must be > 0.

    Returns:
        The truncated markdown string, with a final "..." suffix if truncated.
    """
    if max_words <= 0 or not text:
        return text
    current_words = len(text.split())
    if current_words <= max_words:
        return text

    lines = text.splitlines()
    # Identify section boundaries (lines that start with `#` ATX heading)
    sections: list[tuple[str, list[str]]] = []  # (heading_line, body_lines)
    current_heading = ""
    current_body: list[str] = []
    for line in lines:
        if line.startswith("#") and len(current_body) > 0:
            sections.append((current_heading, current_body))
            current_heading = line
            current_body = []
        elif not current_heading and line.startswith("#"):
            current_heading = line
        else:
            if current_heading:
                current_body.append(line)
            else:
                # Pre-heading content (rare but possible)
                current_body.append(line)
    if current_heading or current_body:
        sections.append((current_heading, current_body))

    if not sections:
        # No headings found; just take the first N words.
        return " ".join(text.split()[:max_words]) + "\n\n..."

    # Allocate a per-section budget
    n_sections = len(sections)
    per_section = max(1, max_words // n_sections)
    truncated_sections: list[str] = []
    any_truncated = False
    for heading, body_lines in sections:
        body_text = "\n".join(body_lines).strip()
        body_words = body_text.split() if body_text else []
        if len(body_words) <= per_section:
            kept_body = body_text
            section_truncated = False
        else:
            kept_body = " ".join(body_words[:per_section])
            section_truncated = True
            any_truncated = True
        if kept_body:
            truncated_sections.append(f"{heading}\n\n{kept_body}")
        else:
            truncated_sections.append(heading)

    out = "\n\n---\n\n".join(truncated_sections)
    if any_truncated:
        out += "\n\n*... [content truncated for context window]*"
    return out
