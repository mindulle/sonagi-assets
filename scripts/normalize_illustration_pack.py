#!/usr/bin/env python3
"""일러스트 팩을 화면에 바로 쓸 수 있게 정규화한다.

원본(illlustrations 등)은 1000×1000 캔버스 하단에 제작자 크레딧을 벡터로 넣고,
배경색을 캔버스 전체에 깔아 둔다. 그대로 배치하면 카드 안에 카드가 생기고
크레딧 텍스트가 노출된다.

이 스크립트는:
- viewBox를 `0 0 1000 <crop>`로 잘라 하단 크레딧 띠를 제거한다(기본 935)
- 배경은 유지한다. 일부 일러스트는 배경색이 그림의 일부라 제거하면 깨진다
- 같은 경로에 덮어쓰고 썸네일을 다시 만든다(cairosvg)

사용::

    sudo python3 normalize_illustration_pack.py \\
        --db /srv/sonagi-assets/asset_hub.db \\
        --library-root /srv/sonagi-assets/library \\
        --set illlustrations --apply
"""

import argparse
import json
import os
import re
import sqlite3

try:
    import cairosvg
except ImportError:
    cairosvg = None

THUMB_SIZE = 160
VIEWBOX = re.compile(r'viewBox="0 0 1000 1000"')


def host_path(original, library_root):
    if original.startswith("/app/data/"):
        return os.path.join(library_root, original[len("/app/data/") :])
    return original


def normalize(text, crop):
    if not VIEWBOX.search(text):
        return None
    return VIEWBOX.sub(f'viewBox="0 0 1000 {crop}"', text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--library-root", required=True)
    ap.add_argument("--set", required=True, dest="pack")
    ap.add_argument("--crop", type=int, default=935)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    rows = list(
        conn.execute(
            "select id, name, original_path, thumbnail_path from items where tags like ?",
            (f"%set:{args.pack}%",),
        )
    )
    conn.close()

    changed, skipped, missing = [], 0, 0
    for item_id, name, original, thumb in rows:
        path = host_path(original, args.library_root)
        if not os.path.isfile(path):
            missing += 1
            continue
        with open(path, errors="ignore") as f:
            text = f.read()
        new = normalize(text, args.crop)
        if new is None:
            skipped += 1
            continue
        changed.append((item_id, path, new, thumb))

    print(
        json.dumps(
            {
                "set": args.pack,
                "items": len(rows),
                "to_normalize": len(changed),
                "already": skipped,
                "missing": missing,
                "crop": args.crop,
                "apply": args.apply,
            },
            ensure_ascii=False,
        )
    )
    if not args.apply:
        return 0

    thumbs = 0
    for item_id, path, text, thumb in changed:
        with open(path, "w") as f:
            f.write(text)
        if cairosvg is not None:
            target = host_path(thumb, args.library_root) if thumb else ""
            if not target:
                target = os.path.join(args.library_root, "thumbnails", f"{item_id}.png")
            try:
                cairosvg.svg2png(
                    url=path,
                    write_to=target,
                    output_width=THUMB_SIZE,
                    output_height=THUMB_SIZE,
                    background_color="white",
                )
                thumbs += 1
            except Exception:
                pass

    print(json.dumps({"normalized": len(changed), "thumbnails": thumbs}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
