#!/usr/bin/env python3
"""인쇄용 PDF — 도련·재단선·CMYK (ASSET-6).

화면용 export와 **분리된 경로**다. 색 재현이 다르므로 같은 파일을 쓰지 않는다.
렌더된 SVG를 받아 인쇄 규격 페이지로 다시 조판하고, Ghostscript로 CMYK로 바꾼다.

```
SVG ──조판(도련+재단선)──▶ Chromium PDF(RGB) ──gs──▶ CMYK PDF
```

사용::

    export_print.py --src out/brandsheet/01-cover.svg --trim 210x297 --out out/print
    export_print.py --src out/brandsheet --pattern '*.svg' --trim 210x297 --bleed 3

검증: 페이지 크기(mm), 도련 값, 재단선 존재, CMYK 색공간, 래스터 실효 dpi.
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CHROME_CANDIDATES = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")
PX_PER_MM = 96 / 25.4  # 96dpi 기준


def find_chrome():
    for name in CHROME_CANDIDATES:
        path = shutil.which(name)
        if path:
            return path
    raise SystemExit("chromium not found")


def find_gs():
    path = shutil.which("gs")
    if not path:
        raise SystemExit("ghostscript(gs) not found")
    return path


def svg_geometry(text):
    width = re.search(r'<svg[^>]*\bwidth="([\d.]+)"', text)
    height = re.search(r'<svg[^>]*\bheight="([\d.]+)"', text)
    if not width or not height:
        raise SystemExit("SVG에 width/height가 없습니다")
    return float(width.group(1)), float(height.group(1))


def background_color(text):
    """페이지 배경색. 렌더러는 첫 rect를 배경으로 깐다."""
    match = re.search(r'<rect[^>]*id="page"[^>]*fill="(#[0-9a-fA-F]{3,8})"', text)
    if not match:
        match = re.search(r'<rect[^>]*fill="(#[0-9a-fA-F]{3,8})"', text)
    return match.group(1) if match else "#ffffff"


def parse_trim(value):
    match = re.fullmatch(r"(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)", value.strip())
    if not match:
        raise SystemExit(f"--trim은 WxH(mm) 형식입니다: {value}")
    return float(match.group(1)), float(match.group(2))


def crop_marks(x0, y0, w, h, bleed, slug, ink="#000000"):
    """재단선 바깥(도련 너머)으로 뻗는 8개 표시."""
    reach = slug * 0.6
    parts = []
    lx, rx = x0, x0 + w
    ty, by = y0, y0 + h
    for x, y in ((lx, ty), (rx, ty), (lx, by), (rx, by)):
        dx = -1 if x == lx else 1
        dy = -1 if y == ty else 1
        parts.append(f'<line x1="{x + dx * bleed:.2f}" y1="{y}" x2="{x + dx * (bleed + reach):.2f}" y2="{y}" stroke="{ink}" stroke-width="0.25"/>')
        parts.append(f'<line x1="{x}" y1="{y + dy * bleed:.2f}" x2="{x}" y2="{y + dy * (bleed + reach):.2f}" stroke="{ink}" stroke-width="0.25"/>')
    return parts


def print_svg(source_text, trim, bleed, slug, label):
    """도련·재단선이 들어간 인쇄 페이지 SVG(mm 단위)."""
    src_w, src_h = svg_geometry(source_text)
    trim_w, trim_h = trim
    src_ratio = src_w / src_h
    trim_ratio = trim_w / trim_h
    if abs(src_ratio - trim_ratio) > 0.01:
        raise SystemExit(f"비율이 맞지 않습니다: 원본 {src_w:.0f}×{src_h:.0f} vs 재단 {trim_w}×{trim_h}mm")

    margin = bleed + slug
    page_w = trim_w + margin * 2
    page_h = trim_h + margin * 2
    bg = background_color(source_text)

    inner = source_text
    inner = re.sub(r"^<\?xml[^>]*\?>\s*", "", inner)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{page_w}mm" height="{page_h}mm" viewBox="0 0 {page_w} {page_h}">',
        # 도련까지 배경을 깐다
        f'<rect x="0" y="0" width="{page_w}" height="{page_h}" fill="{bg}"/>',
        f'<svg x="{margin}" y="{margin}" width="{trim_w}" height="{trim_h}" viewBox="0 0 {src_w:.2f} {src_h:.2f}" preserveAspectRatio="none">',
        inner,
        "</svg>",
    ]
    parts += crop_marks(margin, margin, trim_w, trim_h, bleed, slug)
    parts.append(
        f'<text x="{margin}" y="{page_h - slug * 0.25:.2f}" font-family="monospace" font-size="2.2" fill="#000000" fill-opacity="0.6">{label}</text>'
    )
    parts.append("</svg>")
    return "".join(parts), page_w, page_h, bg


def render_pdf(chrome, svg_text, page_w, page_h, out_pdf):
    html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
@page {{ size: {page_w}mm {page_h}mm; margin: 0; }}
html, body {{ margin: 0; padding: 0; }}
svg {{ display: block; }}
</style></head><body>{svg_text}</body></html>"""
    with tempfile.TemporaryDirectory(prefix="tmp-print-", dir=str(Path(out_pdf).parent)) as tmp:
        page = Path(tmp) / "print.html"
        page.write_text(html)
        subprocess.run(
            [
                chrome,
                "--headless",
                "--no-sandbox",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--print-to-pdf={Path(out_pdf).resolve()}",
                page.resolve().as_uri(),
            ],
            capture_output=True,
            check=True,
        )


def to_cmyk(gs, src_pdf, out_pdf, icc=None):
    cmd = [
        gs,
        "-q",
        "-dBATCH",
        "-dNOPAUSE",
        "-sDEVICE=pdfwrite",
        "-dPDFSETTINGS=/prepress",
        "-dProcessColorModel=/DeviceCMYK",
        "-sColorConversionStrategy=CMYK",
        "-dEmbedAllFonts=true",
        "-dSubsetFonts=true",
        "-dAutoRotatePages=/None",
    ]
    if icc:
        cmd += [f"-sOutputICCProfile={icc}", "-dOverrideICC"]
    cmd += [f"-sOutputFile={out_pdf}", str(src_pdf)]
    subprocess.run(cmd, capture_output=True, check=True)


def normalize(pdf_path, title):
    """생성 시각·ID 고정(결정론)."""
    try:
        import hashlib

        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import ArrayObject, ByteStringObject
    except ImportError:
        return False
    reader = PdfReader(str(pdf_path))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.add_metadata(
        {
            "/Title": title,
            "/Producer": "sonagi-assets (print)",
            "/Creator": "sonagi-assets (print)",
            "/CreationDate": "D:20000101000000Z",
            "/ModDate": "D:20000101000000Z",
        }
    )
    digest = hashlib.md5(title.encode())
    for page in writer.pages:
        digest.update(page.get_contents().get_data())
    value = digest.digest()
    writer._ID = ArrayObject([ByteStringObject(value), ByteStringObject(value)])
    with open(pdf_path, "wb") as f:
        writer.write(f)
    return True


def raster_dpi(svg_text):
    """임베드 래스터의 실효 dpi 최솟값. 없으면 None."""
    try:
        import base64
        from io import BytesIO

        from PIL import Image
    except ImportError:
        return None
    values = []
    for match in re.finditer(r"<image[^>]*>", svg_text):
        tag = match.group(0)
        href = re.search(r'href="data:[^;]+;base64,([^"]+)"', tag)
        width = re.search(r'width="([\d.]+)"', tag)
        if not href or not width:
            continue
        try:
            im = Image.open(BytesIO(base64.b64decode(href.group(1))))
        except Exception:
            continue
        placed_mm = float(width.group(1)) / PX_PER_MM
        if placed_mm <= 0:
            continue
        values.append(im.width / (placed_mm / 25.4))
    return round(min(values)) if values else None


def color_operators(pdf_path):
    """내용 스트림의 색 연산자(k/K=CMYK, rg/RG=RGB)를 센다."""
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    cmyk = rgb = gray = 0
    for page in reader.pages:
        try:
            data = page.get_contents().get_data().decode("latin-1")
        except Exception:
            continue
        cmyk += len(re.findall(r"\bk\b", data)) + len(re.findall(r"\bK\b", data))
        rgb += len(re.findall(r"\brg\b", data)) + len(re.findall(r"\bRG\b", data))
        gray += len(re.findall(r"\bg\b", data)) + len(re.findall(r"\bG\b", data))
    return {"cmyk_ops": cmyk, "rgb_ops": rgb, "gray_ops": gray}


def inspect(pdf_path, trim, bleed, slug, svg_text):
    """페이지 크기·색공간·래스터 해상도 확인."""
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    box = reader.pages[0].mediabox
    width_mm = float(box.width) * 25.4 / 72
    height_mm = float(box.height) * 25.4 / 72
    ops = color_operators(pdf_path)
    dpi = raster_dpi(svg_text)
    return {
        "page_mm": [round(width_mm, 1), round(height_mm, 1)],
        "expected_mm": [round(trim[0] + 2 * (bleed + slug), 1), round(trim[1] + 2 * (bleed + slug), 1)],
        "pages": len(reader.pages),
        "colorspaces": ops,
        "cmyk_ok": ops["cmyk_ops"] > 0 and ops["rgb_ops"] == 0,
        "raster_dpi_min": dpi,
        "raster_dpi_ok": (dpi is None) or dpi >= 300,
    }


def main():
    ap = argparse.ArgumentParser(description="인쇄용 PDF(도련·재단선·CMYK)")
    ap.add_argument("--src", required=True, help="SVG 파일 또는 폴더")
    ap.add_argument("--pattern", default="*.svg")
    ap.add_argument("--out", default="out/print")
    ap.add_argument("--trim", default="210x297", help="재단 크기(mm). 기본 A4")
    ap.add_argument("--bleed", type=float, default=3.0, help="도련(mm)")
    ap.add_argument("--slug", type=float, default=5.0, help="재단선 여백(mm)")
    ap.add_argument("--icc", default=None, help="출력 ICC 프로파일(.icc)")
    ap.add_argument("--check", action="store_true", help="조판 가능 여부만 검사(chromium·gs 불필요)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    trim = parse_trim(args.trim)
    src = Path(args.src)
    files = sorted(src.glob(args.pattern)) if src.is_dir() else [src]
    if not files:
        raise SystemExit(f"SVG가 없습니다: {src}")

    out = Path(args.out)

    if args.check:
        problems = 0
        for path in files:
            try:
                svg_text, page_w, page_h, bg = print_svg(path.read_text(), trim, args.bleed, args.slug, path.stem)
                print(f"  {path.name:24s} {page_w:.1f}×{page_h:.1f}mm ok (bg {bg})")
            except SystemExit as exc:
                problems += 1
                print(f"  ! {path.name}: {exc}", file=sys.stderr)
        return 1 if problems else 0

    out.mkdir(parents=True, exist_ok=True)
    chrome, gs = find_chrome(), find_gs()

    reports = []
    for path in files:
        text = path.read_text()
        try:
            svg_text, page_w, page_h, bg = print_svg(text, trim, args.bleed, args.slug, path.stem)
        except SystemExit as exc:
            reports.append({"file": path.name, "error": str(exc)})
            print(f"  ! {path.name}: {exc}", file=sys.stderr)
            continue

        rgb_pdf = out / f"{path.stem}.rgb.pdf"
        cmyk_pdf = out / f"{path.stem}.pdf"
        render_pdf(chrome, svg_text, page_w, page_h, rgb_pdf)
        to_cmyk(gs, rgb_pdf, cmyk_pdf, args.icc)
        normalize(cmyk_pdf, path.stem)

        info = inspect(cmyk_pdf, trim, args.bleed, args.slug, text)
        info.update(
            {
                "file": path.name,
                "pdf": cmyk_pdf.name,
                "bytes": cmyk_pdf.stat().st_size,
                "sha256": hashlib.sha256(cmyk_pdf.read_bytes()).hexdigest(),
                "bleed_mm": args.bleed,
                "slug_mm": args.slug,
                "background": bg,
                "trim_mm": list(trim),
            }
        )
        reports.append(info)
        rgb_pdf.unlink(missing_ok=True)
        print(f"  {path.name:24s} {info['page_mm']} mm · cmyk={info['cmyk_ok']} · {info['bytes'] // 1024}KB")

    manifest = {
        "trim_mm": list(trim),
        "bleed_mm": args.bleed,
        "slug_mm": args.slug,
        "icc": args.icc,
        "files": reports,
    }
    (out / "print.manifest.json").write_text(json.dumps(manifest, indent=4, ensure_ascii=False) + "\n")

    bad = [r for r in reports if r.get("error") or not r.get("cmyk_ok")]
    if args.json:
        print(json.dumps(manifest, ensure_ascii=False))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
