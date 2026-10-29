#!/usr/bin/env python3
"""Read-only summary of pre-v3 review runs; it does not migrate or validate claims."""
import argparse
import json
import re
import sys
from pathlib import Path


def summarize(root):
    state = json.loads((root / "run-state.json").read_text(encoding="utf-8-sig"))
    version = state.get("schema_version")
    if version not in {1, 2}:
        raise ValueError("legacy audit expects schema_version 1 or 2")
    sources = state.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("sources must be a list")
    levels = [str(s.get("accessLevel", "unknown")) for s in sources if isinstance(s, dict)]
    full = sum(bool(re.search(r"(?i)\b(?:full[ -]?text|complete paper)\b", x)) for x in levels)
    limits = " ".join(str(x) for x in state.get("limitations", []))
    no_trace = bool(re.search(r"(?i)no forward/backward citation crawl", limits))
    bib = root / "07_manuscript" / "references.bib"
    refs = len(re.findall(r"(?m)^\s*@\s*(?!string\b|comment\b|preamble\b)[a-z]+\s*[{(]", bib.read_text(encoding="utf-8-sig"), re.I)) if bib.is_file() else None
    return {"status": "legacy_not_ready", "schema_version": version, "source_records": len(sources),
            "bibliography_entries": refs, "declared_fulltext_sources": full, "source_access_levels": levels,
            "forward_backward_tracking": "not_done" if no_trace else "unknown",
            "structured_coverage_ledger": (root / "04_evidence" / "coverage.json").is_file(),
            "gate_events_available": isinstance(state.get("events"), list) and bool(state["events"]),
            "note": "This is a summary of declared legacy records, not an external verification, new ledger, or migration."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-dir", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    try:
        root = a.run_dir.resolve()
        if a.output.resolve().is_relative_to(root):
            raise ValueError("legacy audit output must be outside the original run")
        report = summarize(root)
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
