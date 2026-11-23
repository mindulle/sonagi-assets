#!/usr/bin/env python3
"""토큰 두 벌 대조 — `sonagi-assets`와 `mindulle-design-system`이 실제로 같은 색인가.

두 저장소가 각자 토큰을 SSOT라고 부른다.

| 저장소 | 파일 | 테마 이름 |
| --- | --- | --- |
| `sonagi-assets` | `tokens/semantic.json` | `editorial` · `architecture` |
| `mindulle-design-system` | `packages/tokens/tokens/{primitives,semantics}.json` | `light` · `dark` |

이름이 달라서 "같다/다르다"를 눈으로 판정하기 어렵다. 역할을 짝지어 hex와
ΔE(CIE76)를 출력한다. 값을 바꾸지 않는다 — 판단은 사람이 한다.

사용::

    compare_tokens.py
    compare_tokens.py --mds ../mindulle-design-system/packages/tokens --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS_TOKENS = ROOT / "tokens/semantic.json"

DEFAULT_MDS = Path("/home/ubuntu/mindulle-design-system/packages/tokens")

# assets 역할 → MDS semantic 경로 (color.*)
ROLE_MAP = {
    "background": "color.background.base",
    "surface": "color.background.surface",
    "ink": "color.text.primary",
    "text": "color.text.primary",
    "text-secondary": "color.text.secondary",
    "text-muted": "color.text.muted",
    "border": "color.border.default",
    "accent": "color.brand.primary",
    "accent-strong": "color.brand.accent",
}

THEME_MAP = {"editorial": "light", "architecture": "dark"}


def flatten(node, prefix=""):
    out = {}
    if isinstance(node, dict):
        for key, value in node.items():
            if key.startswith("$"):
                continue
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict) and "$value" in value:
                out[path] = value["$value"]
            elif isinstance(value, dict):
                out.update(flatten(value, path))
    return out


def resolve(value, flat):
    if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
        key = value[1:-1]
        if key not in flat:
            raise KeyError(f"참조를 풀 수 없습니다: {value}")
        return resolve(flat[key], flat)
    return value


def load_mds(path: Path):
    primitives = flatten(json.loads((path / "tokens/primitives.json").read_text()))
    semantics = json.loads((path / "tokens/semantics.json").read_text())["semantic"]
    out = {}
    for mode, tree in semantics.items():
        flat = flatten(tree)
        out[mode] = {key: resolve(value, primitives) for key, value in flat.items()}
    return out


def rgb(value):
    raw = value.strip().lstrip("#")
    if len(raw) == 3:
        raw = "".join(c * 2 for c in raw)
    return tuple(int(raw[i : i + 2], 16) / 255 for i in (0, 2, 4))


def lab(value):
    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(c) for c in rgb(value))
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e(a, b):
    return sum((x - y) ** 2 for x, y in zip(lab(a), lab(b))) ** 0.5


def luminance(value):
    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(c) for c in rgb(value))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def compare(mds_path: Path):
    assets = json.loads(ASSETS_TOKENS.read_text())
    mds = load_mds(mds_path)
    rows = []
    for assets_theme, mds_mode in THEME_MAP.items():
        a = assets.get(assets_theme, {})
        b = mds.get(mds_mode, {})
        for role, mds_key in ROLE_MAP.items():
            if role not in a or mds_key not in b:
                continue
            rows.append(
                {
                    "theme": assets_theme,
                    "mds_mode": mds_mode,
                    "role": role,
                    "role_mds": mds_key.split(".", 1)[1],
                    "assets": a[role].lower(),
                    "mds": b[mds_key].lower(),
                    "delta_e": round(delta_e(a[role], b[mds_key]), 1),
                    "contrast_assets": round(contrast(a[role], a["background"]), 2),
                    "contrast_mds": round(contrast(b[mds_key], b["color.background.base"]), 2),
                }
            )
    return rows


def main():
    ap = argparse.ArgumentParser(description="두 토큰 저장소 대조")
    ap.add_argument("--mds", default=str(DEFAULT_MDS))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    mds_path = Path(args.mds)
    if not (mds_path / "tokens/semantics.json").is_file():
        raise SystemExit(f"MDS 토큰이 없습니다: {mds_path}")

    rows = compare(mds_path)
    if args.json:
        print(json.dumps(rows, indent=4, ensure_ascii=False))
        return 0

    print(f"{'theme':12s} {'role':16s} {'assets':9s} {'mds':9s} {'ΔE':>6s} {'대비(a)':>7s} {'대비(m)':>7s}")
    same, near, far = 0, 0, 0
    for row in rows:
        mark = "=" if row["delta_e"] < 0.5 else ("~" if row["delta_e"] < 3 else "≠")
        if mark == "=":
            same += 1
        elif mark == "~":
            near += 1
        else:
            far += 1
        print(
            f"{row['theme']:12s} {row['role']:16s} {row['assets']:9s} {row['mds']:9s} "
            f"{row['delta_e']:6.1f}{mark} {row['contrast_assets']:7.2f} {row['contrast_mds']:7.2f}"
        )
    print(f"\n같음 {same} · 근접 {near} · 다름 {far} (총 {len(rows)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
