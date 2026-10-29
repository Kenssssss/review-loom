#!/usr/bin/env python3
"""Check extracted PDF text for Markdown residue and expected visual captions."""
import argparse
import json
import re
from pathlib import Path

import pymupdf


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    doc = pymupdf.open(args.pdf)
    text = "\n".join(page.get_text() for page in doc)
    source = args.source.read_text(encoding="utf-8-sig")
    expected_figures = len(re.findall(r"!\[Figure\s+\d+\.", source))
    expected_tables = len(re.findall(r"(?im)^\s*(?:Table|表)\s*\d+\.", source))
    figure_numbers = sorted({int(x) for x in re.findall(r"\bFigure\s+(\d+)\.", text)})
    table_numbers = sorted({int(x) for x in re.findall(r"\bTable\s+(\d+)\.", text)})
    residue = {
        "bold_markers": len(re.findall(r"\*\*", text)),
        "raw_tex_delimiters": len(re.findall(r"\\\(|\\\)|\\\[|\\\]", text)),
        "pipe_table_rows": len(re.findall(r"(?m)^\s*\|.*\|\s*$", text)),
        "html_entities": len(re.findall(r"&(?:amp|lt|gt|quot|#\d+);", text)),
        "markdown_images": len(re.findall(r"!\[", text)),
        "pandoc_citekeys": len(re.findall(r"\[@[A-Za-z0-9_:+./-]+", text)),
    }
    checks = {
        "markdown_residue": all(value == 0 for value in residue.values()),
        "figure_table_counts": len(figure_numbers) >= expected_figures and len(table_numbers) >= expected_tables,
        "nonempty_text": len(text.strip()) > 1000,
    }
    report = {
        "status": "passed" if all(checks.values()) else "failed",
        "characters": len(text),
        "expected_figures": expected_figures,
        "rendered_figure_numbers": figure_numbers,
        "expected_tables": expected_tables,
        "rendered_table_numbers": table_numbers,
        "markdown_residue": residue,
        "checks": checks,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
