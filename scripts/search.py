#!/usr/bin/env python3
"""Small source-specific search adapters. Network and remote API are external."""
import argparse
import datetime as dt
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ATOM = {"a": "http://www.w3.org/2005/Atom", "o": "http://a9.com/-/spec/opensearch/1.1/"}


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "ReviewLoom/0.1 (narrative review research)"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read()


def arxiv(query, limit, page_size, getter=fetch):
    records, start, total = [], 0, None
    while len(records) < limit:
        if start:
            time.sleep(3)  # Be considerate to arXiv when paging.
        count = min(page_size, limit - len(records))
        params = urllib.parse.urlencode({"search_query": query, "start": start, "max_results": count})
        root = ET.fromstring(getter("https://export.arxiv.org/api/query?" + params))
        total_text = root.findtext("o:totalResults", default="", namespaces=ATOM)
        total = int(total_text) if total_text.isdigit() else None
        entries = root.findall("a:entry", ATOM)
        for entry in entries:
            url = entry.findtext("a:id", default="", namespaces=ATOM)
            full_id = url.rstrip("/").split("/abs/")[-1]
            if not full_id or not url.startswith(("http://", "https://")):
                raise ValueError("arXiv result missing a usable ID")
            # Old-style IDs contain '/', so preserve the full path after /abs/.
            import re
            match = re.match(r"^(.*?)(v[0-9]+)?$", full_id)
            records.append({"source": "arxiv", "source_id": match.group(1), "version": match.group(2),
                            "url": url, "title": " ".join(entry.findtext("a:title", default="", namespaces=ATOM).split()),
                            "abstract": " ".join(entry.findtext("a:summary", default="", namespaces=ATOM).split()),
                            "authors": [x.findtext("a:name", default="", namespaces=ATOM) for x in entry.findall("a:author", ATOM)],
                            "published": entry.findtext("a:published", default="", namespaces=ATOM),
                            "updated": entry.findtext("a:updated", default="", namespaces=ATOM)})
        start += len(entries)
        if not entries or (total is not None and start >= total):
            break
    return records, {"returned": len(records), "reported_total": total,
                     "truncated": total is None or len(records) < total, "page_size": page_size}


def crossref(query, limit, page_size, mailto, getter=fetch):
    records, offset, total = [], 0, None
    while len(records) < limit:
        if offset:
            time.sleep(1)
        params = {"query.bibliographic": query, "offset": offset, "rows": min(page_size, limit-len(records))}
        if mailto:
            params["mailto"] = mailto
        data = json.loads(getter("https://api.crossref.org/works?" + urllib.parse.urlencode(params)))
        if data.get("status") != "ok" or not isinstance(data.get("message"), dict):
            raise ValueError("Crossref response is not successful")
        message = data["message"]
        total = message.get("total-results")
        entries = message.get("items", [])
        if not isinstance(entries, list):
            raise ValueError("Crossref returned invalid items")
        for item in entries:
            if not item.get("DOI"):
                raise ValueError("Crossref result missing DOI")
            records.append({"source": "crossref", "source_id": item["DOI"], "doi": item["DOI"],
                            "url": item.get("URL"), "title": (item.get("title") or [""])[0],
                            "authors": [" ".join(filter(None, [a.get("given"), a.get("family")])) for a in item.get("author", [])],
                            "published": item.get("published"), "type": item.get("type"),
                            "container_title": (item.get("container-title") or [""])[0]})
        offset += len(entries)
        if not entries or (isinstance(total, int) and offset >= total):
            break
    return records, {"returned": len(records), "reported_total": total,
                     "truncated": not isinstance(total, int) or len(records) < total, "page_size": page_size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=["arxiv", "crossref"])
    parser.add_argument("query", help="Source-specific query; arXiv accepts its native search syntax")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--page-size", type=int, default=20)
    parser.add_argument("--mailto", help="Optional Crossref contact address")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.limit <= 200 or not 1 <= args.page_size <= 100:
        parser.error("limit must be 1..200 and page-size 1..100")
    result = {"source": args.source, "query": args.query, "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "status": "error", "records": [], "pagination": None, "errors": []}
    try:
        records, pagination = (arxiv(args.query, args.limit, args.page_size) if args.source == "arxiv"
                               else crossref(args.query, args.limit, args.page_size, args.mailto))
        result.update(status="ok", records=records, pagination=pagination)
    except (OSError, ValueError, ET.ParseError, json.JSONDecodeError) as exc:
        result["errors"].append({"type": type(exc).__name__, "message": str(exc)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "returned": len(result["records"]), "output": str(args.output)}, ensure_ascii=False))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
