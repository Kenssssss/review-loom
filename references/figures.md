# Figure and table workflow

Start only after all body chapters pass acceptance. Read the complete accepted manuscript, evidence ledger and venue constraints before planning visuals. Use five to eight separately numbered figures and four to six tables by default, with hard minima of five figures and four tables in the main manuscript. A panel does not count as a separate figure; supplementary-only material does not count.

## Figure planning

Delegate 06_figures/figure-plan.md. For every stable figure ID, specify:

- the distinct reader question and purpose;
- the chapter placement and nearby prose reference;
- the claims or synthesis to show, with evidence file and source locators;
- exact labels, categories, method families and relationships;
- the intended composition, reading direction and target print width;
- one to three bundled style-reference images and the concrete visual properties to borrow.

Across the figure set, use at least three composition types, such as taxonomy, timeline, process, architecture, comparison matrix, conceptual synthesis or challenge map. Do not repeat one layout merely to meet the minimum. Every figure must add information and must not imply a causal or quantitative relationship that its evidence does not support.

## Generate the final image directly

Generate each figure as the final image that will appear in the manuscript. Do not create an intermediate reference for later Draw.io reconstruction. Use the accepted plan and evidence as the content source; use bundled images only for visual style. Give the image generator the actual reference image files when supported. The prompt must state the reader question, exact short labels, evidence-backed entities and relationships, grouping, reading direction, composition, visual style, target aspect ratio and intended print width. Explicitly prohibit invented claims, numbers, citations, logos and unsupported arrows.

Save one high-resolution PNG per figure under 06_figures/, plus an evidence note and a generation record containing the exact prompt and selected style-reference filenames. Keep a shared palette and type hierarchy across the figure set, while varying composition to fit each figure's purpose.

The figure subagent must inspect its actual PNG at the intended publication size before submission. The image must:

- provide at least 300 effective DPI at the declared print width; for example, about 1004 px wide at 85 mm or 2126 px at 180 mm;
- keep every key label legible at that size, with correct spelling and no pseudo-text;
- have clear hierarchy, adequate contrast, unclipped content, clean edges and no generation artifacts;
- show the planned claims and relationships without adding unsupported material;
- remain readable in grayscale where color is not essential to meaning.

Do not silently accept a low-resolution image, garbled text or decorative complexity that obscures the argument. Regenerate or use an authorized higher-resolution export path. If quality cannot be achieved within bounded attempts, record the blocker and deliver a limited result.

## Primary-agent acceptance

The primary agent opens and inspects every submitted PNG, compares its labels, entities and relationships against the accepted figure plan and cited full-text evidence, and checks that no generated detail changes the paper's claims. It also checks print-size legibility, resolution, clipping, contrast and coherence across the full figure set.

Record the primary agent's content decision in 06_figures/figure-review.json. For a mismatch, mark the figure as rejected in the review record, preserve the finding in the revision history, and delegate a corrected image to a subagent. Do not repair the generated image or rewrite the manuscript yourself to fit a faulty image. Reinspect the replacement and the complete figure set before accepting the phase. No frontmatter work may start until every figure passes.

Use the assembler to insert only accepted PNGs into the manuscript. Each figure must have one in-text marker and one placement marker; numbering follows final reading order. Captions and in-text references use stable citation keys until final citeproc rendering. The figure manifest must map one-to-one to every placed image.

## Tables

Delegate a table plan with at least four distinct tables, each with a purpose, placement, comparison fields and evidence locators. Delegate table authoring and corrections. The primary agent checks each cell against its source, the table's comparison logic, terminology, citation keys and nearby prose. Integrate each accepted table once as a Markdown pipe table with a single sequential caption immediately above it. Cite each table in nearby prose.
