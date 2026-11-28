#!/usr/bin/env python3
"""목업 렌더 — 라벨 아트를 정면·측면 패널로 배치한다(플랫 2패널).

원근 합성(파우치·박스 형태에 앉히기)은 별도 단계다. 여기서는 **평면 목업**만 만든다:
라벨 SVG를 정면 패널로, 같은 아트의 오른쪽 끝을 측면 패널로 잘라 나란히 놓고
종이 그림자와 배경을 얹는다.

사용::

    render_mockup.py --spec pkg.yaml --label out/pkg/label.svg --out out/mockup
    render_mockup.py --spec pkg.yaml --label … --check     # 조판만 검사
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from render_label import SpecError, load_spec  # noqa: E402

CHROME_CANDIDATES = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")
MM = 96 / 25.4


def find_chrome():
    for name in CHROME_CANDIDATES:
        path = __import__("shutil").which(name)
        if path:
            return path
    raise SystemExit("chromium not found (PNG 목업에는 필요)")


def svg_geometry(text):
    w = float(re.search(r'\bwidth="([\d.]+)"', text).group(1))
    h = float(re.search(r'\bheight="([\d.]+)"', text).group(1))
    return w, h


def label_inner(text, keep_guides=False):
    """바깥 <svg> 태그를 떼고 안쪽만 돌려준다. 목업에서는 전개도·접힘선을 뺀다."""
    match = re.search(r"<svg\b[^>]*>", text)
    body = text[match.end() :]
    body = re.sub(r"</svg>\s*$", "", body)
    if not keep_guides:
        body = re.sub(r'<g id="dieline"[^>]*>.*?</g>', "", body, flags=re.S)
        body = re.sub(r'<g id="fold"[^>]*>.*?</g>', "", body, flags=re.S)
    return body


def compose(label_svg, spec):
    """정면 + 측면 패널 목업 SVG."""
    label_w, label_h = svg_geometry(label_svg)
    inner = label_inner(label_svg)

    pad, gap = 80, 56
    front_w = 700
    front_h = front_w * label_h / label_w
    depth_mm = float(spec.get("depth_mm") or 30)
    side_w = max(80, min(front_w * 0.4, depth_mm * (front_w / (label_w / MM))))

    bg = (spec.get("colors") or {}).get("paper", "#fbf9f5")
    ink = (spec.get("colors") or {}).get("ink", "#161616")
    canvas_w = pad * 2 + front_w + gap + side_w
    canvas_h = pad * 2 + front_h + 92

    # 측면: 두께를 표현하는 띠. 브랜드 색 그라디언트 + 세로 워드마크
    calm = (spec.get("colors") or {}).get("calm") or (spec.get("colors") or {}).get("accent", "#1f4536")

    def panel(x, y, w, h, clip_id):
        return (
            f"<defs><clipPath id='{clip_id}'><rect x='{x}' y='{y}' width='{w}' height='{h}' rx='6'/></clipPath></defs>"
            f"<g clip-path='url(#{clip_id})'>"
            f"<svg x='{x}' y='{y}' width='{w}' height='{h}' viewBox='0 0 {label_w} {label_h}' "
            f"preserveAspectRatio='none'>{inner}</svg></g>"
        )

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{canvas_w:.0f}" height="{canvas_h:.0f}" viewBox="0 0 {canvas_w:.0f} {canvas_h:.0f}">',
        f'<rect width="{canvas_w:.0f}" height="{canvas_h:.0f}" fill="{bg}"/>',
        # 바닥 그림자
        f"<defs><linearGradient id='edge' x1='0' y1='0' x2='1' y2='0'>"
        f"<stop offset='0' stop-color='{calm}' stop-opacity='0.95'/>"
        f"<stop offset='1' stop-color='{calm}' stop-opacity='0.65'/></linearGradient></defs>",
        "<defs><filter id='soft' x='-20%' y='-20%' width='140%' height='160%'>"
        "<feDropShadow dx='0' dy='18' stdDeviation='18' flood-color='#000000' flood-opacity='0.18'/></filter></defs>",
        "<g filter='url(#soft)'>",
        panel(pad, pad, front_w, front_h, "front"),
        f"<rect x='{pad + front_w + gap}' y='{pad}' width='{side_w}' height='{front_h}' rx='6' fill='url(#edge)'/>"
        f"<text transform='translate({pad + front_w + gap + side_w / 2 + 6:.0f} {pad + front_h - 24:.0f}) rotate(-90)' "
        f"font-family='Archivo, sans-serif' font-size='20' font-weight='700' letter-spacing='4' "
        f"fill='{bg}' fill-opacity='0.9'>{spec.get('brand', '')}</text>",
        "</g>",
        # 얇은 테두리
        f"<rect x='{pad}' y='{pad}' width='{front_w}' height='{front_h}' rx='6' fill='none' stroke='{ink}' stroke-opacity='0.12'/>",
        f"<rect x='{pad + front_w + gap}' y='{pad}' width='{side_w}' height='{front_h}' rx='6' fill='none' stroke='{ink}' stroke-opacity='0.12'/>",
        # 캡션
        f"<text x='{pad}' y='{pad + front_h + 40}' font-family='monospace' font-size='13' fill='{ink}' "
        f"fill-opacity='0.65'>FRONT · {spec.get('product', '')}</text>",
        f"<text x='{pad + front_w + gap}' y='{pad + front_h + 40}' font-family='monospace' font-size='13' "
        f"fill='{ink}' fill-opacity='0.65'>SIDE · {depth_mm:.0f}mm</text>",
        f"<text x='{canvas_w - pad}' y='{canvas_h - 26}' font-family='monospace' font-size='11' fill='{ink}' "
        f"fill-opacity='0.35' text-anchor='end'>{spec.get('brand', '')} · {spec.get('net', '')}</text>",
        "</svg>",
    ]
    return "".join(parts), canvas_w, canvas_h


def render_png(chrome, svg_text, w, h, out_png, scale):
    html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
html, body {{ margin: 0; padding: 0; background: #ffffff; }}
svg {{ display: block; }}
</style></head><body>{svg_text}</body></html>"""
    out_png.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tmp-mockup-", dir=str(out_png.parent)) as tmp:
        page = Path(tmp) / "mockup.html"
        page.write_text(html)
        subprocess.run(
            [
                chrome,
                "--headless",
                "--no-sandbox",
                "--disable-gpu",
                "--hide-scrollbars",
                f"--force-device-scale-factor={scale}",
                f"--screenshot={out_png.resolve()}",
                f"--window-size={w:.0f},{h:.0f}",
                page.resolve().as_uri(),
            ],
            capture_output=True,
            check=True,
        )


def main():
    ap = argparse.ArgumentParser(description="목업 렌더(정면·측면 플랫)")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--label", required=True, help="render_label이 만든 SVG")
    ap.add_argument("--out", default="out/mockup")
    ap.add_argument("--name", default=None)
    ap.add_argument("--scale", type=float, default=2.0)
    ap.add_argument("--check", action="store_true", help="조판만(렌더 없이)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        spec = load_spec(args.spec)
    except SpecError as exc:
        raise SystemExit(f"스펙 오류: {exc}") from exc

    label_path = Path(args.label)
    if not label_path.is_file():
        raise SystemExit(f"라벨 SVG가 없습니다: {label_path}")

    name = args.name or re.sub(r"[^a-z0-9]+", "-", spec["brand"].lower()).strip("-")
    svg_text, w, h = compose(label_path.read_text(), spec)

    manifest = {
        "brand": spec["brand"],
        "product": spec.get("product", ""),
        "mockup": f"{name}-mockup@2x.png",
        "canvas": [round(w), round(h)],
        "scale": args.scale,
        "assets": ["front", "side"],
        "sha256_svg": hashlib.sha256(svg_text.encode()).hexdigest(),
    }

    if args.check:
        print(f"{name}: {w:.0f}×{h:.0f} · front+side 조판 ok")
        return 0

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}-mockup.svg").write_text(svg_text)
    render_png(find_chrome(), svg_text, w, h, out / f"{name}-mockup@{int(args.scale)}x.png", args.scale)
    manifest["file"] = f"{name}-mockup@{int(args.scale)}x.png"
    manifest["sha256_png"] = hashlib.sha256((out / manifest["file"]).read_bytes()).hexdigest()
    (out / f"{name}-mockup.manifest.json").write_text(json.dumps(manifest, indent=4, ensure_ascii=False) + "\n")

    if args.json:
        print(json.dumps(manifest, ensure_ascii=False))
    else:
        print(f"{name}: {w:.0f}×{h:.0f} · {manifest['file']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
