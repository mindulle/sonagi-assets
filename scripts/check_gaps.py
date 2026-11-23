#!/usr/bin/env python3
"""블록 세로 간격 검수 — 겹침과 리듬을 SVG 좌표에서 되살려 본다.

렌더된 SVG에서 블록 그룹(`<g id="hero">` 등)의 상·하단을 좌표 속성으로 계산해
인접 블록 사이 간격을 출력한다. 렌더러 없이 결과물만 보므로 스타일·브레이크포인트
전수 검수에 쓴다(ASSET-2).

사용::

    check_gaps.py out/golden/editorial/desktop/light/golden-all-blocks.svg
    check_gaps.py out/golden/editorial --recursive --max-gap 40

종료 코드: 겹침(gap < 0)이나 허용 범위를 벗어난 간격이 있으면 1.
기본은 겹침만 본다(글자 상단은 baseline 근사라 간격에 ±0.7em 편향이 있다).

계산 방식
- text: baseline 기준. 상단 -0.72em, 하단 +0.22em로 근사한다.
- rect/image/nested <svg>: y + height.
- line: y1/y2. circle: cy ± r.
- transform이 걸린 그룹(아이콘)과 defs·clipPath는 좌표계가 달라 건너뛴다.
따라서 값은 ±5px 정도 오차를 전제로 읽는다. 0 미만이면 실제 겹침으로 본다.
"""

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

BLOCKS = (
    "header",
    "hero",
    "stats",
    "features",
    "logos",
    "quote",
    "faq",
    "table",
    "pricing",
    "gallery",
    "cta-band",
    "footer",
)
SKIP = {"defs", "clipPath", "style"}
NUM = re.compile(r"-?\d+(?:\.\d+)?")


def num(el, key, default=0.0):
    raw = el.get(key)
    if raw is None:
        return default
    found = NUM.search(raw)
    return float(found.group(0)) if found else default


def bounds(el):
    """서브트리의 (top, bottom). 좌표계가 다른 노드는 건너뛴다."""
    tag = el.tag.split("}")[-1]
    top = bottom = None

    def add(a, b):
        nonlocal top, bottom
        top = a if top is None else min(top, a)
        bottom = b if bottom is None else max(bottom, b)

    if tag == "text":
        size = num(el, "font-size", 16.0)
        lines = max(1, (el.text or "").count("\n") + 1)
        y = num(el, "y")
        add(y - 0.72 * size, y + 0.22 * size + (lines - 1) * size * 1.2)
    elif tag in ("rect", "image"):
        if (el.get("height") or "").strip() in ("100%", "auto"):
            return None
        add(num(el, "y"), num(el, "y") + num(el, "height"))
    elif tag == "svg":
        add(num(el, "y"), num(el, "y") + num(el, "height"))
        return None if top is None else (top, bottom)
    elif tag == "line":
        add(min(num(el, "y1"), num(el, "y2")), max(num(el, "y1"), num(el, "y2")))
    elif tag == "circle":
        add(num(el, "cy") - num(el, "r"), num(el, "cy") + num(el, "r"))
    elif tag in SKIP or el.get("transform"):
        return None

    for child in el:
        got = bounds(child)
        if got:
            add(*got)
    return None if top is None else (top, bottom)


def measure(path):
    root = ET.parse(path).getroot()
    rows = []
    for child in root:
        ident = child.get("id")
        if ident in BLOCKS:
            got = bounds(child)
            if got:
                rows.append((ident, got[0], got[1]))
    rows.sort(key=lambda r: r[1])
    return rows


def report(path, max_gap):
    rows = measure(path)
    problems = []
    print(f"{path}")
    print(f"  {'block':12s} {'top':>8s} {'bottom':>8s} {'gap':>7s}")
    for i, (ident, top, bottom) in enumerate(rows):
        # header는 고정 프레임이라 다음 블록과의 간격을 판정하지 않는다
        gap = rows[i + 1][1] - bottom if i + 1 < len(rows) and ident != "header" else None
        mark = ""
        if gap is not None:
            if gap < 0:
                mark = "  OVERLAP"
                problems.append(f"{ident}: 겹침 {gap:.1f}px")
            elif max_gap and gap > max_gap:
                mark = "  wide"
                problems.append(f"{ident}: 간격 {gap:.1f}px (>{max_gap})")
        shown = "-" if gap is None else f"{gap:.1f}"
        print(f"  {ident:12s} {top:8.1f} {bottom:8.1f} {shown:>7s}{mark}")
    return problems


def main():
    ap = argparse.ArgumentParser(description="블록 세로 간격 검수")
    ap.add_argument("target", help="SVG 파일 또는 폴더")
    ap.add_argument("--recursive", action="store_true", help="폴더 아래 SVG 전부")
    ap.add_argument("--max-gap", type=float, default=0.0, help="허용 최대 간격(px). 0이면 겹침만 본다")
    args = ap.parse_args()

    target = Path(args.target)
    if target.is_dir():
        pattern = "**/*.svg" if args.recursive else "*.svg"
        files = sorted(target.glob(pattern))
    else:
        files = [target]
    if not files:
        raise SystemExit(f"SVG가 없습니다: {target}")

    failures = 0
    for path in files:
        problems = report(path, args.max_gap)
        if problems:
            failures += 1
            for line in problems:
                print(f"  ! {line}")
        print()

    print(f"검수 {len(files)}개 · 문제 {failures}개")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
