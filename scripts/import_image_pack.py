#!/usr/bin/env python3
"""래스터 이미지 팩(jpg/png)을 asset_hub 라이브러리에 등록한다.

- 라이브러리 규칙(`<UUID>.info/<file>`)에 복사하고 items 행 생성
- 360px JPEG 썸네일 생성(Pillow 필요)
- 태그: kind/topic/style/palette/set/license/scope

사용::

    sudo python3 import_image_pack.py --db /srv/sonagi-assets/asset_hub.db \\
        --library-root /srv/sonagi-assets/library --src /tmp/etchings \\
        --set etchings --license cc0 --provider wikimedia \\
        --url https://commons.wikimedia.org/wiki/Category:Etchings \\
        --style etching --palette mono --apply
"""

import argparse
import datetime
import json
import shutil
import sqlite3
import uuid
from pathlib import Path

from PIL import Image

EXTS = (".jpg", ".jpeg", ".png")
THUMB = 360


def load_meta(path):
    if not path:
        return {}
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict):
        raise SystemExit('--meta-json은 {"파일이름": {...}} 형태여야 합니다')
    return data


def build_annotation(stem, args, per_file):
    if args.origin != "generated":
        return None
    entry = per_file.get(stem) or {}
    generator = {
        "model": entry.get("model") or args.model,
        "prompt": entry.get("prompt") or args.prompt,
        "seed": entry.get("seed") or args.seed,
        "generated_at": entry.get("generated_at") or args.generated_at or datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
    }
    return json.dumps({"generator": generator}, ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--library-root", required=True)
    ap.add_argument("--src", required=True)
    ap.add_argument("--set", required=True, dest="pack")
    ap.add_argument("--license", required=True)
    ap.add_argument("--provider", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--style", required=True)
    ap.add_argument("--palette", default="mono")
    ap.add_argument("--origin", default=None, help="open-source|public-domain|freeware|commercial|generated|in-house")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--model", default=None, help="생성 모델(예: gemini-3.1-flash-image)")
    ap.add_argument("--prompt", default=None, help="생성 프롬프트")
    ap.add_argument("--seed", default=None, help="생성 시드/요청 ID")
    ap.add_argument("--generated-at", default=None, help="생성 시각(ISO). 없으면 현재 시각")
    ap.add_argument("--meta-json", default=None, help='파일별 생성 메타데이터 JSON ({"이름": {...}})')
    ap.add_argument("--refresh-meta", action="store_true", help="이미 등록된 자산의 생성 메타데이터만 갱신")
    args = ap.parse_args()

    src = Path(args.src)
    library = Path(args.library_root)
    images = library / "Design.library" / "images"
    thumbs = library / "thumbnails"
    images.mkdir(parents=True, exist_ok=True)
    thumbs.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in src.iterdir() if p.suffix.lower() in EXTS)
    per_file = load_meta(args.meta_json)
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    existing = {r[0] for r in conn.execute("select name from items where tags like ?", (f"%set:{args.pack}%",))}
    conn.close()
    todo = [p for p in files if p.stem not in existing]

    print(json.dumps({"pack": args.pack, "found": len(files), "already": len(files) - len(todo), "to_add": len(todo), "apply": args.apply}))
    if not args.apply:
        return 0

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = f"{args.db}.bak-imgpack-{stamp}"
    ro = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    dst = sqlite3.connect(backup)
    ro.backup(dst)
    dst.close()
    ro.close()

    conn = sqlite3.connect(args.db, timeout=60)
    conn.execute("PRAGMA busy_timeout=60000")
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if args.refresh_meta:
        updated = 0
        for path in files:
            if path.stem not in existing:
                continue
            conn.execute(
                "update items set annotation=? where name=?",
                (build_annotation(path.stem, args, per_file), path.stem),
            )
            updated += 1
        conn.commit()
        conn.close()
        print(json.dumps({"updated": updated, "backup": backup}, ensure_ascii=False))
        return 0
    created = 0
    for path in todo:
        item_id = str(uuid.uuid4()).upper()
        dest_dir = images / f"{item_id}.info"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / path.name
        shutil.copy2(path, dest)

        thumb_file = thumbs / f"{item_id}.png"
        try:
            im = Image.open(dest).convert("RGB")
            im.thumbnail((THUMB, THUMB), Image.LANCZOS)
            im.save(thumb_file, "PNG")
            thumb_path = f"/app/data/thumbnails/{item_id}.png"
        except Exception:
            thumb_path = ""

        origin_tags = []
        base_scope = ["scope:bundle"]
        if args.origin:
            origin_tags = [f"origin:{args.origin}"]
            if args.origin == "generated":
                # 생성물은 재배포 금지(output)다. bundle 태그가 함께 붙으면
                # 카탈로그가 알파벳 순으로 scope:bundle을 먼저 집어 잘못 승격된다.
                origin_tags.append("scope:output")
                base_scope = []
        tags = sorted(
            {
                "category:ui-component",
                "topic:illustration",
                "kind:illustration",
                f"style:{args.style}",
                f"palette:{args.palette}",
                f"set:{args.pack}",
                f"license:{args.license}",
                "license_src:provider",
                f"license_provider:{args.provider}",
                f"license_url:{args.url}",
                *base_scope,
                "src:asset-pack",
                *origin_tags,
            }
        )
        annotation = build_annotation(path.stem, args, per_file)
        conn.execute(
            "insert into items (id, name, ext, tags, annotation, url, thumbnail_path, original_path, created_at) values (?,?,?,?,?,?,?,?,?)",
            (
                item_id,
                path.stem,
                path.suffix.lstrip(".").lower(),
                json.dumps(tags, ensure_ascii=False),
                annotation,
                args.url,
                thumb_path,
                f"/app/data/Design.library/images/{item_id}.info/{path.name}",
                now,
            ),
        )
        created += 1
    conn.commit()
    conn.close()
    print(json.dumps({"created": created, "backup": backup}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
