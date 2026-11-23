#!/usr/bin/env python3
"""레시피 스키마 정리 — 렌더 가능한 형태(`blocks`)로 맞춘다.

세 가지 모양이 돌아다녔다(ASSET-4).

| 모양 | 예 | 상태 |
| --- | --- | --- |
| `blocks` 리스트 | `recipes/landing-hero.json`, 임포터 출력 | **정본** |
| `content` 블록 맵 | `recipes/landing-hero-v2.json` | 레거시, 읽기 전용 |
| `content` 메타 | `{"source": "...", "sha256": "..."}` | 임포터가 붙이는 추적 정보 |

정본은 `blocks`다. 레거시 맵은 순서를 유지한 채 `blocks`로 변환해 읽는다.
새로 쓰는 레시피는 `content.md` → `import_content.py` 경로만 쓴다.

사용::

    recipe_schema.py recipes/landing-hero.json      # 검사 + 블록 요약
    recipe_schema.py recipes/*.json --json          # 기계 판독
"""

import argparse
import json
import sys
from pathlib import Path

BLOCK_TYPES = (
    "header",
    "hero",
    "stats",
    "features",
    "logos",
    "quote",
    "faq",
    "cta",
    "footer",
    "table",
    "pricing",
    "gallery",
)


class RecipeError(Exception):
    pass


def is_legacy_map(value):
    """`content`가 블록 타입을 키로 하는 맵인가."""
    return isinstance(value, dict) and any(isinstance(v, dict) for v in value.values())


def normalize(recipe, name="recipe"):
    """렌더 가능한 레시피를 돌려준다. 원본은 건드리지 않는다."""
    if not isinstance(recipe, dict):
        raise RecipeError(f"{name}: 최상위가 객체가 아닙니다")

    blocks = recipe.get("blocks")
    if isinstance(blocks, list) and blocks:
        for index, block in enumerate(blocks, start=1):
            if not isinstance(block, dict) or block.get("type") not in BLOCK_TYPES:
                raise RecipeError(f"{name}: blocks[{index}] 타입이 없거나 알 수 없습니다: {block!r}")
        return recipe, "blocks"

    content = recipe.get("content")
    if is_legacy_map(content):
        converted = []
        for kind, fields in content.items():
            if kind not in BLOCK_TYPES:
                raise RecipeError(f"{name}: content.{kind}는 블록 타입이 아닙니다")
            if not isinstance(fields, dict):
                raise RecipeError(f"{name}: content.{kind}는 객체여야 합니다")
            converted.append({"type": kind, **fields})
        out = {k: v for k, v in recipe.items() if k != "content"}
        out["blocks"] = converted
        return out, "content-map"

    if isinstance(content, dict) and ("source" in content or "sha256" in content):
        raise RecipeError(f"{name}: 블록이 없습니다. content는 추적 정보만 있습니다. content.md에서 import_content.py로 다시 만드세요.")
    raise RecipeError(f"{name}: `blocks`도 `content` 블록 맵도 없습니다")


def load(path):
    path = Path(path)
    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise RecipeError(f"{path}: JSON이 아닙니다 ({exc})") from exc
    return normalize(raw, name=str(path))


def main():
    ap = argparse.ArgumentParser(description="레시피 스키마 검사")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rows, failed = [], 0
    for path in args.files:
        try:
            recipe, schema = load(path)
            rows.append(
                {
                    "file": path,
                    "name": recipe.get("name"),
                    "schema": schema,
                    "blocks": [b["type"] for b in recipe["blocks"]],
                }
            )
        except RecipeError as exc:
            failed += 1
            rows.append({"file": path, "error": str(exc)})

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            if "error" in row:
                print(f"✗ {row['file']}: {row['error']}")
                continue
            legacy = " (레거시 content 맵 → 변환)" if row["schema"] != "blocks" else ""
            print(f"✓ {row['file']}: {len(row['blocks'])}블록{legacy} — {', '.join(row['blocks'])}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
