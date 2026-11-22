#!/usr/bin/env python3
"""미확인 폰트의 URL 도메인으로 라이선스 성격을 추정한다.

- 상용 파운드리 도메인 → license:commercial
- 알려진 무료 배포 도메인 → license:free
- 그 외 → license_site:<domain> 만 남김 (수동 확인)

기본 dry-run, --apply 시 DB 백업 후 반영.
"""

import argparse
import collections
import datetime
import json
import os
import re
import sqlite3

from fontTools.ttLib import TTFont

NAME_IDS = (0, 7, 8, 9, 10, 11, 12, 13, 14)
COMMERCIAL = {
    "fontfabric.com",
    "www.fontfabric.com",
    "yoondesign.com",
    "www.yoondesign.com",
    "sandoll.co.kr",
    "www.sandoll.co.kr",
    "fontrix.co.kr",
    "www.fontrix.co.kr",
    "agfont.com",
    "www.agfont.com",
    "typolab.co.kr",
    "www.typolab.co.kr",
    "s-core.co.kr",
    "www.s-core.co.kr",
    "thefontgroup.co.kr",
    "www.thefontgroup.co.kr",
    "togethergroup.co.kr",
    "ddungsang.com",
    "www.ddungsang.com",
    "sangsangfont.com",
    "wemakeprice.com",
    "www.wemakeprice.com",
}
FREE = {
    "nhncorp.com",
    "www.nhncorp.com",
    "navercorp.com",
    "www.navercorp.com",
    "fonts.cafe24.com",
    "woodcutter.es",
    "www.woodcutter.es",
    "steffmann.de",
    "www.steffmann.de",
}


def host_path(original_path, library_root):
    if original_path.startswith("/app/data/"):
        return os.path.join(library_root, original_path[len("/app/data/") :])
    return original_path


def font_urls(path):
    try:
        font = TTFont(path, fontNumber=0, lazy=True)
    except Exception:
        return []
    try:
        name = font["name"]
        return [name.getDebugName(i) or "" for i in NAME_IDS]
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

    known = {"ofl", "apache", "gpl", "cc0", "commercial", "personal", "free"}
    updates = []
    stats = collections.Counter()
    for row_id, name, ext, tags_json, original in rows:
        try:
            tags = json.loads(tags_json) if tags_json else []
        except json.JSONDecodeError:
            tags = []
        lic = [t.split(":", 1)[1] for t in tags if t.startswith("license:")]
        if lic and lic[0] in known:
            continue
        path = host_path(original, args.library_root)
        urls = " ".join(font_urls(path)) if path else ""
        domains = {m.group(1).lower() for m in re.finditer(r"https?://([^/\s\"']+)", urls)}
        if not domains:
            stats["no_domain"] += 1
            continue
        commercial = domains & COMMERCIAL
        free = domains & FREE
        tags = [t for t in tags if not t.startswith(("license:", "license_src:", "license_site:"))]
        if commercial:
            tags += ["license:commercial", "license_src:site"]
            stats["commercial"] += 1
        elif free:
            tags += ["license:free", "license_src:site"]
            stats["free"] += 1
        else:
            tags += [f"license_site:{sorted(domains)[0]}"]
            stats["site_only"] += 1
        updates.append((row_id, sorted(set(tags))))

    print(json.dumps({"updates": len(updates), "stats": dict(stats), "apply": args.apply}, ensure_ascii=False))
    if not args.apply:
        return 0

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = f"{args.db}.bak-fontsites-{stamp}"
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
