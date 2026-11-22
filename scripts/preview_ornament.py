#!/usr/bin/env python3
"""장식 모티프 하나(또는 전체)를 미리보기로 렌더한다.

`styles/ornaments.json`의 좌표를 고칠 때 눈으로 바로 확인하기 위한 도구다.
렌더 본체(render_recipe.py)와 독립적으로 동작한다.

사용::

    preview_ornament.py --motif floral --frame plain
    preview_ornament.py --sheet --png
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ornament_data  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CHROME_CANDIDATES = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")


def find_chrome():
    for name in CHROME_CANDIDATES:
        path = shutil.which(name)
        if path:
            return path
    return None


def divider_svg(motif, x1, x2, y, width, accent, weight):
    variables = {"x1": x1, "x2": x2, "cx": (x1 + x2) / 2, "y": y, "weight": weight, "accent": accent}
    return ornament_data.draw("divider", motif, variables)


def frame_svg(name, W, H, inset, accent, weight):
    variables = {"W": W, "H": H, "i": inset, "weight": weight, "accent": accent}
    return ornament_data.draw("frame", name, variables)


def label(text, x, y, size=13, color="#6b6b6b", anchor="start"):
    return f'<text x="{x}" y="{y}" font-family="DejaVu Sans Mono, monospace" font-size="{size}" fill="{color}" text-anchor="{anchor}">{text}</text>'


def single(motif, frame, width, accent, bg, weight):
    height = 220
    parts = [
        f'<rect width="{width}" height="{height}" fill="{bg}"/>',
        divider_svg(motif, 60, width - 60, 110, width, accent, weight),
    ]
    if frame and frame != "none":
        parts.insert(1, frame_svg(frame, width, height, 12, accent, weight))
    parts.append(label(f"divider: {motif}" + (f"  ·  frame: {frame}" if frame else ""), 24, 32))
    parts.append(label(f"weight {weight}", width - 24, 32, anchor="end"))
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">{"".join(parts)}</svg>'


def sheet(data, width, accent, bg, weight):
    dividers = sorted(data.get("divider") or {})
    frames = sorted(data.get("frame") or {})
    pad = 28
    row = 96
    frame_box = 320
    frame_row_h = 260
    cols = max(1, (width - pad * 2 + 20) // (frame_box + 20))
    rows = (len(frames) + cols - 1) // cols
    bg_rows = ((len(data.get("background") or {}) + cols - 1) // cols) if data.get("background") else 0
    height = pad + 30 + len(dividers) * row + 30 + (bg_rows + rows) * frame_row_h + pad

    parts = [f'<rect width="{width}" height="{height}" fill="{bg}"/>']
    parts.append(label("dividers", pad, pad + 8, size=12, color="#9a9a9a"))
    y = pad + 48
    for name in dividers:
        parts.append(label(name, pad, y - 24, size=11, color="#8a8a8a"))
        parts.append(divider_svg(name, pad + 120, width - pad, y, width, accent, weight))
        y += row

    backgrounds = sorted(data.get("background") or {})
    if backgrounds:
        parts.append(label("backgrounds", pad, y + 4, size=12, color="#9a9a9a"))
        y += 24
        for index, name in enumerate(backgrounds):
            col = index % cols
            rowindex = index // cols
            x = pad + col * (frame_box + 20)
            top = y + rowindex * frame_row_h
            sample = ornament_data.draw("background", name, {"W": frame_box, "H": 200, "accent": accent, "weight": weight})
            parts.append(
                f'<g transform="translate({x} {top})">'
                + label(name, 0, 16, size=11, color="#8a8a8a")
                + '<g transform="translate(0 26)">'
                + f'<rect x="0" y="0" width="{frame_box}" height="200" fill="none" stroke="#d9d4c8"/>'
                + f'<svg x="0" y="0" width="{frame_box}" height="200">{sample}</svg>'
                + "</g></g>"
            )
        y += ((len(backgrounds) + cols - 1) // cols) * frame_row_h

    parts.append(label("frames", pad, y + 4, size=12, color="#9a9a9a"))
    y += 24
    for index, name in enumerate(frames):
        col = index % cols
        rowindex = index // cols
        x = pad + col * (frame_box + 20)
        top = y + rowindex * frame_row_h
        parts.append(
            f'<g transform="translate({x} {top})">'
            + label(name, 0, 16, size=11, color="#8a8a8a")
            + '<g transform="translate(0 26)">'
            + frame_svg(name, frame_box, 200, 8, accent, weight)
            + "</g></g>"
        )
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">{"".join(parts)}</svg>'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--motif", default=None)
    ap.add_argument("--frame", default=None)
    ap.add_argument("--sheet", action="store_true", help="모든 모티프를 한 장에 그린다")
    ap.add_argument("--data", default=str(ROOT / "styles" / "ornaments.json"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--width", type=int, default=900)
    ap.add_argument("--accent", default="#b86a04")
    ap.add_argument("--bg", default="#fbf9f5")
    ap.add_argument("--weight", type=float, default=1)
    ap.add_argument("--png", action="store_true", help="chromium으로 PNG도 만든다")
    args = ap.parse_args()

    data = ornament_data.load(Path(args.data))
    if args.sheet:
        svg = sheet(data, args.width, args.accent, args.bg, args.weight)
        name = "ornaments"
    else:
        if not args.motif:
            raise SystemExit("--motif 또는 --sheet 중 하나가 필요합니다.")
        svg = single(args.motif, args.frame, args.width, args.accent, args.bg, args.weight)
        name = f"ornament-{args.motif}" + (f"-{args.frame}" if args.frame else "")

    out = Path(args.out) if args.out else ROOT / "previews" / f"{name}.svg"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg)
    print(f"svg: {out}")

    if args.png:
        chrome = find_chrome()
        if not chrome:
            raise SystemExit("chromium을 찾지 못했습니다.")
        height = int(svg.split('height="', 1)[1].split('"', 1)[0])
        png = out.with_suffix(".png")
        page = out.with_suffix(".html")
        page.write_text(
            f'<!doctype html><html><head><meta charset="utf-8">'
            f"<style>html,body{{margin:0;background:{args.bg}}} svg{{display:block}}</style>"
            f"</head><body>{svg}</body></html>"
        )
        subprocess.run(
            [
                chrome,
                "--headless",
                "--no-sandbox",
                "--disable-gpu",
                "--hide-scrollbars",
                "--force-device-scale-factor=2",
                f"--screenshot={png.resolve()}",
                f"--window-size={args.width},{height}",
                page.resolve().as_uri(),
            ],
            check=True,
            capture_output=True,
        )
        print(f"png: {png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
