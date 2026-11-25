#!/usr/bin/env python3
"""패키지 입력 계약 검증 — 라벨 스펙 YAML을 렌더러 입력으로 변환한다.

계약 예시: `test_data/package/packaging.example.label.yaml`.

라벨 렌더러(`render_label.py`)가 읽는 형태로 변환하는 `to_label_spec()`도 제공한다.
참여 단계에서는 `size_mm`만 있으면 되고, `.ai` 전개도 파싱은 하지 않는다.

사용::

    packaging_spec.py spec.yaml            # 검사 + 요약
    packaging_spec.py spec.yaml --json     # 기계 판독
"""

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

PACKAGE_TYPES = {"label": 2, "pouch": 3, "box": 3}
SIDES = {"front", "back", "both"}
VISIBILITY = {"public", "secret"}
METHODS = {"offset", "digital"}
FINISH = {"none", "matte", "gloss", "foil", "emboss", "spot-uv"}
BRIEF_SOURCES = {"text", "attachment", "none"}
DELIVERABLES = {"mockup_front", "mockup_side", "pdf_cmyk", "svg", "dieline_pdf"}
CHECKS = [f"P{i:03d}" for i in range(1, 8)]


class SpecError(Exception):
    pass


def _as_list(value, label, errors):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    errors.append(f"{label}는 목록이어야 합니다: {value!r}")
    return []


def validate(data):
    """(errors, warnings)를 돌려준다."""
    errors, warnings = [], []

    if not isinstance(data, dict):
        return ["최상위가 객체가 아닙니다"], []
    if data.get("version") != 1:
        errors.append(f"version은 1이어야 합니다: {data.get('version')!r}")

    product = data.get("product") or {}
    for key in ("brand", "name"):
        if not str(product.get(key) or "").strip():
            errors.append(f"product.{key}가 비어 있습니다")
    barcode = str(product.get("barcode") or "").strip()
    if barcode and not re.fullmatch(r"\d{13}", barcode):
        errors.append(f"product.barcode는 EAN-13(13자리)이어야 합니다: {barcode}")

    package = data.get("package") or {}
    kind = package.get("type")
    if kind not in PACKAGE_TYPES:
        errors.append(f"package.type은 label|pouch|box 중 하나여야 합니다: {kind!r}")
    size = package.get("size_mm")
    if not isinstance(size, list) or not all(isinstance(v, (int, float)) and v > 0 for v in size):
        errors.append(f"package.size_mm은 양수 목록이어야 합니다: {size!r}")
    elif kind in PACKAGE_TYPES and len(size) != PACKAGE_TYPES[kind]:
        errors.append(f"{kind}의 size_mm는 {PACKAGE_TYPES[kind]}개여야 합니다: {size}")
    finish = set(_as_list(package.get("finish"), "package.finish", errors))
    if not finish <= FINISH:
        errors.append(f"package.finish에 알 수 없는 값: {sorted(finish - FINISH)}")

    dieline = data.get("dieline") or {}
    source = dieline.get("source")
    if source not in {"client", "template"}:
        errors.append(f"dieline.source는 client|template 이어야 합니다: {source!r}")
    if source == "client" and not dieline.get("file"):
        errors.append("dieline.source=client면 dieline.file이 필요합니다")
    dsize = dieline.get("size_mm")
    if dsize:
        if not isinstance(dsize, list) or len(dsize) != 2:
            errors.append(f"dieline.size_mm는 [W, H] 여야 합니다: {dsize!r}")
        elif isinstance(size, list) and len(size) >= 2:
            for a, b, axis in ((dsize[0], size[0], "W"), (dsize[1], size[1], "H")):
                if abs(a - b) / max(b, 1) > 0.01:
                    warnings.append(f"dieline.size_mm {axis}가 package.size_mm와 1% 넘게 다릅니다 ({a} vs {b})")

    copy = data.get("copy_source") or {}
    brief = copy.get("brief")
    if brief not in BRIEF_SOURCES:
        errors.append(f"copy_source.brief는 text|attachment|none 이어야 합니다: {brief!r}")
    files = _as_list(copy.get("files"), "copy_source.files", errors)
    if brief == "none" and not files:
        warnings.append("copy_source.brief=none이고 참고 파일도 없습니다 — 문안 없이 디자인하게 됩니다")

    if data.get("sides") not in SIDES:
        errors.append(f"sides는 front|back|both 이어야 합니다: {data.get('sides')!r}")
    if data.get("visibility") not in VISIBILITY:
        errors.append(f"visibility는 public|secret 이어야 합니다: {data.get('visibility')!r}")

    printing = data.get("print") or {}
    if printing.get("method") not in METHODS:
        errors.append(f"print.method는 offset|digital 이어야 합니다: {printing.get('method')!r}")
    for key, minimum in (("bleed_mm", 3), ("safe_mm", 3)):
        value = printing.get(key)
        if not isinstance(value, (int, float)) or value < minimum:
            errors.append(f"print.{key}는 {minimum} 이상이어야 합니다: {value!r}")
    tac = printing.get("tac_limit")
    if tac is not None and not 240 <= float(tac) <= 340:
        warnings.append(f"print.tac_limit가 일반 범위(240~340%)를 벗어납니다: {tac}")
    colors = printing.get("colors")
    if not isinstance(colors, int) or not 1 <= colors <= 8:
        errors.append(f"print.colors는 1~8 정수여야 합니다: {colors!r}")
    spot = _as_list(printing.get("spot"), "print.spot", errors)

    typography = data.get("typography") or {}
    min_pt = typography.get("min_pt")
    if not isinstance(min_pt, (int, float)) or min_pt < 6:
        errors.append(f"typography.min_pt는 6 이상이어야 합니다: {min_pt!r}")

    deliverables = data.get("deliverables") or {}
    for lane in ("contest", "production"):
        values = set(_as_list(deliverables.get(lane), f"deliverables.{lane}", errors))
        unknown = values - DELIVERABLES
        if unknown:
            errors.append(f"deliverables.{lane}에 알 수 없는 값: {sorted(unknown)}")

    audit = data.get("audit") or {}
    checks = _as_list(audit.get("checks"), "audit.checks", errors)
    unknown = set(checks) - set(CHECKS)
    if unknown:
        errors.append(f"audit.checks에 알 수 없는 코드: {sorted(unknown)}")

    if spot and not all(re.fullmatch(r"(PANTONE\s*)?\d{2,4}\s*C?", str(s).upper()) for s in spot):
        warnings.append(f"print.spot 형식이 Pantone 번호 같지 않습니다: {spot}")

    return errors, warnings


def load(path):
    try:
        data = yaml.safe_load(Path(path).read_text())
    except FileNotFoundError as exc:
        raise SpecError(f"스펙이 없습니다: {path}") from exc
    except yaml.YAMLError as exc:
        raise SpecError(f"YAML 파싱 실패: {path} ({exc})") from exc
    return data or {}


def to_label_spec(data):
    """렌더러(render_label.py)가 쓰는 평평한 스펙으로 변환."""
    product = data.get("product") or {}
    package = data.get("package") or {}
    colors = data.get("colors") or {}
    size = package.get("size_mm") or [90, 60]
    return {
        "brand": product.get("brand", ""),
        "product": product.get("name", ""),
        "net": product.get("net", ""),
        "ingredients": product.get("ingredients", ""),
        "origin": product.get("origin", ""),
        "size_mm": [size[0], size[1]],
        "barcode": product.get("barcode") or "8800000000000",
        "colors": colors,
        "type_family": "Archivo, sans-serif",
    }


def main():
    ap = argparse.ArgumentParser(description="패키지 입력 계약 검증")
    ap.add_argument("spec")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        data = load(args.spec)
    except SpecError as exc:
        raise SystemExit(str(exc)) from exc

    errors, warnings = validate(data)
    product = data.get("product") or {}
    package = data.get("package") or {}

    if args.json:
        print(
            json.dumps(
                {
                    "errors": errors,
                    "warnings": warnings,
                    "summary": {
                        "brand": product.get("brand"),
                        "product": product.get("name"),
                        "type": package.get("type"),
                        "size_mm": package.get("size_mm"),
                        "sides": data.get("sides"),
                        "visibility": data.get("visibility"),
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"{product.get('name')} ({package.get('type')}, {package.get('size_mm')}mm)")
        for w in warnings:
            print(f"  경고: {w}")
        for e in errors:
            print(f"  오류: {e}")
        print(f"검사: 오류 {len(errors)} · 경고 {len(warnings)}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
