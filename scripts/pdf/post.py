#!/usr/bin/env python3
"""Post-process Pandoc HTML for print typography and local figure links."""
import argparse
import html
import re
from pathlib import Path

CITATION = re.compile(r"\[(\d+(?:\s*[,–-]\s*\d+)*)\]")
TAG = re.compile(r"(<[^>]+>)")
MATH = re.compile(r'<span class="math (?:inline|display)">.*?</span>|<math\b.*?</math>', re.S)
REFERENCE_HEADING = re.compile(r"<h([1-6])([^>]*)>(.*?)</h\1>", re.I | re.S)


def heading_text(fragment):
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip().lower()


def sup_citations(fragment):
    result, skipped, in_math = [], 0, 0
    for token in TAG.split(fragment):
        if token.startswith("<"):
            low = token.lower()
            if low.startswith(("<style", "<script")):
                skipped += 1
            elif low.startswith(("</style", "</script")):
                skipped = max(0, skipped - 1)
            elif low.startswith("<math"):
                in_math += 1
            elif low.startswith("</math"):
                in_math = max(0, in_math - 1)
            result.append(token)
        elif skipped or in_math:
            result.append(token)
        else:
            result.append(CITATION.sub(r'<sup class="cite">[\1]</sup>', token))
    return "".join(result)


def postprocess(text, base_uri, authored_css, print_css, source_css=""):
    if "</head>" not in text.lower():
        raise ValueError("Pandoc HTML has no closing head element")
    split = re.search(r"</head\s*>", text, re.I)
    head, rest = text[:split.start()], text[split.end():]
    css = "\n".join(x for x in (authored_css, source_css, print_css) if x.strip())
    base_tag = '<base href="%s/">' % html.escape(base_uri.rstrip("/"), quote=True)
    style_tag = "<style>\n%s\n</style>" % css
    head += "\n" + base_tag + "\n" + style_tag + "\n"
    text = head + "</head>\n" + text[split.end():]

    heading = None
    for item in REFERENCE_HEADING.finditer(text):
        if re.search(r"references|bibliography|参考文献", heading_text(item.group(3)), re.I):
            heading = item
    if heading is None:
        raise ValueError("references heading not found in Pandoc HTML")
    body, tail = text[:heading.start()], text[heading.start():]

    body = re.sub(r"<annotation[^>]*>.*?</annotation>", "", body, flags=re.S)
    stashed = []

    def save_math(item):
        stashed.append(item.group(0))
        return "\x00MATH%d\x00" % (len(stashed) - 1)

    body = MATH.sub(save_math, body)
    body = sup_citations(body)
    body = re.sub(
        r"\x00MATH(\d+)\x00",
        lambda item: stashed[int(item.group(1))],
        body,
    )
    body = re.sub(
        r'(<sup class="cite">\[[^<]*\]</sup>)([。，、；：.,;:])',
        r'<span class="keep">\1\2</span>',
        body,
    )
    body = re.sub(
        r"<p>\s*((?:Table|表)\s*\d+\.[^<]*?)</p>",
        r'<p class="tcap">\1</p>',
        body,
        flags=re.S,
    )
    body = re.sub(
        r"<p>\s*((?:注|Note)\s*[:：][^<]*?)</p>",
        r'<p class="tnote">\1</p>',
        body,
        flags=re.S | re.I,
    )
    body = re.sub(
        r"<p>\s*<em>(图示依据[^<]*(?:<sup[^>]*>[^<]*</sup>[^<]*)*)</em>\s*</p>",
        r'<p class="fsrc"><em>\1</em></p>',
        body,
        flags=re.S,
    )
    heading_tag = heading.group(0)
    heading_tag = re.sub(r"<h([1-6])", r'<h\1 class="refhead"', heading_tag, count=1, flags=re.I)
    tail = heading_tag + tail[heading.end() - heading.start():]
    cut = re.search(r"</body\s*>", tail, re.I)
    if cut is None:
        raise ValueError("Pandoc HTML has no closing body element")
    ref_body, remainder = tail[:cut.start()], tail[cut.start():]

    def break_url(item):
        value = re.sub(r"([/._-])", lambda part: part.group(1) + "\u200b", item.group(1))
        return '<span class="url">%s</span>' % value

    ref_body = re.sub(r'(https?://[^\s<"]+)', break_url, ref_body)
    tail = "\n<div class=\"refs\">\n" + ref_body + "\n</div>\n" + remainder
    return body + tail


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", required=True, type=Path)
    parser.add_argument("--base-dir", required=True, type=Path)
    parser.add_argument("--authored-css", required=True, type=Path)
    parser.add_argument("--print-css", required=True, type=Path)
    parser.add_argument("--source-css", type=Path)
    args = parser.parse_args()
    try:
        source_css = args.source_css.read_text(encoding="utf-8") if args.source_css and args.source_css.is_file() else ""
        output = postprocess(
            args.html.read_text(encoding="utf-8"),
            args.base_dir.resolve().as_uri(),
            args.authored_css.read_text(encoding="utf-8"),
            args.print_css.read_text(encoding="utf-8"),
            source_css,
        )
        args.html.write_text(output, encoding="utf-8")
        print("post-processed:", args.html)
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
