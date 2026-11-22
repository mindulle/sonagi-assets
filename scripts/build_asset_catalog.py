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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from license_policy import scope_for_license  # noqa: E402
from provenance import origin_for_license, origin_from_tags  # noqa: E402

FONT_EXTS = {"ttf", "otf", "woff", "woff2"}


def normalize_family(name):
    """'BebasNeue_004' / 'Roboto-Bold' → 비교 가능한 family 문자열"""
    base = re.sub(r"\.[A-Za-z0-9]+$", "", name or "")
    base = re.sub(r"[_\-\s]?\d+$", "", base)  # trailing _004
    base = base.replace("_", " ").replace("-", " ")
    base = re.sub(r"\s+", " ", base).strip().lower()
    words = [w for w in base.split(" ") if w and w not in WEIGHT_TOKENS]
    return "".join(words)


def load_google_families(path):
    if not path or not os.path.isfile(path):
        return set()
    with open(path) as f:
        data = json.load(f)
    families = data.get("familyMetadataList") or data.get("families") or []
    return {normalize_family(f.get("family") or "") for f in families if f.get("family")}


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
    ap.add_argument("--google-fonts", default=None, help="Google Fonts metadata JSON (family list)")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    google_families = load_google_families(args.google_fonts)
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
        "license": collections.Counter(),
        "license_scope": collections.Counter(),
        "fonts_matched": 0,
        "with_svg_groups": 0,
        "missing_file": 0,
        "junk": 0,
        "junk_by_ext": collections.Counter(),
        "real_total": 0,
        "glyph": 0,
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
        ext = (row["ext"] or "").lower()
        source = (buckets.get("src") or [None])[0]
        name = row["name"] or ""
        is_junk = name.startswith("._")  # macOS AppleDouble
        is_glyph = ext == "svg" and not is_junk and (bool(re.match(r"^uni[0-9a-f]{4,6}", name.lower())) or len(name.strip()) <= 2)

        embedded_license = None
        for tag in tags:
            if tag.startswith("license:") and tag != "license:unknown":
                embedded_license = tag.split(":", 1)[1]
                break

        if is_junk:
            license_value, license_basis = "n/a", "appledouble-metadata"
        elif ext in FONT_EXTS:
            family = normalize_family(row["name"])
            if embedded_license:
                license_value, license_basis = embedded_license, "font-metadata"
            elif family and family in google_families:
                license_value, license_basis = "ofl", "google-fonts"
                stats["fonts_matched"] += 1
            else:
                license_value, license_basis = "internal-only", "font-unverified"
        elif embedded_license:
            license_value, license_basis = embedded_license, "explicit-tag"
        elif source in ("the-met", "cma"):
            license_value, license_basis = "cc0", f"{source}-open-access"
        else:
            license_value, license_basis = "internal-only", "source-unverified"

        scope_tag = next((t.split(":", 1)[1] for t in tags if t.startswith("scope:")), None)
        origin_value = origin_from_tags(tags)
        if origin_value == "unknown" and license_value:
            origin_value = origin_for_license(license_value)
        meta = inspect_svg(path, args.max_hash_bytes) if ext == "svg" else {"bytes": None, "sha256": None, "svg_groups": None}

        item = {
            "id": row["id"],
            "name": row["name"],
            "ext": ext,
            "category": (buckets.get("category") or [None])[0],
            "topics": sorted(buckets.get("topic") or []),
            "source": source,
            "dept": sorted(buckets.get("dept") or []),
            "medium": sorted(buckets.get("medium") or []),
            "format": (buckets.get("format") or [None])[0],
            "style": [],
            "license": license_value,
            "license_basis": license_basis,
            "license_scope": scope_tag or scope_for_license(license_value),
            "origin": origin_value,
            "junk": is_junk,
            "kind": "glyph" if is_glyph else "asset",
            "brand": None,
            "tags": tags,
            "path": path,
            **meta,
        }
        items.append(item)
        stats["by_ext"][item["ext"]] += 1
        if is_junk:
            stats["junk"] += 1
            stats["junk_by_ext"][item["ext"]] += 1
        else:
            stats["real_total"] += 1
            stats["glyph"] += int(is_glyph)
            stats["style_tagged"] += int(bool(item["style"]))
            stats["license_known"] += int(item["license"] in ("cc0", "ofl", "cleared"))
            stats["with_svg_groups"] += int(bool(item["svg_groups"]))
            stats["missing_file"] += int(bool(path) and not os.path.isfile(path))
        stats["license"][item["license"]] += 1
        stats["license_scope"][item["license_scope"]] += 1
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
            "style": stats["real_total"] - stats["style_tagged"],
            "license": stats["real_total"] - stats["license_known"],
            "svg_without_groups": max(
                0,
                stats["by_ext"]["svg"] - stats["junk_by_ext"]["svg"] - stats["with_svg_groups"],
            ),
            "junk": stats["junk"],
        },
    }
    with open(os.path.join(args.out_dir, "summary.json"), "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
