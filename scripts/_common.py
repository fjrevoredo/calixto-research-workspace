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
- `WorkspaceStateCoordinator`: lock, recover, validate, and commit multi-file search state mutations
- `normalize_url`: strip protocol, www, trailing slashes, tracking params for dedup
- `parse_frontmatter`: extract YAML frontmatter from a markdown file
- `slugify`: convert a string to a valid workspace name slug

All scripts follow the same I/O contract: structured JSON to stdout on success,
structured JSON to stderr on failure, exit code 0 on success, 1 on error.

See requirements.md section 12.4 for the error output format.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import yaml


LOCK_STALE_AFTER_SECONDS = 120.0
LOCK_ACQUIRE_TIMEOUT_SECONDS = 30.0
LOCK_POLL_INTERVAL_SECONDS = 0.1
SOURCE_ID_RE = re.compile(r"^src_(\d{3,})$")
REVIEW_STATUS_VALUES = {"pending", "discarded", "used"}


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


def workspace_state_dir(workspace: Path) -> Path:
    """Return the per-workspace hidden state directory."""
    return workspace / ".calixto"


def workspace_transactions_dir(workspace: Path) -> Path:
    """Return the directory used for staged workspace transactions."""
    return workspace_state_dir(workspace) / "transactions"


def workspace_lock_dir(workspace: Path) -> Path:
    """Return the directory used as an inter-process workspace lock."""
    return workspace_state_dir(workspace) / "workspace.lock"


class WorkspaceLock:
    """Filesystem-backed lock that serializes workspace mutations.

    The lock is a directory created with mkdir, which is atomic across
    supported platforms. A stale lock is broken after `stale_after_seconds`.
    """

    def __init__(
        self,
        workspace: Path,
        *,
        acquire_timeout_seconds: float = LOCK_ACQUIRE_TIMEOUT_SECONDS,
        stale_after_seconds: float = LOCK_STALE_AFTER_SECONDS,
        poll_interval_seconds: float = LOCK_POLL_INTERVAL_SECONDS,
    ) -> None:
        self.workspace = workspace
        self.acquire_timeout_seconds = acquire_timeout_seconds
        self.stale_after_seconds = stale_after_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.lock_dir = workspace_lock_dir(workspace)
        self.info_path = self.lock_dir / "lock.json"
        self._acquired = False

    def __enter__(self) -> "WorkspaceLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()

    def acquire(self) -> None:
        """Acquire the workspace lock or raise TimeoutError."""
        workspace_state_dir(self.workspace).mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        while True:
            try:
                self.lock_dir.mkdir()
                self._write_info()
                self._acquired = True
                return
            except FileExistsError:
                if self._break_stale_lock():
                    continue
                if (time.monotonic() - started) >= self.acquire_timeout_seconds:
                    raise TimeoutError(
                        f"timed out waiting for workspace lock at {self.lock_dir}"
                    )
                time.sleep(self.poll_interval_seconds)

    def release(self) -> None:
        """Release the lock if held."""
        if not self._acquired:
            return
        shutil.rmtree(self.lock_dir, ignore_errors=True)
        self._acquired = False

    def _write_info(self) -> None:
        payload = {
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "created_at": _now_iso(),
        }
        _atomic_write_json(self.info_path, payload)
        try:
            os.utime(self.lock_dir, None)
        except OSError:
            pass

    def _break_stale_lock(self) -> bool:
        try:
            age_seconds = time.time() - self.lock_dir.stat().st_mtime
        except OSError:
            return False
        if age_seconds < self.stale_after_seconds:
            return False
        try:
            shutil.rmtree(self.lock_dir)
        except FileNotFoundError:
            return True
        except OSError:
            return False
        return True


class WorkspaceStateCoordinator:
    """Serialize multi-file workspace mutations and recover interrupted ones."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.lock = WorkspaceLock(workspace)
        self.config: dict[str, Any] = {}
        self.index: dict[str, Any] = {}
        self.recovery: dict[str, Any] = {"recovered": [], "discarded": []}

    def __enter__(self) -> "WorkspaceStateCoordinator":
        self.lock.acquire()
        self.recovery = recover_workspace_transactions_locked(self.workspace)
        self.reload()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.lock.release()

    def reload(self) -> None:
        """Reload config/index after the lock is held."""
        self.config = load_workspace_config(self.workspace)
        self.index = load_source_index(self.workspace)

    def commit(
        self,
        *,
        config: dict[str, Any],
        index: dict[str, Any],
        source_files: list[dict[str, str]],
        transaction_label: str,
    ) -> dict[str, Any]:
        """Commit source files, sources/index.json, and config.json together.

        `source_files` entries must contain:
        - `relpath`: workspace-relative file path such as `sources/web/src_001.md`
        - `content`: full text to publish
        """
        prepared_config = dict(config)
        prepared_index = dict(index)
        prepared_config["updated_at"] = _now_iso()
        validate_workspace_search_state(prepared_config, prepared_index)

        txid = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
        txdir = workspace_transactions_dir(self.workspace) / txid
        stage_root = txdir / "staged"
        txdir.mkdir(parents=True, exist_ok=False)
        try:
            staged_files: list[str] = []
            for item in source_files:
                relpath = item["relpath"]
                content = item["content"]
                _atomic_write_text(stage_root / relpath, content)
                staged_files.append(relpath.replace("\\", "/"))

            _atomic_write_text(
                stage_root / "sources" / "index.json",
                json.dumps(prepared_index, indent=2, ensure_ascii=False),
            )
            staged_files.append("sources/index.json")
            _atomic_write_text(
                stage_root / "config.json",
                json.dumps(prepared_config, indent=2, ensure_ascii=False),
            )
            staged_files.append("config.json")

            manifest = {
                "version": 1,
                "transaction_id": txid,
                "transaction_label": transaction_label,
                "created_at": _now_iso(),
                "files": sorted(staged_files),
            }
            _atomic_write_json(txdir / "manifest.json", manifest)
            _publish_workspace_transaction(self.workspace, txdir, manifest)
            shutil.rmtree(txdir, ignore_errors=True)
            self.config = prepared_config
            self.index = prepared_index
            return manifest
        except Exception:
            # Keep the staged transaction on disk once the manifest exists so a
            # future search or audit can recover it deterministically.
            if not (txdir / "manifest.json").exists():
                shutil.rmtree(txdir, ignore_errors=True)
            raise


def recover_workspace_transactions(workspace: Path) -> dict[str, Any]:
    """Recover or discard staged workspace transactions under an exclusive lock."""
    with WorkspaceLock(workspace):
        return recover_workspace_transactions_locked(workspace)


def recover_workspace_transactions_locked(workspace: Path) -> dict[str, Any]:
    """Recover staged workspace transactions while the caller holds the lock."""
    tx_root = workspace_transactions_dir(workspace)
    if not tx_root.exists():
        return {"recovered": [], "discarded": []}

    recovered: list[str] = []
    discarded: list[str] = []
    for txdir in sorted(p for p in tx_root.iterdir() if p.is_dir()):
        manifest_path = txdir / "manifest.json"
        if not manifest_path.exists():
            shutil.rmtree(txdir, ignore_errors=True)
            discarded.append(txdir.name)
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise RuntimeError(f"cannot recover transaction {txdir.name}: invalid manifest ({exc})") from exc
        _publish_workspace_transaction(workspace, txdir, manifest)
        shutil.rmtree(txdir, ignore_errors=True)
        recovered.append(txdir.name)

    return {"recovered": recovered, "discarded": discarded}


def validate_workspace_search_state(config: dict[str, Any], index: dict[str, Any]) -> None:
    """Raise ValueError if staged search state is internally inconsistent."""
    if not isinstance(config, dict):
        raise ValueError("config must be a JSON object")
    if not isinstance(index, dict):
        raise ValueError("index must be a JSON object")

    sources = index.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("index.sources must be a list")

    seen_ids: set[str] = set()
    seen_files: set[str] = set()
    max_numeric_id = 0
    for pos, source in enumerate(sources):
        if not isinstance(source, dict):
            raise ValueError(f"index.sources[{pos}] must be an object")
        source_id = str(source.get("id", "")).strip()
        url = str(source.get("url", "")).strip()
        file_relpath = str(source.get("file", "")).strip()
        if not source_id or not SOURCE_ID_RE.match(source_id):
            raise ValueError(f"index.sources[{pos}].id must look like src_NNN")
        if not url:
            raise ValueError(f"index.sources[{pos}].url must be non-empty")
        if not file_relpath:
            raise ValueError(f"index.sources[{pos}].file must be non-empty")
        if source_id in seen_ids:
            raise ValueError(f"duplicate source id in index: {source_id}")
        if file_relpath in seen_files:
            raise ValueError(f"duplicate source file path in index: {file_relpath}")
        review_status = source.get("review_status")
        if review_status is not None:
            if not isinstance(review_status, str) or review_status not in REVIEW_STATUS_VALUES:
                raise ValueError(
                    f"index.sources[{pos}].review_status must be one of "
                    f"{sorted(REVIEW_STATUS_VALUES)} when present"
                )
        review_note = source.get("review_note")
        if review_note is not None:
            if not isinstance(review_note, str) or not review_note.strip():
                raise ValueError(f"index.sources[{pos}].review_note must be a non-empty string when present")
        reviewed_at = source.get("reviewed_at")
        if reviewed_at is not None:
            if not isinstance(reviewed_at, str) or not reviewed_at.strip():
                raise ValueError(f"index.sources[{pos}].reviewed_at must be a non-empty string when present")
        seen_ids.add(source_id)
        seen_files.add(file_relpath)
        max_numeric_id = max(max_numeric_id, int(source_id.split("_", 1)[1]))

    next_id = index.get("next_id", 1)
    if not isinstance(next_id, int) or next_id < 1:
        raise ValueError("index.next_id must be a positive integer")
    expected_next_id = max_numeric_id + 1 if seen_ids else 1
    if next_id != expected_next_id:
        raise ValueError(
            f"index.next_id must equal the next available source id ({expected_next_id}), got {next_id}"
        )

    config_next_source_id = config.get("next_source_id", 1)
    if not isinstance(config_next_source_id, int) or config_next_source_id < 1:
        raise ValueError("config.next_source_id must be a positive integer")
    if config_next_source_id != next_id:
        raise ValueError(
            f"config.next_source_id ({config_next_source_id}) must match index.next_id ({next_id})"
        )

    searches = config.get("searches", [])
    if not isinstance(searches, list):
        raise ValueError("config.searches must be a list")
    for pos, search in enumerate(searches):
        if not isinstance(search, dict):
            raise ValueError(f"config.searches[{pos}] must be an object")
        if not str(search.get("query", "")).strip():
            raise ValueError(f"config.searches[{pos}].query must be non-empty")
        if not str(search.get("provider", "")).strip():
            raise ValueError(f"config.searches[{pos}].provider must be non-empty")
        if not str(search.get("timestamp", "")).strip():
            raise ValueError(f"config.searches[{pos}].timestamp must be non-empty")
        source_ids = search.get("source_ids", [])
        if source_ids is None:
            source_ids = []
        if not isinstance(source_ids, list):
            raise ValueError(f"config.searches[{pos}].source_ids must be a list when present")
        unknown_ids = [source_id for source_id in source_ids if source_id not in seen_ids]
        if unknown_ids:
            raise ValueError(
                f"config.searches[{pos}] references source_ids not present in index: {unknown_ids}"
            )


def _publish_workspace_transaction(workspace: Path, txdir: Path, manifest: dict[str, Any]) -> None:
    """Publish a staged transaction into the live workspace."""
    stage_root = txdir / "staged"
    staged_files = manifest.get("files", [])
    if not isinstance(staged_files, list) or not staged_files:
        raise RuntimeError(f"cannot recover transaction {txdir.name}: manifest has no files")
    for relpath in staged_files:
        source = stage_root / relpath
        if not source.exists():
            raise RuntimeError(
                f"cannot recover transaction {txdir.name}: missing staged file {relpath}"
            )
        _atomic_write_text(
            workspace / relpath,
            source.read_text(encoding="utf-8"),
        )


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON to path atomically (temp file + rename)."""
    _atomic_write_text(path, json.dumps(payload, indent=2, ensure_ascii=False))


def _atomic_write_text(path: Path, text: str) -> None:
    """Write text to path atomically (temp file + rename)."""
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
        tmp.write(text)
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


def source_number_for(source_id: str) -> int:
    """Return the numeric portion of a src_NNN identifier."""
    match = SOURCE_ID_RE.match(source_id)
    if not match:
        raise ValueError(f"invalid source id: {source_id}")
    return int(match.group(1))


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
