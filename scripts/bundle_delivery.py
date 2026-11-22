#!/usr/bin/env python3
"""납품 번들을 만든다: 파일 정리 + index.html + CREDITS + zip.

```
delivery/<name>/
├─ index.html        미리보기(스크린별 PNG + 다운로드 링크)
├─ svg/ pdf/ png/ webp/
├─ CREDITS.md        자산 출처·고지 통합
├─ export.json       해시·게이트 결과
└─ README.md
```

사용::

    bundle_delivery.py --src dist --out delivery/landing-v2 --name "Atelier Landing"
"""

import argparse
import json
import shutil
import zipfile
from pathlib import Path

IMAGE_EXT = (".png", ".webp", ".jpg")
GROUPS = {"svg": ".svg", "pdf": ".pdf", "png": "@2x.png", "webp": ".webp"}


def collect(src):
    files = sorted(p for p in Path(src).rglob("*") if p.is_file())
    screens = {}
    for f in files:
        name = f.name
        for group, suffix in GROUPS.items():
            if name.endswith(suffix) and not name.endswith(".manifest.json"):
                stem = name[: -len(suffix)]
                screens.setdefault(stem, {})[group] = f
                break
    screens = {k: v for k, v in screens.items() if "svg" in v}
    return screens, files


def load_manifests(src):
    out = {}
    for f in Path(src).glob("*.manifest.json"):
        out[f.name.replace(".manifest.json", "")] = json.loads(f.read_text())
    return out


def merge_assets(manifests):
    seen = {}
    for m in manifests.values():
        for a in m.get("assets", []):
            seen.setdefault((a["name"], a["origin"], a["license"]), a)
    return [seen[k] for k in sorted(seen)]


def credits_md(manifests):
    assets = merge_assets(manifests)
    lines = ["# Credits", "", "| 자산 | 종류 | 라이선스 | 출처 | 범위 |", "| --- | --- | --- | --- | --- |"]
    for a in assets:
        lines.append(f"| {a['name']} | {a['kind']} | {a['license']} | {a['origin']} | {a['scope']} |")
    notes = sorted({n for m in manifests.values() for n in m.get("disclosure", [])})
    lines += ["", "## 고지", ""]
    lines += [f"- {n}" for n in notes] or ["- 없음"]
    if not any(a["origin"] == "generated" for a in assets):
        lines += ["", "AI 생성 자산은 포함되지 않았습니다."]
    return "\n".join(lines) + "\n"


def index_html(name, screens, manifests):
    cards = []
    for stem in sorted(screens):
        g = screens[stem]
        m = manifests.get(stem, {})
        png = g.get("png")
        links = []
        for group, suffix in (("svg", ".svg"), ("pdf", ".pdf"), ("png", "@2x.png"), ("webp", ".webp")):
            if group in g:
                links.append(f'<a href="{group}/{g[group].name}">{suffix.lstrip("@") or group}</a>')
        img = f'<img src="png/{png.name}" alt="{stem}">' if png else ""
        layers = len(m.get("layers", []))
        cards.append(
            f'<figure><figcaption><b>{stem}</b><span>{layers} layers</span></figcaption>{img}<div class="links">{"".join(links)}</div></figure>'
        )
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>{name} — delivery</title>
<style>
:root{{--ink:#161616;--paper:#fbf9f5;--line:#dcd7cc}}
*{{box-sizing:border-box}}
body{{margin:0;padding:40px;background:var(--paper);color:var(--ink);font-family:system-ui,sans-serif}}
h1{{font-size:28px;margin:0 0 4px}}
p.meta{{color:#63635e;font-size:13px;margin:0 0 28px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:24px}}
figure{{margin:0;background:#fff;border:2px solid var(--line);border-radius:8px;overflow:hidden}}
figcaption{{display:flex;justify-content:space-between;padding:12px 14px;border-bottom:1px solid var(--line);font-size:13px}}
figcaption span{{color:#8d8d86}}
img{{display:block;width:100%;height:auto}}
.links{{display:flex;gap:14px;padding:12px 14px;font-size:12px;border-top:1px solid var(--line)}}
a{{color:var(--ink);text-decoration:none;border-bottom:1px solid var(--ink)}}
</style></head><body>
<h1>{name}</h1>
<p class="meta">{len(screens)} screens · SVG source, PDF, PNG @2x, WebP · see CREDITS.md</p>
<div class="grid">{"".join(cards)}</div>
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--name", default="Delivery")
    ap.add_argument("--zip", action="store_true")
    args = ap.parse_args()

    src = Path(args.src)
    out = Path(args.out)
    screens, files = collect(src)
    manifests = load_manifests(src)

    out.mkdir(parents=True, exist_ok=True)
    for group in ("svg", "pdf", "png", "webp"):
        (out / group).mkdir(exist_ok=True)
        for stem, g in screens.items():
            if group in g:
                shutil.copy2(g[group], out / group / g[group].name)
    for f in files:
        if f.name.endswith(".manifest.json"):
            shutil.copy2(f, out / f.name)
    if (src / "export.json").is_file():
        shutil.copy2(src / "export.json", out / "export.json")

    (out / "CREDITS.md").write_text(credits_md(manifests))
    (out / "index.html").write_text(index_html(args.name, screens, manifests))
    (out / "README.md").write_text(
        f"# {args.name}\n\n"
        f"- screens: {', '.join(sorted(screens))}\n"
        "- `svg/` 원본(편집 가능) · `pdf/` 승인용(폰트 임베드) · `png/` 화면용 2x · `webp/` 웹용\n"
        "- `index.html`을 열면 미리보기와 다운로드 링크가 나옵니다\n"
        "- 자산 출처와 라이선스는 `CREDITS.md`\n"
    )

    if args.zip:
        archive = out.with_suffix(".zip")
        # 고정 타임스탬프 + 정렬된 순서 → 같은 내용이면 같은 zip 바이트
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(out.rglob("*")):
                if not p.is_file():
                    continue
                info = zipfile.ZipInfo(str(p.relative_to(out.parent)), date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                z.writestr(info, p.read_bytes())
        print(json.dumps({"bundle": str(out), "zip": str(archive), "screens": len(screens)}, ensure_ascii=False))
    else:
        print(json.dumps({"bundle": str(out), "screens": len(screens)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
