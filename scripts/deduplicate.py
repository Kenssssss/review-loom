#!/usr/bin/env python3
"""Group search records by strong IDs; never merge on title alone."""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


def identifiers(record):
    keys = set()
    doi = record.get("doi")
    if isinstance(doi, str) and doi.strip():
        doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi.strip(), flags=re.I).lower()
        if doi.startswith("10."):
            keys.add("doi:" + doi)
        if doi.startswith("10.48550/arxiv."):
            arxiv_doi = re.sub(r"v\d+$", "", doi[len("10.48550/arxiv."):], flags=re.I)
            if arxiv_doi:
                keys.add("arxiv:" + arxiv_doi)
    if record.get("source") == "arxiv" and isinstance(record.get("source_id"), str):
        arxiv = re.sub(r"v\d+$", "", record["source_id"].strip(), flags=re.I).lower()
        if arxiv:
            keys.add("arxiv:" + arxiv)
    return keys


def group(records):
    parent = list(range(len(records)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    seen = {}
    for i, record in enumerate(records):
        for key in identifiers(record):
            if key in seen:
                parent[find(i)] = find(seen[key])
            else:
                seen[key] = i
    groups = {}
    for i, record in enumerate(records):
        groups.setdefault(find(i), []).append(record)
    output = []
    for members in groups.values():
        keys = sorted(set().union(*(identifiers(m) for m in members)))
        # This is a grouping fingerprint, NOT the stable citation ID assigned in the registry.
        seed = "|".join(keys) if keys else json.dumps(members[0], sort_keys=True, ensure_ascii=False)
        output.append({"group_fingerprint": hashlib.sha256(seed.encode()).hexdigest()[:16],
                       "identifiers": keys, "records": members})
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("inputs", nargs="+", type=Path, help="search envelope JSON files")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    try:
        if args.output.resolve() in {x.resolve() for x in args.inputs}:
            raise ValueError("output must not overwrite an input")
        records = []
        for path in args.inputs:
            obj = json.loads(path.read_text(encoding="utf-8"))
            if obj.get("status") != "ok" or not isinstance(obj.get("records"), list):
                raise ValueError(f"invalid or failed search envelope: {path}")
            records.extend(obj["records"])
        out = {"status": "ok", "input_records": len(records), "groups": group(records),
               "note": "fingerprints are not stable citation IDs; review preprint/published relationships separately"}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"status": "ok", "groups": len(out["groups"]), "input_records": len(records)}))
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
