#!/usr/bin/env python3
"""Print processed HTML to a temporary PDF using headless Chromium."""
import argparse
import json
import os
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_name(args.output.stem + ".tmp.pdf")
    footer = (
        '<div style="width:100%;font-family:\'Times New Roman\',SimSun,serif;'
        'font-size:9pt;color:#000;text-align:center;">'
        '第 <span class="pageNumber"></span> 页 / 共 '
        '<span class="totalPages"></span> 页</div>'
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1240, "height": 1754})
        page.goto(args.html.resolve().as_uri(), wait_until="load")
        page.evaluate("() => document.fonts.ready")
        missing = page.evaluate(
            """async () => {
                const images = Array.from(document.images);
                await Promise.all(images.map(image => image.decode().catch(() => {})));
                return images.filter(image => !image.complete || image.naturalWidth === 0)
                    .map(image => image.currentSrc || image.src);
            }"""
        )
        if missing:
            browser.close()
            raise SystemExit("unloaded figure images: " + json.dumps(missing, ensure_ascii=False))
        page.emulate_media(media="print")
        page.pdf(
            path=str(temp),
            prefer_css_page_size=True,
            print_background=True,
            display_header_footer=True,
            header_template="<div></div>",
            footer_template=footer,
            margin={"top": "20mm", "bottom": "20mm", "left": "18mm", "right": "18mm"},
            tagged=True,
            outline=True,
        )
        browser.close()
    if not temp.is_file() or not temp.stat().st_size:
        raise SystemExit("Chromium did not produce a nonempty PDF")
    os.replace(temp, args.output)
    print(json.dumps({"status": "rendered", "pdf": str(args.output), "bytes": args.output.stat().st_size}))


if __name__ == "__main__":
    main()
