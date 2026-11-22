#!/usr/bin/env python3
"""심볼 시트(Dingbats/Symbols/Math/Music)에 3축 태그를 붙인다.

- form: line | filled | mixed
- palette: mono | color
- theme: 이름의 `____` 뒤 슬러그 (예: military, navigation-signs)

기본 dry-run. --apply 시 DB 백업 후 태그를 갱신한다.
"""

import argparse
import collections
import datetime
import json
import os
import re
import sqlite3

SHEET_RE = re.compile(r"^(Dingbats|Symbols|Math|Music)____(.+)$", re.I)
COLOR_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)")
STROKE_W_RE = re.compile(r"stroke-width\s*[:=]\s*\"?([0-9.]+)")
MAX_BYTES = 40 * 1024 * 1024


def host_path(original_path, library_root):
    if original_path.startswith("/app/data/"):
        return os.path.join(library_root, original_path[len("/app/data/") :])
    return original_path


def analyze(path):
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return None
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    except OSError:
        return None

    widths = [float(x) for x in STROKE_W_RE.findall(text) if float(x) > 0]
    fills = len(re.findall(r"fill\s*[:=]\s*['\"]?(?!none)(?:#[0-9a-fA-F]{3,8}|rgba?\(|url\()", text))
    strokes = len(re.findall(r"stroke\s*[:=]\s*['\"]?(?!none)(?:#[0-9a-fA-F]{3,8}|rgba?\(|url\()", text))
    colors = {c.lower() for c in COLOR_RE.findall(text)}
    if "url(#" in text:
        colors.add("gradient")

    has_stroke = bool(widths) or strokes > 0
    if has_stroke and not fills:
        form = "line"
    elif fills and not has_stroke:
        form = "filled"
    elif fills and has_stroke:
        form = "mixed"
    else:
        form = "mixed"
    palette = "color" if len(colors) > 6 else "mono"
    return {"form": form, "palette": palette, "colors": len(colors)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--library-root", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    rows = list(conn.execute("select id,name,tags,original_path from items where ext='svg'"))
    conn.close()

    updates = []
    stats = collections.Counter()
    for row_id, name, tags_json, original in rows:
        m = SHEET_RE.match(name or "")
        if not m:
            continue
        theme = re.sub(r"[^a-z0-9]+", "-", m.group(2).lower()).strip("-")
        meta = analyze(host_path(original, args.library_root))
        if not meta:
            continue
        try:
            tags = json.loads(tags_json) if tags_json else []
        except json.JSONDecodeError:
            tags = []
        new_tags = [t for t in tags if not t.startswith(("form:", "palette:", "theme:"))]
        new_tags += [f"form:{meta['form']}", f"palette:{meta['palette']}", f"theme:{theme}"]
        new_tags = sorted(set(new_tags))
        updates.append((row_id, new_tags, meta, theme))
        stats[(meta["form"], meta["palette"])] += 1

    print(json.dumps({"sheets": len(updates), "stats": {f"{k[0]}-{k[1]}": v for k, v in stats.items()}, "apply": args.apply}, ensure_ascii=False))
    if not args.apply:
        for row_id, tags, meta, theme in updates[:5]:
            print(row_id, theme, tags)
        return 0

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = f"{args.db}.bak-symboltags-{stamp}"
    src = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    dst = sqlite3.connect(backup)
    src.backup(dst)
    dst.close()
    src.close()

    conn = sqlite3.connect(args.db, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    for row_id, tags, _, _ in updates:
        conn.execute("update items set tags=? where id=?", (json.dumps(tags, ensure_ascii=False), row_id))
    conn.commit()
    conn.close()
    print(json.dumps({"updated": len(updates), "backup": backup}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
