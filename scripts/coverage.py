#!/usr/bin/env python3
"""Assess a review's structured source and evidence ledger; never determine research quality."""
import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse, unquote

STATUSES = {"pending", "included", "excluded", "unverifiable"}
LEVELS = {"metadata", "abstract", "fulltext"}


def evaluate(ledger, root):
    problems, counts = [], {}
    if not isinstance(ledger, dict):
        raise ValueError("ledger must be an object")
    question_path = root.resolve() / "01_plan/core-question.json"
    if not question_path.is_file():
        raise ValueError("locked 01_plan/core-question.json is required for coverage assessment")
    question = json.loads(question_path.read_text(encoding="utf-8-sig"))
    if not isinstance(question, dict) or question.get("status") != "locked":
        raise ValueError("core question must be locked before evidence coverage is assessed")
    pilot = question.get("pilot_search")
    if not isinstance(pilot, dict) or pilot.get("decision") != "feasible" or pilot.get("artifact") != "02_search/pilot-search.md":
        raise ValueError("a feasible pilot report must be recorded before evidence coverage is assessed")
    pilot_path = (root.resolve() / pilot["artifact"]).resolve()
    if not pilot_path.is_relative_to(root.resolve()) or not pilot_path.is_file() or not pilot_path.stat().st_size:
        raise ValueError("the locked core question's pilot report must exist inside the run")
    subquestions = question.get("subquestions")
    if not isinstance(subquestions, list):
        raise ValueError("locked core question needs a subquestions list")
    subquestion_ids = [item.get("id") for item in subquestions if isinstance(item, dict)]
    if (len(subquestion_ids) != len(subquestions) or not subquestion_ids
            or any(not isinstance(x, str) or not x.strip() for x in subquestion_ids)
            or len(set(subquestion_ids)) != len(subquestion_ids)):
        raise ValueError("locked core question needs unique nonempty subquestion IDs")
    known_subquestions = set(subquestion_ids)
    mapped_subquestions = set()
    topics, candidates = ledger.get("topics"), ledger.get("candidates")
    if not isinstance(topics, list) or not topics or not isinstance(candidates, list):
        raise ValueError("topics must be nonempty and candidates must be a list")
    if not any(isinstance(t, dict) and t.get("core") is True for t in topics):
        raise ValueError("at least one core topic is required")
    topic_ids = [t.get("id") for t in topics if isinstance(t, dict)]
    if len(topic_ids) != len(topics) or any(not isinstance(x, str) or not x.strip() for x in topic_ids) or len(set(topic_ids)) != len(topic_ids):
        raise ValueError("topic IDs must be unique nonempty strings")
    ids = set()
    included_identifiers = {}
    for c in candidates:
        if not isinstance(c, dict) or not isinstance(c.get("id"), str) or not c["id"].strip() or c["id"] in ids:
            raise ValueError("candidate IDs must be unique nonempty strings")
        ids.add(c["id"])
        if c.get("status") not in STATUSES or c.get("access") not in LEVELS:
            raise ValueError("invalid candidate status or access: " + c["id"])
        if c.get("kind") not in {"primary", "review", "other"} or not isinstance(c.get("important"), bool):
            raise ValueError("candidate kind and important flag required: " + c["id"])
        t = c.get("topics")
        if not isinstance(t, list) or not t or len(set(t)) != len(t) or any(x not in topic_ids for x in t):
            raise ValueError("invalid candidate topics: " + c["id"])
        if c["status"] in {"excluded", "unverifiable"} and not str(c.get("reason", "")).strip():
            problems.append(f"{c['id']}: {c['status']} requires a reason")
        if c["status"] == "pending" and c["important"]:
            problems.append(f"{c['id']}: important candidate still pending")
        if c["status"] == "unverifiable" and c["important"]:
            problems.append(f"{c['id']}: important candidate could not be verified")
        if c["status"] == "included":
            url = c.get("verified_url", "")
            parsed = urlparse(url) if isinstance(url, str) else None
            identifier = c.get("identifier", "")
            if not isinstance(identifier, str) or not re.fullmatch(r"(?i)(?:doi:10\.\S+|arxiv:(?:\d{4}\.\d{4,5}|[a-z-]+/\d{7})(?:v\d+)?|pmid:\d+)", identifier):
                problems.append(f"{c['id']}: included candidate needs a recognized DOI, arXiv ID or PMID")
            else:
                canonical = identifier.lower()
                if canonical.startswith("doi:10.48550/arxiv."):
                    canonical = "arxiv:" + canonical[len("doi:10.48550/arxiv."):]
                if canonical.startswith("arxiv:"):
                    canonical = re.sub(r"v\d+$", "", canonical)
                if canonical in included_identifiers:
                    problems.append(f"{c['id']}: duplicate identifier with {included_identifiers[canonical]}")
                included_identifiers[canonical] = c["id"]
            if not parsed or parsed.scheme not in {"http", "https"} or not parsed.netloc:
                problems.append(f"{c['id']}: verified source URL required")
            elif isinstance(identifier, str):
                host = parsed.netloc.lower().split(":")[0]
                path = unquote(parsed.path).strip("/").lower()
                ident = identifier.lower()
                if host in {"arxiv.org", "www.arxiv.org"} and path.startswith("abs/"):
                    url_id = re.sub(r"v\d+$", "", path[4:])
                    expected = ident[len("arxiv:"):] if ident.startswith("arxiv:") else ident[len("doi:10.48550/arxiv."):] if ident.startswith("doi:10.48550/arxiv.") else None
                    if expected and re.sub(r"v\d+$", "", expected) != url_id:
                        problems.append(f"{c['id']}: arXiv URL does not match identifier")
                if host in {"doi.org", "dx.doi.org"} and ident.startswith("doi:") and path != ident[4:]:
                    problems.append(f"{c['id']}: DOI URL does not match identifier")
                if host == "pubmed.ncbi.nlm.nih.gov" and ident.startswith("pmid:") and path.split("/")[0] != ident[5:]:
                    problems.append(f"{c['id']}: PubMed URL does not match identifier")
            title, checked = c.get("title"), c.get("verified_title")
            if not isinstance(title, str) or not isinstance(checked, str) or not title.strip() or " ".join(title.casefold().split()) != " ".join(checked.casefold().split()):
                problems.append(f"{c['id']}: title and verified source title must match")
        if c["access"] == "fulltext" and c["status"] == "included":
            pointer = c.get("evidence_file", "")
            locator = c.get("locator", "")
            path = (root / pointer).resolve() if isinstance(pointer, str) and pointer else None
            if not locator or path is None or not path.is_relative_to(root.resolve()) or not path.is_file() or path.stat().st_size == 0:
                problems.append(f"{c['id']}: full-text claim requires an existing in-run evidence file and locator")
    for t in topics:
        tid = t["id"]
        if not isinstance(t.get("core"), bool):
            raise ValueError("topic core must be boolean: " + tid)
        question_ids = t.get("question_ids")
        if (not isinstance(question_ids, list) or not question_ids
                or any(not isinstance(x, str) or x not in known_subquestions for x in question_ids)
                or len(set(question_ids)) != len(question_ids)):
            problems.append(f"{tid}: topic must map to unique known core-question subquestions")
        else:
            mapped_subquestions.update(question_ids)
        queries = t.get("searches")
        if not isinstance(queries, list) or not queries:
            problems.append(f"{tid}: no source-specific search log")
        else:
            for q in queries:
                if not isinstance(q, dict) or not all(isinstance(q.get(k), str) and q[k].strip() for k in ("source", "query", "date", "status")) or q["status"] not in {"ok", "failed", "unavailable"}:
                    problems.append(f"{tid}: invalid search log entry")
            if not any(isinstance(q, dict) and q.get("status") == "ok" for q in queries):
                problems.append(f"{tid}: no successful source search")
        tracking = t.get("citation_tracking")
        if not isinstance(tracking, dict):
            problems.append(f"{tid}: missing forward/backward tracking")
        else:
            for direction in ("forward", "backward"):
                entry = tracking.get(direction)
                if not isinstance(entry, dict) or entry.get("status") not in {"done", "unavailable"} or not str(entry.get("details", "")).strip():
                    problems.append(f"{tid}: {direction} tracking incomplete")
                elif entry["status"] == "unavailable":
                    problems.append(f"{tid}: {direction} tracking unavailable; report and seek fallback")
        included = [c for c in candidates if tid in c["topics"] and c["status"] == "included"]
        primary = [c for c in included if c["kind"] == "primary"]
        fulltext = [c for c in primary if c["access"] == "fulltext"]
        counts[tid] = {"candidates": sum(tid in c["topics"] for c in candidates), "included": len(included),
                       "primary": len(primary), "primary_fulltext": len(fulltext)}
        minimum = t.get("minimum_primary", 2)
        minimum_full = t.get("minimum_fulltext", 1)
        if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 1 or not isinstance(minimum_full, int) or isinstance(minimum_full, bool) or minimum_full < 1:
            raise ValueError("minimums must be positive integers")
        if t["core"] and (minimum < 2 or minimum_full < 1) and not str(t.get("threshold_reason", "")).strip():
            raise ValueError("lower core thresholds require a reason: " + tid)
        if t["core"] and len(primary) < minimum:
            problems.append(f"{tid}: only {len(primary)} included primary studies; target {minimum}")
        if t["core"] and len(fulltext) < minimum_full:
            problems.append(f"{tid}: only {len(fulltext)} primary full-text records; target {minimum_full}")
    missing_subquestions = known_subquestions - mapped_subquestions
    if missing_subquestions:
        problems.append("no evidence-search topic maps to core-question subquestions: " + ", ".join(sorted(missing_subquestions)))
    return {"status": "ready" if not problems else "insufficient", "topic_counts": counts,
            "included_count": sum(c["status"] == "included" for c in candidates), "problems": problems,
            "note": "Thresholds and structural checks do not prove completeness, correctness or suitability for publication."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("ledger", type=Path)
    p.add_argument("--run-dir", required=True, type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    try:
        if a.ledger.resolve() == a.output.resolve():
            raise ValueError("output must not overwrite ledger")
        report = evaluate(json.loads(a.ledger.read_text(encoding="utf-8-sig")), a.run_dir.resolve())
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
        return 0 if report["status"] == "ready" else 1
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
