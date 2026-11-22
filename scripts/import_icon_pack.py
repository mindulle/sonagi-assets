#!/usr/bin/env python3
"""아이콘 팩(SVG 묶음)을 asset_hub 라이브러리에 등록한다.

- 라이브러리 규칙(`<UUID>.info/<file>`)에 맞춰 복사하고 items 행을 만든다
- 160px PNG 썸네일을 생성한다(cairosvg 필요, 없으면 건너뜀)
- 태그: kind:icon, topic:icon, set:<pack>, license:*, scope:bundle 등
- 같은 set 안에서 같은 이름이 이미 있으면 건너뛴다(재실행 안전)

사용 (devops)::

    sudo python3 import_icon_pack.py --db /srv/sonagi-assets/asset_hub.db \\
        --library-root /srv/sonagi-assets/library \\
        --src /tmp/iconpacks/lucide --set lucide --license isc \\
        --provider lucide --url https://lucide.dev/license --apply
"""

import argparse
import datetime
import json
import shutil
import sqlite3
import uuid
from pathlib import Path

try:
    import cairosvg
except ImportError:  # 썸네일 없이 등록
    cairosvg = None

THUMB_SIZE = 160


def tags_for(name, pack, license_value, provider, url, form):
    return sorted(
        {
            "category:ui-component",
            "topic:icon",
            "kind:icon",
            "palette:mono",
            f"set:{pack}",
            f"form:{form}",
            f"license:{license_value}",
            "license_src:provider",
            f"license_provider:{provider}",
            f"license_url:{url}",
            "scope:bundle",
            "src:icon-pack",
        }
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--library-root", required=True)
    ap.add_argument("--src", required=True)
    ap.add_argument("--set", required=True, dest="pack")
    ap.add_argument("--license", required=True)
    ap.add_argument("--provider", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--form", default="line", choices=("line", "filled", "mixed"))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    src = Path(args.src)
    library = Path(args.library_root)
    images = library / "Design.library" / "images"
    thumbs = library / "thumbnails"
    images.mkdir(parents=True, exist_ok=True)
    thumbs.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in src.glob("*.svg") if p.is_file())
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    existing = {row[0] for row in conn.execute("select name from items where tags like ?", (f"%set:{args.pack}%",))}
    conn.close()

    todo = [p for p in files if p.stem not in existing]
    print(
        json.dumps(
            {
                "pack": args.pack,
                "found": len(files),
                "already": len(files) - len(todo),
                "to_add": len(todo),
                "apply": args.apply,
            },
            ensure_ascii=False,
        )
    )
    if not args.apply:
        return 0

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = f"{args.db}.bak-icons-{stamp}"
    ro = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    dst = sqlite3.connect(backup)
    ro.backup(dst)
    dst.close()
    ro.close()

    conn = sqlite3.connect(args.db, timeout=60)
    conn.execute("PRAGMA busy_timeout=60000")
    created = 0
    thumb_made = 0
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    for path in todo:
        item_id = str(uuid.uuid4()).upper()
        dest_dir = images / f"{item_id}.info"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / path.name
        shutil.copy2(path, dest)

        thumb_path = ""
        if cairosvg is not None:
            thumb_file = thumbs / f"{item_id}.png"
            try:
                cairosvg.svg2png(
                    url=str(dest),
                    write_to=str(thumb_file),
                    output_width=THUMB_SIZE,
                    output_height=THUMB_SIZE,
                    background_color="white",
                )
                thumb_path = f"/app/data/thumbnails/{item_id}.png"
                thumb_made += 1
            except Exception:
                thumb_path = ""

        conn.execute(
            "insert into items (id, name, ext, tags, annotation, url, thumbnail_path, original_path, created_at) values (?,?,?,?,?,?,?,?,?)",
            (
                item_id,
                path.stem,
                "svg",
                json.dumps(tags_for(path.stem, args.pack, args.license, args.provider, args.url, args.form), ensure_ascii=False),
                None,
                None,
                thumb_path,
                f"/app/data/Design.library/images/{item_id}.info/{path.name}",
                now,
            ),
        )
        created += 1
        if created % 500 == 0:
            conn.commit()

    conn.commit()
    conn.close()
    print(
        json.dumps(
            {"created": created, "thumbnails": thumb_made, "backup": backup},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
