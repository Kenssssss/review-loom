import importlib.util
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SearchTests(unittest.TestCase):
    def test_arxiv_preserves_old_style_id_version_and_pagination(self):
        search = load("search")
        feed = b'''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"><opensearch:totalResults>2</opensearch:totalResults><entry><id>http://arxiv.org/abs/cs/0112017v3</id><title>One</title><summary>abstract</summary><published>2001-01-01</published><updated>2002-01-01</updated><author><name>A</name></author></entry></feed>'''
        data, pagination = search.arxiv("all:test", 1, 1, getter=lambda _: feed)
        self.assertEqual((data[0]["source_id"], data[0]["version"]), ("cs/0112017", "v3"))
        self.assertTrue(pagination["truncated"])
        self.assertEqual(pagination["reported_total"], 2)

    def test_crossref_rejects_unsuccessful_response(self):
        with self.assertRaises(ValueError):
            load("search").crossref("test", 1, 1, None, getter=lambda _: b'{"status":"error"}')

    def test_dedup_does_not_merge_title_only(self):
        dedup = load("deduplicate")
        records = [{"doi":"10.1/A", "title":"Same"}, {"doi":"https://doi.org/10.1/a", "title":"Same"},
                   {"doi":"10.1/B", "title":"Same"}]
        groups = dedup.group(records)
        self.assertEqual(sorted(len(x["records"]) for x in groups), [1, 2])

    def test_arxiv_crossref_same_preprint_and_published_distinct(self):
        records = [{"source":"arxiv", "source_id":"2401.12345", "version":"v2"},
                   {"source":"crossref", "doi":"10.48550/arXiv.2401.12345v2"},
                   {"source":"crossref", "doi":"10.1145/1234567"}]
        groups = load("deduplicate").group(records)
        self.assertEqual(sorted(len(x["records"]) for x in groups), [1, 2])


class CitationTests(unittest.TestCase):
    def test_order_and_missing_key(self):
        fixture = ROOT / "tests" / "fixtures"
        if not fixture.exists():
            self.skipTest("fixture directory not available")
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            output = Path(temp) / "out.md"
            source = Path(temp) / "source.md"
            source.write_text((fixture / "before.md").read_text(encoding="utf-8"), encoding="utf-8")
            base = [sys.executable, str(ROOT / "scripts" / "export.py"), "--bibliography", str(fixture / "refs.bib"),
                    "--csl", str(fixture / "probe.csl"), "--output", str(output)]
            result = subprocess.run(base + [str(source)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            text = output.read_text(encoding="utf-8")
            self.assertGreaterEqual(text.replace("\\[", "[").replace("\\]", "]").count("[1]"), 2)
            source.write_text((fixture / "missing.md").read_text(encoding="utf-8"), encoding="utf-8")
            result = subprocess.run(base + [str(source)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing citation keys", result.stderr)

    def test_figure_placement_order_caption_and_missing(self):
        figures = load("assemble_figures")
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            directory = Path(temp)
            (directory / "a.png").write_bytes(b"test")
            (directory / "b.png").write_bytes(b"test")
            data = {"a":{"path":"a.png", "caption":"Source [@ref-A]"},
                    "b":{"path":"b.png", "caption":"B"}}
            text, numbers = figures.assemble("See {{fig:a}} and {{fig:b}}.\n{{figure:b}}\n{{figure:a}}", data, directory, directory)
            self.assertEqual(numbers, {"b": 1, "a": 2})
            self.assertIn("Figure 2", text)
            self.assertIn("[@ref-A]", text)
            with self.assertRaises(ValueError):
                figures.assemble("See {{fig:a}}", data, directory, directory)

    def test_word_export_with_relative_image_and_caption_citation(self):
        import base64
        import zipfile
        fixture = ROOT / "tests" / "fixtures"
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            directory = Path(temp)
            (directory / "image.png").write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+X2ioAAAAASUVORK5CYII="))
            source, output = directory / "source.md", directory / "out.docx"
            source.write_text("# Main\nText [@paper-b]. See Figure 1.\n\n![Figure 1. Caption [@paper-a]](image.png)\n", encoding="utf-8")
            cmd = [sys.executable, str(ROOT / "scripts" / "export.py"), str(source), "--bibliography", str(fixture / "refs.bib"),
                   "--csl", str(fixture / "probe.csl"), "--output", str(output)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            with zipfile.ZipFile(output) as archive:
                self.assertTrue(any(x.startswith("word/media/") for x in archive.namelist()))
                self.assertIn("Caption", archive.read("word/document.xml").decode("utf-8"))


class WorkflowGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.parent = Path(self.temp.name)
        cmd = [sys.executable, str(ROOT / "scripts" / "init_run.py"), "test-run", "--output-root", str(self.parent), "--topic", "Test topic"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.run = self.parent / "test-run"

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, value):
        p = self.run / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value, encoding="utf-8")
        return p

    def gate(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "gate.py"), "--run-dir", str(self.run), *args], capture_output=True, text=True)

    def core_question(self, status="proposed"):
        question = {
            "status": status,
            "core_question": "How do label-relation methods affect multi-label image classification under different supervision conditions?",
            "working_title": "Label Relations in Multi-label Image Classification",
            "focus_rationale": "The question isolates one task, one method family and measurable outcomes.",
            "dimensions": {
                "task_or_context": "multi-label image classification",
                "phenomenon_or_method": "label-relation methods",
                "outcome_or_tradeoff": "classification performance and error patterns",
                "conditions_or_boundaries": "supervision and dataset conditions",
            },
            "include_boundaries": ["image-level multi-label classification"],
            "exclude_boundaries": ["object detection and video classification"],
            "subquestions": [
                {"id":"Q1", "question":"How are label relations represented?", "search_concepts":["label graph", "label query"]},
                {"id":"Q2", "question":"Under which supervision conditions do they help?", "search_concepts":["full supervision", "partial labels"]},
            ],
        }
        if status == "locked":
            question["pilot_search"] = {
                "artifact":"02_search/pilot-search.md", "decision":"feasible",
                "volume_assessment":"Enough primary studies across both subquestions.",
                "existing_reviews":"Existing reviews do not synthesize the supervision comparison.",
                "synthesis_gap":"The evidence supports a focused comparison across supervision conditions.",
                "prior_reviews_artifact":"02_search/prior-reviews.json",
            }
        return question

    def write_prior_reviews(self):
        return self.write("02_search/prior-reviews.json", {
            "status":"reviewed",
            "searches":[{"source":"scholarly search", "query":"label relations multi-label review", "date":"2026-10-27", "status":"ok", "results_screened":12}],
            "reviews":[{"id":"review-1", "title":"Prior review", "year":2024, "url":"https://example.org/review",
                        "scope":"general multi-label learning", "coverage_period":"2015-2023", "organizing_framework":"method taxonomy",
                        "limitations":"does not compare supervision conditions"}],
            "contribution_statement":"This review compares label-relation methods across supervision settings.",
            "difference_basis":"The prior review does not synthesize label-relation evidence by supervision budget.",
        })

    def ready_ledger(self):
        self.write("04_evidence/a.md", "actual evidence excerpt and source locator")
        topic = {"id":"methods", "core":True, "question_ids":["Q1","Q2"], "searches":[{"source":"venue", "query":"q", "date":"2026-10-27", "status":"ok"}],
                 "citation_tracking":{"forward":{"status":"done", "details":"seeds and source"}, "backward":{"status":"done", "details":"seeds and references"}}}
        def paper(id_, access):
            identifier = "arxiv:2302."+("11939" if id_ == "A" else "11940")
            return {"id":id_, "title":id_, "verified_title":id_, "identifier":identifier,
                    "verified_url":"https://arxiv.org/abs/"+identifier.removeprefix("arxiv:"), "topics":["methods"], "status":"included", "kind":"primary", "access":access,
                    "important":True, "evidence_file":"04_evidence/a.md", "locator":"section 3"}
        return {"topics":[topic], "candidates":[paper("A", "fulltext"), paper("B", "abstract")]}

    def ready_core_question_for_coverage(self):
        self.write("01_plan/core-question.json", self.core_question("locked"))
        self.write("02_search/pilot-search.md", "Pilot query, volume, review landscape and synthesis gap.")
        self.write_prior_reviews()

    def write_evidence_synthesis(self, ledger=None):
        ledger_path = self.write("04_evidence/coverage.json", ledger or self.ready_ledger())
        appraisal = self.write("04_evidence/appraisal.json", {
            "criteria":[{"id":"A1", "name":"Evaluation evidence", "definition":"Whether protocols support the stated comparison.",
                         "relevance":"The core question compares method performance across supervision conditions."}],
            "assessments":[
                {"candidate_id":"A", "criterion_id":"A1", "rating":"qualified", "rationale":"Protocol has a limitation relevant to cross-setting comparison.", "locator":"section 3"},
                {"candidate_id":"B", "criterion_id":"A1", "rating":"not_assessable", "rationale":"The abstract does not report enough protocol detail.", "locator":"abstract"},
            ],
        })
        matrix = self.write("04_evidence/synthesis-matrix.json", {
            "units":[{"id":"SYN1", "question_ids":["Q1", "Q2"], "claim":"Label relations help under some supervision settings, with gains depending on protocol.",
                      "comparison_axes":["relation representation", "supervision setting"], "conditions":["dataset and label budget"],
                      "evidence":[{"candidate_id":"A", "relation":"supports", "locator":"section 3"},
                                  {"candidate_id":"B", "relation":"qualifies", "locator":"abstract"}],
                      "counterevidence_analysis":"The available comparison is qualified by different protocols and incomplete abstract reporting.",
                      "confidence":"moderate", "confidence_rationale":"Two studies support a conditional pattern, but reporting is uneven."}],
            "gaps":[{"id":"G1", "description":"Evidence under low-label budgets is limited.", "basis_unit_ids":["SYN1"],
                      "research_direction":"Compare label-relation methods under matched low-label protocols."}],
        })
        import hashlib
        evidence_payload = {"04_evidence/a.md":hashlib.sha256((self.run / "04_evidence/a.md").read_bytes()).hexdigest()}
        evidence_fingerprint = hashlib.sha256(json.dumps(evidence_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        self.write("08_audit/evidence-synthesis-review.json", {
            "decision":"accept", "reason":"Criteria fit the question and the matrix integrates contrasting studies.",
            "inputs":{"coverage_sha256":hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
                     "evidence_sha256":evidence_fingerprint,
                     "appraisal_sha256":hashlib.sha256(appraisal.read_bytes()).hexdigest(),
                     "synthesis_matrix_sha256":hashlib.sha256(matrix.read_bytes()).hexdigest()},
            "checks":{"criteria_fit":True,"source_grounding":True,"cross_study_synthesis":True,
                      "counterevidence":True,"contribution_support":True},
            "findings":["The central claim is conditional and reflects mixed protocol detail."],
        })

    def through_evidence(self):
        self.write("01_plan/scope.md", "topic and scope")
        self.write("01_plan/core-question.json", self.core_question())
        self.assertEqual(self.gate("advance", "searching").returncode, 0)
        self.write("02_search/pilot-search.md", "Pilot queries, sources, result volumes, existing-review coverage and synthesis gap.")
        self.write_prior_reviews()
        self.write("01_plan/core-question.json", self.core_question("locked"))
        self.write("02_search/search-log.md", "actual source and query log")
        self.assertEqual(self.gate("advance", "evidence").returncode, 0)
        self.write_evidence_synthesis()

    def test_focus_gate_requires_proposed_question_and_feasible_pilot(self):
        self.write("01_plan/scope.md", "topic and boundaries")
        result = self.gate("advance", "searching")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("core-question.json", result.stderr)
        proposed = self.core_question()
        proposed["dimensions"]["outcome_or_tradeoff"] = ""
        self.write("01_plan/core-question.json", proposed)
        result = self.gate("advance", "searching")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("concrete task, focus, outcome and condition", result.stderr)
        self.write("01_plan/core-question.json", self.core_question())
        self.assertEqual(self.gate("advance", "searching").returncode, 0)
        self.write("02_search/search-log.md", "full search log")
        result = self.gate("advance", "evidence")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("status 'locked'", result.stderr)
        self.write("02_search/pilot-search.md", "Queries, counts, related reviews and synthesis-gap assessment.")
        self.write_prior_reviews()
        self.write("01_plan/core-question.json", self.core_question("locked"))
        self.assertEqual(self.gate("advance", "evidence").returncode, 0)

    def test_locked_question_and_scope_are_hash_locked(self):
        self.through_evidence()
        question = self.core_question("locked")
        question["core_question"] = "How do thresholds affect classification?"
        self.write("01_plan/core-question.json", question)
        self.write("04_evidence/coverage.json", self.ready_ledger())
        result = self.gate("advance", "outline")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("locked question, scope, pilot or prior-review comparison changed", result.stderr)

    def test_pilot_report_is_hash_locked_with_question(self):
        self.through_evidence()
        self.write("02_search/pilot-search.md", "changed pilot assessment")
        self.write("04_evidence/coverage.json", self.ready_ledger())
        result = self.gate("advance", "outline")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("pilot or prior-review comparison changed", result.stderr)

    def test_outline_must_map_all_subquestions(self):
        self.through_evidence()
        self.write("04_evidence/coverage.json", self.ready_ledger())
        self.assertEqual(self.gate("advance", "outline").returncode, 0)
        self.write("01_plan/outline.md", "Evidence-grounded outline")
        self.write("01_plan/sections.json", [{"id":"S1","priority":1,"reason":"answers Q1","question_ids":["Q1"],"synthesis_ids":["SYN1"],"depends_on":[]}])
        result = self.gate("advance", "drafting")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("leaves core-question subquestions unanswered: Q2", result.stderr)

    def test_outline_requires_accepted_appraisal_and_synthesis_review(self):
        self.through_evidence()
        review_path = self.run / "08_audit/evidence-synthesis-review.json"
        original = review_path.read_text(encoding="utf-8")
        review_path.unlink()
        result = self.gate("advance", "outline")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("evidence-synthesis-review.json", result.stderr)
        review_path.write_text(original, encoding="utf-8")
        self.assertEqual(self.gate("advance", "outline").returncode, 0)

    def test_outline_sections_must_map_synthesis_units(self):
        self.through_evidence()
        self.assertEqual(self.gate("advance", "outline").returncode, 0)
        self.write("01_plan/outline.md", "Evidence-grounded outline")
        self.write("01_plan/sections.json", [{"id":"S1","priority":1,"reason":"answers Q1 and Q2",
                    "question_ids":["Q1","Q2"],"synthesis_ids":[],"depends_on":[]}])
        result = self.gate("advance", "drafting")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("accepted synthesis units", result.stderr)

    def test_evidence_topics_must_cover_all_subquestions(self):
        self.through_evidence()
        ledger = self.ready_ledger()
        ledger["topics"][0]["question_ids"] = ["Q1"]
        self.write("04_evidence/coverage.json", ledger)
        result = self.gate("advance", "outline")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no evidence-search topic maps", result.stderr)

    def through_drafting_with_accepted_section(self):
        self.through_evidence()
        self.write("04_evidence/coverage.json", self.ready_ledger())
        self.assertEqual(self.gate("advance", "outline").returncode, 0)
        self.write("01_plan/outline.md", "Final evidence-grounded outline")
        self.write("01_plan/sections.json", [{"id":"S1","priority":1,"reason":"core mechanism","question_ids":["Q1","Q2"],"synthesis_ids":["SYN1"],"depends_on":[]}])
        self.assertEqual(self.gate("advance", "drafting").returncode, 0)
        self.assertEqual(self.gate("dispatch", "S1", "--delegate", "agent-a").returncode, 0)
        self.write("05_sections/S1.md", "Accepted chapter with evidence")
        self.assertEqual(self.gate("submit", "S1", "--file", "05_sections/S1.md").returncode, 0)
        review = {"section_id":"S1", "decision":"accept", "reason":"evidence and synthesis checked",
                  "checks":{k:True for k in ("scope","evidence","consistency","synthesis","citations","defensive_writing")},
                  "synthesis_findings":[{"synthesis_id":"SYN1", "integrated_claim":"Conditional comparison across two papers.",
                    "evidence_ids":["A","B"], "counterevidence_handling":"The limitation in B qualifies the trend."}]}
        self.write("08_audit/S1.json", review)
        self.assertEqual(self.gate("accept", "S1", "--review", "08_audit/S1.json").returncode, 0)

    def add_accepted_figure(self):
        state = json.loads((self.run / "run-state.json").read_text(encoding="utf-8"))
        binding = state["figure_inputs"]
        self.write("06_figures/figure-plan.md", "Five distinct planned figures with separate explanatory purposes and linked evidence.")
        self.write("06_figures/figure-style-guide.md", "Shared palette, typography, hierarchy, linework and spacing derived from the bundled references.")
        self.write("07_manuscript/table-plan.md", "Four distinct comparison tables with section placement and evidence mapping.")
        figures = []
        for i in range(1, 6):
            stem = f"figure-{i:02d}"
            reference = [
                "reference-01-agent-system-workflow.png",
                "reference-02-agent-workflow-repair.png",
                "reference-03-multimodal-model-architecture.png",
                "reference-04-evaluation-checklist.png",
                "reference-05-frequency-model-mechanism.png",
            ][i - 1]
            png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + (2500).to_bytes(4, "big") + (1400).to_bytes(4, "big")
            (self.run / f"06_figures/{stem}.png").write_bytes(png)
            evidence = f"06_figures/{stem}-evidence.md"
            self.write(evidence, f"Figure {i} nodes map to cited evidence and locators.")
            figures.append({"id":stem,"png":f"06_figures/{stem}.png","evidence":evidence,
                "prompt":"Evidence-grounded final figure prompt with exact labels and composition.",
                "reference_inputs":[reference],
                "style_review":{"accepted":True,"selected_references":[reference],
                                "applied_features":["restrained palette","clear hierarchy"],
                                "conformance_notes":"Applied and checked the selected reference style."},
                "quality_review":{"accepted":True,"width_px":2500,"height_px":1400,"intended_width_mm":180,
                                 "legibility_notes":"All labels remain legible at print size.",
                                 "visual_quality_notes":"No clipping, pseudo-text or generation artifacts."},
                "content_review":{"accepted":True,"reviewer":"primary_agent",
                                  "claim_evidence_alignment":"Every claim and relation matches the linked paper evidence.",
                                  "labels_and_relationships_checked":"All labels and arrows match the accepted plan.",
                                  "unsupported_content":[]}})
        self.write("06_figures/figure-review.json", {"status":"accepted","reason":"evidence and layout checked",
                    **binding,"figures":figures})

    def add_accepted_frontmatter(self):
        state = json.loads((self.run / "run-state.json").read_text(encoding="utf-8"))
        binding = state["frontmatter_inputs"]
        for name in ("abstract", "introduction", "conclusion"):
            self.write(f"07_manuscript/{name}.md", f"Checked {name} based on accepted chapters")
        self.write("07_manuscript/review-approach.md", "The review searched named sources through the stated cutoff and synthesized studies by method and evaluation condition.")
        self.write("07_manuscript/frontmatter-review.json", {"accepted":True,"abstract":"07_manuscript/abstract.md",
                    "introduction":"07_manuscript/introduction.md","conclusion":"07_manuscript/conclusion.md",
                    "review_approach":"07_manuscript/review-approach.md",
                    "method_transparency":{"accepted":True,"search_log_verified":True,"disposition":"included","rationale":"Matches the search log."}, **binding})
        import hashlib
        matrix = self.run / "04_evidence/synthesis-matrix.json"
        conclusion = self.run / "07_manuscript/conclusion.md"
        self.write("08_audit/research-agenda-review.json", {"accepted":True,"reason":"Every gap has a concrete, evidence-linked direction.",
                    "conclusion":"07_manuscript/conclusion.md",
                    "inputs":{"synthesis_matrix_sha256":hashlib.sha256(matrix.read_bytes()).hexdigest(),
                              "conclusion_sha256":hashlib.sha256(conclusion.read_bytes()).hexdigest()},
                    "directions":[{"gap_id":"G1", "recommendation":"Run matched low-label comparisons.",
                                   "evidence_basis":"G1 follows from SYN1.", "conclusion_locator":"final paragraph"}]})

    def add_final_review(self):
        title = "Evidence-Grounded Review"
        state = json.loads((self.run / "run-state.json").read_text(encoding="utf-8"))
        title_binding = state["frontmatter_inputs"]
        parts = ["---", f"title: {title}", "---", f"# {title}", "# Final manuscript"]
        for i in range(1, 6):
            parts.append(f"![Figure {i}. Figure {i} caption](<../06_figures/figure-{i:02d}.png>)")
        for i in range(1, 5):
            parts.extend([f"Table {i}. Table {i} caption", "| Category | Evidence |", "|---|---|", f"| Item {i} | Source {i} |"])
        self.write("07_manuscript/review.md", "\n\n".join(parts))
        self.write("07_manuscript/references.bib", "@article{test, title={Test}}")
        self.write("07_manuscript/title-review.json", {"status":"accepted","selected_title":title, **title_binding})
        manuscript = self.run / "07_manuscript/review.md"
        bibliography = self.run / "07_manuscript/references.bib"
        title_review = self.run / "07_manuscript/title-review.json"
        readable = self.run / "07_manuscript/review.final.md"
        readable.write_text("Citation-resolved readable manuscript.", encoding="utf-8")
        pdf = self.run / "07_manuscript/review.pdf"
        pdf.write_bytes(b"%PDF-1.7 test fixture")
        contact = self.write("07_manuscript/pdf-build/contact-sheet.png", "contact sheet fixture")
        pdf_validation = self.write("08_audit/pdf-validation.json", {
            "status":"passed","pdf_sha256":hashlib.sha256(pdf.read_bytes()).hexdigest(),
            "contact_sheet":"07_manuscript/pdf-build/contact-sheet.png",
            "checks":{k:True for k in ("page_geometry","body_font","margin_overflow","sparse_pages",
                "fonts_embedded","markdown_residue","figure_table_counts","visual_review")}})
        self.write("08_audit/final-review.json", {"cross_review":True,"citations_checked":True,"figure_text_consistent":True,
                    "tables_checked":True,"figure_style_conformance_checked":True,
                    "limitations_reported":True,"section_integrity_checked":True,"defensive_writing_checked":True,
                    "prior_review_contribution_checked":True,"evidence_appraisal_checked":True,"synthesis_contribution_checked":True,
                    "review_approach_checked":True,"research_agenda_checked":True,
                    "research_agenda_review":"08_audit/research-agenda-review.json",
                    "research_agenda_review_sha256":state.get("research_agenda_sha256"),
                    "manuscript":"07_manuscript/review.md",
                    "manuscript_sha256":hashlib.sha256(manuscript.read_bytes()).hexdigest(),
                    "bibliography":"07_manuscript/references.bib","bibliography_sha256":hashlib.sha256(bibliography.read_bytes()).hexdigest(),
                    "readable_manuscript":"07_manuscript/review.final.md",
                    "readable_manuscript_sha256":hashlib.sha256(readable.read_bytes()).hexdigest(),
                    "pdf":"07_manuscript/review.pdf","pdf_sha256":hashlib.sha256(pdf.read_bytes()).hexdigest(),
                    "pdf_validation":"08_audit/pdf-validation.json",
                    "pdf_validation_sha256":hashlib.sha256(pdf_validation.read_bytes()).hexdigest(),
                    "title_review":"07_manuscript/title-review.json","title_review_sha256":hashlib.sha256(title_review.read_bytes()).hexdigest(),
                    "selected_title":title})

    def test_11_abstract_only_and_missing_tracking_block(self):
        coverage = load("coverage")
        self.ready_core_question_for_coverage()
        ledger = self.ready_ledger()
        ledger["topics"][0]["citation_tracking"] = {"forward":{"status":"unavailable","details":"not run"}, "backward":{"status":"unavailable","details":"not run"}}
        ledger["candidates"] = [dict(ledger["candidates"][1], id=f"p{i}", identifier=f"arxiv:2302.{10000+i}") for i in range(11)]
        report = coverage.evaluate(ledger, self.run.resolve())
        self.assertEqual(report["included_count"], 11)
        self.assertEqual(report["status"], "insufficient")
        self.assertTrue(any("full-text" in p for p in report["problems"]))
        self.assertTrue(any("tracking unavailable" in p for p in report["problems"]))

    def test_duplicate_and_wrong_title_block(self):
        self.ready_core_question_for_coverage()
        ledger = self.ready_ledger()
        ledger["candidates"][1]["identifier"] = "doi:10.48550/arxiv.2302.11939"
        ledger["candidates"][1]["verified_title"] = "A different paper"
        report = load("coverage").evaluate(ledger, self.run.resolve())
        self.assertTrue(any("duplicate" in p for p in report["problems"]))
        self.assertTrue(any("title" in p for p in report["problems"]))

    def test_known_source_url_must_match_identifier(self):
        self.ready_core_question_for_coverage()
        ledger = self.ready_ledger()
        ledger["candidates"][1]["verified_url"] = "https://arxiv.org/abs/2302.11939"
        report = load("coverage").evaluate(ledger, self.run.resolve())
        self.assertTrue(any("URL does not match identifier" in p for p in report["problems"]))

    def test_outline_evidence_refresh_relocks_before_drafting(self):
        self.through_evidence()
        ledger = self.ready_ledger()
        self.write_evidence_synthesis(ledger)
        self.assertEqual(self.gate("advance", "outline").returncode, 0)
        ledger["topics"][0]["searches"][0]["query"] = "broader query"
        self.write_evidence_synthesis(ledger)
        self.write("01_plan/outline.md", "Revised outline using the broader evidence")
        self.write("01_plan/sections.json", [{"id":"S1","priority":1,"reason":"updated central question","question_ids":["Q1","Q2"],"synthesis_ids":["SYN1"],"depends_on":[]}])
        self.assertNotEqual(self.gate("advance", "drafting").returncode, 0)
        self.assertEqual(self.gate("refresh-evidence", "--reason", "revised outline after additional search").returncode, 0)
        self.assertEqual(self.gate("advance", "drafting").returncode, 0)

    def test_ledger_and_fulltext_changes_require_reassessment(self):
        self.through_evidence()
        ledger = self.ready_ledger()
        self.write_evidence_synthesis(ledger)
        self.assertEqual(self.gate("advance", "outline").returncode, 0)
        self.write("01_plan/outline.md", "Outline reflects the current evidence")
        self.write("01_plan/sections.json", [{"id":"S1","priority":1,"reason":"core","question_ids":["Q1","Q2"],"synthesis_ids":["SYN1"],"depends_on":[]}])
        self.assertEqual(self.gate("advance", "drafting").returncode, 0)
        ledger["topics"][0]["searches"][0]["query"] = "expanded query"
        self.write_evidence_synthesis(ledger)
        result = self.gate("dispatch", "S1", "--delegate", "agent-a")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("changed", result.stderr)
        self.assertEqual(self.gate("refresh-evidence", "--reason", "updated search coverage and outline").returncode, 1)
        # Once drafting has started, use the chapter-aware recovery path.
        self.assertEqual(self.gate("reassess", "S1", "--reason", "incorporated expanded search").returncode, 0)
        evidence = self.run / "04_evidence/a.md"
        evidence.write_text("new source-grounded detail", encoding="utf-8")
        self.assertNotEqual(self.gate("dispatch", "S1", "--delegate", "agent-a").returncode, 0)
        self.write_evidence_synthesis(ledger)
        self.assertEqual(self.gate("reassess", "S1", "--reason", "updated full-text evidence").returncode, 0)
        self.assertEqual(self.gate("dispatch", "S1", "--delegate", "agent-a").returncode, 0)

    def test_reject_limited_while_delegate_active(self):
        self.through_evidence()
        self.write_evidence_synthesis(self.ready_ledger())
        self.assertEqual(self.gate("advance", "outline").returncode, 0)
        self.write("01_plan/outline.md", "Outline")
        self.write("01_plan/sections.json", [{"id":"S1","priority":1,"reason":"core","question_ids":["Q1","Q2"],"synthesis_ids":["SYN1"],"depends_on":[]}])
        self.assertEqual(self.gate("advance", "drafting").returncode, 0)
        self.assertEqual(self.gate("dispatch", "S1", "--delegate", "agent-a").returncode, 0)
        self.assertNotEqual(self.gate("limited", "--reason", "stop").returncode, 0)

    def test_final_gate_detects_figure_and_frontmatter_mutations_and_reopens(self):
        self.through_drafting_with_accepted_section()
        self.assertEqual(self.gate("advance", "figures").returncode, 0)
        self.add_accepted_figure()
        self.assertEqual(self.gate("advance", "frontmatter").returncode, 0)
        self.add_accepted_frontmatter()
        frontmatter_path = self.run / "07_manuscript/frontmatter-review.json"
        frontmatter = json.loads(frontmatter_path.read_text(encoding="utf-8"))
        frontmatter.pop("method_transparency")
        frontmatter_path.write_text(json.dumps(frontmatter), encoding="utf-8")
        self.assertNotEqual(self.gate("advance", "audit").returncode, 0)
        self.add_accepted_frontmatter()
        self.assertEqual(self.gate("advance", "audit").returncode, 0)
        self.add_final_review()
        (self.run / "06_figures/figure-01.png").write_text("changed after review", encoding="utf-8")
        self.assertNotEqual(self.gate("advance", "complete").returncode, 0)
        self.assertEqual(self.gate("reopen", "figures", "--reason", "figure source changed").returncode, 0)
        self.add_accepted_figure()
        self.assertEqual(self.gate("advance", "frontmatter").returncode, 0)
        self.add_accepted_frontmatter()
        self.assertEqual(self.gate("advance", "audit").returncode, 0)
        self.add_final_review()
        (self.run / "07_manuscript/abstract.md").write_text("Changed after review", encoding="utf-8")
        self.assertNotEqual(self.gate("advance", "complete").returncode, 0)
        self.assertEqual(self.gate("reopen", "frontmatter", "--reason", "abstract changed").returncode, 0)
        self.add_accepted_frontmatter()
        self.assertEqual(self.gate("advance", "audit").returncode, 0)
        self.add_final_review()
        self.assertEqual(self.gate("advance", "complete").returncode, 0)

    def test_reassessment_requires_fresh_figure_and_frontmatter_reviews(self):
        self.through_drafting_with_accepted_section()
        self.assertEqual(self.gate("advance", "figures").returncode, 0)
        self.add_accepted_figure()
        self.assertEqual(self.gate("advance", "frontmatter").returncode, 0)
        self.add_accepted_frontmatter()
        self.assertEqual(self.gate("reassess", "S1", "--reason", "body evidence needs reassessment").returncode, 0)

        self.assertEqual(self.gate("dispatch", "S1", "--delegate", "agent-b").returncode, 0)
        self.write("05_sections/S1.md", "Reassessed chapter with updated evidence")
        self.assertEqual(self.gate("submit", "S1", "--file", "05_sections/S1.md").returncode, 0)
        self.write("08_audit/S1.json", {"section_id":"S1", "decision":"accept", "reason":"rechecked",
                    "checks":{k:True for k in ("scope","evidence","consistency","synthesis","citations","defensive_writing")},
                    "synthesis_findings":[{"synthesis_id":"SYN1", "integrated_claim":"Conditional comparison across two papers.",
                      "evidence_ids":["A","B"], "counterevidence_handling":"The limitation in B qualifies the trend."}]})
        self.assertEqual(self.gate("accept", "S1", "--review", "08_audit/S1.json").returncode, 0)
        self.assertEqual(self.gate("advance", "figures").returncode, 0)
        self.assertNotEqual(self.gate("advance", "frontmatter").returncode, 0)

        self.add_accepted_figure()
        self.assertEqual(self.gate("advance", "frontmatter").returncode, 0)
        self.assertNotEqual(self.gate("advance", "audit").returncode, 0)
        self.add_accepted_frontmatter()
        self.assertEqual(self.gate("advance", "audit").returncode, 0)

    def test_figure_review_requires_style_conformance(self):
        self.through_drafting_with_accepted_section()
        self.assertEqual(self.gate("advance", "figures").returncode, 0)
        self.add_accepted_figure()
        path = self.run / "06_figures/figure-review.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        report["figures"][0]["style_review"]["selected_references"] = []
        path.write_text(json.dumps(report), encoding="utf-8")
        result = self.gate("advance", "frontmatter")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("selected reference", result.stderr)

    def test_minimum_figure_and_table_counts_are_enforced(self):
        self.through_drafting_with_accepted_section()
        self.assertEqual(self.gate("advance", "figures").returncode, 0)
        self.add_accepted_figure()
        review_path = self.run / "06_figures/figure-review.json"
        review = json.loads(review_path.read_text(encoding="utf-8"))
        review["figures"].pop()
        review_path.write_text(json.dumps(review), encoding="utf-8")
        result = self.gate("advance", "frontmatter")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("at least 5", result.stderr)

        self.add_accepted_figure()
        self.assertEqual(self.gate("advance", "frontmatter").returncode, 0)
        self.add_accepted_frontmatter()
        self.assertEqual(self.gate("advance", "audit").returncode, 0)
        self.add_final_review()
        manuscript = self.run / "07_manuscript/review.md"
        text = manuscript.read_text(encoding="utf-8")
        text = text.replace("\n\nTable 4. Table 4 caption\n\n| Category | Evidence |\n\n|---|---|\n\n| Item 4 | Source 4 |", "")
        manuscript.write_text(text, encoding="utf-8")
        final_review = self.run / "08_audit/final-review.json"
        report = json.loads(final_review.read_text(encoding="utf-8"))
        report["manuscript_sha256"] = hashlib.sha256(manuscript.read_bytes()).hexdigest()
        final_review.write_text(json.dumps(report), encoding="utf-8")
        result = self.gate("advance", "complete")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("minimum is 4", result.stderr)

    def test_strict_phase_and_serial_chapter_order_and_invalidation(self):
        self.assertNotEqual(self.gate("advance", "searching").returncode, 0)
        self.through_evidence()
        (self.run / "04_evidence/coverage.json").unlink()
        self.assertNotEqual(self.gate("advance", "outline").returncode, 0)
        self.write_evidence_synthesis(self.ready_ledger())
        self.assertEqual(self.gate("advance", "outline").returncode, 0)
        self.write("01_plan/outline.md", "final outline")
        self.write("01_plan/sections.json", [{"id":"S1","priority":1,"reason":"primary","question_ids":["Q1"],"synthesis_ids":["SYN1"],"depends_on":[]}, {"id":"S2","priority":2,"reason":"following","question_ids":["Q2"],"synthesis_ids":["SYN1"],"depends_on":["S1"]}])
        self.assertEqual(self.gate("advance", "drafting").returncode, 0)
        self.assertNotEqual(self.gate("dispatch", "S2", "--delegate", "agent-b").returncode, 0)
        self.assertEqual(self.gate("dispatch", "S1", "--delegate", "agent-a").returncode, 0)
        self.assertNotEqual(self.gate("dispatch", "S2", "--delegate", "agent-b").returncode, 0)
        self.write("05_sections/S1.md", "Draft with evidence")
        self.assertEqual(self.gate("submit", "S1", "--file", "05_sections/S1.md").returncode, 0)
        review = {"section_id":"S1", "decision":"accept", "reason":"verified", "checks":{k:True for k in ("scope","evidence","consistency","synthesis","citations","defensive_writing")},
                  "synthesis_findings":[{"synthesis_id":"SYN1", "integrated_claim":"Conditional cross-study comparison.", "evidence_ids":["A","B"], "counterevidence_handling":"The studies use different protocols."}]}
        self.write("08_audit/S1.json", review)
        self.assertEqual(self.gate("accept", "S1", "--review", "08_audit/S1.json").returncode, 0)
        self.assertEqual(self.gate("dispatch", "S2", "--delegate", "agent-b").returncode, 0)
        self.assertNotEqual(self.gate("invalidate", "S1", "--reason", "found an error").returncode, 0)
        self.write("05_sections/S2.md", "second section")
        self.assertEqual(self.gate("submit", "S2", "--file", "05_sections/S2.md").returncode, 0)
        review["section_id"] = "S2"
        self.write("08_audit/S2.json", review)
        self.assertEqual(self.gate("accept", "S2", "--review", "08_audit/S2.json").returncode, 0)
        self.assertEqual(self.gate("invalidate", "S1", "--reason", "found an error").returncode, 0)
        state = json.loads((self.run / "run-state.json").read_text(encoding="utf-8"))
        self.assertEqual([x["state"] for x in state["sections"]], ["pending", "pending"])
        self.assertEqual([e["seq"] for e in state["events"]], list(range(1, len(state["events"])+1)))

    def test_limited_run_and_v1_immutability(self):
        state = self.run / "run-state.json"
        old = json.loads(state.read_text(encoding="utf-8"))
        for version in (1, 2):
            old["schema_version"] = version
            state.write_text(json.dumps(old), encoding="utf-8")
            self.assertNotEqual(self.gate("limited", "--reason", "missing evidence").returncode, 0)
            self.assertEqual(json.loads(state.read_text(encoding="utf-8"))["schema_version"], version)


if __name__ == "__main__":
    unittest.main()
