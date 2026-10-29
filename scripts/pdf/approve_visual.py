#!/usr/bin/env python3
"""Record a primary-agent visual review after inspecting the PDF contact sheet."""
import argparse
import json
from pathlib import Path


REQUIRED = (
    "page_geometry", "body_font", "margin_overflow", "sparse_pages",
    "fonts_embedded", "markdown_residue", "figure_table_counts",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--notes", required=True)
    args = parser.parse_args()
    if len(args.notes.strip()) < 20:
        parser.error("provide substantive visual-review notes")
    report = json.loads(args.report.read_text(encoding="utf-8-sig"))
    if report.get("status") != "machine_passed_visual_review_pending":
        parser.error("report is not awaiting visual review")
    checks = report.get("checks", {})
    if any(checks.get(key) is not True for key in REQUIRED):
        parser.error("automated PDF checks must pass before visual approval")
    if not report.get("contact_sheet"):
        parser.error("contact sheet path is missing")
    checks["visual_review"] = True
    report["checks"] = checks
    report["visual_review_notes"] = args.notes.strip()
    report["status"] = "passed"
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "passed", "report": str(args.report)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
