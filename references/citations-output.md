# Citations and deliverables

Maintain one curated references.bib with stable citation keys. Reuse one key for repeated citations to the same work; keep distinct reports distinct and record related versions. Assemble the accepted title, abstract, introduction, review approach, body chapters in final reading order, figure/table placements and conclusion into `07_manuscript/review.source.md`. Use the accepted method-transparency disposition: include the approach section or integrate its content at the recorded location without duplicating it. Chapter drafts, figure captions and table cells retain stable Pandoc keys such as [@ref-A]; never assign independent chapter-level reference numbers.

## Reference-count and recency audit

The final manuscript must cite at least 40 distinct works. At least 60% must be from the latest five publication years. Count unique citation keys used in the assembled source and resolved to bibliography entries; repeated citations count once, unused bibliography entries do not count, and duplicate keys for the same work must be consolidated. Anchor the window to the date in run-state.json created_at. For year-only metadata, use the run year and four preceding calendar years. A missing or unverifiable year stays in the total but does not count as recent. Require recent_count >= ceil(0.60 * total_count); exactly 40 cited works therefore require at least 24 recent works.

Record the audit in 08_audit/final-review.json under reference_audit: anchor date, cutoff year, unique cited keys, year for each key, total, recent count and share. Derive keys from the final Pandoc citation parse, verify years against bibliography metadata, and recalculate after any citation change. Search-result counts and unused bibliography entries cannot satisfy the threshold. If relevant searches cannot meet either threshold after bounded work, mark the run limited; do not pad with irrelevant or unverified citations.

## Figures and tables

Use {{fig:figure-01}} for an in-text reference and {{figure:figure-01}} for a single placement. Map each stable figure ID to a JSON record containing path and caption; paths are relative to the source. Run scripts/assemble_figures.py SOURCE --figures FIGURES.json --output ASSEMBLED.md --map FIGURE_MAP.json. Placement order sets numbering. Every placed image must match one accepted record in 06_figures/figure-review.json. The final image is the generated high-resolution PNG; there is no Draw.io recreation stage.

The main manuscript requires at least five numbered figures and four captioned Markdown tables. Number figures and tables sequentially in final reading order and cite each near its discussion. Each table uses a caption such as “Table 1. Descriptive caption” immediately above a Markdown pipe table. Keep table content evidence-linked and distinct; a plan or supplement does not count toward the main-text minimum.

## Default output and PDF

The accepted source Markdown retains citation keys. Use scripts/render_pdf.py SOURCE --bibliography REFERENCES --output PDF --readable-output READABLE_MD to produce a citation-resolved readable Markdown file and its PDF. The default package includes the source Markdown, readable Markdown, PDF, references.bib, accepted PNGs, captions, search/evidence records and audit artifacts. Do not produce DOCX unless the user asks for it.

The bundled default is a generic numeric CSL, not a verified journal style; pass --csl STYLE when the target venue requires one. The exporter validates Pandoc citation keys and duplicate BibTeX keys. The PDF runner then uses the bundled Pandoc/HTML/Chromium pipeline and runs layout and text checks. Read references/pdf-output.md for parameters, dependencies and acceptance. A PDF is complete only after the JSON validation passes and the primary agent inspects the contact sheet and any flagged pages.

The selected title must match the manuscript metadata, visible heading and every output. Keep title acceptance records in the audit package, but do not include rejected candidates in the submission folder. Include only files permitted and appropriate for submission, not downloaded third-party articles, retrieval logs or concept drafts.
