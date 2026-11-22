#!/usr/bin/env python3
"""미확인 폰트 단서(font-clues.json)를 집계한다.

- URL 도메인 분포
- 'All rights reserved' 비율
- designer(9) / vendor(OS/2) 분포
"""

import argparse
import collections
import json
import re


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clues", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    data = json.load(open(args.clues))
    fonts = data["fonts"]

    domains = collections.Counter()
    vendors = collections.Counter()
    rights = 0
    designer = 0
    for f in fonts:
        for url in f.get("urls", []):
            m = re.search(r"https?://([^/\s\"']+)", url)
            if m:
                domains[m.group(1).lower()] += 1
        if f.get("vendor"):
            vendors[f["vendor"].strip()] += 1
        text = " ".join(f.get("fields", {}).values()).lower()
        if "all rights reserved" in text:
            rights += 1
        if f.get("fields", {}).get("9"):
            designer += 1

    summary = {
        "unknown_fonts": len(fonts),
        "with_url": sum(1 for f in fonts if f.get("urls")),
        "all_rights_reserved": rights,
        "with_designer": designer,
        "top_domains": domains.most_common(25),
        "top_vendors": vendors.most_common(20),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    if args.out:
        json.dump(summary, open(args.out, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
