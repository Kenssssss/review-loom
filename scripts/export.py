#!/usr/bin/env python3
"""Validate Pandoc citation keys and render a Markdown or Word manuscript."""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def walk(value):
    if isinstance(value, dict):
        if value.get("t") == "Cite":
            for citation in value["c"][0]:
                yield citation["citationId"]
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("--bibliography", required=True, type=Path)
    p.add_argument("--csl", type=Path, default=Path(__file__).resolve().parents[1] / "assets" / "generic-numeric.csl",
                   help="CSL file; default is generic numeric style, not a journal template")
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    if args.output.suffix.lower() not in {".md", ".docx"}:
        p.error("output must have .md or .docx extension")
    if args.output.resolve() in {args.source.resolve(), args.bibliography.resolve(), args.csl.resolve()}:
        p.error("output must not overwrite the source, bibliography, or CSL")
    if args.output.suffix.lower() == ".md" and args.output.parent.resolve() != args.source.parent.resolve():
        p.error("Markdown output must be beside the source so relative image paths remain valid")
    try:
        bib = args.bibliography.read_text(encoding="utf-8")
        keys = re.findall(r"(?im)^\s*@\s*(?!string\b|comment\b|preamble\b)[a-z]+\s*[{(]\s*([^\s,]+)\s*,", bib)
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        if duplicates:
            raise ValueError("duplicate BibTeX keys: " + ", ".join(duplicates))
        parse = subprocess.run(["pandoc", str(args.source), "-t", "json", "--fail-if-warnings"], capture_output=True, text=True, encoding="utf-8")
        if parse.returncode:
            raise ValueError("pandoc parsing failed: " + parse.stderr.strip())
        cited = set(walk(json.loads(parse.stdout))) - {"*"}
        missing = sorted(cited - set(keys))
        if missing:
            raise ValueError("missing citation keys: " + ", ".join(missing))
        if not args.csl.is_file():
            raise ValueError("CSL style not found")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # Pandoc infers the format from the requested extension; avoid claiming PDF support.
        with tempfile.TemporaryDirectory(dir=args.output.parent) as temp:
            temporary_output = Path(temp) / ("result" + args.output.suffix)
            run = subprocess.run(["pandoc", str(args.source), "--citeproc", "--bibliography", str(args.bibliography),
                                  "--csl", str(args.csl), "--resource-path", str(args.source.parent.resolve()) + os.pathsep + str(Path.cwd()),
                                  "--fail-if-warnings", "-o", str(temporary_output)],
                                 capture_output=True, text=True, encoding="utf-8")
            if run.returncode:
                raise ValueError("pandoc export failed: " + run.stderr.strip())
            if not temporary_output.is_file() or temporary_output.stat().st_size == 0:
                raise ValueError("pandoc did not produce an output")
            temporary_output.replace(args.output)
        print(json.dumps({"status": "ok", "citation_keys": sorted(cited), "output": str(args.output)}))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
