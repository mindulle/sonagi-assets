#!/usr/bin/env python3
"""라벨 1종 생성 — 패키지 audit 검사용(ASSET-13).

패키지 우선 전략(WORK-29)의 첫 산출물. 실제 발주용이 아니라 규격·검사를
검증하는 기준 샘플이다. 도련·CMYK·안전여백은 `press print`가 처리하고,
이 스크립트는 재단 크기의 아트와 전개도 레이어를 만든다.

레이어 규칙(`press print --check`가 검사):
- `<g id="dieline">` 재단선 / `<g id="fold">` 접힘선 — 아트와 분리
- `<g id="barcode">` 안에 `barcode-quiet`(조용영역)와 `barcode-bars`

사용::

    render_label.py --spec test_data/package/label.json --out out/pkgsample
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

MM = 96 / 25.4  # 1mm = 3.7795px


class SpecError(Exception):
    pass


def load_spec(path):
    try:
        spec = json.loads(Path(path).read_text())
    except FileNotFoundError as exc:
        raise SpecError(f"스펙이 없습니다: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SpecError(f"스펙이 JSON이 아닙니다: {path} ({exc})") from exc
    for key in ("brand", "product", "size_mm"):
        if key not in spec:
            raise SpecError(f"필수 항목이 없습니다: {key}")
    w, h = spec["size_mm"]
    if w <= 0 or h <= 0:
        raise SpecError("size_mm은 양수여야 합니다")
    return spec


def ean_bars(digits):
    """EAN-13 근사 막대 패턴(결정론). 실제 인코딩이 아니라 배치 검사용."""
    seed = int(hashlib.sha256(digits.encode()).hexdigest()[:8], 16)
    bars = []
    x = 0
    for i in range(60):
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        width = 1 + (seed >> 16) % 3
        if i % 2 == 0:
            bars.append((x, width))
        x += width
    return bars, x


def wrap_text(text, size_px, max_width):
    """CJK 1em · 라틴 0.55em 근사로 줄바꿈."""
    lines, current, width = [], "", 0.0
    for ch in text:
        w = size_px if ord(ch) >= 0x2E80 else size_px * 0.55
        if width + w > max_width and current:
            lines.append(current)
            current, width = "", 0.0
        current += ch
        width += w
    if current:
        lines.append(current)
    return lines


def build(spec):
    trim_w, trim_h = spec["size_mm"]
    W, H = trim_w * MM, trim_h * MM
    colors = spec.get("colors") or {}
    ink = colors.get("ink", "#161616")
    paper = colors.get("paper", "#fbf9f5")
    accent = colors.get("accent", "#b4551f")
    calm = colors.get("calm", "#1f4536")
    type_family = spec.get("type_family", "Archivo, sans-serif")

    pad = 6 * MM  # 안전 여백 6mm (기준 3mm 이상)
    # 바코드를 먼저 배치하고, 남은 폭에 텍스트를 접어 넣는다
    digits = spec.get("barcode", "8800000000000")
    bars, bars_w = ean_bars(digits)
    bars_h = 14 * MM
    quiet = 4.6 * MM
    bx = W - pad - (bars_w + quiet * 2)
    by = H - pad - (bars_h + quiet * 2)
    text_w = bx - pad - 2 * MM
    parts_ing_y = pad + 92

    parts = [
        f'<rect id="page" width="{W:.1f}" height="{H:.1f}" fill="{paper}"/>',
        # 전개도·접힘선은 아트와 분리된 그룹
        f'<g id="dieline" fill="none" stroke="#ff00ff" stroke-width="0.5" stroke-dasharray="4 3">'
        f'<rect x="0.5" y="0.5" width="{W - 1:.1f}" height="{H - 1:.1f}"/></g>',
        f'<g id="fold" fill="none" stroke="#00a0ff" stroke-width="0.5" stroke-dasharray="2 4">'
        f'<line x1="{W * 0.62:.1f}" y1="0" x2="{W * 0.62:.1f}" y2="{H:.1f}"/></g>',
        # 아트
        '<g id="art">',
        f'<rect x="{pad}" y="{pad}" width="{W - 2 * pad:.1f}" height="{1.2 * MM:.1f}" fill="{calm}"/>',
        f'<text x="{pad}" y="{pad + 26:.1f}" font-family="{type_family}" font-size="20" font-weight="700" fill="{ink}">{spec["brand"]}</text>',
        f'<text x="{pad}" y="{pad + 54:.1f}" font-family="{type_family}" font-size="13" font-weight="700" fill="{ink}">{spec["product"]}</text>',
        f'<text x="{pad}" y="{pad + 74:.1f}" font-family="monospace" font-size="9" fill="{ink}" fill-opacity="0.7">{spec.get("net", "")}</text>',
    ]
    for line in wrap_text(spec.get("ingredients", ""), 8, text_w):
        parts.append(f'<text x="{pad}" y="{parts_ing_y:.1f}" font-family="monospace" font-size="8" fill="{ink}" fill-opacity="0.6">{line}</text>')
        parts_ing_y += 11

    parts += [
        '<g id="barcode">',
        f'<rect id="barcode-quiet" x="{bx:.1f}" y="{by:.1f}" width="{bars_w + quiet * 2:.1f}" height="{bars_h + quiet * 2:.1f}" fill="{paper}"/>',
        f'<g id="barcode-bars" fill="{ink}">',
    ]
    for offset, width in bars:
        parts.append(f'<rect x="{bx + quiet + offset:.1f}" y="{by + quiet:.1f}" width="{width:.1f}" height="{bars_h:.1f}"/>')
    parts += [
        "</g>",
        f'<text x="{bx + quiet + bars_w / 2:.1f}" y="{by + quiet + bars_h + 9:.1f}" font-family="monospace" '
        f'font-size="8" text-anchor="middle" fill="{ink}">{digits}</text>',
        "</g>",
        f'<text x="{W - pad:.1f}" y="{pad + 54:.1f}" font-family="monospace" font-size="8" text-anchor="end" '
        f'fill="{accent}">{spec.get("origin", "")}</text>',
        "</g>",
    ]

    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.1f}" height="{H:.1f}" viewBox="0 0 {W:.1f} {H:.1f}">' + "".join(parts) + "</svg>"
    manifest = {
        "brand": spec["brand"],
        "product": spec["product"],
        "size_mm": spec["size_mm"],
        "canvas_px": [round(W, 1), round(H, 1)],
        "layers": ["page", "dieline", "fold", "art", "barcode"],
        "barcode": {"digits": digits, "quiet_mm": 4.6, "bars": len(bars)},
        "sha256": hashlib.sha256(svg.encode()).hexdigest(),
    }
    return svg, manifest


def main():
    ap = argparse.ArgumentParser(description="라벨 1종 생성(패키지 audit 샘플)")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", default="out/pkg-sample")
    ap.add_argument("--name", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        spec = load_spec(args.spec)
        svg, manifest = build(spec)
    except SpecError as exc:
        raise SystemExit(f"스펙 오류: {exc}") from exc

    name = args.name or re.sub(r"[^a-z0-9]+", "-", spec["brand"].lower()).strip("-")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.svg").write_text(svg)
    manifest["file"] = f"{name}.svg"
    (out / f"{name}.manifest.json").write_text(json.dumps(manifest, indent=4, ensure_ascii=False) + "\n")

    if args.json:
        print(json.dumps(manifest, ensure_ascii=False))
    else:
        print(f"{name}: {spec['size_mm'][0]}×{spec['size_mm'][1]}mm · {len(manifest['layers'])}레이어")
    return 0


if __name__ == "__main__":
    sys.exit(main())
