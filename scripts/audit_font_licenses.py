#!/usr/bin/env python3
"""폰트 파일에 내장된 라이선스 메타데이터를 읽어 분류한다.

TTF/OTF/WOFF/WOFF2의 name table(ID 0, 13, 14)을 사용한다.
- ofl | apache | gpl | cc0 | personal | commercial | unknown

기본 dry-run, --apply 시 DB 백업 후 `license:*` / `license_src:embedded` 태그를 갱신한다.
"""

import argparse
import collections
import datetime
import json
import os
import re
import sqlite3

from fontTools.ttLib import TTFont

FONT_EXTS = ("ttf", "otf", "woff", "woff2")


def host_path(original_path, library_root):
    if original_path.startswith("/app/data/"):
        return os.path.join(library_root, original_path[len("/app/data/") :])
    return original_path


def classify(text):
    t = (text or "").lower()
    if "open font license" in t or "ofl" in t:
        return "ofl"
    if "apache license" in t:
        return "apache"
    if "gnu general public license" in t or "gpl" in t:
        return "gpl"
    if "cc0" in t or "public domain" in t or "creative commons zero" in t:
        return "cc0"
    if "personal use" in t or "non-commercial" in t or "noncommercial" in t:
        return "personal"
    if "commercial" in t and "license" in t:
        return "commercial"
    return "unknown"


def read_license(path):
    try:
        font = TTFont(path, fontNumber=0, lazy=True)
    except Exception:
        return None, ""
    try:
        name = font["name"]
        parts = []
        for nid in (0, 13, 14):
            val = name.getDebugName(nid)
            if val:
                parts.append(val)
        family = name.getDebugName(16) or name.getDebugName(1) or ""
        return " ".join(parts), family
    finally:
        try:
            font.close()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--library-root", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    rows = list(conn.execute("select id,name,ext,tags,original_path from items where ext in ('ttf','otf','woff','woff2')"))
    conn.close()

    updates = []
    stats = collections.Counter()
    families = collections.Counter()
    for row_id, name, ext, tags_json, original in rows:
        path = host_path(original, args.library_root)
        if not os.path.isfile(path):
            stats["missing"] += 1
            continue
        text, family = read_license(path)
        if text is None:
            stats["parse_error"] += 1
            continue
        lic = classify(text)
        updates.append((row_id, lic, family, name))
        stats[lic] += 1
        if lic in ("commercial", "personal"):
            families[(lic, family or name)] += 1

    print(
        json.dumps(
            {
                "fonts": len(rows),
                "classified": len(updates),
                "stats": dict(stats),
                "top_restricted": [f"{k[0]}:{k[1]}" for k, _ in families.most_common(10)],
                "apply": args.apply,
            },
            ensure_ascii=False,
        )
    )
    if not args.apply:
        return 0

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = f"{args.db}.bak-fontlicense-{stamp}"
    src = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    dst = sqlite3.connect(backup)
    src.backup(dst)
    dst.close()
    src.close()

    conn = sqlite3.connect(args.db, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    for row_id, lic, family, name in updates:
        row = conn.execute("select tags from items where id=?", (row_id,)).fetchone()
        try:
            tags = json.loads(row[0]) if row and row[0] else []
        except json.JSONDecodeError:
            tags = []
        tags = [t for t in tags if not t.startswith(("license:", "license_src:"))]
        tags += [f"license:{lic}", "license_src:embedded"]
        conn.execute("update items set tags=? where id=?", (json.dumps(sorted(set(tags)), ensure_ascii=False), row_id))
    conn.commit()
    conn.close()
    print(json.dumps({"updated": len(updates), "backup": backup}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
