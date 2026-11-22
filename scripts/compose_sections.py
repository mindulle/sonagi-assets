#!/usr/bin/env python3
"""섹션 문법으로 레이아웃 베리에이션을 만든다.

레시피 v2는 `content`(재료)만 주고, 이 스크립트가 섹션 조합을 샘플링한다.
같은 seed면 같은 조합이 나온다.

사용::

    python3 compose_sections.py --recipe recipes/landing-hero-v2.json \\
        --style styles/etching.json --catalog catalog/catalog.json \\
        --tokens tokens/semantic.json --variants 6 --seed 7 --out variants/
"""

import argparse
import itertools
import json
import random
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

PROOF = {"stats", "quote", "logos"}
MIDDLE = ["stats", "quote", "logos", "features", "faq"]


def valid(seq):
    if "features" not in seq:
        return False
    if not (set(seq) & PROOF):
        return False
    for a, b in zip(seq, seq[1:]):
        if a in PROOF and b in PROOF:
            return False
    return True


def score(seq):
    s = 10 * len(seq)
    if seq and seq[0] == "hero":
        s += 4
    if "features" in seq:
        s += 6
    if set(seq) & PROOF:
        s += 8
    if "faq" in seq:
        s += 6
    if "logos" in seq:
        s += 4
    if len(seq) > 6:
        s -= 8
    if seq[:2] == ["hero", "quote"]:
        s += 5
    if "stats" in seq and "features" in seq and seq.index("stats") < seq.index("features"):
        s += 3
    if "features" in seq and "faq" in seq and seq.index("features") < seq.index("faq"):
        s += 2
    return s


def candidates():
    seen = set()
    for size in range(2, len(MIDDLE) + 1):
        for subset in itertools.combinations(MIDDLE, size):
            if "features" not in subset:
                continue
            for perm in itertools.permutations(subset):
                seq = ["header", "hero"] + list(perm) + ["cta", "footer"]
                if valid(list(perm)):
                    key = tuple(seq)
                    if key not in seen:
                        seen.add(key)
                        yield seq


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", required=True)
    ap.add_argument("--style", required=True)
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--tokens", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--variants", type=int, default=6)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--height", type=int, default=0)
    args = ap.parse_args()

    recipe = json.loads(Path(args.recipe).read_text())
    content = recipe["content"]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    pool = list(candidates())
    random.Random(args.seed).shuffle(pool)
    ranked = sorted(pool, key=score, reverse=True)[: args.variants * 8]

    # 1패스: 섹션 집합이 다른 것 우선, 2패스: 같은 집합의 순서 변형 허용
    picked, seen_sets, seen_seq = [], set(), set()
    for seq in ranked:
        key = frozenset(seq)
        if key in seen_sets:
            continue
        seen_sets.add(key)
        seen_seq.add(tuple(seq))
        picked.append(seq)
        if len(picked) >= args.variants:
            break
    if len(picked) < args.variants:
        for seq in ranked:
            if tuple(seq) in seen_seq:
                continue
            seen_seq.add(tuple(seq))
            picked.append(seq)
            if len(picked) >= args.variants:
                break

    results = []
    for i, seq in enumerate(picked, 1):
        blocks = []
        for name in seq:
            if name in ("hero", "cta", "header", "footer"):
                blocks.append({"type": name, **content.get(name, {})})
            else:
                blocks.append({"type": name, **content[name]})
        variant = {
            "name": f"{recipe['name']}-v{i}",
            "seed": recipe.get("seed", args.seed),
            "theme": recipe.get("theme", "editorial"),
            "canvas": recipe.get("canvas", {"width": 1440, "height": "auto"}),
            "blocks": blocks,
        }
        tmp = out / f".v{i}.json"
        tmp.write_text(json.dumps(variant, ensure_ascii=False))
        cmd = [
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
        ]
        if args.height:
            cmd += ["--force-height", str(args.height)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            print(proc.stdout, proc.stderr)
            raise SystemExit(f"render failed: {variant['name']}")
        tmp.unlink()
        manifest = json.loads((out / f"{variant['name']}.manifest.json").read_text())
        results.append(
            {
                "variant": variant["name"],
                "sections": [b["type"] for b in blocks],
                "score": score([b["type"] for b in blocks]),
                "sha256": manifest["sha256"],
                "height": manifest["canvas"]["height"],
            }
        )
        print(variant["name"], results[-1]["score"], " > ".join(results[-1]["sections"]))

    (out / "variants.json").write_text(json.dumps({"seed": args.seed, "variants": results}, indent=4, ensure_ascii=False) + "\n")
    print(json.dumps({"count": len(results)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
