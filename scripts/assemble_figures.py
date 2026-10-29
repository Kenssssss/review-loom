#!/usr/bin/env python3
"""Assemble figure placeholders with numbering based on final placement order."""
import argparse
import json
import os
import re
import sys
from pathlib import Path

TOKEN = re.compile(r"\{\{(fig|figure):([A-Za-z][A-Za-z0-9_-]*)\}\}")


def assemble(source, figures, source_dir, output_dir):
    if re.search(r"(?ms)^\s*(```|~~~).*?\{\{(?:fig|figure):.*?^\s*\1", source):
        raise ValueError("figure tokens in fenced code are not supported")
    if re.search(r"`[^`\n]*\{\{(?:fig|figure):[^`\n]*`", source):
        raise ValueError("figure tokens in inline code are not supported")
    tokens = TOKEN.findall(source)
    placements = [id_ for kind, id_ in tokens if kind == "figure"]
    refs = {id_ for kind, id_ in tokens if kind == "fig"}
    if len(placements) != len(set(placements)):
        raise ValueError("a figure may be placed only once")
    if refs != set(placements):
        raise ValueError("every referenced figure needs exactly one placement and vice versa")
    if set(placements) != set(figures):
        raise ValueError("figure map must match placed figures exactly")
    numbers = {key: i + 1 for i, key in enumerate(placements)}
    def replace(match):
        kind, key = match.groups()
        number = numbers[key]
        if kind == "fig":
            return f"Figure {number}"
        item = figures[key]
        if set(item) != {"path", "caption"} or not all(isinstance(item[x], str) for x in item):
            raise ValueError("each figure requires path and caption strings")
        if "\n" in item["caption"]:
            raise ValueError("captions must be single line")
        path = (source_dir / item["path"]).resolve()
        if not path.is_file():
            raise ValueError("missing image: " + str(path))
        relative = os.path.relpath(path, output_dir).replace("\\", "/")
        if any(x in relative for x in ("\n", "<", ">")):
            raise ValueError("unsupported image path")
        return f"![Figure {number}. {item['caption']}](<{relative}>)"
    result = TOKEN.sub(replace, source)
    if "{{fig:" in result or "{{figure:" in result:
        raise ValueError("invalid figure marker")
    return result, numbers


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("--figures", required=True, type=Path, help="JSON mapping of IDs to path and caption")
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--map", required=True, type=Path)
    args = p.parse_args()
    try:
        if len({args.source.resolve(), args.figures.resolve(), args.output.resolve(), args.map.resolve()}) < 4:
            raise ValueError("source, figure map and outputs must be different files")
        figures = json.loads(args.figures.read_text(encoding="utf-8"))
        if not isinstance(figures, dict):
            raise ValueError("figures must be an object")
        output, numbers = assemble(args.source.read_text(encoding="utf-8"), figures, args.source.parent, args.output.parent)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.map.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
        args.map.write_text(json.dumps(numbers, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"status": "ok", "figures": numbers}))
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
