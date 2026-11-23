#!/usr/bin/env python3
"""press — 소나기 렌더·납품 엔진 CLI.

기존 스크립트를 감싸는 단일 진입점이다. 로직은 각 스크립트에 있고,
여기서는 인자 해석과 순서 보장만 한다.

    press check content/atelier-landing.md
    press render content/atelier-landing.md --style etching --breakpoints desktop,mobile
    press package --src out/dist --out delivery/x --name "Atelier"
    press styles
    press preview --sheet --png
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
VERSION = "0.1.0"

DEFAULT_CATALOG = os.environ.get("PRESS_CATALOG", "/srv/sonagi-assets/catalog/catalog.json")
DEFAULT_TOKENS = os.environ.get("PRESS_TOKENS", str(ROOT / "tokens" / "semantic.json"))
DEFAULT_FONTS_CSS = os.environ.get("PRESS_FONTS_CSS", "/home/ubuntu/brief/fonts/fonts.css")
BREAKPOINTS = ("desktop", "tablet", "mobile")


def run(cmd: list[str]) -> int:
    proc = subprocess.run([str(c) for c in cmd])
    return proc.returncode


def style_path(value: str) -> Path:
    path = Path(value)
    if path.is_file():
        return path
    candidate = ROOT / "styles" / f"{value}.json"
    if candidate.is_file():
        return candidate
    raise SystemExit(f"스타일을 찾을 수 없습니다: {value}")


def require(path: Path, hint: str) -> Path:
    if not path.is_file():
        raise SystemExit(f"파일이 없습니다: {path}\n{hint}")
    return path


def cmd_styles(args) -> int:
    axes_path = ROOT / "styles" / "axes.json"
    axes = json.loads(axes_path.read_text()) if axes_path.is_file() else {}
    skip = {"axes.json", "ornaments.json"}
    styles = sorted(p.stem for p in (ROOT / "styles").glob("*.json") if p.name not in skip)
    if args.json:
        print(
            json.dumps(
                {
                    "version": VERSION,
                    "styles": styles,
                    "axes": {name: sorted(values) for name, values in axes.items() if isinstance(values, dict)},
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    print(f"press {VERSION}")
    for name in ("palette", "type", "geometry", "layout", "ornament"):
        values = axes.get(name) or {}
        print(f"  {name:9s} {len(values):3d}  {', '.join(sorted(values)[:6])}{' …' if len(values) > 6 else ''}")
    print(f"\n스타일 {len(styles)}종: {', '.join(styles)}")
    return 0


def cmd_check(args) -> int:
    catalog = require(Path(args.catalog), "devops의 /srv/sonagi-assets/catalog/catalog.json 또는 로컬 복사본을 지정하세요.")
    cmd = [sys.executable, SCRIPTS / "import_content.py", args.content, "--catalog", catalog, "--check"]
    return run(cmd)


def cmd_render(args) -> int:
    catalog = require(Path(args.catalog), "devops의 카탈로그 경로를 --catalog로 지정하세요.")
    tokens = require(Path(args.tokens), "--tokens로 semantic.json을 지정하세요.")
    style = style_path(args.style)
    source = Path(args.input)
    if not source.is_file():
        raise SystemExit(f"입력이 없습니다: {source}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if source.suffix.lower() in (".md", ".markdown"):
        recipe = out / "recipe.json"
        code = run(
            [
                sys.executable,
                SCRIPTS / "import_content.py",
                source,
                "--catalog",
                catalog,
                "--out",
                recipe,
            ]
        )
        if code != 0:
            return code
    else:
        recipe = source

    wanted = [b.strip() for b in args.breakpoints.split(",") if b.strip()]
    bad = [b for b in wanted if b not in BREAKPOINTS]
    if bad:
        raise SystemExit(f"브레이크포인트는 desktop|tablet|mobile 입니다: {', '.join(bad)}")

    made = []
    for bp in wanted:
        target = out / bp
        code = run(
            [
                sys.executable,
                SCRIPTS / "render_recipe.py",
                "--recipe",
                recipe,
                "--style",
                style,
                "--catalog",
                catalog,
                "--tokens",
                tokens,
                "--out",
                target,
                "--breakpoint",
                bp,
                "--embed-max-width",
                args.embed_max_width,
                "--raster-mode",
                args.raster,
            ]
        )
        if code != 0:
            return code
        made.extend(sorted(str(p) for p in target.glob("*.svg")))

    if args.json:
        print(json.dumps({"out": str(out), "breakpoints": wanted, "svg": made}, ensure_ascii=False))
    return 0


def cmd_package(args) -> int:
    src = Path(args.src)
    if not src.is_dir():
        raise SystemExit(f"소스 폴더가 없습니다: {src}")
    fonts = Path(args.fonts_css)
    out = Path(args.out)
    dist = out / "dist"
    code = run(
        [
            sys.executable,
            SCRIPTS / "export_recipe.py",
            "--src",
            src,
            "--out",
            dist,
            "--formats",
            args.formats,
            "--scale",
            args.scale,
            "--fonts-css",
            fonts,
        ]
    )
    if code != 0:
        return code
    code = run(
        [
            sys.executable,
            SCRIPTS / "bundle_delivery.py",
            "--src",
            dist,
            "--out",
            out / args.name,
            "--name",
            args.title or args.name,
            "--zip",
        ]
    )
    return code


def cmd_preview(args) -> int:
    cmd = [sys.executable, SCRIPTS / "preview_ornament.py"]
    if args.sheet:
        cmd.append("--sheet")
    if args.motif:
        cmd += ["--motif", args.motif]
    if args.frame:
        cmd += ["--frame", args.frame]
    if args.png:
        cmd.append("--png")
    return run(cmd)


def cmd_lockup(args) -> int:
    cmd = [
        sys.executable,
        SCRIPTS / "render_lockup.py",
        "--spec",
        args.spec,
        "--out",
        args.out,
    ]
    if args.name:
        cmd += ["--name", args.name]
    if args.check:
        cmd.append("--check")
    if args.allow_low_contrast:
        cmd.append("--allow-low-contrast")
    if args.json:
        cmd.append("--json")
    return run(cmd)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="press", description="소나기 렌더·납품 엔진")
    parser.add_argument("--version", action="version", version=f"press {VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="content.md 검증")
    check.add_argument("content")
    check.add_argument("--catalog", default=DEFAULT_CATALOG)
    check.set_defaults(func=cmd_check)

    render = sub.add_parser("render", help="SVG 렌더")
    render.add_argument("input", help="content.md 또는 recipe.json")
    render.add_argument("--style", default="editorial")
    render.add_argument("--breakpoints", default="desktop")
    render.add_argument("--out", default="out/press")
    render.add_argument("--catalog", default=DEFAULT_CATALOG)
    render.add_argument("--tokens", default=DEFAULT_TOKENS)
    render.add_argument("--embed-max-width", default="900")
    render.add_argument("--raster", default="embed", choices=("embed", "link"), help="래스터 임베드(embed) 또는 파일 1벌 참조(link)")
    render.add_argument("--json", action="store_true")
    render.set_defaults(func=cmd_render)

    package = sub.add_parser("package", help="PDF·PNG·WebP·zip")
    package.add_argument("--src", required=True)
    package.add_argument("--out", default="delivery")
    package.add_argument("--name", required=True)
    package.add_argument("--title", default="")
    package.add_argument("--formats", default="pdf,png,webp")
    package.add_argument("--scale", default="2")
    package.add_argument("--fonts-css", default=DEFAULT_FONTS_CSS)
    package.set_defaults(func=cmd_package)

    styles = sub.add_parser("styles", help="축·스타일 목록")
    styles.add_argument("--json", action="store_true")
    styles.set_defaults(func=cmd_styles)

    preview = sub.add_parser("preview", help="장식 미리보기")
    preview.add_argument("--sheet", action="store_true")
    preview.add_argument("--motif")
    preview.add_argument("--frame")
    preview.add_argument("--png", action="store_true")
    preview.set_defaults(func=cmd_preview)

    lockup = sub.add_parser("lockup", help="락업·변형 시트 (로고 규격)")
    lockup.add_argument("--spec", required=True)
    lockup.add_argument("--out", default="out/lockup")
    lockup.add_argument("--name")
    lockup.add_argument("--check", action="store_true", help="검사만")
    lockup.add_argument("--allow-low-contrast", action="store_true")
    lockup.add_argument("--json", action="store_true")
    lockup.set_defaults(func=cmd_lockup)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
