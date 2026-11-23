#!/usr/bin/env python3
"""산출물 계약 헤더 — "이 SVG는 어느 값·구조·룰로 만들어졌나"를 네 칸에 고정한다.

골든 기준선은 SVG 바이트가 같은지만 본다. 그래서 토큰을 고치거나 판정 룰셋을
바꿔도 산출물은 조용히 지나간다. 계약 헤더는 그 조용한 변화를 이름으로 남긴다.

| 칸               | 값                                   | 왜                    |
| ---------------- | ------------------------------------ | --------------------- |
| `schema_version` | 계약 헤더 자신의 판(현재 1)          | 헤더 형식 개정 추적   |
| `tokens_version` | `tokens/semantic.json` sha256 앞 12  | 팔레트 개정 추적      |
| `style_id`       | `<이름>@<해석된 스타일 해시 12>`     | 축 조합 동일성 판정   |
| `ruleset_version`| `rules/ruleset.json`의 version      | 어떤 룰로 판정했나    |

`style_id`는 파일 해시가 아니라 **해석된 스타일**(축 병합 후)의 해시다.
같은 축 조합이면 파일이 달라도 같은 id가 나오고, 축 값이 1px이라도 다르면
다른 id가 나온다. 스타일 이름만 보고 "같은 스킨"이라 착각하는 일을 막는다.

사용::

    from contract import stamp
    manifest["contract"] = stamp(style, tokens_path=args.tokens)
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULESET = ROOT / "rules" / "ruleset.json"

CONTRACT_SCHEMA_VERSION = 1
FIELDS = ("schema_version", "tokens_version", "style_id", "ruleset_version")


def sha12(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()[:12]


def canonical(value) -> str:
    """dict/list를 키 정렬 JSON으로 — 같은 내용이면 같은 문자열."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def tokens_version(path: str | Path) -> str:
    return sha12(Path(path).read_bytes())


def style_id(style: dict) -> str:
    name = style.get("name") or "default"
    return f"{name}@{sha12(canonical(style))}"


def ruleset_version(path: str | Path = RULESET) -> str:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"룰셋이 없습니다: {path}")
    return json.loads(path.read_text())["version"]


def stamp(style: dict, tokens_path: str | Path) -> dict:
    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "tokens_version": tokens_version(tokens_path),
        "style_id": style_id(style),
        "ruleset_version": ruleset_version(),
    }


def validate(value, name="contract") -> None:
    """레시피가 선언한 계약 헤더를 검사한다. 값은 렌더 시점에 다시 계산한다."""
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValueError(f"{name}: 객체여야 합니다")
    unknown = set(value) - set(FIELDS)
    if unknown:
        raise ValueError(f"{name}: 알 수 없는 키 {sorted(unknown)}")
    version = value.get("schema_version")
    if version is not None and version != CONTRACT_SCHEMA_VERSION:
        raise ValueError(f"{name}: schema_version {version}은 이 렌더러({CONTRACT_SCHEMA_VERSION})와 다릅니다")


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="현재 값으로 계약 헤더를 출력한다")
    ap.add_argument("--tokens", default=str(ROOT / "tokens/semantic.json"))
    ap.add_argument("--style", default=None, help="styles/*.json — 없으면 default")
    args = ap.parse_args()

    sys_path = str(ROOT / "scripts")
    import sys

    if sys_path not in sys.path:
        sys.path.insert(0, sys_path)
    from render_recipe import DEFAULT_STYLE, deep_merge
    from style_axes import load_style

    style = DEFAULT_STYLE
    if args.style:
        style = deep_merge(DEFAULT_STYLE, load_style(args.style))
    print(json.dumps(stamp(style, args.tokens), indent=4, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
