# Core-question framing

Every review starts from a focused question that can be answered by synthesizing a body of research. A broad domain is an interest area, not yet a review plan. The primary agent owns the framing and makes a defensible narrowing choice from the user's stated interests, constraints and available evidence; it records assumptions instead of repeatedly interrupting the user.

## Frame the question

Write one core question and describe four dimensions:

- **Task or context:** the population, task, setting, data type or theoretical context.
- **Phenomenon or method:** the mechanism, method family, intervention or relationship being examined.
- **Outcome or trade-off:** what the review will compare or explain, such as performance, robustness, interpretability, cost or failure modes.
- **Conditions or boundaries:** the conditions that may change the answer, such as supervision budget, dataset, protocol, model scale or deployment setting.

Use the dimensions that fit the field. The question should be concrete enough to determine inclusion and exclusion decisions, yet broad enough to support synthesis across multiple studies. Decompose it into answerable subquestions. Give each subquestion a stable ID, search concepts and a clear role in answering the core question. Every eventual body chapter must map to one or more subquestion IDs; every subquestion must be answered by at least one chapter.

For a broad user topic, choose a focus that has a coherent evidence base, a meaningful comparison or unresolved synthesis, and enough eligible literature for the requested review. Check whether recent reviews already answer the same question. Do not retain a broad scope just to reach the bibliography threshold or figure/table minimums. If several plausible focuses remain, select the one best supported by the user's constraints and the pilot evidence, and explain the choice in `focus_rationale`.

## Pilot, refine and lock

Before full discovery, run a bounded scoping search across the subquestions. It is a feasibility check, not the final search. Record the actual queries and sources, approximate result volume, existing-review coverage, evidence of a synthesis gap and the decision in `02_search/pilot-search.md`. Compare relevant prior reviews in `02_search/prior-reviews.json` and state a specific, evidence-supported contribution for the proposed review. If the search finds no close predecessor, retain the searches and explain the result; do not treat absence from one index as proof of novelty.

If the result set is too large to synthesize coherently, narrow the task, method, setting, outcome or conditions. If it yields too little eligible evidence, broaden one dimension while preserving the core problem. If an existing review already answers the question, identify a defensible difference in period, task, evidence base or analytical angle. Repeat a bounded pilot as needed. Lock the question only when it is answerable, distinct enough to justify a review and feasible with available evidence. The full search must begin from the locked version.

Once locked, treat a material change to the core question or scope as a new review run: the search strategy, coverage assessment and outline all depend on it. The gate checks file structure and hashes; the primary agent still judges focus, answerability, evidence volume and the value of the synthesis.

## Run record

Save `01_plan/core-question.json` before the first scoping search. Its proposed form contains:

```json
{
  "status": "proposed",
  "core_question": "How do ... under ... conditions?",
  "working_title": "Focused topic: analytical dimension",
  "focus_rationale": "Why this question is coherent and useful",
  "dimensions": {
    "task_or_context": "...",
    "phenomenon_or_method": "...",
    "outcome_or_tradeoff": "...",
    "conditions_or_boundaries": "..."
  },
  "include_boundaries": ["..."],
  "exclude_boundaries": ["..."],
  "subquestions": [
    {"id": "Q1", "question": "...", "search_concepts": ["...", "..."]},
    {"id": "Q2", "question": "...", "search_concepts": ["...", "..."]}
  ]
}
```

After a feasible pilot, change `status` to `locked` and add `pilot_search` with `artifact` (`02_search/pilot-search.md`), `decision` (`feasible`), `volume_assessment`, `existing_reviews`, `synthesis_gap` and `prior_reviews_artifact` (`02_search/prior-reviews.json`). The primary agent evaluates the prior-review comparison and contribution against the cited reviews before full discovery.

For example, “AI in medicine” is too broad. A focused question might ask how interpretability methods for deep-learning cancer imaging systems are evaluated, what evidence they provide to clinicians, and how those evaluations vary by cancer type, imaging modality and validation setting. Its boundaries decide which papers the search should retrieve and which claims the review can make.
