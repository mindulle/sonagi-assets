#!/usr/bin/env python3
"""판정 골든셋 — "이 렌더가 좋은가"에 기준선을 둔다.

SVG에는 골든 해시가 있는데 판정에는 없었다. 그래서 룰을 고치면 어제 72점이
오늘 88점이 되고, 그게 개선인지 표류인지 구분할 수 없었다.

`test_data/judgment/cases.json`의 케이스를 렌더(또는 일부러 망친 뒤) 린트하고,
판정·발화 룰을 `baseline.json`과 비교한다. 케이스는 두 종류다.

| 종류 | 뜻 | 기대 |
| --- | --- | --- |
| good-* | 실제 스타일·브레이크포인트·테마 6장 | `pass` |
| bad-*  | 좋은 렌더를 결정론적으로 망친 8장 (겹침·저대비·찌그러짐·라이선스·계약) | `fail`/`warn` |

사용::

    judgment_golden.py              # 기준선과 비교 (CI가 같은 명령을 돌린다)
    judgment_golden.py --update     # 룰을 의도적으로 바꿨을 때 기준선 갱신
    judgment_golden.py --json       # 기계 판독
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from lint_render import lint  # noqa: E402

CASES = ROOT / "test_data/judgment/cases.json"
BASELINE = ROOT / "test_data/judgment/baseline.json"
TOKENS = ROOT / "tokens/semantic.json"
WORK = ROOT / "out/judgment"

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)


def run(cmd):
    done = subprocess.run([sys.executable, *map(str, cmd)], capture_output=True, text=True)
    if done.returncode != 0:
        sys.stderr.write(done.stdout)
        sys.stderr.write(done.stderr)
        raise SystemExit(f"실패: {' '.join(map(str, cmd))}")
    return done


def build_recipe(out_dir, fixture, catalog):
    recipe = out_dir / "recipe.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    run([SCRIPTS / "import_content.py", fixture, "--catalog", catalog, "--out", recipe])
    return recipe


def find_group(root, ident):
    for el in root.iter():
        if el.get("id") == ident:
            return el
    return None


def first_text(root):
    for el in root.iter():
        if el.tag.split("}")[-1] == "text" and "".join(el.itertext()).strip():
            return el
    return None


def background(root):
    for el in root.iter():
        if el.tag.split("}")[-1] == "rect" and el.get("id") == "background":
            return el.get("fill")
    return "#ffffff"


# --- 결정론적 망치기 ------------------------------------------------------
# 각 함수는 (root, manifest, meta)를 받아 제자리에서 고친다.


def mut_squash(root, manifest, meta):
    root.set("width", "100")
    root.set("height", "100")


def mut_overlap(root, manifest, meta):
    group = find_group(root, "hero")
    texts = [el for el in (group.iter() if group is not None else []) if el.tag.split("}")[-1] == "text"]
    if not texts:
        raise SystemExit("overlap: hero에 text가 없습니다")
    target = texts[-1]
    target.set("y", f"{float(target.get('y', 0)) + 420:.0f}")


def mut_contrast(root, manifest, meta):
    fill = background(root)
    for el in root.iter():
        if el.tag.split("}")[-1] == "text":
            el.set("fill", fill)


def mut_drop_layer(root, manifest, meta):
    for el in root.iter():
        if el.get("id") == "hero":
            el.set("id", "hero-broken")
            return
    raise SystemExit("drop-layer: hero 그룹이 없습니다")


def mut_license(root, manifest, meta):
    manifest["license_ok"] = False
    manifest.setdefault("assets", []).append({"name": "brand-logo", "scope": "blocked", "origin": "unknown"})


def mut_overflow(root, manifest, meta):
    target = first_text(root)
    if target is None:
        raise SystemExit("overflow: text가 없습니다")
    width = float(root.get("width", 1440))
    target.set("x", f"{width - 5:.0f}")
    target.set("text-anchor", "start")
    target.text = "이 문장은 캔버스 오른쪽 경계를 넘어서 잘려야 정상입니다"


def mut_drop_contract(root, manifest, meta):
    manifest.pop("contract", None)


def mut_stale_ruleset(root, manifest, meta):
    contract = manifest.setdefault("contract", {})
    contract["ruleset_version"] = "0.0.0"


MUTATIONS = {
    "squash": mut_squash,
    "overlap": mut_overlap,
    "contrast": mut_contrast,
    "drop-layer": mut_drop_layer,
    "license": mut_license,
    "overflow": mut_overflow,
    "drop-contract": mut_drop_contract,
    "stale-ruleset": mut_stale_ruleset,
}


def render_case(case, recipe, catalog, out_dir):
    name = json.loads(recipe.read_text())["name"]
    run(
        [
            SCRIPTS / "render_recipe.py",
            "--recipe",
            recipe,
            "--style",
            ROOT / "styles" / f"{case['style']}.json",
            "--catalog",
            catalog,
            "--tokens",
            TOKENS,
            "--out",
            out_dir,
            "--breakpoint",
            case["breakpoint"],
            *(["--dark"] if case["theme"] == "dark" else []),
        ]
    )
    svg = out_dir / f"{name}.svg"
    manifest = out_dir / f"{name}.manifest.json"
    return svg, manifest


def prepare_case(case, cache, recipe, catalog, recipe_key):
    key = (recipe_key, case["style"], case["breakpoint"], case["theme"])
    if key not in cache:
        target = WORK / "_base" / f"{Path(recipe_key).stem}-{case['style']}-{case['breakpoint']}-{case['theme']}"
        if target.exists():
            shutil.rmtree(target)
        cache[key] = render_case(case, recipe, catalog, target)

    svg, manifest = cache[key]
    if not case["mutations"]:
        return svg, manifest

    out_dir = WORK / case["id"]
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    shutil.copy(svg, out_dir / svg.name)
    shutil.copy(manifest, out_dir / manifest.name)
    target_svg = out_dir / svg.name
    target_manifest = out_dir / manifest.name

    root = ET.parse(target_svg).getroot()
    data = json.loads(target_manifest.read_text())
    meta = {"svg": svg, "case": case}
    for name in case["mutations"]:
        if name not in MUTATIONS:
            raise SystemExit(f"{case['id']}: 알 수 없는 mutation '{name}'")
        MUTATIONS[name](root, data, meta)
    target_svg.write_text(ET.tostring(root, encoding="unicode"))
    target_manifest.write_text(json.dumps(data, indent=4, ensure_ascii=False) + "\n")
    return target_svg, target_manifest


def collect(config):
    catalog = ROOT / config["catalog"]
    recipes, cache, results = {}, {}, {}
    for case in config["cases"]:
        recipe_path = ROOT / case.get("recipe", config["base_recipe"])
        if recipe_path not in recipes:
            recipes[recipe_path] = build_recipe(WORK / "_recipe" / recipe_path.stem, recipe_path, catalog)
        svg, manifest = prepare_case(case, cache, recipes[recipe_path], catalog, str(recipe_path.relative_to(ROOT)))
        verdict = lint(svg, manifest, TOKENS)
        results[case["id"]] = {
            "expect": case["expect"],
            "verdict": verdict["verdict"],
            "rules": sorted({f["rule"] for f in verdict["findings"]}),
            "contract": verdict["contract"],
        }
        print(
            f"  {case['id']:28s} {verdict['verdict']:4s} (기대 {case['expect']}) {' '.join(results[case['id']]['rules']) or '-'}",
            file=sys.stderr,
        )
    sample = next(iter(results.values()))["contract"]
    return {
        "schema": 1,
        "ruleset_version": sample.get("ruleset_version"),
        "tokens_version": sample.get("tokens_version"),
        "cases": results,
    }


def compare(old, new):
    rows = []
    for case_id in sorted(set(old["cases"]) | set(new["cases"])):
        a, b = old["cases"].get(case_id), new["cases"].get(case_id)
        if not a:
            rows.append((case_id, "added", "-", ""))
        elif not b:
            rows.append((case_id, "removed", "-", ""))
        elif a["verdict"] != b["verdict"]:
            rows.append((case_id, "verdict", f"{a['verdict']}→{b['verdict']}", ""))
        elif a["rules"] != b["rules"]:
            added = sorted(set(b["rules"]) - set(a["rules"]))
            gone = sorted(set(a["rules"]) - set(b["rules"]))
            note = " ".join(filter(None, [f"+{','.join(added)}" if added else "", f"-{','.join(gone)}" if gone else ""]))
            rows.append((case_id, "rules", "", note))
    return rows


def main():
    ap = argparse.ArgumentParser(description="판정 골든셋")
    ap.add_argument("--update", action="store_true", help="현재 판정을 기준선으로 저장")
    ap.add_argument("--cases", default=str(CASES))
    ap.add_argument("--baseline", default=str(BASELINE))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    config = json.loads(Path(args.cases).read_text())
    expected_ruleset = None
    baseline_path = Path(args.baseline)
    if baseline_path.is_file() and not args.update:
        expected_ruleset = json.loads(baseline_path.read_text()).get("ruleset_version")

    print(f"판정 골든: {len(config['cases'])}케이스", file=sys.stderr)
    new = collect(config)
    if expected_ruleset and expected_ruleset != new["ruleset_version"]:
        print(
            f"룰셋이 바뀌었습니다: {expected_ruleset} → {new['ruleset_version']}. 판정이 달라지는 것이 의도라면 --update로 기준선을 갱신하세요.",
            file=sys.stderr,
        )

    mismatched = [(case_id, row["expect"], row["verdict"]) for case_id, row in new["cases"].items() if row["expect"] != row["verdict"]]

    if args.update:
        baseline_path.write_text(json.dumps(new, indent=4, ensure_ascii=False) + "\n")
        print(f"기준선 저장: {baseline_path} ({len(new['cases'])}케이스)")

    rows = []
    if baseline_path.is_file() and not args.update:
        rows = compare(json.loads(baseline_path.read_text()), new)

    if args.json:
        print(
            json.dumps(
                {"cases": new["cases"], "drift": [dict(zip(("case", "kind", "change", "note"), r)) for r in rows], "expect_mismatch": mismatched},
                indent=4,
                ensure_ascii=False,
            )
        )
    else:
        for case_id, kind, change, note in rows:
            print(f"{case_id:32s} {kind:8s} {change:18s} {note}")
        for case_id, expect, actual in mismatched:
            print(f"기대 불일치 {case_id}: 기대 {expect} · 실제 {actual}")

    if mismatched:
        print("\n케이스 기대값과 판정이 다릅니다. 룰 또는 케이스 기대값을 확인하세요.")
        return 1
    if rows:
        print(f"\n기준선과 다름: {len(rows)}케이스. 의도된 변경이면 --update로 갱신하세요.")
        return 1
    if not args.update:
        print(f"기준선과 동일 ({len(new['cases'])}케이스, ruleset {new['ruleset_version']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
