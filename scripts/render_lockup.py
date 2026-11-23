#!/usr/bin/env python3
"""락업·변형 시트 — 로고 원본을 받아 규격 시트를 SVG로 전개한다(ASSET-9).

press는 **로고를 만들지 않는다.** 이미 만든 심볼 벡터와 워드마크를 받아
락업(가로·세로·심볼) × 변형(풀컬러·흑백·반전·단색) 매트릭스로 배치하고,
각 조합의 실제 배경 대비를 계산해 검사한다.

규격: `docs/IDENTITY_DELIVERY.md` 3절(락업·변형), 8절(파일명·매니페스트).

사용::

    render_lockup.py --spec test_data/identity/lockup.json --out out/lockup --name sonagi-lockup
    render_lockup.py --spec … --check          # 파일을 쓰지 않고 검사만
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

LOCKUPS = ("horizontal", "stacked", "symbol")
VARIANTS = ("color", "mono", "inverse", "one-color")
MIN_CONTRAST = 4.5

# 규격 기본값(IDENTITY_DELIVERY 4절)
DEFAULTS = {
    "clearspace": 0.5,
    "minimum": {"print_mm": 15, "screen_px": 24},
    "backgrounds": {"light": "#fbf9f5", "dark": "#12100e"},
    "colors": {"primary": "#1f4536", "ink": "#161616", "paper": "#fbf9f5", "accent": "#b4551f"},
}

SHEET_W = 1296
MARGIN = 64
CELL_W = 280
CELL_H = 220
GAP = 16


class SpecError(Exception):
    pass


def hex_to_rgb(value):
    raw = value.strip().lstrip("#")
    if len(raw) == 3:
        raw = "".join(c * 2 for c in raw)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", raw):
        raise SpecError(f"색이 아닙니다: {value}")
    return tuple(int(raw[i : i + 2], 16) for i in (0, 2, 4))


def relative_luminance(hex_color):
    def channel(c):
        c = c / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in hex_to_rgb(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = relative_luminance(a), relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_spec(path):
    try:
        spec = json.loads(Path(path).read_text())
    except FileNotFoundError as exc:
        raise SpecError(f"스펙 파일이 없습니다: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SpecError(f"스펙이 JSON이 아닙니다: {path} ({exc})") from exc

    for key in ("brand", "symbol"):
        if not spec.get(key):
            raise SpecError(f"필수 항목이 없습니다: {key}")

    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in spec.items() if k not in ("colors", "backgrounds", "minimum")})
    merged["colors"] = {**DEFAULTS["colors"], **(spec.get("colors") or {})}
    merged["backgrounds"] = {**DEFAULTS["backgrounds"], **(spec.get("backgrounds") or {})}
    merged["minimum"] = {**DEFAULTS["minimum"], **(spec.get("minimum") or {})}

    merged["lockups"] = list(spec.get("lockups") or LOCKUPS)
    merged["variants"] = list(spec.get("variants") or VARIANTS)
    unknown = [x for x in merged["lockups"] if x not in LOCKUPS]
    if unknown:
        raise SpecError(f"락업 이름이 아닙니다: {', '.join(unknown)}")
    unknown = [x for x in merged["variants"] if x not in VARIANTS]
    if unknown:
        raise SpecError(f"변형 이름이 아닙니다: {', '.join(unknown)}")
    if not merged["lockups"] or not merged["variants"]:
        raise SpecError("lockups·variants가 비었습니다")

    symbol = Path(merged["symbol"])
    if not symbol.is_file():
        raise SpecError(f"심볼 파일이 없습니다: {symbol}")
    for name, value in {**merged["colors"], **merged["backgrounds"]}.items():
        hex_to_rgb(value)  # 형식 검사
        if name not in ("primary", "ink", "paper", "accent", "light", "dark"):
            raise SpecError(f"알 수 없는 색 이름: {name}")
    return merged


def load_symbol(path):
    text = Path(path).read_text()
    match = re.search(r"<svg\b[^>]*>", text)
    if not match:
        raise SpecError(f"SVG가 아닙니다: {path}")
    open_tag = match.group(0)
    view = re.search(r'viewBox="([^"]+)"', open_tag)
    body = text[match.end() :]
    body = re.sub(r"</svg>\s*$", "", body)
    body = re.sub(r'\sid="[^"]*"', "", body)
    body = re.sub(r"<style\b.*?</style>", "", body, flags=re.S)
    return body.strip(), (view.group(1) if view else "0 0 24 24")


def recolor(body, color):
    """stroke/fill의 hex를 한 색으로 바꾼다('none'은 유지)."""
    body = re.sub(r'(stroke|fill)="(#[0-9a-fA-F]{3,8})"', rf'\1="{color}"', body)
    return re.sub(r"(stroke|fill)='(#[0-9a-fA-F]{3,8})'", rf'\1="{color}"', body)


def variant_colors(variant, spec):
    c, bg = spec["colors"], spec["backgrounds"]
    if variant == "color":
        return c["primary"], bg["light"]
    if variant == "mono":
        return c["ink"], bg["light"]
    if variant == "inverse":
        return c["paper"], bg["dark"]
    if variant == "one-color":
        return c["accent"], bg["light"]
    raise SpecError(f"변형이 아닙니다: {variant}")


def symbol_svg(body, view, x, y, size, color):
    return (
        f'<svg x="{x:.1f}" y="{y:.1f}" width="{size}" height="{size}" viewBox="{view}" '
        f'preserveAspectRatio="xMidYMid meet">{recolor(body, color)}</svg>'
    )


def wordmark_svg(text, x, y, size, color, spec, anchor="start"):
    t = spec.get("type") or {}
    family = t.get("family", "Archivo")
    weight = t.get("weight", 700)
    tracking = float(t.get("tracking", 0)) * size
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" letter-spacing="{tracking:.2f}" '
        f'text-anchor="{anchor}" fill="{color}">{text}</text>'
    )


def lockup_markup(lockup, body, view, cx, cy, color, spec):
    """락업 하나를 셀 중심에 놓는다. wordmark가 없으면 심볼만 크게."""
    word = (spec.get("wordmark") or "").strip()
    if lockup == "symbol" or not word:
        size = 96 if lockup == "symbol" else 64
        return symbol_svg(body, view, cx - size / 2, cy - size / 2, size, color)

    if lockup == "horizontal":
        symbol, mark = 64, 34
        text_w = len(word) * mark * (0.62 + float((spec.get("type") or {}).get("tracking", 0)))
        total = symbol + 18 + text_w
        left = cx - total / 2
        return symbol_svg(body, view, left, cy - symbol / 2, symbol, color) + wordmark_svg(
            word, left + symbol + 18, cy + mark * 0.35, mark, color, spec
        )

    if lockup == "stacked":
        symbol, mark = 72, 26
        return symbol_svg(body, view, cx - symbol / 2, cy - symbol / 2 - 22, symbol, color) + wordmark_svg(
            word, cx, cy + 56, mark, color, spec, anchor="middle"
        )

    raise SpecError(f"락업이 아닙니다: {lockup}")


def build(spec):
    body, view = load_symbol(spec["symbol"])
    cols, rows = len(spec["variants"]), len(spec["lockups"])
    grid_w = cols * CELL_W + (cols - 1) * GAP
    grid_h = rows * CELL_H + (rows - 1) * GAP
    W = max(SHEET_W, MARGIN * 2 + grid_w)
    top = 168
    H = top + grid_h + 132

    parts = [
        f'<rect id="sheet" width="{W}" height="{H}" fill="{spec["backgrounds"]["light"]}"/>',
        f'<text x="{MARGIN}" y="76" font-family="Archivo, sans-serif" font-size="34" font-weight="700" '
        f'letter-spacing="0.04em" fill="{spec["colors"]["ink"]}">{spec["brand"]}</text>',
        f'<text x="{MARGIN}" y="104" font-family="JetBrains Mono, monospace" font-size="12" '
        f'letter-spacing="0.12em" fill="{spec["colors"]["accent"]}">LOCKUP · VARIANT SHEET — {spec.get("version", "v1")}</text>',
        f'<line x1="{MARGIN}" y1="126" x2="{W - MARGIN}" y2="126" stroke="{spec["colors"]["ink"]}" stroke-width="2"/>',
    ]

    cells, failures = [], []
    for r, lockup in enumerate(spec["lockups"]):
        for ci, variant in enumerate(spec["variants"]):
            x = MARGIN + ci * (CELL_W + GAP)
            y = top + r * (CELL_H + GAP)
            fg, bg = variant_colors(variant, spec)
            ratio = contrast(fg, bg)
            ok = ratio >= MIN_CONTRAST
            if not ok and variant != "inverse":
                failures.append(f"{lockup}/{variant}: 대비 {ratio:.2f}:1 (<{MIN_CONTRAST})")
            elif not ok:
                failures.append(f"{lockup}/{variant}: 반전 대비 {ratio:.2f}:1 (<{MIN_CONTRAST})")
            stroke = spec["colors"]["ink"] if bg == spec["backgrounds"]["light"] else spec["colors"]["paper"]
            parts.append(
                f'<g id="cell-{lockup}-{variant}">'
                f'<rect x="{x}" y="{y}" width="{CELL_W}" height="{CELL_H}" fill="{bg}" '
                f'stroke="{spec["colors"]["ink"]}" stroke-opacity="0.18"/>'
                + lockup_markup(lockup, body, view, x + CELL_W / 2, y + CELL_H / 2 - 6, fg, spec)
                + f'<text x="{x + 14}" y="{y + 22}" font-family="JetBrains Mono, monospace" font-size="10" '
                f'letter-spacing="0.1em" fill="{stroke}" fill-opacity="0.65">{lockup.upper()} · {variant.upper()}</text>'
                + f'<text x="{x + 14}" y="{y + CELL_H - 12}" font-family="JetBrains Mono, monospace" font-size="10" '
                f'fill="{stroke}" fill-opacity="0.65">{fg} on {bg} · {ratio:.2f}:1</text>'
                "</g>"
            )
            cells.append(
                {
                    "lockup": lockup,
                    "variant": variant,
                    "fg": fg,
                    "bg": bg,
                    "contrast": round(ratio, 2),
                    "contrast_ok": ok,
                }
            )

    cs = spec["clearspace"]
    minimum = spec["minimum"]
    parts += [
        f'<line x1="{MARGIN}" y1="{H - 92}" x2="{W - MARGIN}" y2="{H - 92}" stroke="{spec["colors"]["ink"]}" stroke-width="1"/>',
        f'<text x="{MARGIN}" y="{H - 64}" font-family="JetBrains Mono, monospace" font-size="11" '
        f'fill="{spec["colors"]["ink"]}" fill-opacity="0.8">클리어 스페이스 심볼 높이 × {cs} · '
        f"최소 크기 인쇄 {minimum['print_mm']}mm / 화면 {minimum['screen_px']}px · "
        f"대비 기준 {MIN_CONTRAST}:1</text>",
        f'<text x="{MARGIN}" y="{H - 44}" font-family="JetBrains Mono, monospace" font-size="11" '
        f'fill="{spec["colors"]["ink"]}" fill-opacity="0.55">{spec.get("note", "")}</text>',
    ]

    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">' + "".join(parts) + "</svg>"
    manifest = {
        "brand": spec["brand"],
        "version": spec.get("version", "v1"),
        "canvas": {"width": W, "height": H},
        "lockups": spec["lockups"],
        "variants": spec["variants"],
        "inputs": {"spec": None, "symbol": file_hash(spec["symbol"])},
        "cells": cells,
        "checks": {"min_contrast": MIN_CONTRAST, "failures": failures, "ok": not failures},
        "clearspace": cs,
        "minimum": minimum,
    }
    return svg, manifest


SINGLE = {
    # 파일명: (락업, 색 역할, 캔버스)
    "primary-horizontal": ("horizontal", "primary", (640, 200)),
    "primary-stacked": ("stacked", "primary", (420, 380)),
    "symbol": ("symbol", "primary", (256, 256)),
    "mono-black": ("horizontal", "ink", (640, 200)),
    "mono-white": ("horizontal", "paper", (640, 200)),
    "one-color": ("horizontal", "accent", (640, 200)),
}


def single_lockup(spec, body, view, name):
    """제출용 단일 락업. 배경 없이(투명) 락업만 그린다."""
    lockup, role, (w, h) = SINGLE[name]
    color = spec["colors"][role]
    markup = lockup_markup(lockup, body, view, w / 2, h / 2, color, spec)
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">' + markup + "</svg>"


def main():
    ap = argparse.ArgumentParser(description="락업·변형 시트")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", default="out/lockup")
    ap.add_argument("--name", default=None, help="파일명(소문자·하이픈). 기본은 brand")
    ap.add_argument("--check", action="store_true", help="검사만 하고 쓰지 않는다")
    ap.add_argument("--allow-low-contrast", action="store_true")
    ap.add_argument("--lockup-dir", default=None, help="제출용 단일 락업 SVG를 쓸 폴더(01_logo)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        spec = load_spec(args.spec)
        svg, manifest = build(spec)
    except SpecError as exc:
        raise SystemExit(f"스펙 오류: {exc}") from exc

    manifest["inputs"]["spec"] = file_hash(args.spec)
    failures = manifest["checks"]["failures"]
    name = args.name or re.sub(r"[^a-z0-9]+", "-", spec["brand"].lower()).strip("-")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name or ""):
        raise SystemExit(f"파일명 규칙 위반(소문자·하이픈): {name}")

    if not args.check:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{name}.svg").write_text(svg)
        manifest["sheet"] = f"{name}.svg"
        manifest["sha256"] = hashlib.sha256(svg.encode()).hexdigest()
        (out / f"{name}.manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    if args.lockup_dir:
        body, view = load_symbol(spec["symbol"])
        target = Path(args.lockup_dir)
        target.mkdir(parents=True, exist_ok=True)
        written = {}
        for single in SINGLE:
            text = single_lockup(spec, body, view, single)
            (target / f"{single}.svg").write_text(text)
            written[f"{single}.svg"] = hashlib.sha256(text.encode()).hexdigest()
        manifest["singles"] = written
        if not args.check:
            (Path(args.out) / f"{name}.manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    if args.json:
        print(json.dumps({"name": name, "cells": len(manifest["cells"]), "checks": manifest["checks"]}, ensure_ascii=False))
    else:
        for cell in manifest["cells"]:
            mark = "✓" if cell["contrast_ok"] else "✗"
            print(f"  {mark} {cell['lockup']:10s} {cell['variant']:10s} {cell['contrast']:5.2f}:1")
        print(f"{name}: {len(manifest['cells'])}셀 · 대비 실패 {len(failures)}건")

    if failures and not args.allow_low_contrast:
        for line in failures:
            print(f"  ! {line}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
