#!/usr/bin/env python3
"""결정 원장(ledger) — "왜 이렇게 만들었나"를 산출물 옆에 남긴다.

매니페스트는 **무엇이 들어갔나**(자산·입력 해시·계약)를 증명한다. 하지만
"왜 이 스타일을 골랐나", "왜 이 안을 승인했나"는 남지 않는다. 그래프가 변주
12개를 만들고 3개로 좁히는 순간, 그 선택의 이유가 사라지면 다음 사람은 같은
고민을 처음부터 다시 한다.

원장은 세 층이다.

| 층          | 누가 쓰나 | 내용                                    |
| ----------- | --------- | --------------------------------------- |
| `contract`  | 렌더러    | tokens·style·ruleset 버전(재현 좌표)    |
| `references`| 렌더러    | 실제로 쓰인 자산과 라이선스 범위        |
| `judgement` | 린터      | verdict와 발화한 룰 id                  |
| `decisions` | 사람/그래프 | key=choice + 이유. 자동 3건은 `render.*` |

 결정에는 시각을 넣지 않는다(번들 결정론). 시각이 필요하면 `--at`으로
 고정 값을 넣는다.

사용::

    ledger.py --svg out/x.svg --manifest out/x.manifest.json \\
        --lint out/x.lint.json \\
        --decision "style=editorial: 레퍼런스보다 여백이 넓어 제목이 살았다" \\
        --by hoyacho

    ledger.py --check out/x.decisions.json --manifest out/x.manifest.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "registry"
SCHEMA = 1


def load_registry():
    path = REGISTRY / "styles.json"
    if not path.is_file():
        raise SystemExit("registry/styles.json이 없습니다. build_registry.py를 먼저 실행하세요")
    styles = json.loads(path.read_text())["styles"]
    return {style["id"]: style for style in styles}


def lint_summary(payload):
    """lint_render.py --out 결과(단일 객체 또는 배열)를 요약한다."""
    if not payload:
        return None
    rows = payload if isinstance(payload, list) else [payload]
    return {
        "verdict": max(
            (row.get("verdict", "pass") for row in rows),
            key=lambda v: {"pass": 0, "warn": 1, "fail": 2}.get(v, 0),
        ),
        "rules": sorted({f["rule"] for row in rows for f in row.get("findings", [])}),
        "ruleset_version": rows[0].get("ruleset_version"),
    }


def parse_decision(raw):
    if "=" not in raw:
        raise SystemExit(f"--decision 형식은 key=choice: 이유 입니다: {raw}")
    key, rest = raw.split("=", 1)
    choice, _, reason = rest.partition(":")
    return {"key": key.strip(), "choice": choice.strip(), "reason": reason.strip()}


def build(svg, manifest_path, lint_path, decisions, by, at=None):
    manifest = json.loads(Path(manifest_path).read_text())
    contract = manifest.get("contract") or {}
    if not contract:
        raise SystemExit(f"{manifest_path}: contract 헤더가 없습니다(구버전 렌더)")

    styles = load_registry()
    style = styles.get(contract.get("style_id"))
    references = [
        {
            "name": asset.get("name"),
            "kind": asset.get("kind"),
            "license": asset.get("license"),
            "scope": asset.get("scope"),
            "origin": asset.get("origin"),
        }
        for asset in sorted(manifest.get("assets", []), key=lambda a: (a.get("name") or "", a.get("scope") or ""))
    ]

    entries = [
        {"key": "render.style", "choice": contract.get("style_id"), "reason": "레시피가 지정한 스타일 축 조합", "by": "render"},
        {"key": "render.tokens", "choice": contract.get("tokens_version"), "reason": "렌더 시점 팔레트", "by": "render"},
        {"key": "render.ruleset", "choice": contract.get("ruleset_version"), "reason": "판정 룰셋", "by": "render"},
    ]
    for parsed in decisions:
        parsed["by"] = by
        entries.append(parsed)
    entries.sort(key=lambda e: (e["key"], e["choice"] or ""))

    ledger = {
        "schema": SCHEMA,
        "artifact": Path(svg).name,
        "recipe": manifest.get("recipe"),
        "contract": contract,
        "style": {"id": contract.get("style_id"), "name": style["name"] if style else None, "file": style["file"] if style else None},
        "inputs": manifest.get("inputs", {}),
        "references": references,
        "judgement": lint_summary(lint_path),
        "decisions": entries,
    }
    if at:
        ledger["decided_at"] = at
    return ledger


def check(ledger_path, manifest_path):
    ledger = json.loads(Path(ledger_path).read_text())
    manifest = json.loads(Path(manifest_path).read_text())
    problems = []

    if ledger.get("schema") != SCHEMA:
        problems.append(f"schema {ledger.get('schema')} ≠ {SCHEMA}")
    contract = manifest.get("contract") or {}
    if ledger.get("contract") != contract:
        problems.append("원장의 contract가 매니페스트와 다릅니다(재렌더 필요)")
    styles = load_registry()
    style_id = (ledger.get("contract") or {}).get("style_id")
    if style_id not in styles:
        problems.append(f"style_id가 명부에 없습니다: {style_id}")
    elif ledger.get("style", {}).get("name") != styles[style_id]["name"]:
        problems.append("원장의 style.name이 명부와 다릅니다")

    keys = [d.get("key") for d in ledger.get("decisions", [])]
    if sorted(keys) != sorted(set(keys)):
        problems.append("decisions에 중복 key가 있습니다")
    for entry in ledger.get("decisions", []):
        if not entry.get("choice") or not entry.get("reason"):
            problems.append(f"결정에 choice/reason이 없습니다: {entry.get('key')}")

    referenced = {r.get("name") for r in ledger.get("references", [])}
    actual = {a.get("name") for a in manifest.get("assets", [])}
    if referenced != actual:
        problems.append(f"references 불일치: 원장 {sorted(referenced)} · 매니페스트 {sorted(actual)}")

    return problems


def main():
    ap = argparse.ArgumentParser(description="결정 원장")
    ap.add_argument("--svg")
    ap.add_argument("--manifest")
    ap.add_argument("--lint", help="lint_render.py --out 결과 JSON")
    ap.add_argument("--decision", action="append", default=[], help="key=choice: 이유 (반복 가능)")
    ap.add_argument("--by", default="human", help="결정을 남긴 주체")
    ap.add_argument("--at", default=None, help="시각을 고정하려면 ISO 문자열(기본은 넣지 않음)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--check", nargs="?", const="", default=None, help="원장 검사(경로 생략 시 --out)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.check is not None:
        ledger_path = args.check or args.out
        if not ledger_path or not args.manifest:
            ap.error("--check에는 원장 경로(또는 --out)와 --manifest가 필요합니다")
        problems = check(ledger_path, args.manifest)
        for problem in problems:
            print(f"✗ {problem}")
        if problems:
            return 1
        print("원장 정합 (contract 일치 · style_id 명부 존재 · references 일치)")
        return 0

    if not args.svg or not args.manifest:
        ap.error("--svg와 --manifest가 필요합니다")

    lint_payload = json.loads(Path(args.lint).read_text()) if args.lint else None
    ledger = build(
        args.svg,
        args.manifest,
        lint_payload,
        [parse_decision(raw) for raw in args.decision],
        args.by,
        args.at,
    )
    out = Path(args.out or Path(args.manifest).with_suffix("").with_suffix(".decisions.json"))
    out.write_text(json.dumps(ledger, indent=4, ensure_ascii=False) + "\n")
    if args.json:
        print(json.dumps(ledger, indent=4, ensure_ascii=False))
    else:
        print(f"원장 저장: {out} (결정 {len(ledger['decisions'])}건 · 자산 {len(ledger['references'])}건)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
