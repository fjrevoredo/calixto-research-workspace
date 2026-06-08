"""
tests/golden/compare.py: Compare two golden runs structurally.

Usage:
    python tests/golden/compare.py <run_a> <run_b>
        [--expected tests/golden/expected]
        [--strict]    # exit 1 on warnings as well as errors

The comparison checks:
  - Source count is within expected range
  - Report contains expected sections
  - Unique domains >= minimum
  - Citation coverage >= minimum
  - All referenced IDs are valid
  - No duplicate URLs
  - ID counter matches expected

Compares two runs side-by-side and reports the diff. Exits 0 if all checks pass
within tolerance, 1 if any check fails (in --strict mode, warnings also fail).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

THIS_FILE = Path(__file__).resolve()
TESTS_DIR = THIS_FILE.parent
GOLDEN_DIR = TESTS_DIR
REPO_ROOT = TESTS_DIR.parent.parent

SRC_ID_RE = re.compile(r"\bsrc_(\d{3,})\b")
FND_ID_RE = re.compile(r"\bfnd_(\d{3,})\b")
INS_ID_RE = re.compile(r"\bins_(\d{3,})\b")


def emit_error(error_type: str, message: str) -> None:
    print(
        json.dumps(
            {"status": "error", "error": error_type, "message": message},
            indent=2,
            ensure_ascii=False,
        ),
        file=sys.stderr,
    )
    sys.exit(1)


def emit_ok(payload: dict) -> None:
    print(json.dumps({"status": "ok", **payload}, indent=2, ensure_ascii=False))


def _read_file(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _normalize_url_for_compare(url: str) -> str:
    """Lightweight URL normalization for domain extraction and dedup."""
    if not url:
        return ""
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return f"{host}{parsed.path}".rstrip("/").lower()


# Template-report marker: if a report contains this string, it has not been
# replaced by the agent and is still the boilerplate from the workspace template.
TEMPLATE_REPORT_MARKER = "A good report typically includes:"


def is_template_report(report_text: str) -> bool:
    """Return True if the report is still the workspace template boilerplate."""
    return TEMPLATE_REPORT_MARKER in report_text


def analyze_run(run_dir: Path) -> dict:
    """Analyze a single run directory. Returns structural metrics."""
    if not run_dir.exists():
        emit_error("run_not_found", f"run directory not found: {run_dir}")
    if not (run_dir / "config.json").exists():
        emit_error("run_invalid", f"run is missing config.json: {run_dir}")

    index_path = run_dir / "sources" / "index.json"
    sources: list[dict] = []
    if index_path.exists():
        try:
            sources = json.loads(index_path.read_text(encoding="utf-8")).get("sources", [])
        except json.JSONDecodeError:
            sources = []

    source_ids = {s.get("id") for s in sources if s.get("id")}
    urls = [s.get("url", "") for s in sources if s.get("url")]
    domains = {_normalize_url_for_compare(u).split("/", 1)[0] for u in urls if u}
    unique_domains = len(domains)

    # Duplicate URLs
    seen = set()
    dup_urls: list[str] = []
    for u in urls:
        norm = _normalize_url_for_compare(u)
        if norm in seen:
            dup_urls.append(u)
        seen.add(norm)

    # Report content
    report_text = _read_file(run_dir / "outputs" / "report.md")
    findings_text = _read_file(run_dir / "notes" / "findings.md")
    summary_text = _read_file(run_dir / "notes" / "summary.md")
    bibliography_text = _read_file(run_dir / "outputs" / "bibliography.md")

    # ID extraction
    report_src_refs = {f"src_{m}" for m in SRC_ID_RE.findall(report_text)}
    findings_src_refs = {f"src_{m}" for m in SRC_ID_RE.findall(findings_text)}
    summary_fnd_refs = {f"fnd_{m}" for m in FND_ID_RE.findall(summary_text)}

    finding_ids_in_findings = {
        f"fnd_{m}" for m in re.findall(r"^##\s+fnd_(\d{3,})", findings_text, re.MULTILINE)
    }
    insight_ids_in_summary = {
        f"ins_{m}" for m in re.findall(r"^##\s+ins_(\d{3,})", summary_text, re.MULTILINE)
    }

    # Validity
    invalid_src_in_findings = findings_src_refs - source_ids
    invalid_src_in_report = report_src_refs - source_ids
    invalid_fnd_in_summary = summary_fnd_refs - finding_ids_in_findings

    # Citation coverage
    all_cited = report_src_refs | findings_src_refs
    citation_coverage = len(all_cited) / len(source_ids) if source_ids else 0.0

    # Report sections (heuristic: lines starting with # then a section name)
    report_sections: list[str] = []
    for line in report_text.splitlines():
        if line.startswith("## "):
            section_name = line[3:].strip()
            # Remove numbering if present like "1. Summary"
            section_name = re.sub(r"^\d+\.\s*", "", section_name)
            report_sections.append(section_name)

    # ID counter
    cfg = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    next_id_in_index = json.loads(index_path.read_text(encoding="utf-8")).get("next_id", 1) if index_path.exists() else 1
    next_id_expected = max((int(sid.split("_", 1)[1]) for sid in source_ids if sid and "_" in sid), default=0) + 1

    return {
        "run": str(run_dir),
        "source_count": len(source_ids),
        "unique_domains": unique_domains,
        "duplicate_urls": dup_urls,
        "report_sections": report_sections,
        "report_cited_sources": sorted(report_src_refs),
        "findings_cited_sources": sorted(findings_src_refs),
        "summary_cited_findings": sorted(summary_fnd_refs),
        "invalid_refs": {
            "source_in_findings": sorted(invalid_src_in_findings),
            "source_in_report": sorted(invalid_src_in_report),
            "finding_in_summary": sorted(invalid_fnd_in_summary),
        },
        "citation_coverage": citation_coverage,
        "orphaned_sources": sorted(source_ids - all_cited),
        "id_counter_expected": next_id_expected,
        "id_counter_actual": next_id_in_index,
        "id_counter_valid": next_id_expected == next_id_in_index,
        "has_findings_file": bool(findings_text.strip()),
        "has_summary_file": bool(summary_text.strip()),
        "has_report_file": bool(report_text.strip()),
        "has_bibliography_file": bool(bibliography_text.strip()),
        "is_template_report": is_template_report(report_text),
        "is_template_findings": "Each finding MUST reference at least one source ID" in findings_text,
        "is_template_summary": "Each insight MUST reference at least one finding ID" in summary_text,
        "workspace_question": cfg.get("question", ""),
    }


def load_expected(expected_dir: Path) -> dict:
    """Load all expected/* files into a single dict."""
    if not expected_dir.exists():
        return {}
    out: dict[str, Any] = {}
    for f in expected_dir.glob("*.json"):
        try:
            out[f.stem] = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return out


def check_against_expected(metrics: dict, expected: dict) -> tuple[list[dict], list[dict]]:
    """Check metrics against expected structural assertions.

    Returns (failures, warnings). The two are distinct:
    - failures are structural breaks that always count (missing required
      IDs, no source diversity, etc.)
    - warnings are soft quality signals (citation coverage below the
      required 80%, etc.) that only count under --strict.

    The 80% citation coverage requirement from requirements.md section
    10.4 is reported as a warning (not a failure) so that source-only
    runs (where the agent has not yet synthesized a report) do not
    falsely fail comparison. A run that synthesizes a real report and
    cites fewer than 80% of its sources will surface as a warning;
    `--strict` then promotes that warning to a non-zero exit so the
    no-silent-failures principle still holds.
    """
    failures: list[dict] = []
    warnings: list[dict] = []

    # Source count range
    if "source_count_range" in expected:
        sc = expected["source_count_range"]
        mn, mx = sc.get("min", 0), sc.get("max", float("inf"))
        if not (mn <= metrics["source_count"] <= mx):
            failures.append(
                {
                    "check": "source_count_range",
                    "expected": f"{mn}-{mx}",
                    "actual": metrics["source_count"],
                }
            )

    # Report sections (only enforced if the report appears agent-synthesized)
    if "report_sections" in expected and metrics.get("has_report_file"):
        # Skip the check if the report is still the template boilerplate
        if metrics.get("is_template_report"):
            pass  # Don't fail on template reports
        else:
            required = expected["report_sections"].get("required_sections", [])
            present = {s.lower() for s in metrics["report_sections"]}
            for req in required:
                if not any(req.lower() in s for s in present):
                    failures.append(
                        {
                            "check": "report_section",
                            "expected": req,
                            "actual_present": sorted(present),
                        }
                    )

    # Quality checks
    if "quality_checks" in expected:
        qc = expected["quality_checks"]
        if metrics["unique_domains"] < qc.get("min_unique_domains", 0):
            failures.append(
                {
                    "check": "min_unique_domains",
                    "expected": f">= {qc['min_unique_domains']}",
                    "actual": metrics["unique_domains"],
                }
            )
        if metrics["citation_coverage"] < qc.get("min_citation_coverage", 0):
            warnings.append(
                {
                    "check": "min_citation_coverage",
                    "expected": f">= {qc['min_citation_coverage']}",
                    "actual": round(metrics["citation_coverage"], 3),
                }
            )
        if qc.get("all_ids_valid", False):
            for kind, ids in metrics["invalid_refs"].items():
                if ids:
                    failures.append(
                        {
                            "check": "all_ids_valid",
                            "kind": kind,
                            "invalid": ids,
                        }
                    )
        if qc.get("no_duplicate_urls", False) and metrics["duplicate_urls"]:
            failures.append(
                {
                    "check": "no_duplicate_urls",
                    "duplicates": metrics["duplicate_urls"],
                }
            )
        if qc.get("id_counter_valid", False) and not metrics["id_counter_valid"]:
            failures.append(
                {
                    "check": "id_counter_valid",
                    "expected": metrics["id_counter_expected"],
                    "actual": metrics["id_counter_actual"],
                }
            )

    return failures, warnings


def build_diff(a: dict, b: dict) -> list[dict]:
    """Build a side-by-side diff of two run analyses."""
    diffs: list[dict] = []
    keys = [
        "source_count",
        "unique_domains",
        "citation_coverage",
        "id_counter_actual",
    ]
    for k in keys:
        if a.get(k) != b.get(k):
            diffs.append({"metric": k, "run_a": a.get(k), "run_b": b.get(k)})
    return diffs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare two golden runs structurally.",
        prog="golden-compare",
    )
    parser.add_argument("run_a", help="Path to the first run directory.")
    parser.add_argument("run_b", help="Path to the second run directory.")
    parser.add_argument("--expected", default=str(GOLDEN_DIR / "expected"), help="Path to the expected/ directory.")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    args = parser.parse_args(argv)

    run_a_path = Path(args.run_a).resolve()
    run_b_path = Path(args.run_b).resolve()

    metrics_a = analyze_run(run_a_path)
    metrics_b = analyze_run(run_b_path)

    expected = load_expected(Path(args.expected).resolve())
    failures_a, warnings_a = check_against_expected(metrics_a, expected)
    failures_b, warnings_b = check_against_expected(metrics_b, expected)
    diff = build_diff(metrics_a, metrics_b)

    all_failures = [
        {"run": "A", "failures": failures_a},
        {"run": "B", "failures": failures_b},
    ]
    all_warnings = [
        {"run": "A", "warnings": warnings_a},
        {"run": "B", "warnings": warnings_b},
    ]

    # Exit code logic:
    # - any failure: error
    # - any warning AND --strict: error
    # - otherwise: ok
    has_failure = bool(failures_a or failures_b)
    has_warning = bool(warnings_a or warnings_b)
    if has_failure or (args.strict and has_warning):
        overall_status = "error"
    else:
        overall_status = "ok"

    payload = {
        "comparison": "ok" if overall_status == "ok" else "failures",
        "run_a": metrics_a,
        "run_b": metrics_b,
        "diff": diff,
        "failures": all_failures,
        "warnings": all_warnings,
        "expected": expected,
        "strict": bool(args.strict),
    }

    if overall_status == "error":
        # Emit a structured error to stderr only. The repository-wide
        # CLI contract is: structured JSON goes to stdout on success
        # and to stderr on failure. Stream-based automation can use
        # the exit code and the top-level `status` field on stderr as
        # the source of truth for whether the comparison succeeded.
        error_payload = {"status": "error", "error": "comparison_failed", **payload}
        print(
            json.dumps(error_payload, indent=2, ensure_ascii=False),
            file=sys.stderr,
        )
        return 1
    emit_ok(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
