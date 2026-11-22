#!/usr/bin/env python3
"""asset_hub.db → catalog.json (읽기 전용, 태그 정규화 포함)

원본 DB는 절대 수정하지 않는다. 정규화 결과는 카탈로그에만 반영하고,
DB 반영이 필요하면 tag-map.json을 검토한 뒤 별도 마이그레이션으로 수행한다.

사용 (devops):
    sudo python3 build_asset_catalog.py \
        --db /srv/sonagi-assets/asset_hub.db \
        --library-root /srv/sonagi-assets/library \
        --out-dir /srv/sonagi-assets/catalog
"""

import argparse
import collections
import datetime
import hashlib
import json
import os
import re
import sqlite3
import sys

# --- 정규화 규칙 -----------------------------------------------------------
# key: 기존 태그, value: 대체 태그 목록
TAG_MAP = {
    "icons": ["category:ui-component", "topic:icon"],
    "components": ["category:ui-component"],
    "category:components": ["category:ui-component"],
    "typography": ["category:typography"],
    "mockups": ["category:mockups"],
    "Auto-Ingested": ["src:auto-ingested"],
    "topic:landscapes": ["topic:landscape"],
}
PREFIXES = ("category", "topic", "src", "dept", "medium", "format")


def normalize_tags(raw_tags):
    out = []
    for tag in raw_tags:
        for new_tag in TAG_MAP.get(tag, [tag]):
            if new_tag not in out:
                out.append(new_tag)
    return sorted(out)


def split_buckets(tags):
    buckets = collections.defaultdict(list)
    for tag in tags:
        if ":" in tag:
            prefix, value = tag.split(":", 1)
            buckets[prefix].append(value)
    return buckets


def host_path(original_path, library_root):
    if not original_path:
        return None
    if original_path.startswith("/app/data/"):
        return os.path.join(library_root, original_path[len("/app/data/") :])
    return original_path


def inspect_svg(path, max_hash_bytes):
    groups = None
    size = None
    digest = None
    if path and os.path.isfile(path):
        try:
            size = os.path.getsize(path)
            if size <= max_hash_bytes:
                with open(path, "rb") as f:
                    data = f.read()
                digest = hashlib.sha256(data).hexdigest()
                groups = len(re.findall(rb"<g[\s>]", data))
        except OSError:
            pass
    return {"bytes": size, "sha256": digest, "svg_groups": groups}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--library-root", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--max-hash-bytes", type=int, default=20 * 1024 * 1024)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = list(conn.execute("select * from items"))
    conn.close()

    items = []
    stats = {
        "total": len(rows),
        "by_ext": collections.Counter(),
        "style_tagged": 0,
        "license_known": 0,
        "with_svg_groups": 0,
        "missing_file": 0,
    }
    tag_usage = collections.Counter()

    for row in rows:
        raw = []
        try:
            raw = json.loads(row["tags"]) if row["tags"] else []
        except json.JSONDecodeError:
            pass

        tags = normalize_tags(raw)
        buckets = split_buckets(tags)
        path = host_path(row["original_path"], args.library_root)
        meta = inspect_svg(path, args.max_hash_bytes) if (row["ext"] or "").lower() == "svg" else {"bytes": None, "sha256": None, "svg_groups": None}

        item = {
            "id": row["id"],
            "name": row["name"],
            "ext": (row["ext"] or "").lower(),
            "category": (buckets.get("category") or [None])[0],
            "topics": sorted(buckets.get("topic") or []),
            "source": (buckets.get("src") or [None])[0],
            "dept": sorted(buckets.get("dept") or []),
            "medium": sorted(buckets.get("medium") or []),
            "format": (buckets.get("format") or [None])[0],
            "style": [],
            "license": "unknown",
            "brand": None,
            "tags": tags,
            "path": path,
            **meta,
        }
        items.append(item)
        stats["by_ext"][item["ext"]] += 1
        stats["style_tagged"] += int(bool(item["style"]))
        stats["license_known"] += int(item["license"] != "unknown")
        stats["with_svg_groups"] += int(bool(item["svg_groups"]))
        stats["missing_file"] += int(bool(path) and not os.path.isfile(path))
        for tag in tags:
            tag_usage[tag] += 1

    generated = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    catalog = {
        "generated_at": generated,
        "source_db": args.db,
        "library_root": args.library_root,
        "counts": {**stats, "by_ext": dict(stats["by_ext"].most_common())},
        "items": sorted(items, key=lambda x: x["ext"] + ":" + x["name"]),
    }

    with open(os.path.join(args.out_dir, "catalog.json"), "w") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=1)

    with open(os.path.join(args.out_dir, "tag-map.json"), "w") as f:
        json.dump({"generated_at": generated, "map": TAG_MAP}, f, ensure_ascii=False, indent=2)

    summary = {
        "generated_at": generated,
        "counts": catalog["counts"],
        "top_tags": tag_usage.most_common(40),
        "gaps": {
            "style": len(items) - stats["style_tagged"],
            "license": len(items) - stats["license_known"],
            "svg_without_groups": max(0, stats["by_ext"]["svg"] - stats["with_svg_groups"]),
        },
    }
    with open(os.path.join(args.out_dir, "summary.json"), "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
