#!/usr/bin/env python3
"""레시피를 단계별로 렌더해 빌드업 프레임을 만든다.

스피드 페인팅(사람의 붓질)과는 다르다. 이건 **레이어 조립 과정**의 기록이다.
배경 → 헤더 → 히어로 → 피처(1,2,3) → 푸터 순으로 SVG를 남긴다.

사용::

    python3 animate_recipe.py --recipe recipes/landing-hero.json \\
        --style styles/etching.json --catalog catalog/catalog.json \\
        --tokens tokens/semantic.json --out frames/
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def stages(blocks):
    """(이름, 블록 목록) 순서를 만든다. 피처는 카드 단위로 쪼갠다."""
    out = [("00-background", [])]
    prefix = []
    for block in blocks:
        if block["type"] == "features":
            for n in range(1, min(3, len(block["items"])) + 1):
                variant = dict(block)
                variant["items"] = block["items"][:n]
                out.append((f"features-{n}", prefix + [variant]))
            prefix.append(block)
        else:
            prefix.append(block)
            out.append((f"{block['type']}", list(prefix)))
    out.append(("99-final", list(blocks)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", required=True)
    ap.add_argument("--style", required=True)
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--tokens", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--height", type=int, default=0, help="고정 높이(0이면 auto)")
    args = ap.parse_args()

    recipe = json.loads(Path(args.recipe).read_text())
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    blocks = [b for b in recipe["blocks"] if b["type"] != "footer"]
    footer = [b for b in recipe["blocks"] if b["type"] == "footer"]
    seq = stages(blocks)
    seq = [(name, blks) for name, blks in seq if name != "99-final"]
    seq.append(("99-final", blocks + footer))

    frames = []
    for i, (name, blks) in enumerate(seq):
        variant = dict(recipe)
        variant["blocks"] = blks
        variant["canvas"] = {"width": recipe["canvas"]["width"], "height": args.height or recipe["canvas"]["height"]}
        variant["name"] = f"frame-{i:02d}"
        tmp = out / f".recipe-{i:02d}.json"
        tmp.write_text(json.dumps(variant, ensure_ascii=False))
        subprocess.run(
            [
                sys.executable,
                str(HERE / "render_recipe.py"),
                "--recipe",
                str(tmp),
                "--style",
                args.style,
                "--catalog",
                args.catalog,
                "--tokens",
                args.tokens,
                "--out",
                str(out),
                "--force-height",
                str(args.height) if args.height else "0",
            ],
            check=True,
            capture_output=True,
        )
        tmp.unlink()
        frames.append(str(out / f"frame-{i:02d}.svg"))
        print(name, "->", frames[-1])

    print(json.dumps({"frames": len(frames)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
