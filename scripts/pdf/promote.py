#!/usr/bin/env python3
"""Atomically promote a reviewed PDF candidate without truncating an open file."""
import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

REQUIRED = (
    "page_geometry", "body_font", "margin_overflow", "sparse_pages",
    "fonts_embedded", "markdown_residue", "figure_table_counts", "visual_review",
)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    candidate = args.candidate.resolve()
    output = args.output.resolve()
    report = json.loads(args.report.read_text(encoding="utf-8-sig"))
    checks = report.get("checks", {})
    if report.get("status") != "passed" or any(checks.get(key) is not True for key in REQUIRED):
        parser.error("PDF report is not fully accepted")
    if not candidate.is_file() or sha256(candidate) != report.get("pdf_sha256"):
        parser.error("candidate PDF does not match the validated hash")
    if candidate == output:
        parser.error("candidate and final PDF paths must differ")
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix=output.stem + ".", suffix=".tmp", delete=False) as stream:
            temp = Path(stream.name)
        shutil.copyfile(candidate, temp)
        if sha256(temp) != report["pdf_sha256"]:
            raise ValueError("temporary copy hash changed")
        os.replace(temp, output)
    except (PermissionError, OSError, ValueError) as error:
        if temp and temp.exists():
            temp.unlink()
        parser.error("could not safely promote the validated PDF; candidate retained at %s (%s)" % (candidate, error))
    print(json.dumps({"status": "promoted", "pdf": str(output), "sha256": report["pdf_sha256"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
