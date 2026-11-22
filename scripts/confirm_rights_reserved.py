#!/usr/bin/env python3
"""'All rights reserved'가 명시된 미확인 폰트를 license:commercial로 확정한다.

- 기존 license:ofl/apache/cc0/commercial/free/personal 은 건드리지 않는다
- name table ID 0/13 텍스트에 'all rights reserved'가 있을 때만 적용

기본 dry-run, --apply 시 DB 백업 후 반영.
"""

import argparse
import collections
import datetime
import json
import os
import sqlite3

from fontTools.ttLib import TTFont

TEXT_IDS = (0, 13)


def host_path(original_path, library_root):
    if original_path.startswith("/app/data/"):
        return os.path.join(library_root, original_path[len("/app/data/") :])
    return original_path


def has_rights(path):
    try:
        font = TTFont(path, fontNumber=0, lazy=True)
    except Exception:
        return False
    try:
        name = font["name"]
        text = " ".join(name.getDebugName(i) or "" for i in TEXT_IDS).lower()
        return "all rights reserved" in text
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

    resolved = {"ofl", "apache", "gpl", "cc0", "commercial", "personal", "free"}
    updates = []
    stats = collections.Counter()
    for row_id, name, ext, tags_json, original in rows:
        try:
            tags = json.loads(tags_json) if tags_json else []
        except json.JSONDecodeError:
            tags = []
        lic = [t.split(":", 1)[1] for t in tags if t.startswith("license:")]
        if lic and lic[0] in resolved:
            continue
        path = host_path(original, args.library_root)
        if not path or not os.path.isfile(path):
            stats["missing"] += 1
            continue
        if not has_rights(path):
            stats["no_rights"] += 1
            continue
        tags = [t for t in tags if not t.startswith(("license:", "license_src:"))]
        tags += ["license:commercial", "license_src:copyright"]
        updates.append((row_id, sorted(set(tags))))
        stats["commercial"] += 1

    print(json.dumps({"confirmed": len(updates), "stats": dict(stats), "apply": args.apply}, ensure_ascii=False))
    if not args.apply:
        return 0

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = f"{args.db}.bak-rightsreserved-{stamp}"
    src = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    dst = sqlite3.connect(backup)
    src.backup(dst)
    dst.close()
    src.close()

    conn = sqlite3.connect(args.db, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    for row_id, tags in updates:
        conn.execute("update items set tags=? where id=?", (json.dumps(tags, ensure_ascii=False), row_id))
    conn.commit()
    conn.close()
    print(json.dumps({"updated": len(updates), "backup": backup}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
