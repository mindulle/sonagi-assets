#!/usr/bin/env python3
"""레시피(JSON) + 스타일 팩 + 자산 + 토큰 → 레이어가 살아있는 SVG 1장.

생성 AI를 쓰지 않는다. 같은 레시피·스타일·시드는 항상 같은 바이트를 만든다.
출력 SVG는 `<g id="...">` 그룹으로 구성되어 Figma에서 레이어로 풀린다.

스타일 팩(`styles/*.json`)이 스킨을 결정한다:
색상·반경·보더·그림자·서체·대소문자·밀도·일러스트 처리·히어로 레이아웃.

사용::

    python3 render_recipe.py --recipe recipes/landing-hero.json \\
        --style styles/brutalist.json --catalog catalog/catalog.json \\
        --tokens tokens/semantic.json --out out/
"""

import argparse
import base64
import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from provenance import disclosure_for, origin_from_tags  # noqa: E402

SVG_OPEN = re.compile(r"<svg\b[^>]*>", re.S)
SVG_CLOSE = re.compile(r"</svg>\s*$")
VIEWBOX = re.compile(r'viewBox="([^"]+)"')

DEFAULT_STYLE = {
    "name": "default",
    "colors": {},
    "geometry": {"radius": 8, "borderWidth": 2, "shadow": "none"},
    "type": {
        "display": "Archivo",
        "sans": "Pretendard",
        "korean": "Pretendard",
        "mono": "JetBrains Mono",
        "scale": 1.0,
        "uppercase": False,
        "tracking": 0,
    },
    "illustration": "color",
    "density": 1.0,
    "hero": "split",
    "features_layout": "cards",
    "header": "rule",
}

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


def deep_merge(base, override):
    out = json.loads(json.dumps(base))
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def host_path(p):
    if p.startswith("/app/data/"):
        return os.path.join("/srv/sonagi-assets/library", p[len("/app/data/") :])
    return p


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

    return re.sub(r'<[a-zA-Z][^>]*class="[^"]*"[^>]*>', apply, body)


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
    def __init__(self, catalog, tokens, theme, style, strict=True):
        self.theme = theme
        self.style = style
        self.colors = dict(tokens[theme])
        self.colors.update(style.get("colors") or {})
        self.strict = strict
        g = style["geometry"]
        self.radius = g["radius"]
        self.border_w = g["borderWidth"]
        self.shadow = g["shadow"]
        t = style["type"]
        self.f_display = t["display"]
        self.f_sans = t["sans"]
        self.f_mono = t["mono"]
        self.f_korean = t.get("korean") or self.f_sans
        self.scale = t["scale"]
        self.upper = t["uppercase"]
        self.tracking = t["tracking"]
        self.density = style["density"]
        self.illustration_mode = style["illustration"]
        self.hero_layout = style.get("hero", "split")
        self.features_layout = style.get("features_layout", "cards")

        self.items = {}
        priority = {"lucide": 0, "tabler": 1, "phosphor": 2, "illlustrations": 3}

        def rank(item):
            sets = [x.split(":", 1)[1] for x in item["tags"] if x.startswith("set:")]
            return min((priority.get(s, 9) for s in sets), default=9)

        for item in sorted(catalog["items"], key=lambda i: (rank(i), i["name"])):
            kinds = {x for x in item["tags"] if x.startswith("kind:")}
            if kinds & {"kind:icon", "kind:illustration"}:
                self.items.setdefault(item["name"], item)
        for item in sorted(catalog["items"], key=lambda i: (rank(i), i["name"])):
            self.items.setdefault(item["name"], item)
        self.used = []

    def case(self, text):
        return text.upper() if self.upper else text

    # --- asset -------------------------------------------------------------
    def asset(self, name, kind):
        item = self.items.get(name)
        if not item:
            raise SystemExit(f"asset not found: {name}")
        kinds = {x for x in item["tags"] if x.startswith("kind:")}
        if kind == "icon" and "kind:icon" not in kinds:
            raise SystemExit(f"asset kind mismatch: {name} is not an icon")
        if kind == "illustration" and "kind:illustration" not in kinds:
            raise SystemExit(f"asset kind mismatch: {name} is not an illustration")
        if self.strict and item.get("license_scope") != "bundle":
            raise SystemExit(f"asset blocked: {name} (scope={item.get('license_scope')}, license={item.get('license')})")
        origin = origin_from_tags(item.get("tags"))
        if origin == "generated" and item.get("license_scope") != "output":
            raise SystemExit(f"generated asset must be scope:output: {name}")
        self.used.append(
            {
                "name": name,
                "kind": kind,
                "license": item.get("license"),
                "scope": item.get("license_scope"),
                "origin": origin,
            }
        )
        return item

    def icon(self, name, x, y, size, color=None, stroke=2):
        item = self.asset(name, "icon")
        body, _vb = inner_svg(host_path(item["path"]))
        color = color or self.colors["text"]
        return (
            f'<g id="icon-{name}" transform="translate({x} {y}) scale({size / 24:.4f})" '
            f'fill="none" stroke="{color}" stroke-width="{stroke}" '
            f'stroke-linecap="round" stroke-linejoin="round">{body}</g>'
        )

    def pick_illustration(self, spec):
        candidates = [spec] if isinstance(spec, str) else list(spec)
        pref = self.style.get("illustration_set")
        if pref:
            for name in candidates:
                item = self.items.get(name)
                if item and f"set:{pref}" in item["tags"]:
                    return name
        return candidates[0]

    def raster_image(self, path, x, y, w, h, clip):
        ext = Path(path).suffix.lower()
        mime = "image/png" if ext == ".png" else "image/jpeg"
        raw = Path(path).read_bytes()
        limit = getattr(self, "embed_max_width", 0)
        if limit and ext in (".jpg", ".jpeg", ".png"):
            try:
                from io import BytesIO

                from PIL import Image

                im = Image.open(BytesIO(raw))
                if im.width > limit:
                    im = im.convert("RGB").resize((limit, int(im.height * limit / im.width)), Image.LANCZOS)
                    buf = BytesIO()
                    im.save(buf, "JPEG", quality=82, optimize=True)
                    raw = buf.getvalue()
                    mime = "image/jpeg"
            except Exception:
                pass
        data = base64.b64encode(raw).decode()
        href = f"data:{mime};base64,{data}"
        return (
            f'<g id="illo-raster" clip-path="url(#{clip})">'
            f'<image x="{x}" y="{y}" width="{w}" height="{h}" preserveAspectRatio="xMidYMid slice" '
            f'href="{href}" xlink:href="{href}"/></g>'
        )

    def illustration(self, spec, x, y, w, h):
        name = self.pick_illustration(spec)
        if self.illustration_mode == "hidden":
            border = self.colors["border"]
            return (
                f'<g id="illo-slot"><rect x="{x}" y="{y}" width="{w}" height="{h}" '
                f'rx="{self.radius}" fill="none" stroke="{border}" '
                f'stroke-width="{self.border_w}" stroke-dasharray="6 8"/></g>'
            )
        item = self.asset(name, "illustration")
        if item.get("ext") in ("jpg", "jpeg", "png"):
            clip = f"clip-{name}"
            clip_def = f'<clipPath id="{clip}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{self.radius}"/></clipPath>'
            return clip_def + self.raster_image(host_path(item["path"]), x, y, w, h, clip)
        body, vb = inner_svg(host_path(item["path"]))
        clip = f"clip-{name}"
        clip_def = f'<clipPath id="{clip}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{self.radius}"/></clipPath>'
        filt = ' filter="url(#mono)"' if self.illustration_mode == "mono" else ""
        return (
            clip_def
            + f'<g id="illo-{name}" clip-path="url(#{clip})"><g{filt}>'
            + f'<svg x="{x}" y="{y}" width="{w}" height="{h}" viewBox="{vb}" '
            + f'preserveAspectRatio="xMidYMid slice">{body}</svg></g></g>'
        )

    # --- text --------------------------------------------------------------
    def text(self, x, y, content, size, weight, color=None, family=None, anchor="start", tracking=None, leading=1.18):
        color = color or self.colors["text"]
        family = family or self.f_sans
        # 라틴 전용 서체에 한글이 오면 Figma에서 글자가 깨진다 → 한글 서체로 교체
        if re.search(r"[가-힣]", str(content)) and family in (self.f_display, self.f_mono):
            family = self.f_korean
        tracking = self.tracking if tracking is None else tracking
        lines = str(content).split("\n")
        head = (
            f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
            f'fill="{color}" text-anchor="{anchor}" letter-spacing="{tracking}">'
        )
        if len(lines) == 1:
            return head + esc(lines[0]) + "</text>"
        dy = round(size * leading, 2)
        spans = [f'<tspan x="{x}" dy="{0 if i == 0 else dy}">{esc(line)}</tspan>' for i, line in enumerate(lines)]
        return head + "".join(spans) + "</text>"

    def card(self, x, y, w, h, fill=None):
        fill = fill or self.colors["surface"]
        parts = []
        if self.shadow == "crisp":
            parts.append(f'<rect x="{x + 6}" y="{y + 6}" width="{w}" height="{h}" rx="{self.radius}" fill="{self.colors["border"]}"/>')
        parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{self.radius}" fill="{fill}" '
            f'stroke="{self.colors["border"]}" stroke-width="{self.border_w}"/>'
        )
        return "".join(parts)

    # --- blocks ------------------------------------------------------------
    def header(self, block, W):
        rule_w = 1 if self.border_w <= 2 else self.border_w
        parts = [self.text(56, 52, self.case(block["brand"]), 20, 700, family=self.f_display)]
        x = W - 56
        for label in reversed(block.get("nav", [])):
            parts.append(self.text(x, 52, self.case(label), 15, 500, self.colors["text-muted"], anchor="end"))
            x -= 96
        if self.style.get("header") == "rule":
            parts.append(f'<line x1="0" y1="88" x2="{W}" y2="88" stroke="{self.colors["border"]}" stroke-width="{rule_w}"/>')
        return f'<g id="header">{"".join(parts)}</g>'

    def hero(self, block, W, y0):
        c = self.colors
        s = self.scale
        if self.hero_layout == "asymmetric":
            return self.hero_asymmetric(block, W, y0)
        if self.hero_layout == "poster":
            return self.hero_poster(block, W, y0)
        if self.hero_layout == "center":
            cx = W / 2
            parts = [
                self.text(cx, y0 + 70, self.case(block["eyebrow"]), 12, 600, c["accent"], family=self.f_mono, anchor="middle", tracking=4),
                self.text(cx, y0 + 170, self.case(block["title"]), 86 * s, 700, family=self.f_display, anchor="middle"),
                self.text(cx, y0 + 240, self.case(block["body"]), 20 * s, 400, c["text-secondary"], anchor="middle"),
            ]
            bw, bh = 240, 64
            bx = cx - bw / 2
            by = y0 + 300
            parts.append(
                f'<g id="cta">{self.card(bx, by, bw, bh, c["accent"])}'
                + self.text(cx, by + 40, self.case(block["cta"]), 16, 700, c["accent-ink"], anchor="middle")
                + "</g>"
            )
            parts.append(self.text(cx, by + 104, self.case(block.get("note", "")), 13, 400, c["text-muted"], anchor="middle"))
            return f'<g id="hero">{"".join(parts)}</g>', 470 * self.density

        size = 64 * s
        lines = block["title"].count("\n") + 1
        title_h = size * 1.12 * lines
        body_y = y0 + 108 + (title_h - size) + 46
        parts = [
            self.text(56, y0 + 40, self.case(block["eyebrow"]), 12, 600, c["accent"], family=self.f_mono, tracking=2.6),
            self.text(56, y0 + 108, self.case(block["title"]), size, 700, family=self.f_display, leading=1.12),
            self.text(56, body_y, self.case(block["body"]), 18 * s, 400, c["text-secondary"]),
        ]
        btn_w, btn_h = 208, 56
        by = body_y + 46
        parts.append(
            f'<g id="cta">{self.card(56, by, btn_w, btn_h, c["accent"])}'
            + self.text(56 + 28, by + 36, self.case(block["cta"]), 16, 700, c["accent-ink"])
            + self.icon(block["ctaIcon"], 56 + btn_w - 46, by + 19, 18, c["accent-ink"])
            + "</g>"
        )
        parts.append(self.text(288, by + 36, self.case(block.get("note", "")), 13, 400, c["text-muted"]))
        parts.append(self.illustration(block["illustration"], W - 56 - 520, y0 + 30, 520, 380))
        return f'<g id="hero">{"".join(parts)}</g>', max(500, by + 160) * self.density

    def hero_asymmetric(self, block, W, y0):
        c = self.colors
        s = self.scale
        size = 84 * s
        lines = block["title"].count("\n") + 1
        title_h = size * 1.12 * lines
        parts = [
            self.illustration(block["illustration"], W - 600, y0 - 20, 600, 470),
            self.text(56, y0 + 150, self.case(block["eyebrow"]), 12, 600, c["accent"], family=self.f_mono, tracking=3.2),
            self.text(56, y0 + 150 + size, self.case(block["title"]), size, 700, family=self.f_display, leading=1.12),
        ]
        body_y = y0 + 150 + size + title_h + 24
        parts.append(self.text(56, body_y, self.case(block["body"]), 17 * s, 400, c["text-secondary"]))
        by = body_y + 42
        bw, bh = 208, 56
        parts.append(
            f'<g id="cta">{self.card(56, by, bw, bh, c["accent"])}'
            + self.text(84, by + 36, self.case(block["cta"]), 16, 700, c["accent-ink"])
            + self.icon(block["ctaIcon"], 56 + bw - 46, by + 19, 18, c["accent-ink"])
            + "</g>"
        )
        parts.append(self.text(288, by + 36, self.case(block.get("note", "")), 13, 400, c["text-muted"]))
        return f'<g id="hero">{"".join(parts)}</g>', max(520, body_y + 120) * self.density

    def hero_poster(self, block, W, y0):
        c = self.colors
        s = self.scale
        h = 600
        panel_w = 660
        size = 68 * s
        lines = block["title"].count("\n") + 1
        title_h = size * 1.06 * lines
        parts = [
            self.illustration(block["illustration"], panel_w, 88, W - panel_w, h),
            f'<rect id="panel" x="0" y="88" width="{panel_w}" height="{h}" fill="{c["background"]}"/>',
            self.text(56, y0 + 90, self.case(block["eyebrow"]), 12, 600, c["accent"], family=self.f_mono, tracking=4),
            self.text(56, y0 + 90 + size, self.case(block["title"]), size, 700, family=self.f_display, leading=1.06),
            self.text(56, y0 + 90 + size + title_h + 34, self.case(block["body"]), 18 * s, 400, c["text-secondary"]),
        ]
        by = y0 + 90 + size + title_h + 84
        bw, bh = 232, 60
        parts.append(
            f'<g id="cta">{self.card(56, by, bw, bh, c["accent"])}'
            + self.text(84, by + 39, self.case(block["cta"]), 16, 700, c["accent-ink"])
            + self.icon(block["ctaIcon"], 56 + bw - 46, by + 21, 18, c["accent-ink"])
            + "</g>"
        )
        parts.append(self.text(56, by + 100, self.case(block.get("note", "")), 13, 400, c["text-muted"]))
        return f'<g id="hero">{"".join(parts)}</g>', h + 40

    def features(self, block, W, y0):
        if self.features_layout == "list":
            return self.features_list(block, W, y0)
        if self.features_layout == "columns":
            return self.features_columns(block, W, y0)
        c = self.colors
        parts = [self.text(56, y0, self.case(block["title"]), 36 * self.scale, 700, family=self.f_display)]
        gap = 24
        card_w = (W - 112 - gap * 2) / 3
        for i, item in enumerate(block["items"][:3]):
            x = 56 + i * (card_w + gap)
            y = y0 + 40
            parts.append(
                f'<g id="feature-{i + 1}">'
                + self.card(x, y, card_w, 212)
                + self.icon(item["icon"], x + 28, y + 28, 26, c["text"])
                + self.text(x + 28, y + 108, self.case(item["title"]), 22, 700, family=self.f_display)
                + self.text(x + 28, y + 146, self.case(item["body"]), 15, 400, c["text-secondary"])
                + "</g>"
            )
        return f'<g id="features">{"".join(parts)}</g>', 300 * self.density

    def features_list(self, block, W, y0):
        c = self.colors
        parts = [self.text(56, y0, self.case(block["title"]), 30 * self.scale, 700, family=self.f_display)]
        for i, item in enumerate(block["items"][:3]):
            y = y0 + 56 + i * 108
            parts.append(f'<g id="feature-{i + 1}">')
            parts.append(self.text(56, y + 30, f"0{i + 1}", 14, 600, c["text-muted"], family=self.f_mono))
            parts.append(self.text(120, y + 30, self.case(item["title"]), 24, 700, family=self.f_display))
            parts.append(self.text(120, y + 62, self.case(item["body"]), 15, 400, c["text-secondary"]))
            parts.append(f'<line x1="56" y1="{y + 84}" x2="{W - 56}" y2="{y + 84}" stroke="{c["border"]}" stroke-width="1"/>')
            parts.append(self.icon(item["icon"], W - 88, y + 8, 22, c["text"]))
            parts.append("</g>")
        return f'<g id="features">{"".join(parts)}</g>', 400 * self.density

    def features_columns(self, block, W, y0):
        c = self.colors
        parts = [self.text(56, y0, self.case(block["title"]), 28 * self.scale, 700, family=self.f_display)]
        gap = 32
        col_w = (W - 112 - gap * 2) / 3
        for i, item in enumerate(block["items"][:3]):
            x = 56 + i * (col_w + gap)
            y = y0 + 48
            parts.append(f'<g id="feature-{i + 1}">')
            parts.append(f'<line x1="{x}" y1="{y}" x2="{x + col_w}" y2="{y}" stroke="{c["border"]}" stroke-width="{self.border_w}"/>')
            parts.append(self.text(x, y + 34, f"0{i + 1} /", 11, 600, c["accent"], family=self.f_mono, tracking=2))
            parts.append(self.text(x, y + 78, self.case(item["title"]), 19, 700, family=self.f_display))
            parts.append(self.text(x, y + 112, self.case(item["body"]), 14, 400, c["text-secondary"], leading=1.5))
            parts.append("</g>")
        return f'<g id="features">{"".join(parts)}</g>', 320 * self.density

    def stats(self, block, W, y0):
        c = self.colors
        gap = 24
        col_w = (W - 112 - gap * 2) / 3
        parts = []
        for i, item in enumerate(block["items"][:3]):
            x = 56 + i * (col_w + gap)
            parts.append(f'<g id="stat-{i + 1}">')
            parts.append(f'<line x1="{x}" y1="{y0}" x2="{x + col_w}" y2="{y0}" stroke="{c["border"]}" stroke-width="{self.border_w}"/>')
            parts.append(self.text(x, y0 + 78 * self.scale, self.case(item["value"]), 56 * self.scale, 700, family=self.f_display))
            parts.append(self.text(x, y0 + 112 * self.scale, self.case(item["label"]), 13, 400, c["text-muted"]))
            parts.append("</g>")
        return f'<g id="stats">{"".join(parts)}</g>', 200 * self.density

    def quote(self, block, W, y0):
        c = self.colors
        size = 36 * self.scale
        parts = [
            '<g id="quote">',
            f'<line x1="56" y1="{y0}" x2="56" y2="{y0 + 150}" stroke="{c["accent"]}" stroke-width="{self.border_w * 2}"/>',
            self.text(96, y0 + 44, self.case(block["text"]), size, 400, family=self.f_display, leading=1.3),
            self.text(96, y0 + 116, self.case(block.get("author", "")), 13, 600, c["text-muted"], family=self.f_mono, tracking=1.6),
        ]
        parts.append("</g>")
        return f"{''.join(parts)}", 210 * self.density

    def logos(self, block, W, y0):
        c = self.colors
        names = block.get("items", [])[:5]
        gap = 24
        col_w = (W - 112 - gap * (len(names) - 1)) / max(1, len(names))
        parts = []
        for i, name in enumerate(names):
            x = 56 + i * (col_w + gap) + col_w / 2
            parts.append(self.text(x, y0 + 40, self.case(name), 18, 700, c["text-faint"], family=self.f_display, anchor="middle", tracking=1.2))
        return f'<g id="logos">{"".join(parts)}</g>', 110 * self.density

    def faq(self, block, W, y0):
        c = self.colors
        parts = [self.text(56, y0, self.case(block.get("title", "자주 묻는 질문")), 30 * self.scale, 700, family=self.f_display)]
        for i, item in enumerate(block["items"][:3]):
            y = y0 + 56 + i * 92
            parts.append(f'<g id="faq-{i + 1}">')
            parts.append(self.text(56, y + 24, self.case(item["q"]), 17, 700, family=self.f_display))
            parts.append(self.text(56, y + 54, self.case(item["a"]), 14, 400, c["text-secondary"]))
            parts.append(f'<line x1="56" y1="{y + 76}" x2="{W - 56}" y2="{y + 76}" stroke="{c["border"]}" stroke-width="1"/>')
            parts.append("</g>")
        return f'<g id="faq">{"".join(parts)}</g>', 340 * self.density

    def cta_band(self, block, W, y0):
        c = self.colors
        h = 220
        parts = [
            f'<g id="cta-band">',
            self.card(56, y0, W - 112, h, c["surface"]),
            self.text(96, y0 + 72, self.case(block.get("eyebrow", "")), 12, 600, c["accent"], family=self.f_mono, tracking=2.6),
            self.text(96, y0 + 118, self.case(block["title"]), 34 * self.scale, 700, family=self.f_display),
            self.text(96, y0 + 152, self.case(block.get("body", "")), 15, 400, c["text-secondary"]),
        ]
        bw, bh = 208, 56
        bx = W - 96 - bw
        by = y0 + 82
        parts.append(f'<g id="cta">{self.card(bx, by, bw, bh, c["accent"])}')
        parts.append(self.text(bx + 28, by + 36, self.case(block["cta"]), 16, 700, c["accent-ink"]))
        parts.append(self.icon(block.get("ctaIcon", "arrow-right"), bx + bw - 46, by + 19, 18, c["accent-ink"]))
        parts.append("</g></g>")
        return "".join(parts), h + 40

    def footer(self, block, W, y):
        c = self.colors
        parts = [
            f'<line x1="56" y1="{y}" x2="{W - 56}" y2="{y}" stroke="{c["border"]}" stroke-width="{1 if self.border_w <= 2 else self.border_w}"/>',
            self.text(56, y + 40, self.case(block.get("left", "")), 12, 400, c["text-muted"], family=self.f_mono),
            self.text(W - 56, y + 40, self.case(block.get("right", "")), 12, 400, c["text-muted"], family=self.f_mono, anchor="end"),
        ]
        return f'<g id="footer">{"".join(parts)}</g>'


def write_credits(path, manifest):
    """납품용 출처·고지 문서."""
    lines = [f"# Credits — {manifest['recipe']}", "", f"- 스타일: `{manifest['style']}`", ""]
    lines += ["| 자산 | 종류 | 라이선스 | 출처 | 범위 |", "| --- | --- | --- | --- | --- |"]
    for a in manifest["assets"]:
        lines.append(f"| {a['name']} | {a['kind']} | {a['license']} | {a['origin']} | {a['scope']} |")
    lines += ["", "## 고지", ""]
    for note in manifest["disclosure"]:
        lines.append(f"- {note}")
    if not any(a["origin"] == "generated" for a in manifest["assets"]):
        lines += ["", "AI 생성 자산은 포함되지 않았습니다."]
    path.write_text("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", required=True)
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--tokens", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--style", default=None, help="styles/*.json")
    ap.add_argument("--allow-blocked", action="store_true")
    ap.add_argument("--force-height", type=int, default=0, help="프레임 고정 높이(0이면 무시)")
    ap.add_argument("--embed-max-width", type=int, default=1200, help="래스터 임베드 최대 폭(0=원본)")
    args = ap.parse_args()

    recipe = json.loads(Path(args.recipe).read_text())
    catalog = json.loads(Path(args.catalog).read_text())
    tokens = json.loads(Path(args.tokens).read_text())

    style_path = args.style or recipe.get("style")
    style = DEFAULT_STYLE
    if style_path:
        style = deep_merge(DEFAULT_STYLE, json.loads(Path(style_path).read_text()))

    W = recipe["canvas"]["width"]
    H = recipe["canvas"]["height"]
    auto_height = (H == "auto" or bool(style.get("auto_height"))) and args.force_height == 0
    if args.force_height:
        H = args.force_height
    theme = style.get("theme") or recipe["theme"]
    r = Renderer(catalog, tokens, theme, style, strict=not args.allow_blocked)
    r.embed_max_width = args.embed_max_width

    body = [f'<rect id="background" width="{W}" height="{H}" fill="{r.colors["background"]}"/>']
    body.append('<defs><filter id="mono"><feColorMatrix type="saturate" values="0"/></filter></defs>')
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
        elif kind == "cta":
            svg, adv = r.cta_band(block, W, y + 30)
            body.append(svg)
            y += adv
        elif kind == "stats":
            svg, adv = r.stats(block, W, y + 30)
            body.append(svg)
            y += adv
        elif kind == "quote":
            svg, adv = r.quote(block, W, y + 30)
            body.append(svg)
            y += adv
        elif kind == "logos":
            svg, adv = r.logos(block, W, y + 30)
            body.append(svg)
            y += adv
        elif kind == "faq":
            svg, adv = r.faq(block, W, y + 30)
            body.append(svg)
            y += adv
        elif kind == "footer":
            body.append(r.footer(block, W, y + 20))
        else:
            raise SystemExit(f"unknown block: {kind}")

    if auto_height:
        H = int(y + 110)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
        + "".join(body)
        + "</svg>"
    )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    name = recipe.get("name", "output")
    svg_path = out / f"{name}.svg"
    svg_path.write_text(svg)

    manifest = {
        "recipe": recipe.get("name"),
        "style": style.get("name"),
        "seed": recipe.get("seed"),
        "theme": theme,
        "canvas": {"width": W, "height": H},
        "output": str(svg_path),
        "sha256": hashlib.sha256(svg.encode()).hexdigest(),
        "layers": re.findall(r'<g id="([^"]+)"', svg),
        "assets": r.used,
        "license_ok": all(a["scope"] == "bundle" for a in r.used),
        "disclosure": sorted({disclosure_for(a["origin"]) for a in r.used}),
    }
    (out / f"{name}.manifest.json").write_text(json.dumps(manifest, indent=4, ensure_ascii=False) + "\n")
    write_credits(out / f"{name}-CREDITS.md", manifest)
    print(
        json.dumps(
            {"recipe": manifest["recipe"], "style": manifest["style"], "sha256": manifest["sha256"], "license_ok": manifest["license_ok"]},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
