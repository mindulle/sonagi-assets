#!/usr/bin/env python3
"""렌더된 SVG를 납품 포맷(PDF·PNG·WebP)으로 내보낸다.

- PDF: 여러 SVG를 한 파일의 페이지로 묶는다(Chromium 인쇄, 폰트 임베드)
- PNG: 배율 지정(기본 2x)
- WebP: PNG에서 변환(Pillow)
- 매니페스트의 자산 출처를 검사해 상용(commercial) 자산이 있으면 중단

전제: Chromium(또는 chromium-browser)과 Pillow. 폰트는 `--fonts-dir`의
`fonts.css`(@font-face 모음)로 주입한다.

사용::

    export_recipe.py --src out/ --pattern '*.svg' --out dist/ \\
        --formats pdf,png,webp --scale 2 --fonts-dir ~/brief/fonts
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CHROME_CANDIDATES = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")


def find_chrome():
    for name in CHROME_CANDIDATES:
        path = shutil.which(name)
        if path:
            return path
    raise SystemExit("chromium not found")


def svg_size(text):
    """SVG 캔버스 크기(px). 소수 폭을 쓰는 인쇄물(라벨 등)도 받는다."""
    w = round(float(re.search(r'\bwidth="([\d.]+)"', text).group(1)))
    h = round(float(re.search(r'\bheight="([\d.]+)"', text).group(1)))
    return w, h


def resolve_font_urls(css_text, base_dir):
    """@font-face의 상대 url을 절대 file URI로 바꾼다(임시 HTML에서도 로드되게)."""

    def repl(m):
        raw = m.group(1)
        if raw.startswith(("http://", "https://", "file://", "data:")):
            return m.group(0)
        path = (Path(base_dir) / raw).resolve()
        return f"url('{path.as_uri()}')"

    return re.sub(r"url\('([^']+)'\)", repl, css_text)


def check_assets(svg_path, allow_freeware=True):
    """같은 폴더의 manifest에서 자산 출처를 확인한다."""
    manifest = svg_path.with_suffix(".manifest.json")
    if not manifest.is_file():
        return {"checked": False}
    data = json.loads(manifest.read_text())
    bad = [a for a in data.get("assets", []) if a.get("origin") == "commercial"]
    warn = [a for a in data.get("assets", []) if a.get("origin") == "freeware"]
    if bad:
        raise SystemExit(f"commercial asset in {svg_path.name}: {[a['name'] for a in bad]}")
    if warn and not allow_freeware:
        raise SystemExit(f"freeware asset in {svg_path.name}: {[a['name'] for a in warn]}")
    return {"checked": True, "assets": len(data.get("assets", [])), "freeware": len(warn)}


def page_html(svg, fonts_css, w, h, first):
    break_css = "" if first else "page-break-before: always;"
    return f'<section class="page" style="{break_css}">{svg}</section>'


def build_html(svgs, fonts_css):
    pages = []
    size_css = []
    for i, (svg, (w, h)) in enumerate(svgs):
        pages.append(page_html(svg, fonts_css, w, h, i == 0))
        size_css.append(f"@page {{ size: {w}px {h}px; margin: 0; }}")
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
{fonts_css}
html, body {{ margin: 0; padding: 0; background: #fff; }}
section.page {{ width: 100%; }}
section.page svg {{ display: block; width: 100%; height: auto; }}
{chr(10).join(size_css)}
</style></head><body>{"".join(pages)}</body></html>"""


def run(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if os.environ.get("EXPORT_DEBUG"):
        print("CMD", cmd)
        print("OUT", proc.stdout[-300:], "ERR", proc.stderr[-300:])
    if proc.returncode != 0:
        print(proc.stdout, proc.stderr)
        raise SystemExit(f"command failed: {' '.join(cmd)}")


def absolutize_refs(text, base_dir):
    """상대 경로 래스터 참조를 절대 file URI로 바꾼다.

    link 모드 SVG는 `assets/<hash>.jpg`를 상대 경로로 가리킨다. Chromium은
    임시 HTML 폴더를 기준으로 상대 경로를 풀기 때문에 그대로 두면 이미지가 빠진다.
    """
    base = Path(base_dir).resolve()
    pattern = re.compile(r'(xlink:href|href)="([^"]+)"')

    def repl(m):
        attr, ref = m.group(1), m.group(2)
        if ref.startswith(("data:", "http://", "https://", "file:", "#")):
            return m.group(0)
        return f'{attr}="{(base / ref).as_uri()}"'

    return pattern.sub(repl, text)


def export_pdf(chrome, svgs, fonts_css, out_pdf):
    html = build_html(svgs, fonts_css)
    # snap chromium은 /tmp을 볼 수 없다 → 출력 폴더 옆에 임시 페이지를 만든다
    with tempfile.TemporaryDirectory(prefix="tmp-export-", dir=str(Path(out_pdf).parent)) as tmp:
        page = Path(tmp) / "print.html"
        page.write_text(html)
        run(
            [
                chrome,
                "--headless",
                "--no-sandbox",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--print-to-pdf={Path(out_pdf).resolve()}",
                page.resolve().as_uri(),
            ]
        )
    # Chromium이 0으로 끝나도 파일을 안 만드는 경우가 있다(스냅 격리: /tmp 쓰기 차단).
    # 여기서 끊지 않으면 pypdf가 FileNotFoundError 트레이스백을 낸다 — 원인을 알 수 없다.
    if not Path(out_pdf).is_file():
        raise SystemExit(
            f"PDF가 만들어지지 않았습니다: {out_pdf}\n"
            "snap Chromium은 /tmp에 쓸 수 없습니다. --out을 리포 안(예: out/)으로 두세요."
        )


def normalize_pdf(path, title="delivery", fixed="D:20000101000000Z"):
    """Chromium이 넣는 생성 시각·랜덤 ID를 고정값으로 바꿔 바이트 재현성을 만든다."""
    try:
        import hashlib

        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import ArrayObject, ByteStringObject
    except ImportError:
        return False

    reader = PdfReader(str(path))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.add_metadata(
        {
            "/Title": title,
            "/Producer": "sonagi-assets",
            "/Creator": "sonagi-assets",
            "/CreationDate": fixed,
            "/ModDate": fixed,
        }
    )
    digest = hashlib.md5(title.encode())
    for page in writer.pages:
        digest.update(page.get_contents().get_data())
    value = digest.digest()
    writer._ID = ArrayObject([ByteStringObject(value), ByteStringObject(value)])
    with open(path, "wb") as f:
        writer.write(f)
    return True


def export_png(chrome, svg, fonts_css, out_png, scale):
    w, h = svg_size(svg)
    html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
{fonts_css}
html, body {{ margin: 0; background: #fff; }}
svg {{ display: block; }}
</style></head><body>{svg}</body></html>"""
    with tempfile.TemporaryDirectory(prefix="tmp-export-", dir=str(Path(out_png).parent)) as tmp:
        page = Path(tmp) / "shot.html"
        page.write_text(html)
        run(
            [
                chrome,
                "--headless",
                "--no-sandbox",
                "--disable-gpu",
                "--hide-scrollbars",
                f"--force-device-scale-factor={scale}",
                f"--screenshot={Path(out_png).resolve()}",
                f"--window-size={w},{h}",
                page.resolve().as_uri(),
            ]
        )


def to_webp(png_path, webp_path, quality=88):
    try:
        from PIL import Image
    except ImportError:
        return False
    Image.open(png_path).convert("RGB").save(webp_path, "WEBP", quality=quality, method=6)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--pattern", default="*.svg")
    ap.add_argument("--out", required=True)
    ap.add_argument("--formats", default="pdf,png")
    ap.add_argument("--scale", type=float, default=2.0)
    ap.add_argument("--fonts-css", default=None, help="@font-face 정의가 담긴 css 파일")
    ap.add_argument("--allow-freeware", action="store_true", default=True)
    ap.add_argument("--pdf-mode", default="per-file", choices=("per-file", "single"), help="PDF를 화면별로 나누거나 한 파일로 묶는다")
    ap.add_argument("--pdf-name", default="sheet", help="--pdf-mode single일 때 파일명")
    args = ap.parse_args()

    src = Path(args.src)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    files = sorted(src.glob(args.pattern))
    if not files:
        raise SystemExit("no svg found")

    fonts_css = ""
    if args.fonts_css and Path(args.fonts_css).is_file():
        css_path = Path(args.fonts_css)
        fonts_css = resolve_font_urls(css_path.read_text(), css_path.parent)
    chrome = find_chrome()
    formats = {f.strip() for f in args.formats.split(",")}

    gate = [check_assets(f) for f in files]
    svgs = [(absolutize_refs(f.read_text(), src), svg_size(f.read_text())) for f in files]

    produced = []
    if "pdf" in formats and args.pdf_mode == "single":
        # 다페이지 문서(브랜드 시트 등): 페이지 크기가 같을 때만 한 파일로 묶는다
        sizes = {size for _, size in svgs}
        if len(sizes) != 1:
            raise SystemExit(f"--pdf-mode single은 페이지 크기가 같아야 합니다: {sorted(sizes)}")
        pdf = out / f"{args.pdf_name}.pdf"
        export_pdf(chrome, svgs, fonts_css, pdf)
        normalize_pdf(pdf, title=args.pdf_name)
        produced.append(pdf)
    elif "pdf" in formats:
        # 페이지 크기가 다른 캔버스를 한 PDF에 넣으면 Chromium이 한 크기로 합친다
        # → 화면(브레이크포인트)별로 PDF를 따로 만든다
        for (text, size), f in zip(svgs, files):
            pdf = out / f"{f.stem}.pdf"
            export_pdf(chrome, [(text, size)], fonts_css, pdf)
            normalize_pdf(pdf, title=f.stem)
            produced.append(pdf)

    for f in files:
        text = absolutize_refs(f.read_text(), src)
        w, h = svg_size(text)
        if "png" in formats or "webp" in formats:
            png = out / f"{f.stem}@{int(args.scale)}x.png"
            export_png(chrome, text, fonts_css, png, args.scale)
            produced.append(png)
            if "webp" in formats:
                webp = png.with_suffix(".webp")
                if to_webp(png, webp):
                    produced.append(webp)
        shutil.copy2(f, out / f.name)
        manifest = f.with_suffix(".manifest.json")
        if manifest.is_file():
            shutil.copy2(manifest, out / manifest.name)

    if (src / "assets").is_dir():
        shutil.copytree(src / "assets", out / "assets", dirs_exist_ok=True)

    summary = {
        "formats": sorted(formats),
        "scale": args.scale,
        "pages": [{"file": f.name, "width": s[0], "height": s[1]} for f, s in zip(files, [s for _, s in svgs])],
        "gate": gate,
        "files": [{"name": p.name, "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in produced],
    }
    (out / "export.json").write_text(json.dumps(summary, indent=4, ensure_ascii=False) + "\n")
    print(json.dumps({"files": len(produced), "out": str(out), "gate": gate}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
