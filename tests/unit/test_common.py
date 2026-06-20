"""Unit tests for scripts/_common.py utilities.

These tests cover the shared helpers used by all CLI scripts: slug validation,
URL normalization, frontmatter parsing/rendering, markdown truncation, and the
structured I/O helpers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make the scripts package importable
SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR.parent))  # repo root
sys.path.insert(0, str(SCRIPTS_DIR))  # so 'import _common' works

from _common import (  # noqa: E402
    WorkspaceStateCoordinator,
    is_valid_slug,
    load_source_index,
    load_workspace_config,
    normalize_url,
    parse_frontmatter,
    recover_workspace_transactions,
    render_frontmatter,
    save_source_index,
    save_workspace_config,
    slugify,
    source_id_for,
    validate_workspace_search_state,
    truncate_markdown,
    utcnow_iso,
    word_count,
    workspace_path,
)


# --- slug validation ---


class TestSlug:
    @pytest.mark.parametrize(
        "slug",
        ["my-research", "python-asyncio", "ab", "a1", "1a", "abc-123-xyz"],
    )
    def test_valid_slugs(self, slug: str) -> None:
        assert is_valid_slug(slug)

    @pytest.mark.parametrize(
        "slug",
        [
            "MyResearch",  # uppercase
            "my_research",  # underscore
            "my research",  # space
            "-leading",
            "trailing-",
            "--double-hyphen",
            "a",  # too short
            "a" * 65,  # too long
            "",
            "123-",  # ends with hyphen
        ],
    )
    def test_invalid_slugs(self, slug: str) -> None:
        assert not is_valid_slug(slug)

    def test_slugify_lowercases(self) -> None:
        assert slugify("Hello World") == "hello-world"

    def test_slugify_replaces_special_chars(self) -> None:
        assert slugify("Foo & Bar / Baz") == "foo-bar-baz"

    def test_slugify_collapses_hyphens(self) -> None:
        assert slugify("foo---bar") == "foo-bar"

    def test_slugify_truncates_long(self) -> None:
        long = "a" * 200
        result = slugify(long)
        assert len(result) <= 64
        assert not result.endswith("-")

    def test_slugify_uses_stable_fallback_for_symbol_only_text(self) -> None:
        result = slugify("!!!")
        assert result.startswith("research-")
        assert is_valid_slug(result)


# --- URL normalization ---


class TestNormalizeUrl:
    def test_strips_https(self) -> None:
        assert normalize_url("https://example.com/path") == "example.com/path"

    def test_strips_http(self) -> None:
        assert normalize_url("http://example.com/path") == "example.com/path"

    def test_strips_www(self) -> None:
        assert normalize_url("https://www.example.com/path") == "example.com/path"

    def test_strips_trailing_slash(self) -> None:
        assert normalize_url("https://example.com/path/") == "example.com/path"

    def test_keeps_root(self) -> None:
        assert normalize_url("https://example.com") == "example.com"

    def test_strips_tracking_params(self) -> None:
        result = normalize_url("https://example.com/path?utm_source=x&gclid=abc&q=keep")
        assert "utm_source" not in result
        assert "gclid" not in result
        assert "q=keep" in result

    def test_preserves_case_lowered(self) -> None:
        assert normalize_url("https://Example.COM/Path") == "example.com/path"

    def test_https_and_http_collapse(self) -> None:
        assert normalize_url("http://www.example.com/x") == normalize_url("https://example.com/x")


# --- frontmatter ---


class TestFrontmatter:
    def test_parse_with_frontmatter(self) -> None:
        text = "---\nid: src_001\nurl: https://x.com\n---\n\n# Body\n\nContent\n"
        meta, body = parse_frontmatter(text)
        assert meta == {"id": "src_001", "url": "https://x.com"}
        assert body.startswith("# Body")

    def test_parse_without_frontmatter(self) -> None:
        text = "# Just content\n"
        meta, body = parse_frontmatter(text)
        assert meta == {}
        assert body == text

    def test_parse_invalid_yaml_returns_empty(self) -> None:
        text = "---\n: invalid: yaml: : :\n---\n\n# Body\n"
        meta, body = parse_frontmatter(text)
        assert meta == {}
        assert body.startswith("# Body")

    def test_render_roundtrip(self) -> None:
        meta = {"id": "src_001", "url": "https://x.com", "title": "Hello"}
        body = "# Body\n\nContent.\n"
        rendered = render_frontmatter(meta, body)
        meta2, body2 = parse_frontmatter(rendered)
        assert meta2 == meta
        assert body2 == body

    def test_render_no_meta(self) -> None:
        body = "# Just content\n"
        assert render_frontmatter({}, body) == body

    def test_render_sorts_keys(self) -> None:
        meta = {"z": 1, "a": 2}
        rendered = render_frontmatter(meta, "body")
        # Sorted alphabetically: a comes before z
        a_pos = rendered.index("a: 2")
        z_pos = rendered.index("z: 1")
        assert a_pos < z_pos


# --- markdown truncation ---


class TestTruncate:
    def test_no_truncation_needed(self) -> None:
        text = "# Title\n\nshort body"
        assert truncate_markdown(text, 100) == text

    def test_truncate_marks_indicator(self) -> None:
        text = "# Title\n\nword1 word2 word3 word4 word5"
        result = truncate_markdown(text, 3)
        assert "[content truncated for context window]" in result

    def test_truncate_preserves_heading(self) -> None:
        text = "# Important\n\nLots of words here, more than the limit."
        result = truncate_markdown(text, 4)
        assert "Important" in result

    def test_truncate_zero_returns_input(self) -> None:
        text = "# Title\n\nbody"
        assert truncate_markdown(text, 0) == text

    def test_truncate_per_section(self) -> None:
        text = "# A\n\n1 2 3 4 5 6 7 8 9 10\n\n# B\n\n1 2 3 4 5 6 7 8 9 10"
        result = truncate_markdown(text, 8)  # 8 / 2 sections = 4 each
        assert "A" in result
        assert "B" in result
        # The total word count should be reasonable (heading + 4 words per section + markers)
        assert len(result.split()) <= 25


# --- source_id_for ---


class TestSourceId:
    def test_format(self) -> None:
        assert source_id_for(1) == "src_001"
        assert source_id_for(42) == "src_042"
        assert source_id_for(100) == "src_100"


# --- word_count ---


class TestWordCount:
    def test_empty(self) -> None:
        assert word_count("") == 0

    def test_words(self) -> None:
        assert word_count("hello world") == 2

    def test_whitespace(self) -> None:
        assert word_count("  hello   world  ") == 2

    def test_multiline(self) -> None:
        assert word_count("line one\nline two\nline three") == 6


# --- workspace_path ---


class TestWorkspacePath:
    def test_absolute(self, tmp_path: Path) -> None:
        p = workspace_path(str(tmp_path))
        assert p == tmp_path.resolve()

    def test_relative_resolved(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        p = workspace_path("subdir")
        assert p == (tmp_path / "subdir").resolve()


# --- workspace I/O roundtrip ---


class TestWorkspaceIO:
    def test_config_roundtrip(self, tmp_path: Path) -> None:
        cfg = {"name": "test", "question": "Q?", "next_source_id": 5, "searches": []}
        save_workspace_config(tmp_path, cfg)
        loaded = load_workspace_config(tmp_path)
        assert loaded["name"] == "test"
        assert loaded["question"] == "Q?"
        assert loaded["next_source_id"] == 5
        assert "updated_at" in loaded

    def test_source_index_roundtrip(self, tmp_path: Path) -> None:
        idx = {
            "next_id": 4,
            "sources": [
                {"id": "src_001", "url": "https://x.com", "file": "web/src_001.md"},
            ],
        }
        save_source_index(tmp_path, idx)
        loaded = load_source_index(tmp_path)
        assert loaded["next_id"] == 4
        assert len(loaded["sources"]) == 1

    def test_load_source_index_missing_returns_empty(self, tmp_path: Path) -> None:
        loaded = load_source_index(tmp_path)
        assert loaded == {"next_id": 1, "sources": []}


# --- utcnow_iso ---


class TestUtcnow:
    def test_format(self) -> None:
        ts = utcnow_iso()
        # Format: YYYY-MM-DDTHH:MM:SSZ
        assert len(ts) == 20
        assert ts.endswith("Z")
        assert "T" in ts


class TestWorkspaceStateCoordinator:
    def _make_workspace(self, tmp_path: Path) -> Path:
        workspace = tmp_path / "ws"
        (workspace / "sources" / "web").mkdir(parents=True)
        (workspace / "sources" / "papers").mkdir(parents=True)
        save_workspace_config(
            workspace,
            {
                "name": "ws",
                "question": "",
                "next_source_id": 1,
                "next_finding_id": 1,
                "next_insight_id": 1,
                "searches": [],
            },
        )
        save_source_index(workspace, {"next_id": 1, "sources": []})
        return workspace

    def test_validate_workspace_search_state_rejects_mismatched_next_id(self) -> None:
        with pytest.raises(ValueError, match="config.next_source_id"):
            validate_workspace_search_state(
                {
                    "next_source_id": 9,
                    "searches": [],
                },
                {
                    "next_id": 2,
                    "sources": [
                        {"id": "src_001", "url": "https://example.com", "file": "web/src_001.md"},
                    ],
                },
            )

    def test_validate_workspace_search_state_accepts_review_metadata(self) -> None:
        validate_workspace_search_state(
            {
                "next_source_id": 2,
                "searches": [],
            },
            {
                "next_id": 2,
                "sources": [
                    {
                        "id": "src_001",
                        "url": "https://example.com",
                        "file": "web/src_001.md",
                        "review_status": "discarded",
                        "review_note": "duplicate coverage",
                        "reviewed_at": utcnow_iso(),
                    },
                ],
            },
        )

    def test_validate_workspace_search_state_accepts_quality_metadata(self) -> None:
        validate_workspace_search_state(
            {
                "next_source_id": 2,
                "searches": [],
            },
            {
                "next_id": 2,
                "sources": [
                    {
                        "id": "src_001",
                        "url": "https://pubmed.ncbi.nlm.nih.gov/123456/",
                        "file": "papers/src_001.md",
                        "quality_tier": "authoritative",
                        "quality_reasons": ["pubmed_record"],
                        "quality_requires_corroboration": False,
                    },
                ],
            },
        )

    def test_validate_workspace_search_state_rejects_invalid_review_status(self) -> None:
        with pytest.raises(ValueError, match="review_status"):
            validate_workspace_search_state(
                {
                    "next_source_id": 2,
                    "searches": [],
                },
                {
                    "next_id": 2,
                    "sources": [
                        {
                            "id": "src_001",
                            "url": "https://example.com",
                            "file": "web/src_001.md",
                            "review_status": "maybe",
                        },
                    ],
                },
            )

    def test_validate_workspace_search_state_rejects_invalid_quality_tier(self) -> None:
        with pytest.raises(ValueError, match="quality_tier"):
            validate_workspace_search_state(
                {
                    "next_source_id": 2,
                    "searches": [],
                },
                {
                    "next_id": 2,
                    "sources": [
                        {
                            "id": "src_001",
                            "url": "https://example.com",
                            "file": "web/src_001.md",
                            "quality_tier": "peerless",
                        },
                    ],
                },
            )

    def test_coordinator_commit_writes_source_index_and_config(self, tmp_path: Path) -> None:
        workspace = self._make_workspace(tmp_path)
        with WorkspaceStateCoordinator(workspace) as coordinator:
            config = coordinator.config
            index = coordinator.index
            index["sources"].append(
                {
                    "id": "src_001",
                    "url": "https://example.com/a",
                    "file": "web/src_001.md",
                    "url_normalized": "example.com/a",
                    "added_at": utcnow_iso(),
                    "query": "q",
                    "word_count": 3,
                }
            )
            index["next_id"] = 2
            config["next_source_id"] = 2
            config["searches"].append(
                {
                    "query": "q",
                    "provider": "duckduckgo",
                    "timestamp": utcnow_iso(),
                    "source_ids": ["src_001"],
                }
            )
            coordinator.commit(
                config=config,
                index=index,
                source_files=[
                    {
                        "relpath": "sources/web/src_001.md",
                        "content": "---\nid: src_001\n---\n\nbody\n",
                    }
                ],
                transaction_label="test_commit",
            )

        assert (workspace / "sources" / "web" / "src_001.md").exists()
        loaded_index = load_source_index(workspace)
        assert loaded_index["next_id"] == 2
        assert loaded_index["sources"][0]["id"] == "src_001"
        loaded_config = load_workspace_config(workspace)
        assert loaded_config["next_source_id"] == 2
        assert len(loaded_config["searches"]) == 1
        assert not (workspace / ".calixto" / "transactions").exists() or not any(
            (workspace / ".calixto" / "transactions").iterdir()
        )

    def test_recover_workspace_transactions_rolls_forward_staged_files(self, tmp_path: Path) -> None:
        workspace = self._make_workspace(tmp_path)
        txdir = workspace / ".calixto" / "transactions" / "tx-test"
        staged = txdir / "staged"
        staged.joinpath("sources", "web").mkdir(parents=True, exist_ok=True)
        staged.joinpath("sources").mkdir(parents=True, exist_ok=True)
        staged.joinpath("config.json").write_text(
            json.dumps(
                {
                    "name": "ws",
                    "question": "",
                    "next_source_id": 2,
                    "next_finding_id": 1,
                    "next_insight_id": 1,
                    "searches": [
                        {
                            "query": "q",
                            "provider": "duckduckgo",
                            "timestamp": utcnow_iso(),
                            "source_ids": ["src_001"],
                        }
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        staged.joinpath("sources", "index.json").write_text(
            json.dumps(
                {
                    "next_id": 2,
                    "sources": [
                        {
                            "id": "src_001",
                            "url": "https://example.com/a",
                            "file": "web/src_001.md",
                            "url_normalized": "example.com/a",
                            "added_at": utcnow_iso(),
                            "query": "q",
                            "word_count": 3,
                        }
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        staged.joinpath("sources", "web", "src_001.md").write_text(
            "---\nid: src_001\n---\n\nbody\n",
            encoding="utf-8",
        )
        txdir.mkdir(parents=True, exist_ok=True)
        (txdir / "manifest.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "transaction_id": "tx-test",
                    "transaction_label": "test_recovery",
                    "created_at": utcnow_iso(),
                    "files": [
                        "config.json",
                        "sources/index.json",
                        "sources/web/src_001.md",
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        summary = recover_workspace_transactions(workspace)
        assert summary["recovered"] == ["tx-test"]
        assert (workspace / "sources" / "web" / "src_001.md").exists()
        assert load_source_index(workspace)["next_id"] == 2
        assert load_workspace_config(workspace)["next_source_id"] == 2
