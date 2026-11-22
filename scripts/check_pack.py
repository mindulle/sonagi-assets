#!/usr/bin/env python3
"""배포 팩에 넣을 파일이 allow-list의 bundle인지 검사한다.

- 기본은 파일명으로 조회하고, `--sha256`을 주면 해시로 먼저 대조한다
- 하나라도 bundle이 아니거나 목록에 없으면 exit 1

사용::

    python3 scripts/check_pack.py --allowlist catalog/font-allowlist.json \\
        pack/fonts/NanumGothic.ttf pack/fonts/GmarketSans.ttf

    python3 scripts/check_pack.py --sha256 ...
"""

import argparse
import hashlib
import json
import os
import sys


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_index(entries):
    by_name = {}
    by_hash = {}
    by_path = {}
    for entry in entries:
        for f in entry.get("files", []):
            scope = entry.get("scope")
            info = {
                "scope": scope,
                "license": entry.get("license"),
                "family": entry.get("family"),
                "provider": entry.get("provider"),
            }
            if f.get("name"):
                by_name.setdefault(f["name"], info)
            if f.get("sha256"):
                by_hash.setdefault(f["sha256"], info)
            if f.get("path"):
                by_path.setdefault(f["path"], info)
    return by_name, by_hash, by_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--allowlist", required=True)
    ap.add_argument("--sha256", action="store_true", help="파일 해시로 먼저 대조")
    ap.add_argument("files", nargs="+")
    args = ap.parse_args()

    with open(args.allowlist) as f:
        data = json.load(f)
    by_name, by_hash, by_path = build_index(data.get("entries", []))

    failures = []
    rows = []
    for path in args.files:
        lookup = None
        if args.sha256 and os.path.isfile(path):
            lookup = by_hash.get(sha256_of(path))
        if not lookup:
            lookup = by_name.get(os.path.basename(path))
        if not lookup:
            lookup = by_path.get(path)
        if not lookup:
            rows.append((path, "unknown", "-", "-"))
            failures.append(path)
            continue
        rows.append((path, lookup["scope"], lookup["license"], lookup["family"]))
        if lookup["scope"] != "bundle":
            failures.append(path)

    for path, scope, license_value, family in rows:
        print(f"{scope:8} {license_value:10} {family or '-':24} {path}")

    total = len(rows)
    print(f"\n{total - len(failures)}/{total} bundle")
    if failures:
        print("허용되지 않는 파일:")
        for path in failures:
            print(f"  - {path}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
