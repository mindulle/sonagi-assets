#!/usr/bin/env python3
"""폰트 라이선스 현황 리포트 (읽기 전용).

- Google Fonts(OFL) 패밀리와 대조
- 알려진 무료 배포처(Cafe24, 나눔, Pretendard 등) 분리
- 나머지는 미확인으로 집계
"""

import argparse
import collections
import json
import re
import sqlite3

WEIGHT_TOKENS = (
    "thin",
    "extralight",
    "ultralight",
    "light",
    "regular",
    "book",
    "medium",
    "semibold",
    "demibold",
    "bold",
    "extrabold",
    "ultrabold",
    "black",
    "heavy",
    "italic",
    "oblique",
    "variable",
    "wght",
    "width",
)
KNOWN_FREE = (
    "noto",
    "nanum",
    "pretendard",
    "spoqa",
    "ibmplex",
    "cafe24",
    "gmarket",
    "dohyeon",
    "jua",
    "blackhansans",
    "gasoek",
    "gowun",
    "poorstory",
    "songmyung",
)


def family_of(name):
    base = re.sub(r"\.[A-Za-z0-9]+$", "", name or "")
    base = re.sub(r"[_\-\s]?\d+$", "", base)
    base = re.sub(r"[_\-]", " ", base)
    base = re.sub(r"\s+", " ", base).strip().lower()
    return "".join(w for w in base.split() if w not in WEIGHT_TOKENS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--google-fonts", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    names = [r[0] or "" for r in conn.execute("select name from items where ext in ('ttf','otf','woff','woff2')")]
    conn.close()

    with open(args.google_fonts) as f:
        data = json.load(f)
    google = {family_of(f.get("family", "")) for f in (data.get("familyMetadataList") or []) if f.get("family")}

    counts = collections.Counter(family_of(n) for n in names if family_of(n))
    ofl = [(f, c) for f, c in counts.items() if f in google]
    free = [(f, c) for f, c in counts.items() if f not in google and any(k in f for k in KNOWN_FREE)]
    unknown = [(f, c) for f, c in counts.items() if f not in google and (f, c) not in free]
    unknown.sort(key=lambda x: -x[1])

    report = {
        "total_fonts": len(names),
        "unique_families": len(counts),
        "google_ofl_families": len(ofl),
        "known_free_families": len(free),
        "unknown_families": len(unknown),
        "unknown_files": sum(c for _, c in unknown),
        "top_unknown": unknown[:30],
    }
    with open(args.out, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(
        json.dumps(
            {
                k: report[k]
                for k in ("total_fonts", "unique_families", "google_ofl_families", "known_free_families", "unknown_families", "unknown_files")
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
