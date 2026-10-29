# Review title naming

Use this guide for the final title of a narrative review. It distills the user-provided `survey-title-naming-reference.md`; its sample statistics and long example catalog are not general publication rules.

## Timing and ownership

Create a provisional working title when the core question is framed; it should already reflect the chosen task and analytical focus. Name the final review after all body sections, figures/tables, abstract, introduction and conclusion have passed review and cross-section corrections are complete. Delegate final title generation to a subagent using the locked core question and boundaries, complete accepted manuscript, scope, article type, outline, target venue and language. The title must represent the question the manuscript actually answers and must not broaden its scope. The primary agent checks the candidates and accepts one. If none is accurate and usable, delegate a revision; do not rewrite the title itself. Integrate the exact accepted wording into manuscript metadata and the visible title. If accepted content later changes, repeat title generation and review.

## Generate grounded candidates

Identify the topic's standard searchable terms, the actual scope boundaries, and the review's real analytical perspective. Generate 4–6 materially different candidates across at least three suitable patterns, chosen from:

- Topic or domain + `A Survey` / `A Review`.
- Topic + the substantive dimensions actually covered, such as methods, evaluation, applications or challenges.
- Technology + application domain, when the review genuinely covers that intersection.
- `From X to Y`, only when the evidence supports a real historical or conceptual transition.
- A research-question or problem-led title, only when the manuscript develops and answers that question.

Prefer a clear topic-first title. A colon is common and useful, but optional. Keep the title compact and searchable without enforcing a fixed word count. Follow the target venue's title and article-type conventions when known; otherwise use the manuscript's primary language. Provide a translation only when requested or useful, and keep both versions semantically aligned.

## Accuracy checks

- Use `Survey` or `Review` according to the field and venue; do not imply a method the manuscript did not use.
- Use `Systematic Review` or `Scoping Review` only when the corresponding method was actually followed and reported.
- Use `Comprehensive`, `Critical`, `Unified`, `General`, or similar claims only when the scope and analysis support them.
- Every dimension promised in a subtitle must receive substantive treatment in the final manuscript.
- Do not force parallel methods into a false `From X to Y` progression, claim novelty without evidence, or use hype such as `ultimate`, `revolutionary`, or `definitive`.
- Search for exact and close title matches in relevant scholarly indexes or the target venue when search tools are available. Record what was checked; an unavailable search is a limitation, not proof of uniqueness.

Score candidates as a ranking aid, not as an acceptance probability: scope and factual accuracy (30), topic clarity (25), useful analytical distinction (20), searchability (15), and concision/readability (10). Hard accuracy failures override the numerical score.

## Title task and acceptance record

The delegate returns `07_manuscript/title-review.json` with the current `frontmatter_inputs` binding copied from `run-state.json` (`generation`, `cycle`, `body_fingerprint`, `figure_fingerprint`), `status`, `selected_title`, `language`, `article_type`, 4–6 `candidates` (each with title, pattern, score and rationale), `checks` (scope match, article-type support, promised dimensions present, searchable terminology), `similarity_check` (sources/results or `unavailable` with reason), and a substantive `reason`. The primary agent verifies the record against the actual final manuscript, accepts it, or sends it back for delegated revision. Copy the accepted title exactly into manuscript metadata and the visible title; the final audit checks consistency and rejects stale bindings.
