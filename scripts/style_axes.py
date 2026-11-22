#!/usr/bin/env python3
"""스타일을 축(palette/type/geometry/layout)의 조합으로 해석한다.

스타일 파일은 두 형태를 모두 허용한다.

    { "name": "victorian", "palette": "victorian", "type": "cormorant-gowun",
      "geometry": "r2b2", "layout": "center-cards", "ornament": "victorian" }

    { "name": "legacy", "colors": {...}, "geometry": {...}, "type": {...} }  # 기존 형태

축 정의는 `styles/axes.json`에 있고, 축보다 스타일 파일의 명시 값이 우선한다.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AXES_PATH = ROOT / "styles" / "axes.json"
AXIS_KEYS = ("palette", "type", "geometry", "layout", "ornament")


def deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_axes() -> dict:
    return json.loads(AXES_PATH.read_text())


def resolve(spec: dict, axes: dict | None = None) -> dict:
    axes = axes or load_axes()
    out: dict = {}

    palette = spec.get("palette")
    if palette:
        if palette not in axes["palette"]:
            raise SystemExit(f"없는 palette: {palette}")
        colors = axes["palette"][palette].get("colors") or {}
        if colors:
            out["colors"] = dict(colors)

    type_ref = spec.get("type")
    if isinstance(type_ref, str):
        if type_ref not in axes["type"]:
            raise SystemExit(f"없는 type: {type_ref}")
        out["type"] = dict(axes["type"][type_ref])

    geometry_ref = spec.get("geometry")
    if isinstance(geometry_ref, str):
        if geometry_ref not in axes["geometry"]:
            raise SystemExit(f"없는 geometry: {geometry_ref}")
        out["geometry"] = dict(axes["geometry"][geometry_ref])

    layout_ref = spec.get("layout")
    if layout_ref:
        if layout_ref not in axes["layout"]:
            raise SystemExit(f"없는 layout: {layout_ref}")
        for key, value in axes["layout"][layout_ref].items():
            out[key] = value

    ornament = spec.get("ornament")
    if isinstance(ornament, str):
        if ornament and ornament != "none":
            if ornament not in axes.get("ornament", {}):
                raise SystemExit(f"없는 ornament: {ornament}")
            out["ornament"] = dict(axes["ornament"][ornament])
    elif isinstance(ornament, dict):
        out["ornament"] = deep_merge({"motif": "none", "frame": "none"}, ornament)

    # 명시 값이 축을 덮어쓴다
    for key in ("colors", "type", "geometry"):
        if isinstance(spec.get(key), dict):
            out[key] = deep_merge(out.get(key, {}), spec[key])
    for key in ("hero", "features_layout", "header", "illustration_set"):
        if key in spec:
            out[key] = spec[key]

    for key, value in spec.items():
        if key in AXIS_KEYS or key in ("colors", "hero", "features_layout", "header", "illustration_set"):
            continue
        out[key] = value

    return out


def load_style(path: str | Path, axes: dict | None = None) -> dict:
    return resolve(json.loads(Path(path).read_text()), axes)
