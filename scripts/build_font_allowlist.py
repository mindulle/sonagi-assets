#!/usr/bin/env python3
"""폰트 allow-list를 2단계(bundle / output)로 생성한다.

- DB의 items.tags에서 대표 라이선스를 읽고 license_policy로 scope를 정한다
- --apply 시 `scope:<bundle|output|blocked>` 태그를 DB에 반영(백업 생성)
- 항상 JSON 리포트를 만든다 (기본 dry-run에서도 리포트는 작성하지 않음)

출력 스키마::

    {
      "generated_at": "...",
      "policy": {"bundle": [...], "output": [...], "blocked": [...]},
      "counts": {"bundle": {...}, "output": {...}, "blocked": {...}},
      "entries": [
        {"family": "...", "license": "ofl", "scope": "bundle",
         "provider": "...", "url": "...", "files": [{name, ext, sha256, path}]}
      ]
    }
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from license_policy import (  # noqa: E402
    BUNDLE_LICENSES,
    LICENSE_SCOPE,
    OUTPUT_LICENSES,
    SCOPE_BLOCKED,
    license_from_tags,
    scope_for_license,
)

FONT_EXTS = ("ttf", "otf", "woff", "woff2")
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


def family_of(name):
    base = re.sub(r"\.[A-Za-z0-9]+$", "", name or "")
    base = re.sub(r"[_\-]?\d+$", "", base)
    base = re.sub(r"[_\-]", " ", base)
    base = re.sub(r"\s+", " ", base).strip().lower()
    return "".join(w for w in base.split() if w not in WEIGHT_TOKENS)


def tag_value(tags, prefix):
    for tag in tags:
        if tag.startswith(prefix):
            return tag.split(":", 1)[1]
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--library-root", default="/srv/sonagi-assets/library")
    ap.add_argument("--no-hash", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    rows = list(conn.execute("select id,name,ext,tags,original_path from items where ext in ('ttf','otf','woff','woff2')"))
    conn.close()

    entries = collections.defaultdict(
        lambda: {
            "family": "",
            "license": "unknown",
            "scope": SCOPE_BLOCKED,
            "provider": "",
            "url": "",
            "files": [],
        }
    )
    updates = []
    scope_counts = collections.Counter()
    file_counts = collections.Counter()
    license_counts = collections.Counter()

    for row_id, name, ext, tags_json, original in rows:
        try:
            tags = json.loads(tags_json) if tags_json else []
        except json.JSONDecodeError:
            tags = []
        license_value = license_from_tags(tags)
        scope = scope_for_license(license_value)
        family = family_of(name) or (name or "").strip().lower()

        key = family
        entry = entries[key]
        entry["family"] = family
        entry["license"] = license_value
        entry["scope"] = scope
        entry["provider"] = entry["provider"] or tag_value(tags, "license_provider:")
        entry["url"] = entry["url"] or tag_value(tags, "license_url:")
        host = original or ""
        if host.startswith("/app/data/"):
            host = os.path.join(args.library_root, host[len("/app/data/") :])
        size = os.path.getsize(host) if host and os.path.isfile(host) else None
        digest = ""
        if size is not None and not args.no_hash:
            h = hashlib.sha256()
            with open(host, "rb") as fh:
                for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                    h.update(chunk)
            digest = h.hexdigest()

        entry["files"].append(
            {
                "name": name,
                "ext": ext,
                "bytes": size,
                "sha256": digest,
                "path": original or "",
            }
        )

        scope_counts[scope] += 1
        file_counts[scope] += 1
        license_counts[license_value] += 1

        if f"scope:{scope}" not in tags:
            tags = [t for t in tags if not t.startswith("scope:")] + [f"scope:{scope}"]
            updates.append((row_id, tags))

    family_counts = collections.Counter(e["scope"] for e in entries.values())
    report = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "policy": {
            "bundle": list(BUNDLE_LICENSES),
            "output": list(OUTPUT_LICENSES),
            "blocked": sorted(k for k, v in LICENSE_SCOPE.items() if v == SCOPE_BLOCKED),
        },
        "counts": {
            "families": dict(family_counts),
            "files": dict(file_counts),
            "licenses": dict(license_counts),
        },
        "entries": sorted(entries.values(), key=lambda e: (e["scope"], e["family"])),
    }

    print(
        json.dumps(
            {
                "families": dict(family_counts),
                "files": dict(file_counts),
                "scope_tag_updates": len(updates),
                "apply": args.apply,
            },
            ensure_ascii=False,
        )
    )

    if args.apply:
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = f"{args.db}.bak-scope-{stamp}"
        src = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
        dst = sqlite3.connect(backup)
        src.backup(dst)
        dst.close()
        src.close()

        conn = sqlite3.connect(args.db, timeout=30)
        conn.execute("PRAGMA busy_timeout=30000")
        for row_id, tags in updates:
            conn.execute(
                "update items set tags=? where id=?",
                (json.dumps(sorted(set(tags)), ensure_ascii=False), row_id),
            )
        conn.commit()
        conn.close()
        print(json.dumps({"updated": len(updates), "backup": backup}, ensure_ascii=False))

    with open(args.out, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(json.dumps({"out": args.out, "entries": len(report["entries"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
