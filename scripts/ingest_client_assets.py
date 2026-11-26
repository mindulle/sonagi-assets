#!/usr/bin/env python3
"""클라이언트 자산(사진·마크·목업)을 카탈로그에 인제스트한다.

카탈로그는 UI 컴포넌트·폰트가 대부분이라 홈페이지 컴프에 쓸 우리 사진·마크가
없다. 이 스크립트는 로컬 폴더를 라이브러리(`clients/<brand>/<category>/`)에
복사하고 catalog.json 끝에 항목을 덧붙인다.

원칙:

- 기존 항목은 절대 고치거나 지우지 않는다(append only).
- id는 파일 내용 sha256이다. 같은 바이트는 어디서 왔든 같은 id가 된다.
- 같은 id가 다른 브랜드/카테고리로 이미 있으면 덮어쓰지 않고 실패한다.
- 라이선스는 `owned`(직접 보유) 또는 `given`(고객 제공)만 받는다.
  둘 다 `license_scope=public`, `origin=client`가 된다.
- `blocked`로 판정되는 라이선스는 인제스트 단계에서 거부한다.

사용::

    scripts/ingest_assets.sh --src ./photos --brand mindulle \\
        --category photo --license owned --apply

`--apply` 없이는 계획만 출력한다(dry-run).
"""

import argparse
import collections
import datetime
import hashlib
import json
import os
import re
import shutil
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from license_policy import SCOPE_PUBLIC, scope_for_license  # noqa: E402

# 렌더러가 실제로 읽을 수 있는 형식만 받는다. PDF·WebP는 슬롯에 넣을 수 없다.
SUPPORTED = {
    ".svg": "vector",
    ".png": "raster",
    ".jpg": "raster",
    ".jpeg": "raster",
}
CLIENT_LICENSES = {
    "owned": "client-owned",
    "given": "client-given",
}
KINDS = ("illustration", "icon")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SVG_GROUP_RE = re.compile(rb"<g[\s>]")


class IngestError(Exception):
    """인제스트를 중단해야 하는 입력·상태 오류."""


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slugify(value):
    """파일 이름을 카탈로그 name에 쓸 수 있는 ASCII 슬러그로 바꾼다."""
    normalized = unicodedata.normalize("NFKD", value or "")
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", normalized).strip("-._").lower()
    return slug or "asset"


def asset_name(brand, path, asset_id, taken):
    """`<brand>-<stem>-<ext>` 꼴의 이름. 충돌하면 id 앞 8자리를 붙인다."""
    ext = path.suffix.lstrip(".").lower()
    base = f"{brand}-{slugify(path.stem)}-{ext}"
    if base in taken:
        base = f"{base}-{asset_id[:8]}"
    if base in taken:
        raise IngestError(f"이름을 만들 수 없습니다: {path} (이미 사용 중: {base})")
    return base


def load_catalog(path):
    try:
        catalog = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise IngestError(f"카탈로그가 없습니다: {path}") from exc
    except json.JSONDecodeError as exc:
        raise IngestError(f"카탈로그가 JSON이 아닙니다: {path} ({exc})") from exc
    if not isinstance(catalog, dict) or not isinstance(catalog.get("items"), list):
        raise IngestError(f"카탈로그 구조가 아닙니다(items 배열 없음): {path}")
    return catalog


def _svg_groups(path):
    if path.suffix.lower() != ".svg":
        return None
    try:
        data = path.read_bytes()
    except OSError:
        return None
    return len(SVG_GROUP_RE.findall(data))


def build_item(*, asset_id, name, path, brand, category, license_value, kind):
    ext = path.suffix.lstrip(".").lower()
    fmt = SUPPORTED[f".{ext}"]
    source = f"client:{brand}"
    tags = sorted(
        {
            f"category:{category}",
            f"kind:{kind}",
            f"format:{fmt}",
            f"license:{license_value}",
            "origin:client",
            f"scope:{SCOPE_PUBLIC}",
            "src:client",
            f"set:client-{brand}",
            f"brand:{brand}",
        }
    )
    annotation = json.dumps({"client": brand, "source_file": path.name}, ensure_ascii=False)
    return {
        "id": asset_id,
        "name": name,
        "ext": ext,
        "category": category,
        "topics": [],
        "source": source,
        "dept": [],
        "medium": [],
        "format": fmt,
        "style": [],
        "license": license_value,
        "license_basis": CLIENT_LICENSES[license_value],
        "license_scope": SCOPE_PUBLIC,
        "origin": "client",
        "junk": False,
        "kind": kind,
        "annotation": annotation,
        "brand": brand,
        "tags": tags,
        "path": f"/app/data/clients/{brand}/{category}/{asset_id}.{ext}",
        "bytes": path.stat().st_size,
        "sha256": asset_id,
        "svg_groups": _svg_groups(path),
    }


def _recount(catalog):
    """items에서 파생 가능한 counts만 다시 센다. 나머지 키는 보존한다."""
    items = catalog["items"]
    counts = catalog.setdefault("counts", {})
    by_ext = collections.Counter(item.get("ext") for item in items if item.get("ext"))
    licenses = collections.Counter(item.get("license") for item in items if item.get("license"))
    scopes = collections.Counter(item.get("license_scope") for item in items if item.get("license_scope"))
    junk = [item for item in items if item.get("junk")]
    counts["total"] = len(items)
    counts["real_total"] = len(items) - len(junk)
    counts["by_ext"] = dict(by_ext.most_common())
    counts["license"] = dict(licenses)
    counts["license_scope"] = dict(scopes)
    counts["junk"] = len(junk)
    counts["junk_by_ext"] = dict(collections.Counter(item.get("ext") for item in junk).most_common())
    counts["style_tagged"] = sum(1 for item in items if item.get("style"))
    counts["license_known"] = sum(1 for item in items if item.get("license") in ("cc0", "ofl", "cleared", "owned", "given"))
    counts["with_svg_groups"] = sum(1 for item in items if item.get("svg_groups"))
    counts["missing_file"] = 0  # 파일 존재 여부는 라이브러리가 붙은 호스트에서만 확인한다
    counts["glyph"] = sum(1 for item in items if item.get("kind") == "glyph")
    counts["client"] = sum(1 for item in items if item.get("origin") == "client")


def _atomic_write_json(path, data):
    path = Path(path)
    tmp = path.with_name(f".{path.name}.tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _backup_catalog(path):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = Path(path).with_name(f"{Path(path).name}.bak-client-{stamp}")
    shutil.copyfile(path, backup)
    return backup


def _collect(src, brand, category, license_value, kind, catalog):
    """인제스트 계획을 세운다. (plan, summary, conflicts)"""
    by_id = {item.get("id"): item for item in catalog["items"] if item.get("id")}
    taken_names = {item.get("name") for item in catalog["items"] if item.get("name")}
    plan = []
    conflicts = []
    unsupported = []
    seen_ids = set()
    skipped = 0
    duplicated = 0

    files = sorted(path for path in src.rglob("*") if path.is_file())
    for path in files:
        relative = path.relative_to(src)
        if path.name.startswith("._") or any(part.startswith(".") for part in relative.parts):
            continue
        ext = path.suffix.lower()
        if ext not in SUPPORTED:
            unsupported.append(str(relative))
            continue
        if kind == "icon" and ext != ".svg":
            raise IngestError(f"icon은 SVG만 됩니다: {relative}")

        asset_id = sha256_file(path)
        existing = by_id.get(asset_id)
        if existing is not None:
            same = existing.get("source") == f"client:{brand}" and existing.get("category") == category
            if same:
                skipped += 1
                continue
            conflicts.append(
                f"{relative}: id {asset_id[:12]}… 이 이미 있습니다 "
                f"(source={existing.get('source')}, category={existing.get('category')}, name={existing.get('name')})"
            )
            continue

        # 같은 폴더 안에서 바이트가 같은 파일(예: dark/light 심볼)은 한 항목으로 센다.
        if asset_id in seen_ids:
            duplicated += 1
            continue

        name = asset_name(brand, path, asset_id, taken_names)
        item = build_item(
            asset_id=asset_id,
            name=name,
            path=path,
            brand=brand,
            category=category,
            license_value=license_value,
            kind=kind,
        )
        plan.append((path, item))
        seen_ids.add(asset_id)
        taken_names.add(name)

    summary = {
        "brand": brand,
        "category": category,
        "license": license_value,
        "kind": kind,
        "license_scope": SCOPE_PUBLIC,
        "scanned": len(files),
        "planned": len(plan),
        "names": [item["name"] for _, item in plan],
        "skipped_existing": skipped,
        "skipped_duplicate": duplicated,
        "skipped_unsupported": len(unsupported),
        "unsupported": unsupported,
        "conflicts": conflicts,
    }
    return plan, summary


def ingest(*, src, brand, category, license_value, catalog_path, library_root, kind="illustration", apply=False):
    if not SLUG_RE.match(brand or ""):
        raise IngestError(f"브랜드는 소문자·숫자·하이픈만 됩니다: {brand!r}")
    if not SLUG_RE.match(category or ""):
        raise IngestError(f"카테고리는 소문자·숫자·하이픈만 됩니다: {category!r}")
    if license_value not in CLIENT_LICENSES:
        raise IngestError(f"라이선스는 {', '.join(sorted(CLIENT_LICENSES))}만 됩니다: {license_value!r}")
    if scope_for_license(license_value) != SCOPE_PUBLIC:
        raise IngestError(f"이 라이선스는 public scope가 아닙니다: {license_value}")
    if kind not in KINDS:
        raise IngestError(f"kind는 {', '.join(KINDS)}만 됩니다: {kind!r}")

    src = Path(src).expanduser().resolve()
    if not src.is_dir():
        raise IngestError(f"소스 폴더가 없습니다: {src}")
    catalog_path = Path(catalog_path).expanduser().resolve()
    library_root = Path(library_root).expanduser().resolve()
    catalog = load_catalog(catalog_path)
    plan, summary = _collect(src, brand, category, license_value, kind, catalog)

    if summary["conflicts"]:
        raise IngestError("이미 있는 id와 충돌합니다. 덮어쓰지 않습니다:\n- " + "\n- ".join(summary["conflicts"]))

    summary["apply"] = bool(apply)
    summary["catalog"] = str(catalog_path)
    summary["library_root"] = str(library_root)
    summary["total_before"] = len(catalog["items"])
    summary["total_after"] = len(catalog["items"]) + len(plan)
    if not apply or not plan:
        return summary

    target_dir = library_root / "clients" / brand / category
    target_dir.mkdir(parents=True, exist_ok=True)
    for source_path, item in plan:
        destination = target_dir / f"{item['id']}.{item['ext']}"
        if destination.exists() and sha256_file(destination) != item["id"]:
            raise IngestError(f"대상 파일이 이미 있고 내용이 다릅니다: {destination}")
        if not destination.exists():
            shutil.copyfile(source_path, destination)

    backup = _backup_catalog(catalog_path)
    catalog["items"].extend(item for _, item in plan)
    catalog["generated_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _recount(catalog)
    _atomic_write_json(catalog_path, catalog)
    summary["backup"] = str(backup)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description="클라이언트 자산을 라이브러리·카탈로그에 인제스트")
    parser.add_argument("--src", required=True, help="인제스트할 폴더(하위 폴더 포함)")
    parser.add_argument("--brand", required=True, help="브랜드 슬러그 (예: mindulle)")
    parser.add_argument("--category", required=True, help="카테고리 슬러그 (예: brand-mark, photo, mockup)")
    parser.add_argument("--license", required=True, dest="license_value", choices=sorted(CLIENT_LICENSES))
    parser.add_argument("--kind", default="illustration", choices=KINDS)
    parser.add_argument("--catalog", default="catalog/catalog.json")
    parser.add_argument("--library-root", default="library")
    parser.add_argument("--apply", action="store_true", help="실제로 복사·기록한다(없으면 dry-run)")
    args = parser.parse_args(argv)

    try:
        summary = ingest(
            src=args.src,
            brand=args.brand,
            category=args.category,
            license_value=args.license_value,
            catalog_path=args.catalog,
            library_root=args.library_root,
            kind=args.kind,
            apply=args.apply,
        )
    except IngestError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
