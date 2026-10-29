#!/usr/bin/env python3
"""Measure PDF geometry, fonts, page density and overflows; rasterize all pages."""
import argparse
import json
import re
from pathlib import Path

import pymupdf

MM = 72 / 25.4
FOOTER = re.compile(r"(?:第\s*\d+\s*页\s*/\s*共\s*\d+\s*页|Page\s+\d+\s+of\s+\d+)", re.I)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--page-dir", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--require-math-font", action="store_true")
    args = parser.parse_args()
    args.page_dir.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(args.pdf)
    first = doc[0].rect
    page_geometry = abs(first.width - 595.28) <= 2 and abs(first.height - 841.89) <= 2
    reference_start = None
    for page_number, page in enumerate(doc):
        for block in page.get_text("blocks"):
            value = str(block[4]).strip()
            if re.search(r"(?im)^\s*(?:references|bibliography|参考文献)\s*$", value):
                reference_start = (page_number, block[1])
                break
        if reference_start is not None:
            break
    content = {"left": 18 * MM, "right": first.width - 18 * MM,
               "top": 20 * MM, "bottom": first.height - 20 * MM}
    overflows, sparse_pages = [], []
    sizes, fonts = {}, {}
    for page_number, page in enumerate(doc, 1):
        page_text = page.get_text().strip()
        image_area = 0.0
        for image in page.get_images(full=True):
            for rect in page.get_image_rects(image[0]):
                image_area += max(0, rect.width) * max(0, rect.height)
        page_area = page.rect.width * page.rect.height
        if len(re.sub(r"\s+", "", page_text)) < 24 and image_area < page_area * 0.08:
            sparse_pages.append(page_number)
        for block in page.get_text("blocks"):
            x0, y0, x1, y1 = block[:4]
            value = str(block[4]).strip()
            if FOOTER.search(value):
                continue
            if x0 < content["left"] - 3 or x1 > content["right"] + 3:
                overflows.append({"page": page_number, "axis": "x", "text": value[:40]})
            if y0 < content["top"] - 12 or y1 > content["bottom"] + 3:
                overflows.append({"page": page_number, "axis": "y", "text": value[:40]})
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    if reference_start is None or page_number - 1 > reference_start[0]:
                        continue
                    if page_number - 1 == reference_start[0] and span["bbox"][1] >= reference_start[1]:
                        continue
                    size = round(span["size"], 1)
                    sizes[size] = sizes.get(size, 0) + len(span["text"])
        for font in page.get_fonts(full=True):
            xref = font[0]
            name = font[3].strip()
            if not name:
                continue
            try:
                embedded_data = doc.extract_font(xref)[3]
            except Exception:
                embedded_data = b""
            record = fonts.setdefault(name, {"name": name, "embedded": bool(embedded_data)})
            record["embedded"] = record["embedded"] and bool(embedded_data)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(110 / 72, 110 / 72), alpha=False)
        pix.save(args.page_dir / ("page-%02d.png" % page_number))
    dominant = max(sizes, key=sizes.get) if sizes else 0
    font_names = [name.lower().replace(" ", "").replace("-", "") for name in fonts]
    embedded_values = [entry["embedded"] for entry in fonts.values()]
    families_present = ("simsun" in " ".join(font_names)
                        and "timesnewroman" in " ".join(font_names))
    if args.require_math_font:
        families_present = families_present and "cambriamath" in " ".join(font_names)
    checks = {
        "page_geometry": page_geometry,
        "body_font": reference_start is not None and abs(dominant - 14.0) <= 0.2,
        "margin_overflow": len(overflows) == 0,
        "sparse_pages": len(sparse_pages) == 0,
        "fonts_embedded": families_present and all(embedded_values),
    }
    report = {
        "status": "passed" if all(checks.values()) else "failed",
        "pages": doc.page_count,
        "page_size_pt": [round(first.width, 2), round(first.height, 2)],
        "dominant_font_pt": dominant,
        "body_font_scope": "main text before references",
        "reference_heading_found": reference_start is not None,
        "font_size_counts": sizes,
        "fonts": list(fonts.values()),
        "blocks_outside_margins": overflows,
        "sparse_pages": sparse_pages,
        "page_rasters": str(args.page_dir.resolve()),
        "checks": checks,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
