#!/usr/bin/env python3
"""Enforce ordinary Review Loom phase and serial chapter transitions in a run state."""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import struct
import sys
import tempfile
from pathlib import Path

from coverage import evaluate

PHASES = ["planning", "searching", "evidence", "outline", "drafting", "figures", "frontmatter", "audit", "complete"]
MIN_FIGURES = 5
MIN_TABLES = 4
STYLE_REFERENCE_DIR = Path(__file__).resolve().parents[1] / "assets" / "Reference Figures"
FIGURE_MARKER = re.compile(r"!\[Figure\s+(\d+)\.\s+.*?\]\(<([^>]+)>\)", re.S)
TABLE_CAPTION = re.compile(r"^\s*Table\s+(\d+)\.\s+\S.*$")
TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def artifact(root, relative):
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError("artifact path is required")
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file() or not path.stat().st_size:
        raise ValueError("artifact must be a nonempty file within run: " + relative)
    return path


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate_core_question(root, expected_status):
    path = artifact(root, "01_plan/core-question.json")
    question = load_json(path)
    if not isinstance(question, dict):
        raise ValueError("core-question.json must contain a JSON object")
    if question.get("status") != expected_status:
        raise ValueError("core question must have status %r" % expected_status)
    for key in ("core_question", "working_title", "focus_rationale"):
        if not isinstance(question.get(key), str) or not question[key].strip():
            raise ValueError("core question needs a nonempty %s" % key)
    dimensions = question.get("dimensions")
    required_dimensions = ("task_or_context", "phenomenon_or_method", "outcome_or_tradeoff", "conditions_or_boundaries")
    if not isinstance(dimensions, dict) or any(not isinstance(dimensions.get(key), str) or not dimensions[key].strip()
                                               for key in required_dimensions):
        raise ValueError("core question needs concrete task, focus, outcome and condition dimensions")
    for key in ("include_boundaries", "exclude_boundaries"):
        values = question.get(key)
        if not isinstance(values, list) or not values or any(not isinstance(x, str) or not x.strip() for x in values):
            raise ValueError("core question needs nonempty %s" % key)
    subquestions = question.get("subquestions")
    if not isinstance(subquestions, list) or len(subquestions) < 2:
        raise ValueError("core question must be decomposed into at least two subquestions")
    ids = []
    for item in subquestions:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"].strip():
            raise ValueError("each subquestion needs a unique nonempty id")
        if not isinstance(item.get("question"), str) or not item["question"].strip():
            raise ValueError("each subquestion needs a focused question")
        concepts = item.get("search_concepts")
        if not isinstance(concepts, list) or len(concepts) < 2 or any(not isinstance(x, str) or not x.strip() for x in concepts):
            raise ValueError("each subquestion needs at least two search concepts")
        ids.append(item["id"])
    if len(set(ids)) != len(ids):
        raise ValueError("subquestion IDs must be unique")
    if expected_status == "locked":
        pilot = question.get("pilot_search")
        if not isinstance(pilot, dict) or pilot.get("decision") != "feasible":
            raise ValueError("core question can be locked only after a feasible pilot search")
        if pilot.get("artifact") != "02_search/pilot-search.md":
            raise ValueError("pilot search report must be saved at 02_search/pilot-search.md")
        for key in ("volume_assessment", "existing_reviews", "synthesis_gap"):
            if not isinstance(pilot.get(key), str) or not pilot[key].strip():
                raise ValueError("pilot search needs a nonempty %s assessment" % key)
        artifact(root, pilot.get("artifact"))
        if pilot.get("prior_reviews_artifact") != "02_search/prior-reviews.json":
            raise ValueError("locked question must link 02_search/prior-reviews.json")
        validate_prior_reviews(root, pilot["prior_reviews_artifact"])
    return question, path


def validate_prior_reviews(root, relative="02_search/prior-reviews.json"):
    path = artifact(root, relative)
    report = load_json(path)
    if not isinstance(report, dict) or report.get("status") != "reviewed":
        raise ValueError("prior-review comparison must have status 'reviewed'")
    searches = report.get("searches")
    if not isinstance(searches, list) or not searches:
        raise ValueError("prior-review comparison needs recorded searches")
    successful = 0
    for item in searches:
        if not isinstance(item, dict) or any(not isinstance(item.get(k), str) or not item[k].strip()
                                             for k in ("source", "query", "date")):
            raise ValueError("each prior-review search needs source, query and date")
        if item.get("status") not in {"ok", "failed", "unavailable"}:
            raise ValueError("prior-review search status must be ok, failed or unavailable")
        count = item.get("results_screened")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError("prior-review search needs a nonnegative results_screened count")
        successful += item["status"] == "ok"
    if successful == 0:
        raise ValueError("prior-review comparison needs at least one successful search")
    reviews = report.get("reviews")
    if not isinstance(reviews, list):
        raise ValueError("prior-review comparison reviews must be an array")
    review_ids = set()
    for review in reviews:
        required = ("id", "title", "year", "url", "scope", "coverage_period", "organizing_framework", "limitations")
        if not isinstance(review, dict) or any(not str(review.get(k, "")).strip() for k in required):
            raise ValueError("each prior review needs identity, scope, coverage, framework and limitations")
        if review["id"] in review_ids:
            raise ValueError("prior-review IDs must be unique")
        review_ids.add(review["id"])
    if not reviews and not str(report.get("no_close_review_reason", "")).strip():
        raise ValueError("when no close prior review is found, explain the search result")
    for key in ("contribution_statement", "difference_basis"):
        if not isinstance(report.get(key), str) or not report[key].strip():
            raise ValueError("prior-review comparison needs a nonempty %s" % key)
    return path


def validate_evidence_synthesis(root, question, ledger):
    appraisal_path = artifact(root, "04_evidence/appraisal.json")
    appraisal = load_json(appraisal_path)
    criteria = appraisal.get("criteria") if isinstance(appraisal, dict) else None
    assessments = appraisal.get("assessments") if isinstance(appraisal, dict) else None
    if not isinstance(criteria, list) or not criteria:
        raise ValueError("appraisal.json needs question-specific criteria")
    criterion_ids = set()
    for criterion in criteria:
        if not isinstance(criterion, dict) or not isinstance(criterion.get("id"), str) or not criterion["id"].strip():
            raise ValueError("each appraisal criterion needs a unique ID")
        if criterion["id"] in criterion_ids:
            raise ValueError("appraisal criterion IDs must be unique")
        criterion_ids.add(criterion["id"])
        for key in ("name", "definition", "relevance"):
            if not isinstance(criterion.get(key), str) or not criterion[key].strip():
                raise ValueError("each appraisal criterion needs name, definition and relevance")
    if not isinstance(assessments, list):
        raise ValueError("appraisal.json assessments must be an array")
    ledger_data = load_json(ledger)
    candidates = {c["id"]: c for c in ledger_data["candidates"]}
    important_primary = {cid for cid, c in candidates.items()
                         if c.get("status") == "included" and c.get("kind") == "primary" and c.get("important") is True}
    assessed_primary = set()
    seen_assessments = set()
    ratings = {"strong", "qualified", "weak", "not_assessable", "not_applicable"}
    for item in assessments:
        if not isinstance(item, dict):
            raise ValueError("each appraisal assessment must be an object")
        cid, criterion_id = item.get("candidate_id"), item.get("criterion_id")
        if cid not in important_primary or criterion_id not in criterion_ids:
            raise ValueError("appraisal assessment must refer to an important included primary study and a known criterion")
        if (cid, criterion_id) in seen_assessments:
            raise ValueError("duplicate study/criterion appraisal")
        seen_assessments.add((cid, criterion_id))
        assessed_primary.add(cid)
        if item.get("rating") not in ratings:
            raise ValueError("appraisal rating must be strong, qualified, weak, not_assessable or not_applicable")
        for key in ("rationale", "locator"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError("each appraisal assessment needs a rationale and observed locator")
    missing_assessment = important_primary - assessed_primary
    if missing_assessment:
        raise ValueError("important primary studies need at least one appraisal: " + ", ".join(sorted(missing_assessment)))

    matrix_path = artifact(root, "04_evidence/synthesis-matrix.json")
    matrix = load_json(matrix_path)
    units = matrix.get("units") if isinstance(matrix, dict) else None
    gaps = matrix.get("gaps") if isinstance(matrix, dict) else None
    if not isinstance(units, list) or not units:
        raise ValueError("synthesis-matrix.json needs at least one synthesis unit")
    if not isinstance(gaps, list) or not gaps:
        raise ValueError("synthesis-matrix.json needs evidence-grounded research gaps")
    subquestion_ids = {x["id"] for x in question["subquestions"]}
    unit_ids, mapped_questions = set(), set()
    valid_relations = {"supports", "qualifies", "contradicts"}
    valid_confidence = {"strong", "moderate", "tentative"}
    unit_sources = {}
    for unit in units:
        if not isinstance(unit, dict) or not isinstance(unit.get("id"), str) or not unit["id"].strip():
            raise ValueError("each synthesis unit needs a unique ID")
        if unit["id"] in unit_ids:
            raise ValueError("synthesis unit IDs must be unique")
        unit_ids.add(unit["id"])
        qids = unit.get("question_ids")
        if not isinstance(qids, list) or not qids or any(qid not in subquestion_ids for qid in qids):
            raise ValueError("each synthesis unit must map to known core-question subquestions")
        mapped_questions.update(qids)
        for key in ("claim", "counterevidence_analysis", "confidence_rationale"):
            if not isinstance(unit.get(key), str) or not unit[key].strip():
                raise ValueError("each synthesis unit needs a claim, counterevidence analysis and confidence rationale")
        for key in ("comparison_axes", "conditions"):
            if not isinstance(unit.get(key), list) or not unit[key] or any(not isinstance(x, str) or not x.strip() for x in unit[key]):
                raise ValueError("each synthesis unit needs nonempty comparison_axes and conditions")
        if unit.get("confidence") not in valid_confidence:
            raise ValueError("synthesis confidence must be strong, moderate or tentative")
        evidence = unit.get("evidence")
        if not isinstance(evidence, list):
            raise ValueError("synthesis unit evidence must be an array")
        sources = set()
        for item in evidence:
            if not isinstance(item, dict) or item.get("candidate_id") not in candidates:
                raise ValueError("synthesis evidence must refer to a known candidate")
            candidate = candidates[item["candidate_id"]]
            if candidate.get("status") != "included":
                raise ValueError("synthesis evidence must refer to an included candidate")
            if item.get("relation") not in valid_relations or not isinstance(item.get("locator"), str) or not item["locator"].strip():
                raise ValueError("synthesis evidence needs a valid relation and observed locator")
            sources.add(item["candidate_id"])
        if len(sources) < 2:
            raise ValueError("each synthesis unit must compare at least two distinct included papers")
        unit_sources[unit["id"]] = sources
    if mapped_questions != subquestion_ids:
        raise ValueError("synthesis matrix must cover every locked subquestion")

    gap_ids = set()
    for gap in gaps:
        if not isinstance(gap, dict) or not isinstance(gap.get("id"), str) or not gap["id"].strip():
            raise ValueError("each evidence gap needs a unique ID")
        if gap["id"] in gap_ids:
            raise ValueError("research gap IDs must be unique")
        gap_ids.add(gap["id"])
        for key in ("description", "research_direction"):
            if not isinstance(gap.get(key), str) or not gap[key].strip():
                raise ValueError("each research gap needs a description and a concrete direction")
        bases = gap.get("basis_unit_ids")
        if not isinstance(bases, list) or not bases or any(x not in unit_ids for x in bases):
            raise ValueError("each research gap must point to known synthesis units")

    review_path = artifact(root, "08_audit/evidence-synthesis-review.json")
    review = load_json(review_path)
    if not isinstance(review, dict) or review.get("decision") != "accept" or not str(review.get("reason", "")).strip():
        raise ValueError("evidence-synthesis-review.json must accept the appraisal and synthesis artifacts")
    expected_inputs = {"coverage_sha256": digest(ledger), "evidence_sha256": fingerprint(evidence_snapshot(root, ledger)),
                       "appraisal_sha256": digest(appraisal_path), "synthesis_matrix_sha256": digest(matrix_path)}
    if review.get("inputs") != expected_inputs:
        raise ValueError("evidence-synthesis review is stale or not bound to current appraisal, matrix and coverage")
    checks = review.get("checks", {})
    required_checks = ("criteria_fit", "source_grounding", "cross_study_synthesis", "counterevidence", "contribution_support")
    if any(checks.get(key) is not True for key in required_checks):
        raise ValueError("evidence-synthesis review must pass all five primary-agent checks")
    findings = review.get("findings")
    if not isinstance(findings, list) or not findings or any(not isinstance(x, str) or not x.strip() for x in findings):
        raise ValueError("evidence-synthesis review needs substantive findings")
    return {"appraisal": appraisal_path, "matrix": matrix_path, "review": review_path,
            "unit_ids": unit_ids, "gap_ids": gap_ids,
            "hashes": {"appraisal_sha256": digest(appraisal_path), "synthesis_matrix_sha256": digest(matrix_path),
                       "synthesis_review_sha256": digest(review_path)}}


def assert_question_unchanged(root, state):
    question, path = validate_core_question(root, "locked")
    scope = artifact(root, "01_plan/scope.md")
    pilot = artifact(root, question["pilot_search"]["artifact"])
    prior_reviews = artifact(root, question["pilot_search"]["prior_reviews_artifact"])
    if (digest(path) != state.get("core_question_sha256")
            or digest(scope) != state.get("scope_sha256")
            or digest(pilot) != state.get("pilot_search_sha256")
            or digest(prior_reviews) != state.get("prior_reviews_sha256")):
        raise ValueError("locked question, scope, pilot or prior-review comparison changed; start a fresh run and redo discovery")
    return question


def png_dimensions(path):
    with path.open("rb") as f:
        header = f.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError("figure image must be a valid PNG: " + str(path))
    width, height = struct.unpack(">II", header[16:24])
    if width < 1 or height < 1:
        raise ValueError("figure PNG has invalid dimensions: " + str(path))
    return width, height


def coverage(root):
    ledger = artifact(root, "04_evidence/coverage.json")
    result = evaluate(load_json(ledger), root)
    if result["status"] != "ready":
        raise ValueError("coverage insufficient: " + "; ".join(result["problems"]))
    return ledger


def evidence_snapshot(root, ledger):
    data = load_json(ledger)
    paths = sorted({c["evidence_file"] for c in data["candidates"]
                    if c.get("status") == "included" and c.get("access") == "fulltext"})
    return {path: digest(artifact(root, path)) for path in paths}


def assert_evidence_unchanged(root, state):
    question = assert_question_unchanged(root, state)
    ledger = coverage(root)
    search_log = artifact(root, "02_search/search-log.md")
    if (digest(ledger) != state.get("coverage_sha256")
            or evidence_snapshot(root, ledger) != state.get("evidence_hashes")
            or digest(search_log) != state.get("search_log_sha256")):
        raise ValueError("search coverage or full-text evidence changed; cancel active work and reassess affected sections")
    if state.get("synthesis_artifact_hashes"):
        synthesis = validate_evidence_synthesis(root, question, ledger)
        if synthesis["hashes"] != state["synthesis_artifact_hashes"]:
            raise ValueError("appraisal or synthesis artifacts changed; refresh their primary-agent review and reassess affected sections")


def snapshot(root, review_path, paths):
    return {"review": str(review_path.relative_to(root)), "review_sha256": digest(review_path),
            "artifacts": {p: digest(artifact(root, p)) for p in paths}}


def assert_snapshot(root, state, key):
    value = state.get(key)
    if not isinstance(value, dict):
        raise ValueError("missing accepted snapshot: " + key)
    if digest(artifact(root, value["review"])) != value["review_sha256"]:
        raise ValueError("accepted review changed: " + key)
    for path, expected in value["artifacts"].items():
        if digest(artifact(root, path)) != expected:
            raise ValueError("accepted artifact changed: " + path)


def assert_accepted_unchanged(root, state):
    for section in state["sections"]:
        if section["state"] == "accepted":
            p = artifact(root, section["artifact"])
            if digest(p) != section["artifact_sha256"]:
                raise ValueError("accepted section changed; invalidate it first: " + section["id"])


def accepted_body_fingerprint(root, state):
    assert_evidence_unchanged(root, state)
    if not state.get("sections") or any(s.get("state") != "accepted" for s in state["sections"]):
        raise ValueError("every section must be accepted before downstream work")
    assert_accepted_unchanged(root, state)
    body = [{"id": s["id"], "artifact": s["artifact"], "sha256": s["artifact_sha256"]}
            for s in state["sections"]]
    return fingerprint({"content_generation": state.get("content_generation", 0),
                        "coverage_sha256": state["coverage_sha256"],
                        "evidence_hashes": state["evidence_hashes"], "sections": body})


def figure_fingerprint(state):
    snap = state.get("figure_snapshot")
    if not isinstance(snap, dict):
        raise ValueError("missing accepted snapshot: figure_snapshot")
    return fingerprint(snap)


def require_binding(report, expected, label):
    for key, value in expected.items():
        if report.get(key) != value:
            raise ValueError(f"{label} is stale or missing workflow binding: {key}")


def begin_figure_cycle(root, state):
    state["figure_cycle"] = state.get("figure_cycle", 0) + 1
    state["figure_inputs"] = {"generation": state.get("content_generation", 0),
                              "cycle": state["figure_cycle"],
                              "body_fingerprint": accepted_body_fingerprint(root, state)}
    state.pop("figure_snapshot", None)
    state.pop("frontmatter_inputs", None)
    state.pop("frontmatter_snapshot", None)


def begin_frontmatter_cycle(root, state):
    state["frontmatter_cycle"] = state.get("frontmatter_cycle", 0) + 1
    state["frontmatter_inputs"] = {"generation": state.get("content_generation", 0),
                                   "cycle": state["frontmatter_cycle"],
                                   "body_fingerprint": accepted_body_fingerprint(root, state),
                                   "figure_fingerprint": figure_fingerprint(state)}
    state.pop("frontmatter_snapshot", None)


def clear_downstream(state, *, new_content=False):
    if new_content:
        state["content_generation"] = state.get("content_generation", 0) + 1
    for key in ("figure_inputs", "figure_snapshot", "frontmatter_inputs", "frontmatter_snapshot"):
        state.pop(key, None)


def validate_visual_counts(root, manuscript):
    path = artifact(root, manuscript)
    if path.suffix.lower() != ".md":
        raise ValueError("visual-count audit requires the assembled Markdown manuscript as the canonical source")
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    text = "\n".join(lines)
    figure_matches = list(FIGURE_MARKER.finditer(text))
    figure_numbers = [int(m.group(1)) for m in figure_matches]
    if len(figure_numbers) < MIN_FIGURES:
        raise ValueError(f"final manuscript has {len(figure_numbers)} numbered figures; minimum is {MIN_FIGURES}")
    if figure_numbers != list(range(1, len(figure_numbers) + 1)):
        raise ValueError("figure numbers must be unique and contiguous from 1 in manuscript order")
    figure_paths = []
    for match in figure_matches:
        image_path = (path.parent / match.group(2)).resolve()
        if not image_path.is_relative_to(root) or not image_path.is_file() or not image_path.stat().st_size:
            raise ValueError("numbered figure image must be a nonempty file inside the run: " + match.group(2))
        figure_paths.append(image_path)
    if len(set(figure_paths)) != len(figure_paths):
        raise ValueError("each numbered figure must use a distinct image file")

    table_numbers = []
    for index, line in enumerate(lines):
        if not TABLE_SEPARATOR.fullmatch(line):
            continue
        header_index = index - 1
        while header_index >= 0 and not lines[header_index].strip():
            header_index -= 1
        if header_index < 0 or "|" not in lines[header_index]:
            continue
        caption_index = header_index - 1
        while caption_index >= 0 and not lines[caption_index].strip():
            caption_index -= 1
        if caption_index < 0:
            continue
        caption = TABLE_CAPTION.fullmatch(lines[caption_index])
        if not caption:
            continue
        row_index = index + 1
        while row_index < len(lines) and not lines[row_index].strip():
            row_index += 1
        if row_index >= len(lines) or "|" not in lines[row_index]:
            continue
        table_numbers.append(int(caption.group(1)))
    if len(table_numbers) < MIN_TABLES:
        raise ValueError(f"final manuscript has {len(table_numbers)} captioned Markdown tables; minimum is {MIN_TABLES}")
    if table_numbers != list(range(1, len(table_numbers) + 1)):
        raise ValueError("table numbers must be unique and contiguous from 1 in manuscript order")
    return figure_paths, len(table_numbers)


def validate_section_manifest(root, question, synthesis_unit_ids):
    artifact(root, "01_plan/outline.md")
    manifest = load_json(artifact(root, "01_plan/sections.json"))
    if not isinstance(manifest, list) or not manifest:
        raise ValueError("sections.json must be a nonempty array")
    all_ids = [x.get("id") for x in manifest if isinstance(x, dict)]
    if len(all_ids) != len(manifest) or len(set(all_ids)) != len(all_ids):
        raise ValueError("section IDs must be unique")
    seen, mapped_questions, mapped_synthesis = set(), set(), set()
    subquestion_ids = {item["id"] for item in question["subquestions"]}
    for section in manifest:
        sid = section.get("id")
        if not isinstance(sid, str) or not sid.strip() or sid in seen:
            raise ValueError("section IDs must be unique nonempty strings")
        if not isinstance(section.get("priority"), int) or isinstance(section.get("priority"), bool) or section["priority"] < 1:
            raise ValueError("each section needs a positive integer priority")
        if not isinstance(section.get("reason"), str) or not section["reason"].strip():
            raise ValueError("each section needs a priority rationale")
        question_ids = section.get("question_ids")
        if not isinstance(question_ids, list) or not question_ids or any(x not in subquestion_ids for x in question_ids):
            raise ValueError("each section must map to one or more known core-question subquestions: " + sid)
        synthesis_ids = section.get("synthesis_ids")
        if not isinstance(synthesis_ids, list) or not synthesis_ids or any(x not in synthesis_unit_ids for x in synthesis_ids):
            raise ValueError("each section must map to one or more accepted synthesis units: " + sid)
        mapped_questions.update(question_ids)
        mapped_synthesis.update(synthesis_ids)
        depends = section.get("depends_on", [])
        if not isinstance(depends, list) or any(d not in seen for d in depends):
            raise ValueError("dependencies must precede dependent section: " + sid)
        eligible = [x for x in manifest if x.get("id") not in seen and isinstance(x.get("depends_on", []), list)
                    and set(x.get("depends_on", [])).issubset(seen) and isinstance(x.get("priority"), int)
                    and not isinstance(x.get("priority"), bool)]
        if eligible and section["priority"] > min(x["priority"] for x in eligible):
            raise ValueError("higher-priority eligible section must come first: " + sid)
        seen.add(sid)
    if subquestion_ids - mapped_questions:
        raise ValueError("outline leaves core-question subquestions unanswered: " + ", ".join(sorted(subquestion_ids - mapped_questions)))
    if synthesis_unit_ids - mapped_synthesis:
        raise ValueError("outline leaves synthesis units unmapped: " + ", ".join(sorted(synthesis_unit_ids - mapped_synthesis)))
    return manifest


def validate_research_agenda(root, state):
    if not isinstance(state.get("synthesis_artifact_hashes"), dict):
        raise ValueError("missing accepted synthesis artifacts for research agenda audit")
    matrix_path = artifact(root, "04_evidence/synthesis-matrix.json")
    frontmatter = load_json(artifact(root, "07_manuscript/frontmatter-review.json"))
    conclusion_path = artifact(root, frontmatter.get("conclusion"))
    report_path = artifact(root, "08_audit/research-agenda-review.json")
    report = load_json(report_path)
    if not isinstance(report, dict) or report.get("accepted") is not True or not str(report.get("reason", "")).strip():
        raise ValueError("research-agenda-review.json must be accepted with a reason")
    if report.get("conclusion") != frontmatter.get("conclusion"):
        raise ValueError("research agenda review must name the accepted conclusion")
    expected = {"synthesis_matrix_sha256": digest(matrix_path), "conclusion_sha256": digest(conclusion_path)}
    if report.get("inputs") != expected:
        raise ValueError("research agenda review is stale or not bound to the current synthesis matrix and conclusion")
    directions = report.get("directions")
    if not isinstance(directions, list):
        raise ValueError("research agenda review directions must be an array")
    required_gap_ids = {item["id"] for item in load_json(matrix_path)["gaps"]}
    mapped = set()
    for item in directions:
        if not isinstance(item, dict) or item.get("gap_id") not in required_gap_ids:
            raise ValueError("each research direction must map to a known synthesis-matrix gap")
        for key in ("recommendation", "evidence_basis", "conclusion_locator"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError("each research direction needs a recommendation, evidence basis and conclusion locator")
        mapped.add(item["gap_id"])
    if required_gap_ids - mapped:
        raise ValueError("conclusion research agenda omits evidence gaps: " + ", ".join(sorted(required_gap_ids - mapped)))
    return report_path


def event(state, action, **details):
    state.setdefault("events", []).append({"seq": len(state.get("events", [])) + 1,
        "at": dt.datetime.now(dt.timezone.utc).isoformat(), "action": action, **details})


def save(path, state):
    state["revision"] = state.get("revision", 0) + 1
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp") as f:
        tmp = Path(f.name)
        json.dump(state, f, ensure_ascii=False, indent=2)
    try:
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def advance(root, state, target):
    current = state["phase"]
    if current not in PHASES or target not in PHASES or PHASES.index(target) != PHASES.index(current) + 1:
        raise ValueError(f"invalid phase transition: {current} -> {target}")
    if target == "searching":
        artifact(root, "01_plan/scope.md")
        validate_core_question(root, "proposed")
    elif target == "evidence":
        artifact(root, "02_search/search-log.md")
        question, question_path = validate_core_question(root, "locked")
        state["core_question_sha256"] = digest(question_path)
        state["scope_sha256"] = digest(artifact(root, "01_plan/scope.md"))
        state["pilot_search_sha256"] = digest(artifact(root, question["pilot_search"]["artifact"]))
        state["prior_reviews_sha256"] = digest(artifact(root, question["pilot_search"]["prior_reviews_artifact"]))
        state["search_log_sha256"] = digest(artifact(root, "02_search/search-log.md"))
    elif target == "outline":
        assert_question_unchanged(root, state)
        ledger = coverage(root)
        state["coverage_sha256"] = digest(ledger)
        state["evidence_hashes"] = evidence_snapshot(root, ledger)
        synthesis = validate_evidence_synthesis(root, validate_core_question(root, "locked")[0], ledger)
        state["synthesis_artifact_hashes"] = synthesis["hashes"]
    elif target == "drafting":
        ledger = coverage(root)
        assert_evidence_unchanged(root, state)
        question = assert_question_unchanged(root, state)
        synthesis = validate_evidence_synthesis(root, question, ledger)
        manifest = validate_section_manifest(root, question, synthesis["unit_ids"])
        state["sections"] = [{**x, "state": "pending", "attempt": 0} for x in manifest]
    elif target == "figures":
        begin_figure_cycle(root, state)
    elif target == "frontmatter":
        expected = state.get("figure_inputs")
        if not isinstance(expected, dict):
            raise ValueError("missing figure workflow binding; reassess or reopen figures and regenerate the figure review")
        require_binding(load_json(artifact(root, "06_figures/figure-review.json")), expected, "figure review")
        actual_body = accepted_body_fingerprint(root, state)
        if actual_body != expected.get("body_fingerprint"):
            raise ValueError("accepted body changed since figure work; reassess affected sections")
        review_path = artifact(root, "06_figures/figure-review.json")
        report = load_json(review_path)
        if report.get("status") != "accepted" or not report.get("reason"):
            raise ValueError("at least five planned figures are required; figure review must be accepted with a reason")
        paths = []
        for plan_path in ("06_figures/figure-plan.md", "06_figures/figure-style-guide.md", "07_manuscript/table-plan.md"):
            artifact(root, plan_path)
            paths.append(plan_path)
        figures = report.get("figures")
        if not isinstance(figures, list) or len(figures) < MIN_FIGURES:
            raise ValueError(f"figure review must include at least {MIN_FIGURES} distinct figure records")
        ids = [item.get("id") for item in figures if isinstance(item, dict)]
        if len(ids) != len(figures) or len(set(ids)) != len(ids) or any(not isinstance(x, str) or not x.strip() for x in ids):
            raise ValueError("figure IDs must be unique nonempty strings")
        for figure in figures:
            style = figure.get("style_review")
            if not isinstance(style, dict) or style.get("accepted") is not True or not str(style.get("conformance_notes", "")).strip():
                raise ValueError("each accepted figure needs an accepted style_review with conformance_notes")
            if not isinstance(style.get("selected_references"), list) or not style["selected_references"]:
                raise ValueError("each figure style review must identify selected reference figures")
            for reference in style["selected_references"]:
                if not isinstance(reference, str) or Path(reference).name != reference:
                    raise ValueError("selected style references must use bundled reference filenames")
                reference_path = STYLE_REFERENCE_DIR / reference
                if not reference_path.is_file() or not reference_path.stat().st_size:
                    raise ValueError("selected style reference is not in the bundled reference set: " + str(reference))
            if not isinstance(style.get("applied_features"), list) or not style["applied_features"]:
                raise ValueError("each figure style review must record the visual features carried over")
            for key in ("png", "evidence"):
                artifact(root, figure.get(key)); paths.append(figure[key])
            if not isinstance(figure.get("prompt"), str) or not figure["prompt"].strip():
                raise ValueError("each final figure needs its exact nonempty generation prompt")
            inputs = figure.get("reference_inputs")
            if not isinstance(inputs, list):
                raise ValueError("each final figure needs a reference_inputs list")
            if inputs:
                for reference in inputs:
                    if not isinstance(reference, str) or Path(reference).name != reference:
                        raise ValueError("reference_inputs must use bundled reference filenames")
                    reference_path = STYLE_REFERENCE_DIR / reference
                    if not reference_path.is_file() or not reference_path.stat().st_size:
                        raise ValueError("reference input is not in the bundled reference set: " + str(reference))
                if set(inputs) != set(style["selected_references"]):
                    raise ValueError("reference_inputs must match the selected style references passed to image generation")
            elif not isinstance(figure.get("reference_input_limitation"), str) or not figure["reference_input_limitation"].strip():
                raise ValueError("empty reference_inputs need a substantive reference_input_limitation")
            quality = figure.get("quality_review")
            if (not isinstance(quality, dict) or quality.get("accepted") is not True
                    or not str(quality.get("legibility_notes", "")).strip()
                    or not str(quality.get("visual_quality_notes", "")).strip()):
                raise ValueError("each figure needs an accepted print-size quality review")
            image_path = artifact(root, figure["png"])
            width, height = png_dimensions(image_path)
            declared_width = quality.get("width_px")
            declared_height = quality.get("height_px")
            print_width_mm = quality.get("intended_width_mm")
            if declared_width != width or declared_height != height:
                raise ValueError("quality review dimensions do not match the actual PNG")
            if not isinstance(print_width_mm, (int, float)) or isinstance(print_width_mm, bool) or print_width_mm <= 0:
                raise ValueError("quality review needs a positive intended_width_mm")
            effective_dpi = width / (print_width_mm / 25.4)
            if effective_dpi < 300:
                raise ValueError(f"figure {figure['id']} is below 300 effective DPI at its intended width ({effective_dpi:.1f})")
            content = figure.get("content_review")
            if (not isinstance(content, dict) or content.get("accepted") is not True
                    or content.get("reviewer") != "primary_agent"
                    or not str(content.get("claim_evidence_alignment", "")).strip()
                    or not str(content.get("labels_and_relationships_checked", "")).strip()
                    or content.get("unsupported_content") != []):
                raise ValueError("each figure needs a passing primary-agent evidence and content review")
        state["figure_snapshot"] = snapshot(root, review_path, paths)
        begin_frontmatter_cycle(root, state)
    elif target == "audit":
        expected = state.get("frontmatter_inputs")
        if not isinstance(expected, dict):
            raise ValueError("missing frontmatter workflow binding; regenerate and review abstract, introduction and conclusion")
        actual_body = accepted_body_fingerprint(root, state)
        if actual_body != expected.get("body_fingerprint") or figure_fingerprint(state) != expected.get("figure_fingerprint"):
            raise ValueError("frontmatter inputs changed; regenerate abstract, introduction and conclusion")
        assert_snapshot(root, state, "figure_snapshot")
        review_path = artifact(root, "07_manuscript/frontmatter-review.json")
        report = load_json(review_path)
        if report.get("accepted") is not True:
            raise ValueError("frontmatter must be accepted")
        require_binding(report, expected, "frontmatter review")
        for key in ("abstract", "introduction", "conclusion"):
            artifact(root, report.get(key))
        artifact(root, report.get("review_approach"))
        method_check = report.get("method_transparency", {})
        if (method_check.get("accepted") is not True
                or method_check.get("search_log_verified") is not True
                or method_check.get("disposition") not in {"included", "integrated"}
                or not str(method_check.get("rationale", "")).strip()):
            raise ValueError("frontmatter review must accept a search-log-verified review approach")
        state["frontmatter_snapshot"] = snapshot(root, review_path, [report[k] for k in ("abstract", "introduction", "conclusion")])
        state["frontmatter_snapshot"]["artifacts"][report["review_approach"]] = digest(artifact(root, report["review_approach"]))
        agenda_review = validate_research_agenda(root, state)
        state["research_agenda_sha256"] = digest(agenda_review)
    elif target == "complete":
        accepted_body_fingerprint(root, state)
        assert_accepted_unchanged(root, state)
        assert_snapshot(root, state, "figure_snapshot")
        assert_snapshot(root, state, "frontmatter_snapshot")
        report = load_json(artifact(root, "08_audit/final-review.json"))
        agenda_review_path = validate_research_agenda(root, state)
        if digest(agenda_review_path) != state.get("research_agenda_sha256"):
            raise ValueError("research agenda review changed after audit")
        if (report.get("research_agenda_review") != "08_audit/research-agenda-review.json"
                or report.get("research_agenda_review_sha256") != state.get("research_agenda_sha256")):
            raise ValueError("final review must bind to the accepted research agenda review")
        title_review_path = artifact(root, report.get("title_review"))
        title_review = load_json(title_review_path)
        expected_title_inputs = state.get("frontmatter_inputs")
        if not isinstance(expected_title_inputs, dict):
            raise ValueError("missing frontmatter binding for the final title")
        require_binding(title_review, expected_title_inputs, "title review")
        selected_title = title_review.get("selected_title")
        if title_review.get("status") != "accepted" or not isinstance(selected_title, str) or not selected_title.strip():
            raise ValueError("final title needs an accepted title-review.json with selected_title")
        if report.get("selected_title") != selected_title or report.get("title_review_sha256") != digest(title_review_path):
            raise ValueError("final review title or title-review hash does not match the accepted title record")
        manuscript_path = artifact(root, report.get("manuscript"))
        if selected_title not in manuscript_path.read_text(encoding="utf-8-sig"):
            raise ValueError("accepted title is missing from the final manuscript metadata or visible title")
        for key in ("cross_review", "citations_checked", "figure_text_consistent", "limitations_reported", "section_integrity_checked", "defensive_writing_checked",
                    "prior_review_contribution_checked", "evidence_appraisal_checked", "synthesis_contribution_checked",
                    "review_approach_checked", "research_agenda_checked"):
            if report.get(key) is not True:
                raise ValueError("final review missing passing check: " + key)
        for key in ("tables_checked", "figure_style_conformance_checked"):
            if report.get(key) is not True:
                raise ValueError("final review missing passing visual check: " + key)
        for key in ("manuscript", "bibliography"):
            if digest(artifact(root, report.get(key))) != report.get(key + "_sha256"):
                raise ValueError("final output changed after audit: " + key)
        readable = artifact(root, report.get("readable_manuscript"))
        if readable.suffix.lower() != ".md" or digest(readable) != report.get("readable_manuscript_sha256"):
            raise ValueError("citation-resolved readable Markdown is missing or changed after audit")
        pdf = artifact(root, report.get("pdf"))
        if pdf.suffix.lower() != ".pdf" or digest(pdf) != report.get("pdf_sha256"):
            raise ValueError("final PDF is missing or changed after audit")
        pdf_validation_path = artifact(root, report.get("pdf_validation"))
        if digest(pdf_validation_path) != report.get("pdf_validation_sha256"):
            raise ValueError("PDF validation report changed after audit")
        pdf_validation = load_json(pdf_validation_path)
        if pdf_validation.get("status") != "passed" or pdf_validation.get("pdf_sha256") != report.get("pdf_sha256"):
            raise ValueError("PDF validation does not pass for the final PDF")
        pdf_checks = pdf_validation.get("checks", {})
        required_pdf_checks = ("page_geometry", "body_font", "margin_overflow", "sparse_pages",
                               "fonts_embedded", "markdown_residue", "figure_table_counts", "visual_review")
        if any(pdf_checks.get(key) is not True for key in required_pdf_checks):
            raise ValueError("PDF validation report is missing a passing required check")
        artifact(root, pdf_validation.get("contact_sheet"))
        manuscript_figures, _ = validate_visual_counts(root, report["manuscript"])
        figure_review = load_json(artifact(root, state["figure_snapshot"]["review"]))
        accepted_figures = {artifact(root, item["png"]).resolve() for item in figure_review["figures"]}
        if set(manuscript_figures) != accepted_figures:
            raise ValueError("assembled manuscript figures must match the accepted figure review one-to-one")
        state["status"] = "ready_for_author_review"
    state["phase"] = target
    event(state, "advance", old=current, new=target)


def section_action(root, state, action, sid, delegate=None, file=None, review=None):
    if state.get("phase") != "drafting":
        raise ValueError("chapter actions require drafting phase")
    assert_evidence_unchanged(root, state)
    assert_accepted_unchanged(root, state)
    sections = state["sections"]
    matching = [x for x in sections if x["id"] == sid]
    if not matching:
        raise ValueError("unknown section: " + sid)
    section = matching[0]
    if action == "dispatch":
        if not delegate or not str(delegate).strip():
            raise ValueError("delegate identity required")
        if section["state"] not in {"pending", "needs_revision"}:
            raise ValueError("section not dispatchable")
        if any(s["state"] in {"dispatched", "submitted"} for s in sections):
            raise ValueError("another chapter is still active")
        index = sections.index(section)
        if any(s["state"] != "accepted" for s in sections[:index]):
            raise ValueError("previous chapters must be accepted first")
        section.update(state="dispatched", delegate=delegate, attempt=section["attempt"]+1)
        event(state, "dispatch", section=sid, delegate=delegate, attempt=section["attempt"], coverage_sha256=state["coverage_sha256"])
    elif action == "submit":
        if section["state"] != "dispatched":
            raise ValueError("section must be dispatched before submission")
        p = artifact(root, file)
        section.update(state="submitted", artifact=file, artifact_sha256=digest(p))
        event(state, "submit", section=sid, artifact=file, sha256=section["artifact_sha256"])
    elif action in {"accept", "revise"}:
        if section["state"] != "submitted":
            raise ValueError("section must be submitted before review")
        p = artifact(root, section["artifact"])
        if digest(p) != section["artifact_sha256"]:
            raise ValueError("submitted section changed since submission")
        review_path = artifact(root, review)
        check = load_json(review_path)
        if check.get("section_id") != sid or check.get("decision") != action or not str(check.get("reason", "")).strip():
            raise ValueError("review must include matching section_id, decision and reason")
        if action == "accept":
            required = ("scope", "evidence", "consistency", "synthesis", "citations", "defensive_writing")
            if any(check.get("checks", {}).get(x) is not True for x in required):
                raise ValueError("acceptance requires all six checks to pass")
            matrix = load_json(artifact(root, "04_evidence/synthesis-matrix.json"))
            sources_by_unit = {unit["id"]: {item["candidate_id"] for item in unit["evidence"]}
                               for unit in matrix["units"]}
            findings = check.get("synthesis_findings")
            if not isinstance(findings, list):
                raise ValueError("chapter acceptance needs synthesis_findings for its assigned synthesis units")
            covered_units = set()
            for finding in findings:
                if not isinstance(finding, dict) or finding.get("synthesis_id") not in section.get("synthesis_ids", []):
                    raise ValueError("chapter synthesis finding must refer to an assigned synthesis unit")
                sid_unit = finding["synthesis_id"]
                for key in ("integrated_claim", "counterevidence_handling"):
                    if not isinstance(finding.get(key), str) or not finding[key].strip():
                        raise ValueError("chapter synthesis finding needs an integrated claim and counterevidence handling")
                evidence_ids = finding.get("evidence_ids")
                if (not isinstance(evidence_ids, list) or len(set(evidence_ids)) < 2
                        or not set(evidence_ids).issubset(sources_by_unit[sid_unit])):
                    raise ValueError("chapter synthesis finding must cite at least two sources from its accepted synthesis unit")
                covered_units.add(sid_unit)
            missing_units = set(section.get("synthesis_ids", [])) - covered_units
            if missing_units:
                raise ValueError("chapter acceptance is missing synthesis findings for: " + ", ".join(sorted(missing_units)))
            section["state"] = "accepted"
        else:
            section["state"] = "needs_revision"
        event(state, action, section=sid, review=review, review_sha256=digest(review_path),
              artifact=section["artifact"], artifact_sha256=section["artifact_sha256"])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-dir", type=Path, required=True)
    sub = p.add_subparsers(dest="action", required=True)
    a = sub.add_parser("advance"); a.add_argument("phase", choices=PHASES)
    for name in ("dispatch", "submit", "accept", "revise"):
        q = sub.add_parser(name); q.add_argument("section")
        if name == "dispatch": q.add_argument("--delegate", required=True)
        if name == "submit": q.add_argument("--file", required=True)
        if name in {"accept", "revise"}: q.add_argument("--review", required=True)
    q = sub.add_parser("limited"); q.add_argument("--reason", required=True)
    q = sub.add_parser("invalidate"); q.add_argument("section"); q.add_argument("--reason", required=True)
    q = sub.add_parser("cancel"); q.add_argument("section"); q.add_argument("--reason", required=True)
    q = sub.add_parser("reassess"); q.add_argument("section"); q.add_argument("--reason", required=True)
    q = sub.add_parser("refresh-evidence"); q.add_argument("--reason", required=True)
    q = sub.add_parser("reopen"); q.add_argument("phase", choices=["figures", "frontmatter"]); q.add_argument("--reason", required=True)
    args = p.parse_args()
    try:
        root = args.run_dir.resolve()
        state_path = artifact(root, "run-state.json")
        state = load_json(state_path)
        if state.get("schema_version") != 3 or state.get("status") != "in_progress":
            raise ValueError("expected an in-progress schema v3 run; older workflow runs must be retained and restarted, and finalized runs are read-only")
        if args.action == "advance":
            advance(root, state, args.phase)
        elif args.action == "limited":
            if not args.reason.strip():
                raise ValueError("reason required")
            if any(s.get("state") in {"dispatched", "submitted"} for s in state.get("sections", [])):
                raise ValueError("cancel the active delegate before ending the run as limited")
            state["status"] = "limited_draft"
            state.setdefault("limitations", []).append(args.reason)
            event(state, "limited", reason=args.reason)
        elif args.action == "cancel":
            if state.get("phase") != "drafting" or not args.reason.strip():
                raise ValueError("cancel requires drafting phase and a reason")
            active = [s for s in state.get("sections", []) if s["id"] == args.section]
            if not active or active[0]["state"] not in {"dispatched", "submitted"}:
                raise ValueError("only a dispatched or submitted section can be canceled")
            previous = active[0]["state"]
            active[0]["state"] = "pending"
            event(state, "cancel", section=args.section, previous=previous, reason=args.reason,
                  note="cancel the real delegate independently before dispatching another task")
        elif args.action == "reassess":
            if not args.reason.strip(): raise ValueError("reason required")
            sections = state.get("sections", [])
            indices = [i for i, x in enumerate(sections) if x["id"] == args.section]
            if not indices or state.get("phase") not in {"drafting", "figures", "frontmatter", "audit"}:
                raise ValueError("reassess requires an existing section after drafting started")
            if any(x["state"] in {"dispatched", "submitted"} for x in sections):
                raise ValueError("cancel the active section before reassessing coverage")
            ledger = coverage(root)
            assert_accepted_unchanged(root, state)
            question = assert_question_unchanged(root, state)
            synthesis = validate_evidence_synthesis(root, question, ledger)
            manifest = validate_section_manifest(root, question, synthesis["unit_ids"])
            new_indices = [i for i, x in enumerate(manifest) if x["id"] == args.section]
            if not new_indices:
                raise ValueError("reassess section must appear in the revised sections manifest")
            start_index = new_indices[0]
            old_by_id = {x["id"]: x for x in sections}
            runtime_keys = {"state", "attempt", "delegate", "artifact", "artifact_sha256"}
            refreshed_sections = []
            for i, item in enumerate(manifest):
                prior = old_by_id.get(item["id"])
                if i < start_index:
                    prior_definition = {k: v for k, v in (prior or {}).items() if k not in runtime_keys}
                    if not prior or prior.get("state") != "accepted" or prior_definition != item:
                        raise ValueError("reassess must start at the earliest changed or unaccepted section")
                    refreshed_sections.append(prior)
                else:
                    refreshed_sections.append({**item, "state": "pending", "attempt": 0})
            state["sections"] = refreshed_sections
            state["phase"] = "drafting"
            state["coverage_sha256"] = digest(ledger)
            state["evidence_hashes"] = evidence_snapshot(root, ledger)
            state["search_log_sha256"] = digest(artifact(root, "02_search/search-log.md"))
            state["synthesis_artifact_hashes"] = synthesis["hashes"]
            clear_downstream(state, new_content=True)
            event(state, "reassess", section=args.section, reason=args.reason, coverage_sha256=state["coverage_sha256"])
        elif args.action == "refresh-evidence":
            if state.get("phase") != "outline" or not args.reason.strip():
                raise ValueError("refresh-evidence requires outline phase and a reason")
            assert_question_unchanged(root, state)
            ledger = coverage(root)
            artifact(root, "01_plan/outline.md")
            artifact(root, "01_plan/sections.json")
            synthesis = validate_evidence_synthesis(root, assert_question_unchanged(root, state), ledger)
            validate_section_manifest(root, assert_question_unchanged(root, state), synthesis["unit_ids"])
            state["coverage_sha256"] = digest(ledger)
            state["evidence_hashes"] = evidence_snapshot(root, ledger)
            state["search_log_sha256"] = digest(artifact(root, "02_search/search-log.md"))
            state["synthesis_artifact_hashes"] = synthesis["hashes"]
            event(state, "refresh_evidence", reason=args.reason, coverage_sha256=state["coverage_sha256"])
        elif args.action == "reopen":
            if not args.reason.strip() or state.get("phase") not in {"figures", "frontmatter", "audit"} or PHASES.index(args.phase) > PHASES.index(state["phase"]):
                raise ValueError("reopen needs a reason and the current or an earlier figures/frontmatter phase")
            assert_evidence_unchanged(root, state)
            assert_accepted_unchanged(root, state)
            if args.phase == "figures":
                begin_figure_cycle(root, state)
            elif args.phase == "frontmatter":
                assert_snapshot(root, state, "figure_snapshot")
                begin_frontmatter_cycle(root, state)
            state["phase"] = args.phase
            event(state, "reopen", phase=args.phase, reason=args.reason)
        elif args.action == "invalidate":
            if not args.reason.strip(): raise ValueError("reason required")
            sections = state.get("sections", [])
            indices = [i for i, x in enumerate(sections) if x["id"] == args.section]
            if not indices or sections[indices[0]]["state"] != "accepted":
                raise ValueError("only an accepted section can be invalidated")
            if any(x["state"] in {"dispatched", "submitted"} for x in sections):
                raise ValueError("cannot invalidate while a section is active")
            for x in sections[indices[0]:]:
                x["state"] = "pending"
            state["phase"] = "drafting"
            ledger = coverage(root)
            state["coverage_sha256"] = digest(ledger)
            state["evidence_hashes"] = evidence_snapshot(root, ledger)
            clear_downstream(state, new_content=True)
            event(state, "invalidate", section=args.section, reason=args.reason)
        else:
            section_action(root, state, args.action, args.section, getattr(args, "delegate", None),
                           getattr(args, "file", None), getattr(args, "review", None))
        save(state_path, state)
        print(json.dumps({"status": state["status"], "phase": state["phase"], "revision": state["revision"]}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
