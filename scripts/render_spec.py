#!/usr/bin/env python3
"""규격 도해 — 클리어 스페이스·작도·최소 크기(ASSET-10).

lockup 스펙(심볼·색·`clearspace`·`minimum`)을 그대로 받아 세 장의 도해를 만든다.
규격: `docs/IDENTITY_DELIVERY.md` 4절.

| 파일 | 내용 |
| --- | --- |
| `clearspace.svg` | 심볼 높이 기준 여백 그리드 + 치수 표기 |
| `construction.svg` | 12u 그리드·중심축·대각선·내접원 |
| `minimum-size.svg` | 인쇄 15mm / 화면 24px 최소 크기 예시 |

사용::

    render_spec.py --spec test_data/identity/lockup.json --out out/spec
    render_spec.py --spec … --check          # 검사만
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from render_lockup import SpecError, load_spec, load_symbol, symbol_svg  # noqa: E402

W, H = 1000, 760
MARGIN = 64
MONO = "JetBrains Mono, monospace"
DISPLAY = "Archivo, sans-serif"


def head(spec, title, subtitle, ink, accent):
    return [
        f'<rect id="sheet" width="{W}" height="{H}" fill="{spec["backgrounds"]["light"]}"/>',
        f'<text x="{MARGIN}" y="76" font-family="{DISPLAY}" font-size="30" font-weight="700" '
        f'letter-spacing="0.04em" fill="{ink}">{spec["brand"]}</text>',
        f'<text x="{MARGIN}" y="102" font-family="{MONO}" font-size="12" letter-spacing="0.12em" '
        f'fill="{accent}">{title} — {spec.get("version", "v1")}</text>',
        f'<line x1="{MARGIN}" y1="124" x2="{W - MARGIN}" y2="124" stroke="{ink}" stroke-width="2"/>',
        f'<text x="{MARGIN}" y="{H - 52}" font-family="{MONO}" font-size="11" fill="{ink}" fill-opacity="0.7">{subtitle}</text>',
    ]


def dim_h(x1, x2, y, label, ink):
    """가로 치수선."""
    return [
        f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{ink}" stroke-width="1"/>',
        f'<line x1="{x1}" y1="{y - 5}" x2="{x1}" y2="{y + 5}" stroke="{ink}" stroke-width="1"/>',
        f'<line x1="{x2}" y1="{y - 5}" x2="{x2}" y2="{y + 5}" stroke="{ink}" stroke-width="1"/>',
        f'<text x="{(x1 + x2) / 2}" y="{y - 10}" font-family="{MONO}" font-size="11" text-anchor="middle" fill="{ink}">{label}</text>',
    ]


def dim_v(x, y1, y2, label, ink):
    return [
        f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="{ink}" stroke-width="1"/>',
        f'<line x1="{x - 5}" y1="{y1}" x2="{x + 5}" y2="{y1}" stroke="{ink}" stroke-width="1"/>',
        f'<line x1="{x - 5}" y1="{y2}" x2="{x + 5}" y2="{y2}" stroke="{ink}" stroke-width="1"/>',
        f'<text x="{x - 8}" y="{(y1 + y2) / 2}" font-family="{MONO}" font-size="11" text-anchor="end" fill="{ink}">{label}</text>',
    ]


def clearspace_metrics(spec):
    factor = float(spec["clearspace"])
    area_top, area_bottom = 170, 646
    size = min(280, (area_bottom - area_top) / (1 + 2 * factor))
    margin = size * factor
    return size, margin


def clearspace_svg(spec, body, view):
    ink, accent = spec["colors"]["ink"], spec["colors"]["accent"]
    area_top, area_bottom = 170, 646
    size, m = clearspace_metrics(spec)
    box = size + 2 * m
    box_top = area_top + ((area_bottom - area_top) - box) / 2
    x = (W - size) / 2
    y = box_top + m
    parts = head(
        spec,
        "CLEAR SPACE",
        f"심볼 높이(h) × {spec['clearspace']} = {m:.0f}px 여백. 이 안에는 어떤 요소도 넣지 않는다.",
        ink,
        accent,
    )
    parts += [
        f'<rect id="clearspace" x="{x - m:.1f}" y="{y - m:.1f}" width="{size + 2 * m:.1f}" '
        f'height="{size + 2 * m:.1f}" fill="none" stroke="{accent}" stroke-width="1.5" stroke-dasharray="8 6"/>',
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{size}" height="{size}" fill="none" stroke="{ink}" stroke-opacity="0.18" stroke-width="1"/>',
        symbol_svg(body, view, x, y, size, spec["colors"]["primary"]),
    ]
    parts += dim_v(x - m - 18, y - m, y, f"{spec['clearspace']}h", ink)
    parts += dim_v(x - m - 18, y, y + size, "h", ink)
    parts += dim_h(x, x + size, y + size + m + 26, "h", ink)
    parts += dim_h(x - m, x, y - m - 18, f"{spec['clearspace']}h", ink)
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">' + "".join(parts) + "</svg>"


def construction_svg(spec, body, view):
    ink, accent = spec["colors"]["ink"], spec["colors"]["accent"]
    size = 320
    x = (W - size) / 2
    y = 380 - size / 2 + 40
    u = size / 12
    parts = head(
        spec,
        "CONSTRUCTION",
        "12u 그리드 · 중심축 · 대각선 · 내접원. u = 심볼 높이/12.",
        ink,
        accent,
    )
    parts.append(f'<rect id="construction" x="{x}" y="{y}" width="{size}" height="{size}" fill="none"/>')
    for i in range(13):
        gx, gy = x + i * u, y + i * u
        strong = i in (0, 6, 12)
        width = 1.2 if strong else 0.6
        paint = accent if strong else ink
        parts.append(
            f'<line x1="{gx:.1f}" y1="{y}" x2="{gx:.1f}" y2="{y + size}" stroke="{paint}" '
            f'stroke-width="{width}" stroke-opacity="{0.9 if strong else 0.18}"/>'
        )
        parts.append(
            f'<line x1="{x}" y1="{gy:.1f}" x2="{x + size}" y2="{gy:.1f}" stroke="{paint}" '
            f'stroke-width="{width}" stroke-opacity="{0.9 if strong else 0.18}"/>'
        )
    parts += [
        f'<circle cx="{x + size / 2}" cy="{y + size / 2}" r="{size / 2}" fill="none" '
        f'stroke="{accent}" stroke-width="1" stroke-opacity="0.55" stroke-dasharray="4 8"/>',
        f'<circle cx="{x + size / 2}" cy="{y + size / 2}" r="{size * 0.06:.1f}" fill="{accent}"/>',
        f'<line x1="{x}" y1="{y + size}" x2="{x + size}" y2="{y}" stroke="{ink}" stroke-width="1" stroke-opacity="0.35"/>',
        symbol_svg(body, view, x, y, size, spec["colors"]["primary"]),
    ]
    parts += dim_h(x, x + u, y + size + 34, "u", ink)
    parts += dim_h(x, x + size, y + size + 62, "12u", ink)
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">' + "".join(parts) + "</svg>"


def minimum_svg(spec, body, view):
    ink, accent = spec["colors"]["ink"], spec["colors"]["accent"]
    minimum = spec["minimum"]
    # 96dpi 기준: 1mm = 3.7795px
    print_px = minimum["print_mm"] * 3.7795
    screen_px = minimum["screen_px"]
    parts = head(
        spec,
        "MINIMUM SIZE",
        f"인쇄 {minimum['print_mm']}mm / 화면 {minimum['screen_px']}px 이하로 줄이지 않는다.",
        ink,
        accent,
    )
    rows = [
        ("인쇄", f"{minimum['print_mm']}mm", print_px, 220),
        ("화면", f"{minimum['screen_px']}px", screen_px, 356),
    ]
    for label, value, size, cy in rows:
        parts += [
            f'<line x1="{MARGIN}" y1="{cy + size + 40}" x2="520" y2="{cy + size + 40}" '
            f'stroke="{ink}" stroke-opacity="0.16"/>',
            f'<text x="{MARGIN}" y="{cy - 26}" font-family="{MONO}" font-size="12" fill="{accent}">{label.upper()}</text>',
            f'<text x="{MARGIN + 72}" y="{cy - 26}" font-family="{MONO}" font-size="12" fill="{ink}" '
            f'fill-opacity="0.7">{value} — 실물 크기</text>',
            symbol_svg(body, view, MARGIN, cy, size, spec["colors"]["primary"]),
        ]
        parts += dim_h(MARGIN, MARGIN + size, cy + size + 14, value, ink)

    # 최소 미만 예시: 금지 표시
    forbidden = max(12.0, screen_px / 2)
    fy = 486
    parts += [
        f'<text x="{MARGIN}" y="{fy - 26}" font-family="{MONO}" font-size="12" fill="{accent}">미만</text>',
        f'<text x="{MARGIN + 72}" y="{fy - 26}" font-family="{MONO}" font-size="12" fill="{ink}" '
        f'fill-opacity="0.7">{forbidden:.0f}px — 사용 금지</text>',
        symbol_svg(body, view, MARGIN, fy, forbidden, spec["colors"]["primary"]),
        f'<line x1="{MARGIN - 4}" y1="{fy + forbidden + 4}" x2="{MARGIN + forbidden + 4}" y2="{fy - 4}" '
        f'stroke="{spec["colors"]["accent"]}" stroke-width="2"/>',
    ]

    # 확대 비교: 화면 최소 크기를 키워 형태 유지 여부를 확인
    zoom, zx, zy = 5, 560, 232
    parts += [
        f'<text x="{zx}" y="{zy - 30}" font-family="{MONO}" font-size="12" fill="{accent}">×{zoom} DETAIL</text>',
        f'<rect x="{zx - 20}" y="{zy - 20}" width="{screen_px * zoom + 40}" height="{screen_px * zoom + 40}" '
        f'fill="none" stroke="{ink}" stroke-opacity="0.2"/>',
        symbol_svg(body, view, zx, zy, screen_px * zoom, spec["colors"]["primary"]),
        f'<line x1="{zx}" y1="{zy + screen_px * zoom + 34}" x2="{zx + screen_px * zoom}" '
        f'y2="{zy + screen_px * zoom + 34}" stroke="{ink}" stroke-width="1"/>',
        f'<text x="{zx}" y="{zy + screen_px * zoom + 56}" font-family="{MONO}" font-size="11" fill="{ink}" '
        f'fill-opacity="0.7">최소 화면 크기에서 형태가 유지되는지 확인</text>',
        f'<text x="{zx}" y="{zy + screen_px * zoom + 76}" font-family="{MONO}" font-size="11" fill="{ink}" '
        f'fill-opacity="0.45">가는 선은 최소 0.25pt 이상</text>',
    ]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
        + "".join(parts)
        + "</svg>"
    )


def build(spec):
    body, view = load_symbol(spec["symbol"])
    size, margin = clearspace_metrics(spec)
    diagrams = {
        "clearspace": clearspace_svg(spec, body, view),
        "construction": construction_svg(spec, body, view),
        "minimum-size": minimum_svg(spec, body, view),
    }
    manifest = {
        "brand": spec["brand"],
        "version": spec.get("version", "v1"),
        "canvas": {"width": W, "height": H},
        "diagrams": [{"file": f"{name}.svg", "sha256": hashlib.sha256(text.encode()).hexdigest()} for name, text in diagrams.items()],
        "clearspace": {
            "factor": spec["clearspace"],
            "symbol_px": round(size, 1),
            "margin_px": round(margin, 1),
        },
        "minimum": spec["minimum"],
        "inputs": {"symbol": hashlib.sha256(Path(spec["symbol"]).read_bytes()).hexdigest()},
    }
    return diagrams, manifest


def main():
    ap = argparse.ArgumentParser(description="규격 도해(클리어 스페이스·작도·최소 크기)")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", default="out/spec")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        spec = load_spec(args.spec)
        diagrams, manifest = build(spec)
    except SpecError as exc:
        raise SystemExit(f"스펙 오류: {exc}") from exc

    if not args.check:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        for name, text in diagrams.items():
            (out / f"{name}.svg").write_text(text)
        (out / "spec.manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    if args.json:
        print(json.dumps({"brand": spec["brand"], "diagrams": list(diagrams)}, ensure_ascii=False))
    else:
        for name, text in diagrams.items():
            print(f"  {name:14s} {len(text):6d}B")
        print(
            f"{spec['brand']}: 클리어 스페이스 {spec['clearspace']}h · "
            f"최소 인쇄 {spec['minimum']['print_mm']}mm / 화면 {spec['minimum']['screen_px']}px"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
