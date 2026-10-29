#!/usr/bin/env python3
"""Prepare citation-resolved Markdown for deterministic HTML/PDF rendering."""
import argparse
import re
from pathlib import Path

MATH = re.compile(r"\\\(.*?\\\)|\\\[.*?\\\]|\$\$.*?\$\$|\$[^$\n]+\$", re.S)
CITE_PAIR = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]\s*\[(\d+(?:\s*,\s*\d+)*)\]")
REFERENCE_HEADING = re.compile(
    r"(?im)^#{1,6}\s*(?:references|bibliography|参考文献)\s*$"
)


def prepare(text):
    match = REFERENCE_HEADING.search(text)
    if not match:
        raise ValueError("references heading not found in citation-resolved Markdown")
    body, references = text[:match.start()], text[match.start():]
    saved = []

    def stash(item):
        saved.append(item.group(0))
        return "\x00MATH%d\x00" % (len(saved) - 1)

    body = MATH.sub(stash, body)
    merges = 0
    while True:
        body, count = CITE_PAIR.subn(r"[\1, \2]", body)
        merges += count
        if count == 0:
            break
    if re.search(r"\]\s*\[\d", body):
        raise ValueError("unmerged adjacent citation groups remain")

    def sort_group(item):
        values = sorted({int(x) for x in re.split(r"\s*,\s*", item.group(1))})
        return "[" + ", ".join(str(x) for x in values) + "]"

    body, sorted_groups = re.subn(
        r"\[(\d+(?:\s*,\s*\d+)+)\]", sort_group, body
    )
    body = re.sub(
        r"\x00MATH(\d+)\x00", lambda item: saved[int(item.group(1))], body
    )
    references = re.sub(r"(?m)^(?=\[\d+\]\s)", "\n", references)
    references = re.sub(r"\n{3,}", "\n\n", references)
    return body + references, merges, sorted_groups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        text = args.source.read_text(encoding="utf-8-sig")
        output, merges, sorted_groups = prepare(text)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
        print("prepared:", args.output)
        print("citation merges:", merges, "| sorted groups:", sorted_groups)
        print("reference entries:", len(re.findall(r"(?m)^\[\d+\]\s", output)))
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
