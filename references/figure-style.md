# User-provided figure style references

Use these images only to guide visual hierarchy, palette, grouping and composition. They are not scientific sources. Do not copy their claims, wording, data, logos or complete layouts into a new review figure.

| File | Useful visual qualities | Best fit | Cautions |
|---|---|---|---|
| assets/Reference Figures/reference-01-agent-system-workflow.png | Two-panel comparison, pastel module fills, restrained outlines and direct arrows | System architecture; overview plus one mechanism | Keep panel labels readable at print size |
| assets/Reference Figures/reference-02-agent-workflow-repair.png | Left-to-right stages, blue framing and nested detail panels | Review workflow or multi-stage process | Dense; simplify to the central stages |
| assets/Reference Figures/reference-03-multimodal-model-architecture.png | Semantic color families and explicit data flow | Multimodal or multi-branch architecture | Avoid garbled handwriting, gradients and decorative icons |
| assets/Reference Figures/reference-04-evaluation-checklist.png | Clear sections, checklist grouping and validation loop | Evaluation framework or protocol checklist | Borrow grouping, not clip art, shadows or decorative treatment |
| assets/Reference Figures/reference-05-frequency-model-mechanism.png | Compact technical pipeline, restrained accents and intermediate representations | Model mechanism or computational pipeline | Preserve only evidence-backed equations and symbols |
| assets/Reference Figures/reference-06-world-model-taxonomy.png | Branching taxonomy around a central topic | Field map or broad method taxonomy | Simplify dense labels; avoid tiny text |
| assets/Reference Figures/reference-07-image-editing-taxonomy.png | Timeline-like bands and grouped method families | Historical development or method taxonomy | Maintain a clear reading direction |
| assets/Reference Figures/reference-08-autonomous-driving-map.png | Multiple research streams and category labels | Taxonomy combining research directions | Avoid logo copying, tiny text and unsupported branches |

## Shared style direction

Prefer a white or very light background, strong contrast, clean alignment and generous whitespace. Use a small consistent palette with stable semantic color mapping. Make hierarchy visible through size, grouping and spacing before decoration. Use consistent sans-serif labels. Arrows must represent an evidence-backed relation or process. Avoid logos, clip art, heavy shadows and gradients unless the figure's data or venue requires them.

## Make the references operational

Before generation, inspect the selected image files and delegate 06_figures/figure-style-guide.md. Describe the shared background, palette, semantic color mapping, typography, line and arrow treatment, spacing, hierarchy, framing, label density, contrast and grayscale behavior. Separate shared style tokens from figure-specific composition.

Pass one to three actual bundled image paths to each generation task when image conditioning is supported. Map each figure ID to its selected files and the exact features to borrow. The primary agent compares the final PNG against both the accepted figure plan and the shared guide. A named reference without visible, purposeful style transfer does not pass.
