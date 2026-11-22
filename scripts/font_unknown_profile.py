#!/usr/bin/env python3
"""URL 단서가 없는 미확인 폰트의 공통점 프로파일."""

import collections
import json
import re
import sys

HANGUL = re.compile(r"[가-힣]")
NUM_PREFIX = re.compile(r"^\d{2,3}")


def main():
    data = json.load(open(sys.argv[1]))
    fonts = [f for f in data["fonts"] if not f.get("urls")]
    vendors = collections.Counter()
    exts = collections.Counter()
    hangul = 0
    numeric = 0
    has_designer = 0
    has_rights = 0
    samples_ko, samples_en = [], []
    for f in fonts:
        name = f["name"]
        exts[f["ext"]] += 1
        vendors[(f.get("vendor") or "").strip() or "(blank)"] += 1
        if HANGUL.search(name):
            hangul += 1
            if len(samples_ko) < 8:
                samples_ko.append(name)
        else:
            if len(samples_en) < 8:
                samples_en.append(name)
        if NUM_PREFIX.match(name):
            numeric += 1
        fields = f.get("fields", {})
        if fields.get("9"):
            has_designer += 1
        if "all rights reserved" in " ".join(fields.values()).lower():
            has_rights += 1

    print(
        json.dumps(
            {
                "no_url_fonts": len(fonts),
                "hangul_in_name": hangul,
                "latin_or_other_name": len(fonts) - hangul,
                "numeric_prefix": numeric,
                "with_designer": has_designer,
                "all_rights_reserved": has_rights,
                "exts": dict(exts),
                "top_vendors": vendors.most_common(12),
                "ko_samples": samples_ko,
                "en_samples": samples_en,
            },
            ensure_ascii=False,
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
