#!/usr/bin/env python3
"""아이콘/일러스트 벡터 에셋에 객관적 4축 태그를 붙인다.

- kind: icon | illustration
- form: line | filled | mixed
- palette: mono | color
- shape: geometric | organic
- detail: simple | detailed

심볼 시트(dingbats/symbols), 글리프(uniXXXX), 타이포 specimen, 색상 팔레트 목록은 제외.
기본 dry-run, --apply 시 DB 백업 후 반영.
"""

import argparse
import collections
import datetime
import json
import os
import re
import sqlite3

SHEET_RE = re.compile(r"^(Dingbats|Symbols|Math|Music|Alphabets|Colors)____", re.I)
EXCLUDE_RE = re.compile(
    r"(Alphabets|Latin|Serif|Sans|Script|Display|Blonde_|Colors____|분리_필요|Slab_|Gold_|Khaki_|Hangul_Jamo|uni[0-9a-f]{4,6})",
    re.I,
)
COLOR_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)")
STROKE_W_RE = re.compile(r"stroke-width\s*[:=]\s*\"?([0-9.]+)")
PATH_CMD_RE = re.compile(r"[A-Za-z]")
CURVE_CMDS = set("CcSsQqTtAa")
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
    n_elements = sum(len(re.findall(rf"<{tag}\b", text)) for tag in ("path", "rect", "circle", "ellipse", "polygon", "polyline", "line"))
    d_attrs = re.findall(r"\bd=\"([^\"]{0,20000})\"", text)
    cmd = collections.Counter()
    for d in d_attrs:
        cmd.update(PATH_CMD_RE.findall(d))
    total = sum(cmd.values())
    curve = sum(cmd[c] for c in CURVE_CMDS)
    n_paths = len(re.findall(r"<path\b", text))

    has_stroke = bool(widths) or strokes > 0
    if has_stroke and not fills:
        form = "line"
    elif fills and not has_stroke:
        form = "filled"
    else:
        form = "mixed"

    return {
        "form": form,
        "palette": "color" if len(colors) > 4 else "mono",
        "shape": "organic" if total and curve / total >= 0.3 else "geometric",
        "detail": "simple" if (n_elements <= 6 and (total / max(1, n_paths)) < 12) else "detailed",
        "kind": "icon" if (n_elements <= 15 and len(colors) <= 8 and len(text) < 500_000) else "illustration",
        "n_elements": n_elements,
        "n_colors": len(colors),
    }


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
    seen = set()
    for row_id, name, tags_json, original in rows:
        name = name or ""
        if (
            SHEET_RE.match(name)
            or EXCLUDE_RE.search(name)
            or re.match(r"^[a-z]+$", name)
            or len(name.strip()) <= 2
            or "korean" in name.lower()
            or name in seen
            or len(name) > 60
        ):
            continue
        seen.add(name)
        meta = analyze(host_path(original, args.library_root))
        if not meta:
            continue
        try:
            tags = json.loads(tags_json) if tags_json else []
        except json.JSONDecodeError:
            tags = []
        tags = [t for t in tags if not t.startswith(("kind:", "form:", "palette:", "shape:", "detail:"))]
        tags += [f"kind:{meta['kind']}", f"form:{meta['form']}", f"palette:{meta['palette']}", f"shape:{meta['shape']}", f"detail:{meta['detail']}"]
        updates.append((row_id, sorted(set(tags)), meta, name))
        stats[(meta["kind"], meta["form"], meta["palette"])] += 1

    print(json.dumps({"assets": len(updates), "stats": {"/".join(k): v for k, v in stats.items()}, "apply": args.apply}, ensure_ascii=False))
    for _, _, meta, name in updates[:5]:
        print(name, meta)

    if not args.apply:
        return 0

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = f"{args.db}.bak-vectortags-{stamp}"
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
