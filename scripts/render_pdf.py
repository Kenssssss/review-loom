#!/usr/bin/env python3
"""Build a citeproc-resolved Markdown manuscript and a QA-checked PDF candidate."""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = SKILL_ROOT / "scripts" / "pdf"
ASSETS = SKILL_ROOT / "assets" / "pdf"
MATH = re.compile(r"\\\(.*?\\\)|\\\[.*?\\\]|\$\$.*?\$\$|\$(?!\s)(?:\\.|[^$\n])+\$", re.S)


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def require_runtime():
    missing = []
    if not shutil.which("pandoc"):
        missing.append("Pandoc executable")
    for module in ("playwright", "pymupdf", "PIL"):
        try:
            __import__(module)
        except ImportError:
            missing.append("Python package " + module)
    if missing:
        raise RuntimeError("missing PDF dependencies: " + ", ".join(missing))


def run(command, *, cwd=None, capture=False):
    result = subprocess.run(
        [str(x) for x in command],
        cwd=str(cwd) if cwd else None,
        capture_output=capture,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if capture:
        return result
    if result.returncode:
        raise RuntimeError("command failed (%d): %s" % (result.returncode, " ".join(map(str, command))))
    return result


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="accepted assembled Markdown with stable citation keys")
    parser.add_argument("--bibliography", type=Path, help="curated BibTeX file; resolves citation keys first")
    parser.add_argument("--csl", type=Path, default=SKILL_ROOT / "assets" / "generic-numeric.csl")
    parser.add_argument("--output", type=Path, help="final PDF path; promotion is a separate reviewed step")
    parser.add_argument("--readable-output", type=Path, help="citation-resolved Markdown path")
    parser.add_argument("--build-dir", type=Path, help="defaults to SOURCE parent/pdf-build")
    parser.add_argument("--run-root", type=Path, help="defaults to SOURCE grandparent")
    args = parser.parse_args()
    try:
        require_runtime()
        source = args.source.resolve()
        if not source.is_file() or source.suffix.lower() != ".md":
            raise ValueError("source must be an existing Markdown file")
        output = (args.output or source.with_name("review.pdf")).resolve()
        readable = (args.readable_output or source.with_name("review.final.md")).resolve()
        build = (args.build_dir or source.parent / "pdf-build").resolve()
        run_root = (args.run_root or source.parent.parent).resolve()
        if source == readable or readable.suffix.lower() != ".md":
            raise ValueError("readable output must be a distinct Markdown file")
        if not output.is_relative_to(run_root) or not build.is_relative_to(run_root):
            raise ValueError("final PDF and build directory must stay inside the run directory")
        if args.bibliography:
            bibliography = args.bibliography.resolve()
            if readable.parent != source.parent:
                raise ValueError("citation-resolved Markdown must be beside its source so image paths remain valid")
            csl = args.csl.resolve()
            export = SKILL_ROOT / "scripts" / "export.py"
            run([
                sys.executable, export, source,
                "--bibliography", bibliography,
                "--csl", csl,
                "--output", readable,
            ])
        else:
            shutil.copyfile(source, readable)
        build.mkdir(parents=True, exist_ok=True)
        prepared = build / "review.build.md"
        html_file = build / "doc.html"
        candidate = build / "out.pdf"
        page_dir = build / "pages"
        metric_path = build / "page-metrics.json"
        content_path = build / "content-validation.json"
        contact_path = build / "contact-sheet.png"
        final_report_path = build / "pdf-validation.json"
        run([sys.executable, PDF_DIR / "prepare.py", "--source", readable, "--output", prepared])
        resource_path = str(source.parent.resolve()) + os.pathsep + str(Path.cwd())
        pandoc = [
            "pandoc", prepared,
            "--from=markdown+implicit_figures+pipe_tables+tex_math_dollars+tex_math_single_backslash+yaml_metadata_block",
            "--to=html5", "--standalone", "--mathml",
            "--resource-path", resource_path,
            "--output", html_file,
        ]
        run(pandoc, cwd=source.parent)
        run([
            sys.executable, PDF_DIR / "post.py",
            "--html", html_file,
            "--base-dir", source.parent,
            "--authored-css", ASSETS / "authored.css",
            "--print-css", ASSETS / "print.css",
        ])
        source_text = readable.read_text(encoding="utf-8-sig")
        has_math = bool(MATH.search(source_text))
        print_args = [sys.executable, PDF_DIR / "print.py", "--html", html_file, "--output", candidate]
        run(print_args)

        metric_args = [
            sys.executable, PDF_DIR / "check.py",
            "--pdf", candidate, "--page-dir", page_dir, "--report", metric_path,
        ]
        if has_math:
            metric_args.append("--require-math-font")
        metrics_result = run(metric_args, capture=True)
        metrics = load_json(metric_path)

        validation_result = run([
            sys.executable, PDF_DIR / "validate.py",
            "--pdf", candidate, "--source", readable, "--report", content_path,
        ], capture=True)
        content = load_json(content_path)
        run([
            sys.executable, PDF_DIR / "contact.py",
            "--pages-dir", page_dir, "--output", contact_path,
        ])

        machine_checks = {
            "page_geometry": metrics["checks"].get("page_geometry") is True,
            "body_font": metrics["checks"].get("body_font") is True,
            "margin_overflow": metrics["checks"].get("margin_overflow") is True,
            "sparse_pages": metrics["checks"].get("sparse_pages") is True,
            "fonts_embedded": metrics["checks"].get("fonts_embedded") is True,
            "markdown_residue": content["checks"].get("markdown_residue") is True,
            "figure_table_counts": content["checks"].get("figure_table_counts") is True,
        }
        passed = all(machine_checks.values()) and metrics_result.returncode == 0 and validation_result.returncode == 0
        report = {
            "status": "machine_passed_visual_review_pending" if passed else "failed",
            "pdf_candidate": str(candidate.relative_to(run_root)).replace("\\", "/"),
            "pdf_sha256": digest(candidate),
            "readable_manuscript": str(readable.relative_to(run_root)).replace("\\", "/"),
            "readable_manuscript_sha256": digest(readable),
            "contact_sheet": str(contact_path.relative_to(run_root)).replace("\\", "/"),
            "page_metrics": str(metric_path.relative_to(run_root)).replace("\\", "/"),
            "content_validation": str(content_path.relative_to(run_root)).replace("\\", "/"),
            "checks": {**machine_checks, "visual_review": False},
            "visual_review_notes": "",
            "pages": metrics.get("pages"),
            "body_font_pt": metrics.get("dominant_font_pt"),
            "figure_numbers": content.get("rendered_figure_numbers"),
            "table_numbers": content.get("rendered_table_numbers"),
        }
        final_report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
        if not passed:
            raise RuntimeError("PDF candidate failed one or more automated checks; inspect pdf-build reports")
        print("Review the contact sheet, then run approve_visual.py and promote.py to create the final PDF.")
    except (OSError, ValueError, RuntimeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
