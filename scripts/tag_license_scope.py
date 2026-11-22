#!/usr/bin/env python3
"""카탈로그의 license_scope를 DB 태그로 반영한다.

폰트·아이콘처럼 개별 스크립트가 scope를 붙인 항목을 제외하고,
나머지(이미지·도판·글리프)는 카탈로그 계산값을 그대로 쓴다.
`/api/items?license_scope=` 필터가 DB 태그를 보기 때문에 필요하다.

사용::

    sudo python3 tag_license_scope.py --db /srv/sonagi-assets/asset_hub.db \\
        --catalog /srv/sonagi-assets/catalog/catalog.json --apply
"""

import argparse
import datetime
import json
import sqlite3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    with open(args.catalog) as f:
        catalog = json.load(f)

    wanted = {}
    for item in catalog.get("items", []):
        scope = item.get("license_scope")
        if scope and item.get("id"):
            wanted[item["id"]] = scope

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    updates = []
    for item_id, tags_json in conn.execute("select id, tags from items"):
        scope = wanted.get(item_id)
        if not scope:
            continue
        try:
            tags = json.loads(tags_json) if tags_json else []
        except json.JSONDecodeError:
            tags = []
        if f"scope:{scope}" in tags:
            continue
        tags = [t for t in tags if not t.startswith("scope:")] + [f"scope:{scope}"]
        updates.append((item_id, sorted(set(tags))))
    conn.close()

    print(json.dumps({"to_tag": len(updates), "apply": args.apply}, ensure_ascii=False))
    if not args.apply:
        return 0

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = f"{args.db}.bak-scopeall-{stamp}"
    ro = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    dst = sqlite3.connect(backup)
    ro.backup(dst)
    dst.close()
    ro.close()

    conn = sqlite3.connect(args.db, timeout=60)
    conn.execute("PRAGMA busy_timeout=60000")
    for item_id, tags in updates:
        conn.execute(
            "update items set tags=? where id=?",
            (json.dumps(tags, ensure_ascii=False), item_id),
        )
    conn.commit()
    conn.close()
    print(json.dumps({"updated": len(updates), "backup": backup}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
