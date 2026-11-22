#!/usr/bin/env python3
"""미확인 폰트의 추가 단서 수집 (읽기 전용).

- name table ID 0,7,8,9,10,11,12,13,14
- OS/2 achVendID, head created
- 폰트와 같은 .info 폴더의 문서(.txt/.pdf/.url/.webloc/.md/.rtf)
"""

import argparse
import collections
import json
import os
import sqlite3

from fontTools.ttLib import TTFont

NAME_IDS = (0, 7, 8, 9, 10, 11, 12, 13, 14)
DOC_EXTS = (".txt", ".pdf", ".url", ".webloc", ".md", ".rtf", ".html", ".htm")


def host_path(original_path, library_root):
    if original_path.startswith("/app/data/"):
        return os.path.join(library_root, original_path[len("/app/data/") :])
    return original_path


def inspect(path):
    try:
        font = TTFont(path, fontNumber=0, lazy=True)
    except Exception:
        return None
    try:
        name = font["name"]
        fields = {}
        for nid in NAME_IDS:
            val = name.getDebugName(nid)
            if val:
                fields[str(nid)] = val.strip()
        vendor = None
        created = None
        if "OS/2" in font:
            vendor = font["OS/2"].achVendID
        if "head" in font:
            created = font["head"].created
        return {"fields": fields, "vendor": vendor, "created": created}
    finally:
        try:
            font.close()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--library-root", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    rows = list(conn.execute("select name,ext,tags,original_path from items where ext in ('ttf','otf','woff','woff2')"))
    conn.close()

    known = {"ofl", "apache", "gpl", "cc0", "commercial", "personal"}
    results = []
    vendors = collections.Counter()
    with_docs = 0
    with_url = 0
    with_vendor = 0
    for name, ext, tags_json, original in rows:
        try:
            tags = json.loads(tags_json) if tags_json else []
        except json.JSONDecodeError:
            tags = []
        lic = [t.split(":", 1)[1] for t in tags if t.startswith("license:")]
        if lic and lic[0] in known:
            continue
        path = host_path(original, args.library_root)
        if not os.path.isfile(path):
            continue
        meta = inspect(path)
        if not meta:
            continue
        fields = meta["fields"]
        docs = []
        folder = os.path.dirname(path)
        try:
            docs = [f for f in os.listdir(folder) if os.path.splitext(f)[1].lower() in DOC_EXTS]
        except OSError:
            pass
        urls = [v for v in fields.values() if "http" in v.lower()]
        results.append(
            {
                "name": name,
                "ext": ext,
                "vendor": meta["vendor"],
                "fields": fields,
                "docs": docs[:5],
                "urls": urls[:3],
            }
        )
        if meta["vendor"]:
            vendors[meta["vendor"]] += 1
            with_vendor += 1
        if docs:
            with_docs += 1
        if urls:
            with_url += 1

    summary = {
        "unknown_fonts": len(results),
        "with_vendor_id": with_vendor,
        "with_docs": with_docs,
        "with_url": with_url,
        "top_vendors": vendors.most_common(15),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    if args.out:
        with open(args.out, "w") as f:
            json.dump({"summary": summary, "fonts": results}, f, ensure_ascii=False, indent=1)
    for r in results[:5]:
        print(json.dumps(r, ensure_ascii=False)[:300])


if __name__ == "__main__":
    main()
