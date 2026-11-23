#!/usr/bin/env python3
"""명부(registry) — 스타일·블록·룰을 이름이 아니라 id로 참조한다.

스타일 27종은 손으로 쓴 27장이 아니라 축 조합이다. 그래서 "victorian"이라는
이름만 보고는 어떤 축인지 알 수 없고, 파일이 바뀌어도 이름은 그대로다.
계약 헤더의 `style_id`(`<이름>@<해석된 스타일 해시>`)를 명부로 모아 두면
그래프·레시피·문서가 **이름 대신 id로** 같은 것을 가리킬 수 있다.

산출물은 `registry/` 아래 세 파일과 색인 하나다. 손으로 고치지 않는다.

| 파일          | 내용                                             |
| ------------- | ------------------------------------------------ |
| `styles.json` | 27스타일의 id·축 선언·파일·해시                   |
| `blocks.json` | 렌더 가능한 12블록의 id와 순서                    |
| `rules.json`  | 판정 룰셋 version과 룰 id/severity                |
| `index.json`  | 개수·섹션 해시·중복 id·레시피 참조·tokens_version |

사용::

    build_registry.py            # registry/ 다시 쓰기
    build_registry.py --check    # 커밋된 명부와 현재 파일이 같은지 (CI)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import contract  # noqa: E402
from recipe_schema import BLOCK_TYPES, RecipeError, normalize  # noqa: E402
from render_recipe import DEFAULT_STYLE, deep_merge  # noqa: E402
from style_axes import AXIS_KEYS, load_style  # noqa: E402

REGISTRY = ROOT / "registry"
SCHEMA = 1
SKIP_STYLES = {"axes.json", "ornaments.json"}


def sha12(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()[:12]


def style_files():
    return sorted(p for p in (ROOT / "styles").glob("*.json") if p.name not in SKIP_STYLES)


def collect_styles():
    entries, seen = [], {}
    for path in style_files():
        spec = json.loads(path.read_text())
        resolved = deep_merge(DEFAULT_STYLE, load_style(path))
        entry = {
            "id": contract.style_id(resolved),
            "name": spec.get("name") or path.stem,
            "file": f"styles/{path.name}",
            "sha256": sha12(path.read_bytes()),
            "theme": resolved.get("theme"),
            "axes": {key: spec[key] for key in AXIS_KEYS if key in spec},
        }
        # 축을 파일에 직접 쓰지 않고 dict로 덮은 스타일도 있다
        for key in ("hero", "features_layout", "header", "illustration_set", "density"):
            if key in spec:
                entry[key] = spec[key]
        entries.append(entry)
        seen.setdefault(entry["id"], []).append(entry["file"])
    entries.sort(key=lambda e: (e["name"], e["file"]))
    duplicates = {k: v for k, v in seen.items() if len(v) > 1}
    return entries, duplicates


def collect_blocks():
    return [{"id": kind, "order": index + 1} for index, kind in enumerate(BLOCK_TYPES)]


def collect_rules():
    ruleset = json.loads((ROOT / "rules/ruleset.json").read_text())
    return {
        "ruleset_version": ruleset["version"],
        "rules": [{"id": r["id"], "severity": r["severity"]} for r in ruleset["rules"]],
        "sha256": sha12((ROOT / "rules/ruleset.json").read_bytes()),
    }


def collect_themes():
    tokens = json.loads((ROOT / "tokens/semantic.json").read_text())
    return sorted(tokens)


def collect_recipe_refs(style_names, themes):
    """레시피가 어떤 스타일·테마를 이름으로 부르는지, 없는 이름은 아닌지."""
    refs, unknown = {}, []
    for path in sorted((ROOT / "recipes").glob("*.json")):
        raw = json.loads(path.read_text())
        try:
            recipe, _ = normalize(raw, name=str(path))
        except RecipeError as exc:
            unknown.append({"recipe": path.name, "error": str(exc)})
            continue
        row = {}
        style = recipe.get("style")
        if style:
            name = style.get("name") if isinstance(style, dict) else Path(style).stem
            row["style"] = name
            if name not in style_names:
                unknown.append({"recipe": path.name, "style": name})
        theme = recipe.get("theme")
        if theme:
            row["theme"] = theme
            if theme not in themes:
                unknown.append({"recipe": path.name, "theme": theme})
        if row:
            refs[path.name] = row
    return refs, unknown


def build():
    styles, duplicates = collect_styles()
    blocks = collect_blocks()
    rules = collect_rules()
    themes = collect_themes()
    refs, unknown = collect_recipe_refs({s["name"] for s in styles}, set(themes))
    for style in styles:
        if style.get("theme") and style["theme"] not in themes:
            unknown.append({"style": style["name"], "theme": style["theme"]})
    documents = {
        "styles.json": {"schema": SCHEMA, "styles": styles},
        "blocks.json": {"schema": SCHEMA, "blocks": blocks},
        "rules.json": {"schema": SCHEMA, **rules},
    }
    index = {
        "schema": SCHEMA,
        "tokens_version": contract.tokens_version(ROOT / "tokens/semantic.json"),
        "themes": themes,
        "style_count": len(styles),
        "block_count": len(blocks),
        "ruleset_version": rules["ruleset_version"],
        "sections": {name: sha12(serialize(doc)) for name, doc in documents.items()},
        "duplicate_style_ids": duplicates,
        "recipes": refs,
        "unknown": unknown,
    }
    documents["index.json"] = index
    return documents, index


def serialize(document):
    return json.dumps(document, indent=4, ensure_ascii=False, sort_keys=False) + "\n"


def write(documents):
    REGISTRY.mkdir(exist_ok=True)
    for name, document in documents.items():
        (REGISTRY / name).write_text(serialize(document))


def check(documents, index):
    problems = []
    for name, document in documents.items():
        path = REGISTRY / name
        if not path.is_file():
            problems.append(f"{name}: 없습니다. build_registry.py로 생성하세요")
        elif path.read_text() != serialize(document):
            problems.append(f"{name}: 현재 파일과 다릅니다")
    if index["duplicate_style_ids"]:
        for style_id, names in index["duplicate_style_ids"].items():
            problems.append(f"중복 style_id {style_id}: {', '.join(names)}")
    for row in index["unknown"]:
        problems.append(f"레시피 참조 오류: {row}")
    return problems


def main():
    ap = argparse.ArgumentParser(description="스타일·블록·룰 명부")
    ap.add_argument("--check", action="store_true", help="커밋된 명부와 현재 파일을 비교")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    documents, index = build()

    if args.json:
        print(json.dumps(index, indent=4, ensure_ascii=False))
    else:
        print(f"스타일 {index['style_count']} · 블록 {index['block_count']} · 룰 {index['ruleset_version']} · tokens {index['tokens_version']}")
        for style_id, names in index["duplicate_style_ids"].items():
            print(f"  중복 id {style_id}: {', '.join(names)}")
        for row in index["unknown"]:
            print(f"  참조 오류 {row}")

    if args.check:
        problems = check(documents, index)
        for problem in problems:
            print(f"✗ {problem}")
        if problems:
            return 1
        print("명부 최신 (registry/ 4개 파일)")
        return 0

    write(documents)
    print(f"명부 저장: registry/ ({len(documents)}개 파일)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
