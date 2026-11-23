#!/usr/bin/env python3
"""렌더 산출물 L1 기계 판정 — 눈이 아니라 자로 재는 크리틱.

`visual_consistency_graph`는 LLM에게 점수를 묻는다. 점수는 같은 SVG에도
65~85를 오가고, 룰을 바꿨을 때 "좋아졌다"와 "표류했다"를 구분하지 못한다.
이 린터는 그 앞단의 **결정론 게이트**다. LLM 없이 SVG 좌표와 매니페스트만 읽는다.

판정 대상(룰은 `rules/ruleset.json`):

| 룰               | 무엇을 재나                                  |
| ---------------- | -------------------------------------------- |
| `canvas.size`    | 100×100 기본값에 찌그러진 캔버스             |
| `canvas.squash`  | 높이 0~8px로 눌린 블록                       |
| `block.overlap`  | 인접 블록 겹침                               |
| `layer.required` | `<g id>` 레이어 생존(피그마 왕복 전제)       |
| `text.contrast`  | 텍스트 vs 배경/표면 WCAG 대비                |
| `text.overflow`  | 캔버스 오른쪽 경계를 넘는 텍스트             |
| `license.scope`  | blocked 자산 · license_ok=false              |
| `contract.present` / `.stale` | 계약 헤더 4칸과 룰셋 최신도     |

사용::

    lint_render.py --svg out/x.svg --manifest out/x.manifest.json --tokens tokens/semantic.json
    lint_render.py --dir out/x --json
    lint_render.py --dir out/golden --recursive --quiet

종료 코드: FAIL이 있으면 1, 아니면 0. `--strict`면 WARN도 1.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_gaps import BLOCKS, bounds  # noqa: E402
from contract import FIELDS, RULESET, ruleset_version  # noqa: E402

NUM = re.compile(r"-?\d+(?:\.\d+)?")
HEX = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
SEVERITY_RANK = {"pass": 0, "warn": 1, "fail": 2}


def num(el, key, default=0.0):
    raw = el.get(key)
    if raw is None:
        return default
    found = NUM.search(raw)
    return float(found.group(0)) if found else default


def local(tag):
    return tag.split("}")[-1]


def hex_rgb(value):
    if not value or not HEX.match(value.strip()):
        return None
    raw = value.strip()[1:]
    if len(raw) == 3:
        raw = "".join(c * 2 for c in raw)
    return tuple(int(raw[i : i + 2], 16) / 255 for i in (0, 2, 4))


def luminance(rgb):
    def channel(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def text_width(text, size):
    """글자폭 근사 — 한글 1.0em, 숫자/대문자 0.6em, 나머지 0.52em."""
    total = 0.0
    for ch in text:
        if ch == " ":
            total += 0.26
        elif ord(ch) > 0x2E80:
            total += 1.0
        elif ch in "iljI.,:;'|!":
            total += 0.28
        elif ch.isupper() or ch.isdigit():
            total += 0.6
        else:
            total += 0.52
    return total * size


class Lint:
    def __init__(self, ruleset):
        self.version = ruleset["version"]
        self.rules = {r["id"]: r for r in ruleset["rules"]}
        self.findings = []

    def add(self, rule_id, detail, count=1, severity=None):
        rule = self.rules[rule_id]
        self.findings.append(
            {
                "rule": rule_id,
                "severity": severity or rule["severity"],
                "detail": detail,
                "count": count,
            }
        )

    def param(self, rule_id, key, default=None):
        return self.rules.get(rule_id, {}).get(key, default)


def collect_text(root):
    """(text, size, x, anchor, fill, letter-spacing, local_fills).

    `local_fills`는 텍스트가 놓인 그룹(`<g id>`) 안의 rect 채우기다. 버튼 글자는
    캔버스 배경이 아니라 버튼 면 위에 있으므로, 대비 계산은 둘 다 후보로 둔다.
    """
    out = []

    def rect_fills(el, into):
        if local(el.tag) == "rect":
            fill = el.get("fill")
            if fill and HEX.match(fill.strip()):
                into.append(fill)

    def walk(el, fill=None, skip=False, group_fills=None):
        tag = local(el.tag)
        if tag in ("defs", "clipPath", "pattern", "style"):
            skip = True
        if tag == "g" and el.get("id"):
            group_fills = []
            for child in el.iter():
                rect_fills(child, group_fills)
        current = el.get("fill") or fill
        if tag == "text" and not skip:
            out.append(
                (
                    "".join(el.itertext()).strip(),
                    num(el, "font-size", 16.0),
                    num(el, "x", 0.0),
                    el.get("text-anchor", "start"),
                    current,
                    num(el, "letter-spacing", 0.0),
                    list(group_fills or []),
                )
            )
        for child in el:
            walk(child, current, skip, group_fills)

    walk(root)
    return out


def background_fill(root):
    for el in root.iter():
        if local(el.tag) == "rect" and el.get("id") == "background":
            return el.get("fill")
    return None


def lint(svg_path, manifest_path=None, tokens_path=None, ruleset=None):
    ruleset = ruleset or json.loads(RULESET.read_text())
    lint_state = Lint(ruleset)
    svg_path = Path(svg_path)
    root = ET.parse(svg_path).getroot()
    manifest = {}
    if manifest_path and Path(manifest_path).is_file():
        manifest = json.loads(Path(manifest_path).read_text())

    # 1. 캔버스
    width, height = num(root, "width"), num(root, "height")
    min_w = lint_state.param("canvas.size", "min_width")
    min_h = lint_state.param("canvas.size", "min_height")
    if width < min_w or height < min_h:
        lint_state.add("canvas.size", f"캔버스 {width:.0f}×{height:.0f} (최소 {min_w}×{min_h})")

    # 2. 블록 눌림 / 3. 겹침
    min_h_block = lint_state.param("canvas.squash", "min_block_height")
    rows = []
    for el in root:
        ident = el.get("id")
        if ident not in BLOCKS:
            continue
        got = bounds(el)
        if got is None:
            lint_state.add("canvas.squash", f"{ident}: 높이 0")
            continue
        top, bottom = got
        if bottom - top < min_h_block:
            lint_state.add("canvas.squash", f"{ident}: 높이 {bottom - top:.0f}px")
        rows.append((ident, top, bottom))
    rows.sort(key=lambda r: r[1])
    tolerance = lint_state.param("block.overlap", "tolerance")
    for i, (ident, _, bottom) in enumerate(rows):
        if i + 1 >= len(rows) or ident == "header":
            continue
        gap = rows[i + 1][1] - bottom
        if gap < -tolerance:
            lint_state.add("block.overlap", f"{ident} → {rows[i + 1][0]}: {gap:.1f}px")

    # 4. 레이어 — SVG 실물을 기준으로 본다. 매니페스트는 교차 확인용.
    required = lint_state.param("layer.required", "required", [])
    svg_layers = re.findall(r'<g id="([^"]+)"', svg_path.read_text())
    missing = [layer for layer in required if layer not in svg_layers]
    if missing:
        lint_state.add("layer.required", f"레이어 없음: {', '.join(missing)}")
    if len(svg_layers) < lint_state.param("layer.required", "min_layers", 0):
        lint_state.add("layer.required", f"레이어 {len(svg_layers)}개 (최소 {lint_state.param('layer.required', 'min_layers')})")
    manifest_layers = manifest.get("layers") or []
    if manifest_layers and manifest_layers != svg_layers:
        lint_state.add("layer.required", "매니페스트 layers가 SVG와 다릅니다")

    # 5. 대비
    background = hex_rgb(background_fill(root) or "")
    surface = None
    if tokens_path and manifest.get("theme"):
        try:
            tokens = json.loads(Path(tokens_path).read_text())
            surface = hex_rgb(tokens.get(manifest["theme"], {}).get("surface", ""))
        except (OSError, json.JSONDecodeError, AttributeError):
            surface = None
    body_min = lint_state.param("text.contrast", "body")
    large_min = lint_state.param("text.contrast", "large")
    large_px = lint_state.param("text.contrast", "large_px")
    floor = lint_state.param("text.contrast", "floor", 3.0)
    flunks, warnings = [], []
    for content, size, _, _, fill, _, local_fills in collect_text(root):
        rgb = hex_rgb(fill or "")
        if rgb is None or not content:
            continue
        bases = [b for b in (background, surface) if b is not None]
        bases += [b for b in (hex_rgb(f) for f in local_fills) if b is not None]
        if not bases:
            continue
        ratio = max(contrast(rgb, base) for base in bases)
        threshold = large_min if size >= large_px else body_min
        entry = f"'{content[:24]}' {ratio:.2f}:1 < {threshold} (size {size:.0f})"
        if ratio < floor:
            flunks.append(entry)
        elif ratio < threshold:
            warnings.append(entry)
    if flunks:
        lint_state.add("text.contrast", "; ".join(flunks[:4]), count=len(flunks), severity="fail")
    if warnings:
        lint_state.add("text.contrast", "; ".join(warnings[:4]), count=len(warnings), severity="warn")

    # 6. 오버플로
    margin = lint_state.param("text.overflow", "margin", 0)
    overflow = []
    for content, size, x, anchor, _, spacing, _ in collect_text(root):
        if not content:
            continue
        w = text_width(content, size) + spacing * max(0, len(content) - 1)
        start = x - w / 2 if anchor == "middle" else (x - w if anchor == "end" else x)
        if start + w > width - margin:
            overflow.append(f"'{content[:20]}' +{start + w - width:.0f}px")
    if overflow:
        lint_state.add("text.overflow", "; ".join(overflow[:4]), count=len(overflow))

    # 7. 라이선스
    if manifest:
        blocked = [a.get("name") for a in manifest.get("assets", []) if a.get("scope") == "blocked"]
        if blocked or manifest.get("license_ok") is False:
            lint_state.add("license.scope", f"blocked: {', '.join(map(str, blocked)) or 'license_ok=false'}")

    # 8. 계약 헤더
    contract = manifest.get("contract") or {}
    absent = [field for field in FIELDS if not contract.get(field)]
    if manifest and absent:
        lint_state.add("contract.present", f"없음: {', '.join(absent)}")
    if contract.get("ruleset_version") and contract["ruleset_version"] != lint_state.version:
        lint_state.add(
            "contract.stale",
            f"ruleset {contract['ruleset_version']} → 현재 {lint_state.version}",
        )

    verdict = "pass"
    for finding in lint_state.findings:
        if SEVERITY_RANK[finding["severity"]] > SEVERITY_RANK[verdict]:
            verdict = finding["severity"]

    return {
        "svg": svg_path.name,
        "ruleset_version": lint_state.version,
        "verdict": verdict,
        "findings": lint_state.findings,
        "counts": {
            "fail": sum(1 for f in lint_state.findings if f["severity"] == "fail"),
            "warn": sum(1 for f in lint_state.findings if f["severity"] == "warn"),
        },
        "contract": contract,
    }


def render_dir(directory, recursive):
    directory = Path(directory)
    pattern = "**/*.svg" if recursive else "*.svg"
    for svg in sorted(directory.glob(pattern)):
        manifest = svg.with_name(svg.name.replace(".svg", ".manifest.json"))
        if not manifest.is_file():
            # `<name>.svg` 옆의 `<name>.manifest.json`
            manifest = None
        yield svg, manifest


def main():
    ap = argparse.ArgumentParser(description="렌더 산출물 L1 기계 판정")
    ap.add_argument("--svg")
    ap.add_argument("--manifest")
    ap.add_argument("--dir")
    ap.add_argument("--tokens", default=None, help="대비 계산용 semantic.json")
    ap.add_argument("--recursive", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", help="판정 JSON 저장 경로")
    ap.add_argument("--strict", action="store_true", help="WARN도 실패로 본다")
    ap.add_argument("--quiet", action="store_true", help="PASS는 출력하지 않는다")
    args = ap.parse_args()

    if not args.svg and not args.dir:
        ap.error("--svg 또는 --dir 중 하나가 필요합니다")

    targets = [(Path(args.svg), Path(args.manifest) if args.manifest else None)] if args.svg else list(render_dir(args.dir, args.recursive))
    if not targets:
        raise SystemExit(f"SVG가 없습니다: {args.dir}")

    results = [lint(svg, manifest, args.tokens) for svg, manifest in targets]
    worst = "pass"
    for result in results:
        if SEVERITY_RANK[result["verdict"]] > SEVERITY_RANK[worst]:
            worst = result["verdict"]
        if args.quiet and result["verdict"] == "pass":
            continue
        if args.json:
            continue
        mark = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}[result["verdict"]]
        print(f"{mark}  {result['svg']}  (ruleset {result['ruleset_version']})")
        for finding in result["findings"]:
            print(f"      [{finding['severity']}] {finding['rule']}: {finding['detail']}")

    if args.json:
        payload = results[0] if len(results) == 1 else results
        print(json.dumps(payload, indent=4, ensure_ascii=False))
    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=4, ensure_ascii=False) + "\n")

    fails = sum(r["counts"]["fail"] for r in results)
    warns = sum(r["counts"]["warn"] for r in results)
    if not args.json:
        print(
            f"\n{len(results)}건 · fail {fails} · warn {warns} · ruleset {ruleset_version()}",
            file=sys.stderr,
        )
    if worst == "fail" or (args.strict and worst == "warn"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
