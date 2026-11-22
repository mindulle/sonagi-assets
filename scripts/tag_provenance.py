#!/usr/bin/env python3
"""기존 자산에 origin 태그를 소급 적용한다.

- 라이선스 태그(license:*)로부터 출처를 추정한다
- generated는 반드시 scope:output으로 강제한다
- --apply 시 DB 백업 후 반영

사용::

    sudo python3 tag_provenance.py --db /srv/sonagi-assets/asset_hub.db --apply
"""

import argparse
import datetime
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from provenance import origin_for_license  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--catalog", default=None, help="license 태그가 없을 때 카탈로그 값을 사용")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    rows = list(conn.execute("select id, name, tags from items"))
    conn.close()

    catalog_license = {}
    if args.catalog:
        data = json.loads(Path(args.catalog).read_text())
        for item in data.get("items", []):
            if item.get("id") and item.get("license"):
                catalog_license[item["id"]] = item["license"]

    updates = []
    counts = {}
    for item_id, name, tags_json in rows:
        try:
            tags = json.loads(tags_json) if tags_json else []
        except json.JSONDecodeError:
            tags = []
        if any(t.startswith("origin:") for t in tags):
            continue
        license_value = ""
        for t in tags:
            if t.startswith("license:"):
                license_value = t.split(":", 1)[1]
                break
        if not license_value:
            license_value = catalog_license.get(item_id, "")
        origin = origin_for_license(license_value)
        tags = tags + [f"origin:{origin}"]
        if origin == "generated":
            tags = [t for t in tags if not t.startswith("scope:")] + ["scope:output"]
        updates.append((item_id, sorted(set(tags))))
        counts[origin] = counts.get(origin, 0) + 1

    print(json.dumps({"to_tag": len(updates), "by_origin": counts, "apply": args.apply}, ensure_ascii=False))
    if not args.apply:
        return 0

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = f"{args.db}.bak-origin-{stamp}"
    ro = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    dst = sqlite3.connect(backup)
    ro.backup(dst)
    dst.close()
    ro.close()

    conn = sqlite3.connect(args.db, timeout=60)
    conn.execute("PRAGMA busy_timeout=60000")
    for item_id, tags in updates:
        conn.execute("update items set tags=? where id=?", (json.dumps(tags, ensure_ascii=False), item_id))
    conn.commit()
    conn.close()
    print(json.dumps({"updated": len(updates), "backup": backup}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
