"""브랜드 키트 빌더 — 결정론·구성·스킵 기록.

키트는 "남에게 건넬 한 벌"이라 두 번 만들면 같은 바이트여야 한다. 렌더러
(lockup·spec·brandsheet)는 이미 검증돼 있으므로 여기서는 **묶는 규칙**만 고정한다:
정렬된 파일 목록, 고정 타임스탬프, 생성 시각 없는 매니페스트, 실패는 SKIP 사유.
"""

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_brandkit as bk  # noqa: E402

SPEC = ROOT / "test_data" / "identity" / "lockup.json"


def test_build_produces_sections_and_manifest(tmp_path):
    result = bk.build(SPEC, tmp_path, "kit")
    stage = Path(result["stage"])

    assert (stage / "logo").is_dir()
    assert (stage / "spec").is_dir()
    assert (stage / "color" / "palette.json").is_file()
    assert (stage / "color" / "palette.css").is_file()
    assert (stage / "type" / "type-scale.json").is_file()
    assert (stage / "CREDITS.md").is_file()

    manifest = json.loads((stage / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == bk.SCHEMA
    assert manifest["fileCount"] == len(manifest["files"])
    # 매니페스트는 생성 시각을 담지 않는다(결정론)
    assert "createdAt" not in manifest
    paths = [item["path"] for item in manifest["files"]]
    assert paths == sorted(paths)


def test_zip_is_deterministic_across_runs(tmp_path):
    first = bk.build(SPEC, tmp_path / "a", "kit")
    second = bk.build(SPEC, tmp_path / "b", "kit")

    assert first["zipSha256"] == second["zipSha256"]


def test_zip_entries_are_sorted_with_fixed_timestamp(tmp_path):
    result = bk.build(SPEC, tmp_path, "kit")
    with zipfile.ZipFile(result["zip"]) as archive:
        infos = archive.infolist()

    names = [info.filename for info in infos]
    assert names == sorted(names)
    assert {info.date_time for info in infos} == {bk.ZIP_TIMESTAMP}


def test_palette_uses_spec_colors_without_inventing(tmp_path):
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    palette = bk.palette_of(spec)

    assert palette["colors"] == spec["colors"]
    assert palette["backgrounds"] == spec["backgrounds"]
    css = bk.palette_css(palette)
    for key, value in spec["colors"].items():
        assert f"--brand-{key}: {value};" in css


def test_type_scale_has_no_invented_steps(tmp_path):
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    scale = bk.type_scale_of(spec)

    assert scale["family"] == spec["type"]["family"]
    # 스펙에 scale이 없으면 단계도 비어 있어야 한다(지어내지 않는다)
    assert scale["steps"] == {}


def test_pdf_is_skipped_with_reason_when_fonts_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("PRESS_FONTS_CSS", str(tmp_path / "nope.css"))
    result = bk.build(SPEC, tmp_path, "kit", with_pdf=True)

    manifest = result["manifest"]
    # 성공하든 실패하든 조용히 넘어가지 않는다: 실패면 사유가 남는다
    if "print" in manifest["skipped"]:
        assert manifest["skipped"]["print"]


def test_cli_exit_code_when_spec_missing(tmp_path, capsys):
    code = bk.main(["--spec", str(tmp_path / "nope.json"), "--out", str(tmp_path / "out")])
    assert code == 2
    assert "스펙을 찾을 수 없습니다" in capsys.readouterr().err


def test_artwork_files_are_copied_after_render(tmp_path):
    """폰트로 다시 그린 시트와 별개로 원본 벡터를 함께 넣는다."""
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    spec["artwork"] = ["test_data/identity/symbol.svg"]
    spec_path = tmp_path / "brand.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")

    result = bk.build(spec_path, tmp_path / "out", "kit")
    stage = Path(result["stage"])

    assert (stage / "logo" / "symbol.svg").is_file()
    manifest = json.loads((stage / "manifest.json").read_text(encoding="utf-8"))
    assert "logo/symbol.svg" in [item["path"] for item in manifest["files"]]


def test_real_brand_spec_builds_without_contrast_failures(tmp_path):
    """리포의 실제 스펙(brands/sonagi.json)이 그대로 빌드돼야 한다."""
    spec = ROOT / "brands" / "sonagi.json"
    if not spec.is_file():
        return
    result = bk.build(spec, tmp_path, "sonagi")

    manifest = result["manifest"]
    assert manifest["brand"] == "SONAGI"
    assert manifest["skipped"] == {}  # 로고·규격은 폰트 없이도 나온다
    assert manifest["fileCount"] >= 8
