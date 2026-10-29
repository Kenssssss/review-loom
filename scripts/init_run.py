#!/usr/bin/env python3
"""Create a new isolated review workspace without overwriting an existing run."""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("name", help="ASCII slug for run directory")
    p.add_argument("--output-root", type=Path, required=True)
    p.add_argument("--topic", required=True)
    a = p.parse_args()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", a.name) or len(a.name) > 60:
        p.error("name must be a lowercase ASCII slug (up to 60 characters)")
    dest = a.output_root / a.name
    try:
        dest.mkdir(parents=True, exist_ok=False)
        for folder in ("01_plan", "02_search", "03_sources", "04_evidence", "05_sections", "06_figures", "07_manuscript", "08_audit", "submission"):
            (dest / folder).mkdir()
        state = {"schema_version": 3, "topic": a.topic, "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                 "phase": "planning", "status": "in_progress", "sections": [], "sources": [],
                 "limitations": [], "events": [], "content_generation": 0,
                 "figure_cycle": 0, "frontmatter_cycle": 0}
        (dest / "run-state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"status": "ok", "run_dir": str(dest)}, ensure_ascii=False))
        return 0
    except OSError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
