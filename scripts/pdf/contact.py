#!/usr/bin/env python3
"""Create a labeled contact sheet from the page rasters."""
import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pages-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--columns", type=int, default=6)
    parser.add_argument("--thumbnail-width", type=int, default=240)
    args = parser.parse_args()
    pages = sorted(args.pages_dir.glob("page-*.png"))
    if not pages:
        parser.error("no page rasters found")
    if args.columns < 1 or args.thumbnail_width < 1:
        parser.error("columns and thumbnail width must be positive")
    with Image.open(pages[0]) as first:
        thumb_height = round(first.height * args.thumbnail_width / first.width)
    rows = math.ceil(len(pages) / args.columns)
    padding = 8
    sheet = Image.new(
        "RGB",
        (args.columns * (args.thumbnail_width + padding) + padding,
         rows * (thumb_height + padding) + padding),
        "white",
    )
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(pages):
        with Image.open(path) as source:
            thumb = source.convert("RGB").resize((args.thumbnail_width, thumb_height))
        row, column = divmod(index, args.columns)
        x, y = padding + column * (args.thumbnail_width + padding), padding + row * (thumb_height + padding)
        sheet.paste(thumb, (x, y))
        draw.rectangle([x, y, x + args.thumbnail_width, y + thumb_height], outline="#888")
        draw.text((x + 4, y + 2), str(index + 1), fill="#c00")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)
    print("written:", args.output, sheet.size)


if __name__ == "__main__":
    main()
