"""클라이언트 자산 인제스트 — 오프라인 테스트.

카탈로그·라이브러리 모두 tmp_path에 만든다. 실제 /srv나 devops에 붙지 않는다.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import ingest_client_assets as ingest  # noqa: E402
import license_policy  # noqa: E402
import provenance  # noqa: E402

REQUIRED_FIELDS = {
    "id",
    "name",
    "ext",
    "category",
    "topics",
    "source",
    "format",
    "license",
    "license_basis",
    "license_scope",
    "origin",
    "kind",
    "tags",
    "path",
}


def write_catalog(path, items=None):
    catalog = {
        "generated_at": "2026-01-01T00:00:00Z",
        "source_db": "/tmp/asset_hub.db",
        "library_root": "/tmp/library",
        "counts": {
            "total": len(items or []),
            "real_total": len(items or []),
            "by_ext": {"svg": len(items or [])},
            "license": {"mit": len(items or [])},
            "license_scope": {"bundle": len(items or [])},
        },
        "items": items or [],
    }
    path.write_text(json.dumps(catalog, ensure_ascii=False, indent=1), encoding="utf-8")
    return catalog


def existing_item(item_id="OLD-1", name="old-asset"):
    return {
        "id": item_id,
        "name": name,
        "ext": "svg",
        "category": "ui-component",
        "source": "sonagi-legacy",
        "format": "vector",
        "license": "mit",
        "license_basis": "explicit-tag",
        "license_scope": "bundle",
        "origin": "open-source",
        "kind": "asset",
        "tags": ["category:ui-component", "format:vector", "scope:bundle"],
        "path": "/app/data/old.svg",
    }


def make_src(tmp_path, files):
    src = tmp_path / "src"
    src.mkdir()
    for name, data in files.items():
        target = src / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return src


def run_ingest(tmp_path, src, *, brand="acme", category="photo", license_value="owned", apply=True, catalog=None, kind="illustration"):
    catalog_path = catalog or (tmp_path / "catalog" / "catalog.json")
    return ingest.ingest(
        src=src,
        brand=brand,
        category=category,
        license_value=license_value,
        catalog_path=catalog_path,
        library_root=tmp_path / "library",
        kind=kind,
        apply=apply,
    )


def test_id_is_content_hash_and_path_independent(tmp_path):
    one = tmp_path / "one.svg"
    two = tmp_path / "nested" / "two.svg"
    two.parent.mkdir()
    payload = b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>'
    one.write_bytes(payload)
    two.write_bytes(payload)
    different = tmp_path / "different.svg"
    different.write_bytes(payload + b" ")

    assert ingest.sha256_file(one) == ingest.sha256_file(two)
    assert ingest.sha256_file(one) != ingest.sha256_file(different)
    # 이름은 파일명에서 나오지만 id는 내용에서만 나온다
    assert ingest.asset_name("acme", one, "a" * 64, set()) == "acme-one-svg"
    assert ingest.asset_name("acme", two, "a" * 64, set()) == "acme-two-svg"


def test_ingest_appends_client_item_and_copies_file(tmp_path):
    catalog_path = tmp_path / "catalog" / "catalog.json"
    catalog_path.parent.mkdir()
    original = existing_item()
    write_catalog(catalog_path, [original])
    before = json.loads(catalog_path.read_text(encoding="utf-8"))
    src = make_src(tmp_path, {"seal.svg": b"<svg><g/></svg>"})

    summary = run_ingest(tmp_path, src)

    assert summary["planned"] == 1
    assert summary["total_before"] == 1
    assert summary["total_after"] == 2

    after = json.loads(catalog_path.read_text(encoding="utf-8"))
    # 기존 항목은 한 글자도 바뀌지 않는다(append only)
    assert after["items"][0] == before["items"][0]
    item = after["items"][1]
    for field in REQUIRED_FIELDS:
        assert field in item, field
    assert item["license"] == "owned"
    assert item["license_scope"] == "public"
    assert item["origin"] == "client"
    assert item["source"] == "client:acme"
    assert item["category"] == "photo"
    assert item["kind"] == "illustration"
    assert item["sha256"] == item["id"]
    assert item["name"] == "acme-seal-svg"
    assert {"category:photo", "kind:illustration", "format:vector"} <= set(item["tags"])
    assert after["counts"]["total"] == 2
    assert after["counts"]["client"] == 1
    assert after["counts"]["license_scope"]["public"] == 1

    copied = tmp_path / "library" / "clients" / "acme" / "photo" / f"{item['id']}.svg"
    assert copied.is_file()
    assert copied.read_bytes() == src.joinpath("seal.svg").read_bytes()


def test_rerun_is_idempotent_and_keeps_generated_at(tmp_path):
    catalog_path = tmp_path / "catalog" / "catalog.json"
    catalog_path.parent.mkdir()
    write_catalog(catalog_path)
    src = make_src(tmp_path, {"seal.svg": b"<svg><g/></svg>"})

    run_ingest(tmp_path, src)
    first = catalog_path.read_bytes()
    summary = run_ingest(tmp_path, src)

    assert summary["planned"] == 0
    assert summary["skipped_existing"] == 1
    assert catalog_path.read_bytes() == first


def test_duplicate_id_in_other_category_is_rejected(tmp_path):
    catalog_path = tmp_path / "catalog" / "catalog.json"
    catalog_path.parent.mkdir()
    write_catalog(catalog_path)
    src = make_src(tmp_path, {"seal.svg": b"<svg><g/></svg>"})

    run_ingest(tmp_path, src, category="photo")
    snapshot = catalog_path.read_bytes()

    with pytest.raises(ingest.IngestError, match="충돌"):
        run_ingest(tmp_path, src, category="brand-mark")
    assert catalog_path.read_bytes() == snapshot


def test_blocked_license_is_never_produced(tmp_path):
    catalog_path = tmp_path / "catalog" / "catalog.json"
    catalog_path.parent.mkdir()
    write_catalog(catalog_path)
    src = make_src(tmp_path, {"seal.svg": b"<svg/>"})

    with pytest.raises(ingest.IngestError):
        run_ingest(tmp_path, src, license_value="internal-only")
    with pytest.raises(ingest.IngestError):
        run_ingest(tmp_path, src, license_value="commercial")

    # 정책 자체: owned/given은 public, blocked는 그대로 blocked
    assert license_policy.scope_for_license("owned") == license_policy.SCOPE_PUBLIC
    assert license_policy.scope_for_license("given") == license_policy.SCOPE_PUBLIC
    assert license_policy.scope_for_license("internal-only") == license_policy.SCOPE_BLOCKED
    assert provenance.origin_for_license("owned") == provenance.ORIGIN_CLIENT
    assert provenance.scope_for_origin(provenance.ORIGIN_CLIENT) == "public"


def test_dry_run_writes_nothing(tmp_path):
    catalog_path = tmp_path / "catalog" / "catalog.json"
    catalog_path.parent.mkdir()
    write_catalog(catalog_path)
    before = catalog_path.read_bytes()
    src = make_src(tmp_path, {"seal.svg": b"<svg/>"})

    summary = run_ingest(tmp_path, src, apply=False)

    assert summary["planned"] == 1
    assert summary["apply"] is False
    assert catalog_path.read_bytes() == before
    assert not (tmp_path / "library").exists()


def test_name_collision_gets_stable_suffix(tmp_path):
    catalog_path = tmp_path / "catalog" / "catalog.json"
    catalog_path.parent.mkdir()
    other = existing_item(item_id="OTHER-1", name="acme-seal-svg")
    write_catalog(catalog_path, [other])
    src = make_src(tmp_path, {"seal.svg": b"<svg><g/></svg>"})

    run_ingest(tmp_path, src)
    item = json.loads(catalog_path.read_text(encoding="utf-8"))["items"][1]

    assert item["name"].startswith("acme-seal-svg-")
    assert item["name"] != "acme-seal-svg"


def test_identical_bytes_in_one_run_are_counted_once(tmp_path):
    catalog_path = tmp_path / "catalog" / "catalog.json"
    catalog_path.parent.mkdir()
    write_catalog(catalog_path)
    src = make_src(tmp_path, {"dark-symbol.svg": b"<svg><g/></svg>", "light-symbol.svg": b"<svg><g/></svg>"})

    summary = run_ingest(tmp_path, src)

    assert summary["planned"] == 1
    assert summary["skipped_duplicate"] == 1
    assert len(json.loads(catalog_path.read_text(encoding="utf-8"))["items"]) == 1


def test_unsupported_files_are_skipped(tmp_path):
    catalog_path = tmp_path / "catalog" / "catalog.json"
    catalog_path.parent.mkdir()
    write_catalog(catalog_path)
    src = make_src(tmp_path, {"seal.svg": b"<svg/>", "brief.pdf": b"%PDF-1.7"})

    summary = run_ingest(tmp_path, src)

    assert summary["skipped_unsupported"] == 1
    assert summary["planned"] == 1


def test_icon_requires_svg(tmp_path):
    catalog_path = tmp_path / "catalog" / "catalog.json"
    catalog_path.parent.mkdir()
    write_catalog(catalog_path)
    src = make_src(tmp_path, {"mark.png": b"png-bytes"})

    with pytest.raises(ingest.IngestError, match="SVG"):
        run_ingest(tmp_path, src, kind="icon")
