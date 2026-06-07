"""
build_arxiv_cache.py: Manually populate the arxiv cache from a downloaded XML response.

This is a one-off workaround for flaky arxiv connectivity. The output is a
properly formatted cache file that search_arxiv.py will consume when --use-cache
is set.
"""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = REPO_ROOT / "tests" / "golden" / "cache" / "arxiv"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

QUERY = "open source large language model evaluation"
MAX_RESULTS = 4
CACHE_KEY = "e97ea4c6719f07c0"  # sha256("arxiv|<QUERY>|<MAX_RESULTS>")[:16]

ATOM = "http://www.w3.org/2005/Atom"
ARXIV = "http://arxiv.org/schemas/atom"


def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return (el.text or "").strip()


def _arxiv_id_from_entry_id(entry_id: str) -> str:
    if not entry_id:
        return ""
    if "://" in entry_id:
        entry_id = entry_id.split("://", 1)[1]
    if "/" in entry_id:
        entry_id = entry_id.split("/", 1)[1]
    if entry_id.startswith("abs/"):
        entry_id = entry_id[4:]
    if "v" in entry_id:
        last_v = entry_id.rfind("v")
        suffix = entry_id[last_v + 1:]
        if suffix.isdigit():
            entry_id = entry_id[:last_v]
    return entry_id


def main() -> int:
    xml_path = Path(r"C:\Users\Francisco\AppData\Local\Temp\opencode\arxiv.xml")
    if not xml_path.exists():
        # Fallback to WSL /tmp
        xml_path = Path("/tmp/arxiv.xml")
    if not xml_path.exists():
        print(
            f"ERROR: arxiv.xml not found. Download with:\n"
            f"  curl -s 'https://export.arxiv.org/api/query?search_query=...&max_results=4' "
            f"-o {xml_path}",
            file=sys.stderr,
        )
        return 1

    tree = ET.parse(xml_path)
    root = tree.getroot()

    results: list[dict] = []
    for entry in root.findall(f"{{{ATOM}}}entry"):
        entry_id = _text(entry.find(f"{{{ATOM}}}id"))
        arxiv_id = _arxiv_id_from_entry_id(entry_id)
        url = entry_id or f"https://arxiv.org/abs/{arxiv_id}"
        # Find PDF link
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
        for link in entry.findall(f"{{{ATOM}}}link"):
            if link.get("title") == "pdf":
                pdf_url = link.get("href", pdf_url)
                break
        title = _text(entry.find(f"{{{ATOM}}}title")).replace("\n", " ")
        summary = _text(entry.find(f"{{{ATOM}}}summary"))
        authors = ", ".join(_text(a.find(f"{{{ATOM}}}name")) for a in entry.findall(f"{{{ATOM}}}author"))
        published = _text(entry.find(f"{{{ATOM}}}published"))[:10]
        categories = [c.get("term", "") for c in entry.findall(f"{{{ATOM}}}category")]
        primary = _text(entry.find(f"{{{ARXIV}}}primary_category"))
        results.append(
            {
                "arxiv_id": arxiv_id,
                "url": url,
                "pdf_url": pdf_url,
                "title": title,
                "summary": summary,
                "authors": authors,
                "date_published": published,
                "categories": categories,
                "primary_category": primary,
            }
        )

    payload = {
        "provider": "arxiv",
        "query": QUERY,
        "max_results": MAX_RESULTS,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "result_count": len(results),
        "results": results,
    }
    out_path = CACHE_DIR / f"{CACHE_KEY}.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(results)} arxiv results to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
