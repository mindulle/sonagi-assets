#!/usr/bin/env python3
"""골든 렌더 기준선 — 픽스처 SVG 해시를 떠서 회귀를 잡는다.

`test_data/golden/all-blocks.md`(12블록)를 스타일 × 브레이크포인트 × 테마로
렌더하고 해시·높이·레이어 순서를 `test_data/golden/baseline.json`에 기록한다.
렌더러를 고친 뒤 `--check`로 돌려 무엇이 달라졌는지 본다.

사용::

    golden_render.py --update          # 기준선 갱신(의도된 변경일 때만)
    golden_render.py                   # 현재 코드가 기준선과 같은지 확인
    golden_render.py --styles editorial,brutalist --breakpoints desktop

왜 필요한가: ASSET-2(30px 오프셋)처럼 전체 SVG 바이트를 바꾸는 수정은
"좋아졌다"와 "깨졌다"를 해시만으로 구분할 수 없다. 수정 전 기준선과
수정 후 diff를 나란히 놓고 판단한다. 카탈로그는 픽스처 7개 자산만 쓰므로
devops의 7.2GB 라이브러리 없이 돌고, CI에도 그대로 넣을 수 있다(ASSET-5).
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
FIXTURE = ROOT / "test_data/golden/all-blocks.md"
CATALOG = ROOT / "test_data/golden/catalog.json"
TOKENS = ROOT / "tokens/semantic.json"
BASELINE = ROOT / "test_data/golden/baseline.json"
WORK = ROOT / "out/golden"

DEFAULT_STYLES = ("editorial", "brutalist", "etching", "poster", "swiss", "art-nouveau", "minimal")
DEFAULT_BREAKPOINTS = ("desktop", "tablet", "mobile")
THEMES = (("light", []), ("dark", ["--dark"]))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(cmd):
    done = subprocess.run([sys.executable, *map(str, cmd)], capture_output=True, text=True)
    if done.returncode != 0:
        sys.stderr.write(done.stdout)
        sys.stderr.write(done.stderr)
        raise SystemExit(f"실패: {' '.join(map(str, cmd))}")
    return done


def build_recipe(out_dir):
    recipe = out_dir / "recipe.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    run([SCRIPTS / "import_content.py", FIXTURE, "--catalog", CATALOG, "--out", recipe])
    return recipe


def render(recipe, name, style, bp, flag, out_dir):
    run(
        [
            SCRIPTS / "render_recipe.py",
            "--recipe",
            recipe,
            "--style",
            ROOT / "styles" / f"{style}.json",
            "--catalog",
            CATALOG,
            "--tokens",
            TOKENS,
            "--out",
            out_dir,
            "--breakpoint",
            bp,
            *flag,
        ]
    )
    svg = out_dir / f"{name}.svg"
    manifest_path = out_dir / f"{name}.manifest.json"
    manifest = json.loads(manifest_path.read_text())
    head = svg.read_text()
    size = re.search(r'<svg[^>]*width="(\d+)" height="(\d+)"', head)
    return {
        "svg_sha256": sha256(svg),
        "svg_bytes": svg.stat().st_size,
        "manifest_sha256": sha256(manifest_path),
        "canvas": {"width": int(size.group(1)), "height": int(size.group(2))} if size else {},
        "layers": manifest["layers"],
    }


def collect(styles, breakpoints):
    out_dir = WORK
    recipe = build_recipe(out_dir)
    name = json.loads(recipe.read_text())["name"]
    renders = {}
    for style in styles:
        for bp in breakpoints:
            for theme, flag in THEMES:
                target = out_dir / style / bp / theme
                key = f"{style}|{bp}|{theme}"
                renders[key] = render(recipe, name, style, bp, flag, target)
                print(f"  {key:32s} h={renders[key]['canvas'].get('height')}", file=sys.stderr)
    return {
        "schema": 1,
        "fixture": str(FIXTURE.relative_to(ROOT)),
        "catalog": str(CATALOG.relative_to(ROOT)),
        "tokens": str(TOKENS.relative_to(ROOT)),
        "matrix": {"styles": list(styles), "breakpoints": list(breakpoints), "themes": [t for t, _ in THEMES]},
        "renders": renders,
    }


def compare(old, new):
    rows = []
    for key in sorted(set(old) | set(new)):
        a, b = old.get(key), new.get(key)
        if not a:
            rows.append((key, "added", "-", ""))
        elif not b:
            rows.append((key, "removed", "-", ""))
        elif a["svg_sha256"] != b["svg_sha256"]:
            dh = b["canvas"].get("height", 0) - a["canvas"].get("height", 0)
            dl = a["layers"] != b["layers"]
            rows.append((key, "layers" if dl else "svg", f"{dh:+d}px", "layer order changed" if dl else ""))
        elif a["manifest_sha256"] != b["manifest_sha256"]:
            rows.append((key, "manifest", "0px", ""))
    return rows


def main():
    ap = argparse.ArgumentParser(description="골든 렌더 기준선")
    ap.add_argument("--update", action="store_true", help="현재 결과를 기준선으로 저장")
    ap.add_argument("--styles", default=",".join(DEFAULT_STYLES))
    ap.add_argument("--breakpoints", default=",".join(DEFAULT_BREAKPOINTS))
    ap.add_argument("--baseline", default=str(BASELINE))
    args = ap.parse_args()

    for path in (FIXTURE, CATALOG, TOKENS):
        if not path.is_file():
            raise SystemExit(f"없습니다: {path.relative_to(ROOT)}")

    styles = [s.strip() for s in args.styles.split(",") if s.strip()]
    breakpoints = [b.strip() for b in args.breakpoints.split(",") if b.strip()]
    missing = [s for s in styles if not (ROOT / "styles" / f"{s}.json").is_file()]
    if missing:
        raise SystemExit(f"스타일이 없습니다: {', '.join(missing)}")

    baseline_path = Path(args.baseline)
    print(
        f"골든 렌더: 스타일 {len(styles)} × bp {len(breakpoints)} × 테마 {len(THEMES)} = {len(styles) * len(breakpoints) * len(THEMES)}",
        file=sys.stderr,
    )
    new = collect(styles, breakpoints)

    if args.update:
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps(new, indent=4, ensure_ascii=False) + "\n")
        print(f"기준선 저장: {baseline_path} ({len(new['renders'])} 렌더)")
        return 0

    if not baseline_path.is_file():
        raise SystemExit(f"기준선이 없습니다. 먼저 --update로 만드세요: {baseline_path}")

    old = json.loads(baseline_path.read_text())
    if old.get("matrix") != new["matrix"]:
        print(f"비교 범위가 다릅니다: {old.get('matrix')} → {new['matrix']}")
        print("범위를 같게 맞추거나 --update로 기준선을 새로 뜨세요.")
        return 2

    rows = compare(old["renders"], new["renders"])
    if not rows:
        print(f"기준선과 동일 ({len(new['renders'])} 렌더)")
        return 0

    print(f"기준선과 다름: {len(rows)}/{len(new['renders'])}")
    print(f"{'key':32s} {'변화':10s} {'높이':>8s}  비고")
    for key, kind, delta, note in rows:
        print(f"{key:32s} {kind:10s} {delta:>8s}  {note}")
    print("\n의도된 변경이면 --update로 기준선을 갱신하고 커밋 메시지에 이유를 남기세요.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
