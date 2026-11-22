#!/usr/bin/env python3
"""폰트 글리프 SVG(uniXXXX, 1~2글자 이름)에 kind:glyph 태그를 부여한다.

앱(/api/items)은 기본적으로 kind:glyph를 제외하고, ?include_glyphs=1 로 포함한다.
기본 dry-run, --apply 시 DB 백업 후 반영.
"""

import argparse
import datetime
import json
import re
import sqlite3

GLYPH_RE = re.compile(r"^uni[0-9a-f]{4,6}$", re.I)


def is_glyph(name):
    name = (name or "").strip()
    return bool(GLYPH_RE.match(name)) or len(name) <= 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    rows = list(conn.execute("select id,name,tags from items where ext='svg'"))
    conn.close()

    updates = []
    for row_id, name, tags_json in rows:
        if not is_glyph(name):
            continue
        try:
            tags = json.loads(tags_json) if tags_json else []
        except json.JSONDecodeError:
            tags = []
        if "kind:glyph" in tags:
            continue
        tags = [t for t in tags if not t.startswith("kind:")] + ["kind:glyph"]
        updates.append((row_id, sorted(set(tags))))

    print(json.dumps({"glyphs": len(updates), "apply": args.apply}, ensure_ascii=False))
    if not args.apply:
        return 0

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = f"{args.db}.bak-glyphtags-{stamp}"
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
