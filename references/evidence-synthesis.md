# Evidence appraisal and cross-study synthesis

Use this reference after full discovery and coverage screening, before the final outline. It applies to the default critical narrative review. It is not a systematic-review risk-of-bias protocol.

## Prior-review comparison

Before locking the core question, save `02_search/prior-reviews.json`. Record the actual sources, queries, dates and screening outcome used to locate earlier reviews. For each relevant review, capture its verified title, year, URL, scope, coverage period, organizing framework and limitations. If no close review exists, record the searches and why the results do not contain a direct predecessor. End with a specific contribution statement explaining what the proposed review adds and why the evidence supports that distinction. Do not infer novelty from an empty search result alone.

The locked `core-question.json` points to this artifact in `pilot_search.prior_reviews_artifact`. The primary agent checks the records against the cited reviews before full discovery.

Each review entry uses `id`, `title`, `year`, `url`, `scope`, `coverage_period`, `organizing_framework` and `limitations`. If the search finds no close review, set `reviews` to an empty array and provide `no_close_review_reason`. The report also contains `status: "reviewed"`, a nonempty `searches` array (`source`, `query`, `date`, `status`, `results_screened`), `contribution_statement` and `difference_basis`. At least one search must have succeeded; a failed review landscape scan is not evidence of novelty.

## Domain-fit appraisal

Save `04_evidence/appraisal.json` with:

```json
{
  "criteria": [
    {"id":"A1", "name":"Criterion", "definition":"What is assessed", "relevance":"Why it matters to this question"}
  ],
  "assessments": [
    {"candidate_id":"paper-id", "criterion_id":"A1", "rating":"qualified", "rationale":"Source-grounded assessment", "locator":"section or page actually inspected"}
  ]
}
```

Define criteria from the question and study types. In CS, relevant dimensions may include data and benchmark validity, split or leakage risks, baseline fairness, metrics, ablations and uncertainty, compute reporting, reproducibility, and external validity. Select only dimensions that matter. Use `strong`, `qualified`, `weak`, `not_assessable` or `not_applicable`; explain every rating and cite an observed locator. Do not compute a universal quality score. Assess every important included primary study at least on the dimensions relevant to its central claims. Use `not_assessable` when the available source does not support a judgment, and narrow prose claims accordingly. Appraisal informs interpretation; it is not an automatic exclusion filter.

## Synthesis matrix

Save `04_evidence/synthesis-matrix.json`:

```json
{
  "units": [
    {
      "id":"SYN1", "question_ids":["Q1"], "claim":"A cross-study synthesis claim",
      "comparison_axes":["assumption", "evaluation condition"],
      "conditions":["conditions that change the interpretation"],
      "evidence":[
        {"candidate_id":"paper-a", "relation":"supports", "locator":"section 3"},
        {"candidate_id":"paper-b", "relation":"qualifies", "locator":"table 2"}
      ],
      "counterevidence_analysis":"How conflicting or qualifying findings affect the claim",
      "confidence":"moderate", "confidence_rationale":"Why this strength matches the evidence"
    }
  ],
  "gaps": [
    {"id":"G1", "description":"An evidence-grounded gap", "basis_unit_ids":["SYN1"], "research_direction":"A focused next question or study"}
  ]
}
```

Every unit must map to at least one locked subquestion, compare at least two distinct included papers, and link observed evidence locators. Relations are `supports`, `qualifies` or `contradicts`. Confidence labels are qualitative judgments, not pooled statistics. The primary agent verifies that the claim, counterevidence and confidence rationale match the cited sources. Every subquestion needs at least one unit. Each gap must point to synthesis units and give a research direction; recommendations must follow from the evidence, not generic boilerplate.

Before outline approval, save `08_audit/evidence-synthesis-review.json`. Its `inputs` object records `coverage_sha256`, `appraisal_sha256` and `synthesis_matrix_sha256` as file hashes, plus `evidence_sha256`, a SHA-256 fingerprint of the evidence-file hash mapping for included full-text sources. Include `decision` (`accept` or `revise`), a reason, nonempty `findings`, and a `checks` object with `criteria_fit`, `source_grounding`, `cross_study_synthesis`, `counterevidence` and `contribution_support`. All five checks must be true for acceptance. A change to any input requires a fresh review.

## Chapter and conclusion links

Each `sections.json` entry includes `synthesis_ids` in addition to `question_ids`. All synthesis units must be represented in the body outline. A chapter acceptance record includes a `synthesis_findings` array with one entry per assigned unit. Each entry uses `synthesis_id`, `integrated_claim`, `evidence_ids` (at least two IDs drawn from that unit) and `counterevidence_handling`. The primary agent returns a chapter for delegated revision when its synthesis finding is only a list of paper summaries.

Before completion, `08_audit/research-agenda-review.json` contains `accepted: true`, a reason, the accepted conclusion path, and `inputs` with `synthesis_matrix_sha256` and `conclusion_sha256`. Its `directions` array maps every synthesis-matrix gap ID to a `recommendation`, `evidence_basis` and `conclusion_locator`. The primary agent checks that each recommendation follows from the reviewed evidence.

## Manuscript method disclosure

After the search is complete, delegate `07_manuscript/review-approach.md` from the locked question and actual search/screening logs. It should concisely state the review type, information sources, search date or cutoff, key query concepts, eligibility logic, citation-tracing approach and synthesis method, at the level expected by the target venue. Do not claim exhaustive or systematic retrieval unless the method supports that claim. The frontmatter review records `review_approach`, and a `method_transparency` object with `accepted: true`, `search_log_verified: true`, a `disposition` (`included` or `integrated`) and a rationale. The primary agent verifies it against the logs. If the venue requires the information to be integrated elsewhere, record that disposition and where it appears; still retain the reviewed approach artifact in the audit package.
