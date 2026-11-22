#!/usr/bin/env python3
"""레시피(JSON) + 자산 + 토큰 → 레이어가 살아있는 SVG 1장.

생성 AI를 쓰지 않는다. 같은 레시피·시드는 항상 같은 바이트를 만든다.
출력 SVG는 `<g id="...">` 그룹으로 구성되어 Figma에서 레이어로 풀린다.

사용::

    python3 render_recipe.py --recipe recipes/landing-hero.json \\
        --catalog catalog/catalog.json --out out/

검증:
- 레시피가 참조한 자산이 `scope:bundle`이 아니면 즉시 실패한다
- 참조 자산을 찾지 못하면 실패한다
"""

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

SVG_OPEN = re.compile(r"<svg\b[^>]*>", re.S)
SVG_CLOSE = re.compile(r"</svg>\s*$")
VIEWBOX = re.compile(r'viewBox="([^"]+)"')


def host_path(p):
    if p.startswith("/app/data/"):
        return os.path.join("/srv/sonagi-assets/library", p[len("/app/data/") :])
    return p


STYLE_PROPS = {
    "fill",
    "stroke",
    "stroke-width",
    "stroke-linecap",
    "stroke-linejoin",
    "stroke-miterlimit",
    "fill-rule",
    "clip-rule",
    "opacity",
    "fill-opacity",
    "stroke-opacity",
}


def inline_styles(body, css):
    """Illustrator의 .st0{} 클래스를 요소 속성으로 옮긴다(클래스 충돌 방지)."""
    rules = {}
    for cls, decl in re.findall(r"\.([\w-]+)\s*\{([^}]*)\}", css):
        props = {}
        for part in decl.split(";"):
            if ":" in part:
                k, v = part.split(":", 1)
                if k.strip() in STYLE_PROPS:
                    props[k.strip()] = v.strip()
        if props:
            rules[cls] = props

    def apply(m):
        tag = m.group(0)
        cm = re.search(r'class="([^"]+)"', tag)
        if not cm:
            return tag
        attrs = []
        for cls in cm.group(1).split():
            for k, v in rules.get(cls, {}).items():
                attrs.append(f'{k}="{v}"')
        tag = re.sub(r'\sclass="[^"]*"', "", tag)
        if not attrs:
            return tag
        return tag[:-2] + " " + " ".join(attrs) + tag[-2:] if tag.endswith("/>") else tag

    body = re.sub(r"<[a-zA-Z][^>]*class=\"[^\"]*\"[^>]*>", apply, body)
    return body


def inner_svg(path):
    text = Path(path).read_text(errors="ignore")
    m = SVG_OPEN.search(text)
    if not m:
        return "", "0 0 24 24"
    vb = VIEWBOX.search(m.group(0))
    body = text[m.end() :]
    body = SVG_CLOSE.sub("", body)
    styles = re.findall(r"<style\b.*?</style>", body, flags=re.S)
    css = "\n".join(styles)
    body = re.sub(r"<style\b.*?</style>", "", body, flags=re.S)
    if css:
        body = inline_styles(body, css)
    body = re.sub(r'\sid="[^"]*"', "", body)
    return body, (vb.group(1) if vb else "0 0 24 24")


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Renderer:
    def __init__(self, catalog, tokens, theme, strict=True):
        self.theme = theme
        self.colors = tokens[theme]
        self.strict = strict
        self.items = {}
        # 같은 이름이 여러 팩에 있으므로 세트 우선순위로 고정한다(결정성)
        priority = {"lucide": 0, "tabler": 1, "phosphor": 2, "illlustrations": 3}

        def rank(item):
            sets = [t.split(":", 1)[1] for t in item["tags"] if t.startswith("set:")]
            return min((priority.get(s, 9) for s in sets), default=9)

        for item in sorted(catalog["items"], key=lambda i: (rank(i), i["name"])):
            kinds = {t for t in item["tags"] if t.startswith("kind:")}
            if kinds & {"kind:icon", "kind:illustration"}:
                self.items.setdefault(item["name"], item)
        for item in sorted(catalog["items"], key=lambda i: (rank(i), i["name"])):
            self.items.setdefault(item["name"], item)
        self.used = []
        self.layers = []

    # --- asset -------------------------------------------------------------
    def asset(self, name, kind):
        item = self.items.get(name)
        if not item:
            raise SystemExit(f"asset not found: {name}")
        kinds = {t for t in item["tags"] if t.startswith("kind:")}
        if kind == "icon" and "kind:icon" not in kinds:
            raise SystemExit(f"asset kind mismatch: {name} is not an icon")
        if kind == "illustration" and "kind:illustration" not in kinds:
            raise SystemExit(f"asset kind mismatch: {name} is not an illustration")
        if self.strict and item.get("license_scope") != "bundle":
            raise SystemExit(f"asset blocked: {name} (scope={item.get('license_scope')}, license={item.get('license')})")
        self.used.append(
            {
                "name": name,
                "kind": kind,
                "license": item.get("license"),
                "scope": item.get("license_scope"),
            }
        )
        return item

    def icon(self, name, x, y, size, color=None, stroke=2):
        item = self.asset(name, "icon")
        body, vb = inner_svg(host_path(item["path"]))
        color = color or self.colors["text"]
        return (
            f'<g id="icon-{name}" transform="translate({x} {y}) scale({size / 24:.4f})" '
            f'fill="none" stroke="{color}" stroke-width="{stroke}" '
            f'stroke-linecap="round" stroke-linejoin="round">{body}</g>'
        )

    def illustration(self, name, x, y, w, h):
        item = self.asset(name, "illustration")
        body, vb = inner_svg(host_path(item["path"]))
        return (
            f'<g id="illo-{name}"><svg x="{x}" y="{y}" width="{w}" height="{h}" viewBox="{vb}" preserveAspectRatio="xMidYMid slice">{body}</svg></g>'
        )

    # --- text --------------------------------------------------------------
    def text(self, x, y, content, size, weight, color=None, family="Pretendard", anchor="start", tracking=0):
        color = color or self.colors["text"]
        return (
            f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
            f'fill="{color}" text-anchor="{anchor}" letter-spacing="{tracking}">{esc(content)}</text>'
        )

    # --- blocks ------------------------------------------------------------
    def header(self, block, W):
        parts = [
            self.text(56, 52, block["brand"], 20, 700),
        ]
        x = W - 56
        for label in reversed(block.get("nav", [])):
            parts.append(self.text(x, 52, label, 15, 500, self.colors["text-muted"], anchor="end"))
            x -= 96
        parts.append(f'<line x1="0" y1="88" x2="{W}" y2="88" stroke="{self.colors["border"]}" stroke-width="1"/>')
        return f'<g id="header">{"".join(parts)}</g>'

    def hero(self, block, W, y0):
        c = self.colors
        parts = [
            self.text(56, y0 + 40, block["eyebrow"], 12, 600, c["accent"], family="JetBrains Mono", tracking="2.6"),
            self.text(56, y0 + 108, block["title"], 64, 700, family="NanumSquare"),
            self.text(56, y0 + 186, block["body"], 18, 400, c["text-secondary"], tracking="-0.1"),
        ]
        # CTA
        btn_w = 208
        btn_h = 56
        parts.append(
            f'<g id="cta"><rect x="56" y="{y0 + 232}" width="{btn_w}" height="{btn_h}" rx="6" '
            f'fill="{c["accent"]}"/>'
            + self.text(56 + 28, y0 + 232 + 36, block["cta"], 16, 700, c["accent-ink"])
            + self.icon(block["ctaIcon"], 56 + btn_w - 46, y0 + 232 + 19, 18, c["accent-ink"])
            + "</g>"
        )
        parts.append(self.text(288, y0 + 268, block.get("note", ""), 13, 400, c["text-muted"]))
        parts.append(self.illustration(block["illustration"], W - 56 - 520, y0 + 30, 520, 380))
        return f'<g id="hero">{"".join(parts)}</g>', 500

    def features(self, block, W, y0):
        c = self.colors
        parts = [self.text(56, y0, block["title"], 36, 700)]
        gap = 24
        card_w = (W - 112 - gap * 2) / 3
        for i, item in enumerate(block["items"][:3]):
            x = 56 + i * (card_w + gap)
            y = y0 + 40
            parts.append(
                f'<g id="feature-{i + 1}"><rect x="{x}" y="{y}" width="{card_w}" height="212" rx="8" '
                f'fill="{c["surface"]}" stroke="{c["border"]}" stroke-width="2"/>'
                + self.icon(item["icon"], x + 28, y + 28, 26, c["text"])
                + self.text(x + 28, y + 108, item["title"], 22, 700)
                + self.text(x + 28, y + 146, item["body"], 15, 400, c["text-secondary"])
                + "</g>"
            )
        return f'<g id="features">{"".join(parts)}</g>', 300

    def footer(self, block, W, y):
        c = self.colors
        parts = [
            f'<line x1="56" y1="{y}" x2="{W - 56}" y2="{y}" stroke="{c["border"]}" stroke-width="1"/>',
            self.text(56, y + 40, block.get("left", ""), 12, 400, c["text-muted"]),
            self.text(W - 56, y + 40, block.get("right", ""), 12, 400, c["text-muted"], anchor="end"),
        ]
        return f'<g id="footer">{"".join(parts)}</g>'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", required=True)
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--tokens", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--allow-blocked", action="store_true")
    args = ap.parse_args()

    recipe = json.loads(Path(args.recipe).read_text())
    catalog = json.loads(Path(args.catalog).read_text())
    tokens = json.loads(Path(args.tokens).read_text())

    W = recipe["canvas"]["width"]
    H = recipe["canvas"]["height"]
    r = Renderer(catalog, tokens, recipe["theme"], strict=not args.allow_blocked)

    body = [f'<rect id="background" width="{W}" height="{H}" fill="{r.colors["background"]}"/>']
    y = 88
    for block in recipe["blocks"]:
        kind = block["type"]
        if kind == "header":
            body.append(r.header(block, W))
        elif kind == "hero":
            svg, adv = r.hero(block, W, y + 30)
            body.append(svg)
            y += adv
        elif kind == "features":
            svg, adv = r.features(block, W, y + 30)
            body.append(svg)
            y += adv
        elif kind == "footer":
            body.append(r.footer(block, W, y + 20))
        else:
            raise SystemExit(f"unknown block: {kind}")

    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">' + "".join(body) + "</svg>"
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    name = recipe.get("name", "output")
    svg_path = out / f"{name}.svg"
    svg_path.write_text(svg)

    manifest = {
        "recipe": recipe.get("name"),
        "seed": recipe.get("seed"),
        "theme": recipe["theme"],
        "canvas": recipe["canvas"],
        "output": str(svg_path),
        "sha256": hashlib.sha256(svg.encode()).hexdigest(),
        "layers": re.findall(r'<g id="([^"]+)"', svg),
        "assets": r.used,
        "license_ok": all(a["scope"] == "bundle" for a in r.used),
    }
    (out / f"{name}.manifest.json").write_text(json.dumps(manifest, indent=4, ensure_ascii=False) + "\n")
    print(json.dumps({k: manifest[k] for k in ("recipe", "sha256", "license_ok", "layers")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
