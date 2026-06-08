"""Unit tests for tests/golden/compare.py.

The comparison must:
- Return warnings and failures separately
- Make --strict promote warnings to non-zero exit
- Promote a citation_coverage below threshold to a warning (not failure)
- Surface warning details in the JSON output

These tests build tiny synthetic run directories and exercise compare.py
end-to-end. No network is involved.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COMPARE_PY = REPO_ROOT / "tests" / "golden" / "compare.py"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))


def _run_compare(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(COMPARE_PY), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def _build_run(run_dir: Path, *, sources: list[str], report_text: str = "") -> None:
    """Build a minimal run directory with the given source URLs and a report.

    Each source becomes a `src_NNN` entry in sources/index.json plus a stub
    markdown file. The report, if provided, is written to outputs/report.md.
    The notes/findings.md is left empty so citation coverage comes only
    from the report (or is 0 if no report).
    """
    if run_dir.exists():
        shutil.rmtree(run_dir)
    (run_dir / "sources" / "web").mkdir(parents=True)
    (run_dir / "sources" / "papers").mkdir(parents=True)
    (run_dir / "notes").mkdir(parents=True)
    (run_dir / "outputs").mkdir(parents=True)
    (run_dir / "notes" / "findings.md").write_text("", encoding="utf-8")
    (run_dir / "notes" / "summary.md").write_text("", encoding="utf-8")
    (run_dir / "outputs" / "bibliography.md").write_text("", encoding="utf-8")
    (run_dir / "config.json").write_text(json.dumps({"name": run_dir.name, "created_at": ""}), encoding="utf-8")

    sources_list: list[dict] = []
    for i, url in enumerate(sources, start=1):
        sid = f"src_{i:03d}"
        sources_list.append(
            {
                "id": sid,
                "url": url,
                "url_normalized": url.replace("https://", "").rstrip("/"),
                "file": f"web/{sid}.md",
                "added_at": "2026-06-07T00:00:00Z",
                "query": "q",
                "word_count": 1,
                "title": url,
                "search_provider": "duckduckgo",
            }
        )
        (run_dir / "sources" / "web" / f"{sid}.md").write_text(
            f"---\nid: {sid}\nurl: {url}\n---\n\n# {url}\n",
            encoding="utf-8",
        )
    (run_dir / "sources" / "index.json").write_text(
        json.dumps({"next_id": len(sources) + 1, "sources": sources_list}),
        encoding="utf-8",
    )
    (run_dir / "outputs" / "report.md").write_text(report_text, encoding="utf-8")


class TestCompareCitationsAndStrict:
    def _expected_dir(self, tmp_path: Path) -> Path:
        """A minimal expected/ dir with our quality assertions."""
        ed = tmp_path / "expected"
        ed.mkdir()
        (ed / "quality_checks.json").write_text(
            json.dumps(
                {
                    "min_unique_domains": 1,
                    "min_citation_coverage": 0.8,
                    "all_ids_valid": True,
                    "no_duplicate_urls": True,
                    "id_counter_valid": True,
                }
            ),
            encoding="utf-8",
        )
        (ed / "source_count_range.json").write_text(
            json.dumps({"min": 1, "max": 100}), encoding="utf-8"
        )
        return ed

    def test_below_threshold_emits_warning(self, tmp_path: Path) -> None:
        """A run with 4 sources citing only 1 should produce a citation_coverage warning."""
        run_a = tmp_path / "runA"
        run_b = tmp_path / "runB"
        # 4 sources, report cites 1 -> 25% coverage, below 80%
        report = "# Report\n\nCites [src_001] only.\n"
        _build_run(
            run_a,
            sources=[
                "https://a.example.com/1",
                "https://b.example.com/2",
                "https://c.example.com/3",
                "https://d.example.com/4",
            ],
            report_text=report,
        )
        _build_run(
            run_b,
            sources=[
                "https://a.example.com/1",
                "https://b.example.com/2",
                "https://c.example.com/3",
                "https://d.example.com/4",
            ],
            report_text=report,
        )
        ed = self._expected_dir(tmp_path)
        proc = _run_compare(str(run_a), str(run_b), "--expected", str(ed))
        assert proc.returncode == 0, (
            f"non-strict mode should not fail on warnings; "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )
        out = json.loads(proc.stdout)
        # Warnings must be present in the output
        assert "warnings" in out
        all_warnings = out["warnings"]
        flat = [w for r in all_warnings for w in r["warnings"]]
        assert any(w.get("check") == "min_citation_coverage" for w in flat), flat
        # No failures in this scenario
        assert all(not r["failures"] for r in out["failures"])

    def test_below_threshold_fails_under_strict(self, tmp_path: Path) -> None:
        """Same scenario, with --strict, must exit nonzero."""
        run_a = tmp_path / "runA"
        run_b = tmp_path / "runB"
        report = "# Report\n\nCites [src_001] only.\n"
        _build_run(
            run_a,
            sources=[
                "https://a.example.com/1",
                "https://b.example.com/2",
                "https://c.example.com/3",
                "https://d.example.com/4",
            ],
            report_text=report,
        )
        _build_run(
            run_b,
            sources=[
                "https://a.example.com/1",
                "https://b.example.com/2",
                "https://c.example.com/3",
                "https://d.example.com/4",
            ],
            report_text=report,
        )
        ed = self._expected_dir(tmp_path)
        proc = _run_compare(str(run_a), str(run_b), "--expected", str(ed), "--strict")
        assert proc.returncode != 0, (
            f"strict mode must fail on warnings; "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )
        # On failure, the payload is on stderr only
        assert proc.stdout == "", (
            f"on failure, stdout must be silent, got: {proc.stdout!r}"
        )
        out = json.loads(proc.stderr)
        assert out["comparison"] == "failures"
        assert out["strict"] is True

    def test_above_threshold_passes_under_strict(self, tmp_path: Path) -> None:
        """A run that cites all of its sources must pass in both modes."""
        run_a = tmp_path / "runA"
        run_b = tmp_path / "runB"
        # 4 sources, report cites all 4 -> 100% coverage
        report = "# Report\n\nCites [src_001] [src_002] [src_003] [src_004] all of them.\n"
        _build_run(
            run_a,
            sources=[
                "https://a.example.com/1",
                "https://b.example.com/2",
                "https://c.example.com/3",
                "https://d.example.com/4",
            ],
            report_text=report,
        )
        _build_run(
            run_b,
            sources=[
                "https://a.example.com/1",
                "https://b.example.com/2",
                "https://c.example.com/3",
                "https://d.example.com/4",
            ],
            report_text=report,
        )
        ed = self._expected_dir(tmp_path)
        proc = _run_compare(str(run_a), str(run_b), "--expected", str(ed), "--strict")
        assert proc.returncode == 0, (
            f"strict mode should pass when warnings are absent; "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )
        out = json.loads(proc.stdout)
        assert out["comparison"] == "ok"
        assert proc.stderr == "", (
            f"on success, stderr must be silent, got: {proc.stderr!r}"
        )

    def test_failures_always_fail_even_without_strict(self, tmp_path: Path) -> None:
        """A duplicate-URL failure must exit nonzero in both strict and non-strict modes."""
        run_a = tmp_path / "runA"
        run_b = tmp_path / "runB"
        # Build runs that have an invalid reference: report cites src_999 which doesn't exist
        report = "# Report\n\nCites [src_999] but it does not exist.\n"
        _build_run(
            run_a,
            sources=["https://a.example.com/1"],
            report_text=report,
        )
        _build_run(
            run_b,
            sources=["https://a.example.com/1"],
            report_text=report,
        )
        ed = self._expected_dir(tmp_path)
        proc = _run_compare(str(run_a), str(run_b), "--expected", str(ed))
        # The all_ids_valid check is a failure, not a warning -> non-zero exit
        assert proc.returncode != 0, "invalid IDs must fail the comparison"
        # Repository-wide CLI contract: structured JSON on success goes
        # to stdout, structured JSON on failure goes to stderr. Stream
        # capture must match that contract.
        assert proc.stdout == "", (
            f"on failure, stdout must be empty, got: {proc.stdout!r}"
        )
        err = json.loads(proc.stderr)
        # Top-level status must be "error", not "ok", so automation can
        # distinguish a failed comparison from a passing one.
        assert err["status"] == "error", err
        assert err.get("error") == "comparison_failed", err
        assert err["comparison"] == "failures"
        flat_failures = [f for r in err["failures"] for f in r["failures"]]
        assert any(f.get("check") == "all_ids_valid" for f in flat_failures), flat_failures

    def test_success_payload_is_only_on_stdout(self, tmp_path: Path) -> None:
        """A passing comparison must emit JSON on stdout and nothing on stderr."""
        run_a = tmp_path / "runA"
        run_b = tmp_path / "runB"
        _build_run(
            run_a,
            sources=["https://a.example.com/1"],
            report_text="# Report\n\nCites [src_001].\n",
        )
        _build_run(
            run_b,
            sources=["https://a.example.com/1"],
            report_text="# Report\n\nCites [src_001].\n",
        )
        ed = self._expected_dir(tmp_path)
        proc = _run_compare(str(run_a), str(run_b), "--expected", str(ed))
        assert proc.returncode == 0, (
            f"unexpected failure: stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )
        # On success, stdout has the payload and stderr is silent
        out = json.loads(proc.stdout)
        assert out["status"] == "ok", out
        assert proc.stderr == "", (
            f"on success, stderr must be silent, got: {proc.stderr!r}"
        )
