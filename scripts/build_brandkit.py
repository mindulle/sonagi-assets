"""브랜드 키트 — 로고·팔레트·타이포·규격·인쇄를 하나의 zip으로 묶는다.

브랜드 산출물은 스크립트마다 흩어져 있었다(`render_lockup.py`, `render_spec.py`,
`render_brandsheet.py`, `export_print.py`). 남에게 건넬 때는 네 번 실행하고 폴더를 손으로
합쳐야 했다. 이 빌더는 한 번에 **하나의 인수인계물**을 만든다.

```
brand.json (스펙)
  ├─ logo/    락업·변형 시트 (render_lockup)
  ├─ spec/    클리어 스페이스·작도·최소 크기 (render_spec)
  ├─ color/   palette.json · palette.css (스펙 색)
  ├─ type/    type-scale.json (스펙 타이포)
  ├─ print/   브랜드 시트 PDF (선택: --pdf, 폰트 필요)
  ├─ manifest.json · CREDITS.md
  └─ <name>.zip
```

결정론: 같은 스펙이면 같은 zip 바이트. 매니페스트에 생성 시각을 넣지 않고, zip
엔트리 타임스탬프를 1980-01-01로 고정하고, 파일 목록을 정렬한다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, List

SCRIPTS = Path(__file__).resolve().parent
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
SCHEMA = "sonagi.brandkit/1"
SKIP = "SKIP"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(cmd: List[str]) -> int:
    """하위 렌더러 호출. 실패하면 코드를 그대로 올린다(조용히 넘어가지 않는다)."""
    return subprocess.run([str(part) for part in cmd]).returncode


def palette_of(spec: Dict[str, Any]) -> Dict[str, Any]:
    """스펙의 색을 역할별로 편다. 값은 스펙이 정본이고 여기서 발명하지 않는다."""
    colors = spec.get("colors") or {}
    backgrounds = spec.get("backgrounds") or {}
    return {
        "brand": spec.get("brand"),
        "version": spec.get("version"),
        "colors": {key: colors[key] for key in sorted(colors)},
        "backgrounds": {key: backgrounds[key] for key in sorted(backgrounds)},
        "contrastPartner": {
            "light": {"ink": colors.get("ink"), "bg": backgrounds.get("light")},
            "dark": {"ink": colors.get("paper"), "bg": backgrounds.get("dark")},
        },
    }


def palette_css(palette: Dict[str, Any]) -> str:
    lines = [":root {", f"  /* {palette['brand']} {palette['version']} */"]
    for key, value in palette["colors"].items():
        lines.append(f"  --brand-{key}: {value};")
    for key, value in palette["backgrounds"].items():
        lines.append(f"  --brand-bg-{key}: {value};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def type_scale_of(spec: Dict[str, Any]) -> Dict[str, Any]:
    """타이포는 스펙이 가진 만큼만 적는다. 없는 단계를 지어내지 않는다."""
    typo = spec.get("type") or {}
    scale = spec.get("scale") or {}
    return {
        "brand": spec.get("brand"),
        "wordmark": spec.get("wordmark"),
        "family": typo.get("family"),
        "weight": typo.get("weight"),
        "tracking": typo.get("tracking"),
        "steps": {key: scale[key] for key in sorted(scale)} if scale else {},
    }


def credits_md(spec: Dict[str, Any]) -> str:
    typo = spec.get("type") or {}
    return "\n".join(
        [
            f"# {spec.get('brand')} 브랜드 키트 — CREDITS",
            "",
            f"- 버전: {spec.get('version')}",
            "- 제작: scripts/build_brandkit.py (결정론 산출물 · 생성 시각 없음)",
            f"- 워드마크 서체: {typo.get('family')} {typo.get('weight')} (자간 {typo.get('tracking')})",
            "- 로고 작화: 스펙의 symbol·wordmark 원본을 따른다.",
            "- 재배포·상표 사용 범위는 별도 합의가 우선한다.",
            "",
        ]
    )


def copy_artwork(stage: Path, spec: Dict[str, Any], spec_path: Path) -> List[str]:
    """스펙이 가리키는 원본 아트워크를 logo/로 복사한다.

    폰트로 다시 그린 워드마크와 **원본 벡터는 다르다**. 납품받는 쪽이 실제 로고를
    쓸 수 있도록 원본을 함께 넣는다. 경로는 스펙 파일 기준 상대경로다.
    """
    copied: List[str] = []
    target_dir = stage / "logo"
    target_dir.mkdir(parents=True, exist_ok=True)
    for entry in spec.get("artwork") or []:
        source = Path(entry)
        if not source.is_file():
            source = spec_path.parent / entry
        if not source.is_file():
            continue
        # 스펙이 리포 밖 경로를 가리켜도 파일명만 쓴다(구조 고정)
        (target_dir / source.name).write_bytes(source.read_bytes())
        copied.append(source.name)
    return copied


def build_staging(stage: Path, spec_path: Path, spec: Dict[str, Any], with_pdf: bool) -> Dict[str, Any]:
    """스테이징 폴더에 섹션을 만든다. 반환값은 스킵 사유 기록용."""
    stage.mkdir(parents=True, exist_ok=True)
    skipped: Dict[str, str] = {}

    # 1) 로고 락업 시트
    logo_dir = stage / "logo"
    code = run([sys.executable, SCRIPTS / "render_lockup.py", "--spec", spec_path, "--out", logo_dir])
    if code != 0:
        skipped["logo"] = f"render_lockup exit {code}"

    # 1-1) 원본 아트워크는 렌더 뒤에 복사한다(렌더러가 logo/를 다시 쓰기 때문)
    copy_artwork(stage, spec, spec_path)

    # 2) 규격 도해
    spec_dir = stage / "spec"
    code = run([sys.executable, SCRIPTS / "render_spec.py", "--spec", spec_path, "--out", spec_dir])
    if code != 0:
        skipped["spec"] = f"render_spec exit {code}"

    # 3) 색
    color_dir = stage / "color"
    color_dir.mkdir(parents=True, exist_ok=True)
    palette = palette_of(spec)
    (color_dir / "palette.json").write_text(json.dumps(palette, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    (color_dir / "palette.css").write_text(palette_css(palette), encoding="utf-8")

    # 4) 타이포
    type_dir = stage / "type"
    type_dir.mkdir(parents=True, exist_ok=True)
    (type_dir / "type-scale.json").write_text(
        json.dumps(type_scale_of(spec), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # 5) 인쇄용 브랜드 시트(선택). 폰트가 없으면 실패하는 것이 정상이라 사유를 남긴다.
    if with_pdf:
        pages = stage / "print" / "pages"
        code = run([sys.executable, SCRIPTS / "render_brandsheet.py", "--spec", spec_path, "--out", pages])
        if code == 0:
            pdf_dir = stage / "print"
            code = run(
                [
                    sys.executable,
                    SCRIPTS / "export_recipe.py",
                    "--src",
                    pages,
                    "--out",
                    pdf_dir,
                    "--formats",
                    "pdf",
                    "--pdf-mode",
                    "single",
                    "--pdf-name",
                    "brand-sheet",
                ]
            )
            if code != 0:
                skipped["print"] = f"export_recipe exit {code}(폰트 없음 가능)"
        else:
            skipped["print"] = f"render_brandsheet exit {code}"

    return skipped


def collect_files(stage: Path) -> List[Path]:
    """매니페스트 대상. 정렬해서 zip·해시 순서를 고정한다."""
    ignore = {".DS_Store", "Thumbs.db"}
    return sorted(path for path in stage.rglob("*") if path.is_file() and path.name not in ignore)


def write_manifest(stage: Path, spec: Dict[str, Any], skipped: Dict[str, str]) -> Dict[str, Any]:
    files = []
    for path in collect_files(stage):
        files.append(
            {
                "path": path.relative_to(stage).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    manifest = {
        "schema": SCHEMA,
        "brand": spec.get("brand"),
        "version": spec.get("version"),
        "date": spec.get("date"),
        "skipped": {key: skipped[key] for key in sorted(skipped)},
        "files": files,
        "fileCount": len(files),
    }
    (stage / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def write_zip(stage: Path, target: Path, spec: Dict[str, Any]) -> Path:
    """결정론 zip: 엔트리 정렬 + 고정 타임스탬프 + 고정 권한."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".zip.tmp")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in collect_files(stage):
            info = zipfile.ZipInfo(path.relative_to(stage).as_posix(), date_time=ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    tmp.replace(target)
    return target


def build(spec_path: Path, out_dir: Path, name: str, with_pdf: bool = False) -> Dict[str, Any]:
    spec_path = Path(spec_path).resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    stage = Path(out_dir) / name
    if stage.exists():
        shutil.rmtree(stage)

    skipped = build_staging(stage, spec_path, spec, with_pdf)
    (stage / "CREDITS.md").write_text(credits_md(spec), encoding="utf-8")
    manifest = write_manifest(stage, spec, skipped)
    zip_path = write_zip(stage, Path(out_dir) / f"{name}.zip", spec)
    return {
        "stage": str(stage),
        "zip": str(zip_path),
        "manifest": manifest,
        "zipSha256": sha256_file(zip_path),
        "zipBytes": zip_path.stat().st_size,
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="브랜드 키트 — 하나의 zip으로 묶는다")
    parser.add_argument("--spec", required=True, help="brand.json 경로")
    parser.add_argument("--out", default="out/brandkit")
    parser.add_argument("--name", default="brand-kit")
    parser.add_argument("--pdf", action="store_true", help="브랜드 시트 PDF까지 만든다(폰트 필요)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        result = build(Path(args.spec), Path(args.out), args.name, args.pdf)
    except FileNotFoundError as exc:
        print(f"스펙을 찾을 수 없습니다: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        manifest = result["manifest"]
        print(f"zip  {result['zip']}  ({result['zipBytes']} bytes)")
        print(f"files {manifest['fileCount']} · zip sha256 {result['zipSha256'][:12]}")
        for key in sorted(manifest["skipped"]):
            print(f"skip  {key}: {manifest['skipped'][key]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
