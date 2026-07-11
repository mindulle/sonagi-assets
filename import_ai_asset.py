#!/usr/bin/env python3
"""
import_ai_asset.py

AI 생성 이미지를 Eagle.cool .info/ 포맷으로 변환하여
ai-assets 디렉토리에 저장하는 스크립트.

사용법:
    python import_ai_asset.py <image_path> [--tags tag1,tag2] [--name "이름"] [--annotation "메모"]

예시:
    python import_ai_asset.py /path/to/output.png --tags "ai-generated,comfyui" --name "로고 v1"
"""

import argparse
import json
import shutil
import sys
import time
import uuid
from pathlib import Path

try:
    from PIL import Image

    HAS_PIL = True
except ImportError:
    HAS_PIL = False

AI_ASSETS_PATH = "/mnt/monitoring/ai-assets/images"
THUMBNAIL_SIZE = (256, 256)


def generate_id():
    return str(uuid.uuid4()).upper()


def make_thumbnail(src_path: Path, dest_path: Path):
    if not HAS_PIL:
        # PIL 없으면 원본 복사
        shutil.copy2(src_path, dest_path)
        return
    try:
        with Image.open(src_path) as img:
            img.thumbnail(THUMBNAIL_SIZE)
            img.save(dest_path)
    except Exception as e:
        print(f"Warning: thumbnail 생성 실패 ({e}), 원본 복사로 대체")
        shutil.copy2(src_path, dest_path)


def import_asset(image_path: str, name: str = None, tags: list = None, annotation: str = ""):
    src = Path(image_path)
    if not src.exists():
        print(f"Error: 파일이 존재하지 않습니다: {image_path}")
        sys.exit(1)

    ext = src.suffix.lstrip(".").lower()
    asset_id = generate_id()
    asset_name = name or src.stem

    # .info 디렉토리 생성
    info_dir = Path(AI_ASSETS_PATH) / f"{asset_id}.info"
    info_dir.mkdir(parents=True, exist_ok=True)

    # 원본 파일 복사
    dest_original = info_dir / f"{asset_name}.{ext}"
    shutil.copy2(src, dest_original)

    # 썸네일 생성
    thumb_ext = "jpg" if ext not in ("png", "gif", "webp") else ext
    dest_thumbnail = info_dir / f"{asset_id}_thumbnail.{thumb_ext}"
    make_thumbnail(src, dest_thumbnail)

    # metadata.json 생성
    metadata = {
        "id": asset_id,
        "name": asset_name,
        "ext": ext,
        "tags": tags or ["ai-generated", "comfyui"],
        "folders": [],
        "isDeleted": False,
        "url": "",
        "annotation": annotation,
        "modificationTime": int(time.time() * 1000),
    }

    meta_path = info_dir / "metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"✓ 임포트 완료: {asset_name}.{ext}")
    print(f"  ID: {asset_id}")
    print(f"  경로: {info_dir}")
    return asset_id


def main():
    parser = argparse.ArgumentParser(description="AI 생성 이미지를 Eagle Gallery 포맷으로 임포트")
    parser.add_argument("image_path", help="임포트할 이미지 파일 경로")
    parser.add_argument("--name", help="에셋 이름 (기본값: 파일명)")
    parser.add_argument("--tags", help="태그 (쉼표 구분, 예: ai-generated,comfyui,logo)")
    parser.add_argument("--annotation", help="메모/설명", default="")

    args = parser.parse_args()

    tags = [t.strip() for t in args.tags.split(",")] if args.tags else ["ai-generated", "comfyui"]

    import_asset(
        image_path=args.image_path,
        name=args.name,
        tags=tags,
        annotation=args.annotation,
    )


if __name__ == "__main__":
    main()
