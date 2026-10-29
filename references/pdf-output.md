# Markdown-to-PDF production

The canonical manuscript remains Markdown. Default final outputs are the accepted citation-key source Markdown, a citation-resolved readable Markdown file, and the PDF rendered from that readable Markdown. Do not create DOCX unless the user explicitly requests it.

Use the bundled unattended pipeline:

    python scripts/render_pdf.py SOURCE.md --bibliography references.bib --output review.pdf --readable-output review.final.md

The runner preserves each stage under pdf-build/: citation-resolved Markdown copy, prepared Markdown, HTML, the final PDF candidate as out.pdf, page rasters, page metrics, content validation and contact-sheet.png. It promotes out.pdf to the requested final path only after all automated checks pass. If the requested output is locked, retain out.pdf and report that promotion failed; do not overwrite it by truncating an open file.

## Four-stage render chain

1. **Prepare:** validate and resolve stable Pandoc citation keys using export.py. Merge adjacent numeric citation groups, sort numbers within a group, protect inline/display TeX and MathML from citation processing, and place one bibliography entry in each paragraph. Preserve the source and its images. Save every intermediate.
2. **Pandoc:** render Markdown to standalone HTML5 using native MathML, bundled authored.css and print.css. Do not depend on a math CDN or external network. Resolve image links relative to the Markdown source directory.
3. **Post-process:** turn body citation markers into superscripts without touching MathML or bibliography numbers; classify table captions/notes and figure-source notes; wrap the references block; add natural zero-width URL break points; attach a base URL so relative images still resolve from the source directory.
4. **Chromium print:** print A4 with the bundled footer. Wait for fonts and image decoding. Render to pdf-build/out.pdf first; never declare success until it passes PDF and text checks.

## Layout defaults

Use A4 paper with 20 mm top/bottom and 18 mm left/right margins; Chinese body text in SimSun and Latin text in Times New Roman, 14 pt, 1.5 line spacing, justified, first-line indent of two characters. Use a centered 16 pt level-one title; 9.5 pt table cells with repeating headers and unsplit rows; 10.5 pt figure captions and bibliography; 0.6 em citation superscripts in body text and 0.8 em inside tables; and a centered “第 N 页 / 共 M 页” footer. Keep captions visually bound to their figure or table.

References are left-aligned with a 2.1 em hanging indent. Insert zero-width break opportunities after URL punctuation (slash, period, underscore and hyphen) so long URLs wrap without large justified gaps or broken words. Keep heading with following content, repeat table headers across pages, prevent figure and caption separation, and avoid forcing the references onto a new page.

## Required safeguards

- Chromium may silently scale an over-wide page. The renderer must assert that the dominant body size remains 14.0 pt (±0.2 pt); fail and repair layout overflow rather than accepting a smaller document.
- Protect math spans before citation merging or superscript conversion. Remove TeX annotations from MathML if they would print as stray duplicate text.
- Raise citations with relative positioning, not vertical-align: super, so line boxes retain their intended rhythm. Keep a citation and its following punctuation together.
- Prevent long URLs from forcing justified spaces. Do not split words at arbitrary character positions.
- Check page geometry, dominant body size, left/right overflow, sparse pages, embedded fonts, image decoding, Markdown residue, figure/table captions and reference extraction. Generate page rasters and a contact sheet for visual inspection.
- Retain build/doc.html, build/out.pdf, page images, check/validation JSON and the contact sheet. Automated success is not visual acceptance: the primary agent must inspect the contact sheet and any pages flagged by metrics before completing the run.

Pandoc, Python Playwright with an installed Chromium browser, PyMuPDF, and Pillow are required for the full default PDF workflow. If a dependency is missing, record which check failed and do not claim a verified PDF. Keep the accepted Markdown and any successful intermediate artifacts.
