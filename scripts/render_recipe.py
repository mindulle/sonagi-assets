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
import contract  # noqa: E402
import ornament_data  # noqa: E402
from provenance import disclosure_for, origin_from_tags  # noqa: E402
from recipe_schema import RecipeError, normalize  # noqa: E402
from style_axes import load_style  # noqa: E402

SVG_OPEN = re.compile(r"<svg\b[^>]*>", re.S)
SVG_CLOSE = re.compile(r"</svg>\s*$")
VIEWBOX = re.compile(r'viewBox="([^"]+)"')

# 블록 사이 세로 여백(px). 블록 메서드는 자기 내용 높이만 돌려주고,
# 호출부가 이 여백을 더해 다음 블록의 시작 y를 정한다(ASSET-2).
# 30이면 작은 라벨로 끝나는 블록(통계·인용)이 붙어 보여 44로 둔다.
BLOCK_GAP = 44

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


# --- 다크 모드 -------------------------------------------------------------
# 스타일 팩은 라이트 기준 hex를 직접 갖고 있다. 다크는 팔레트를 새로 쓰지 않고
# 역할별 밝기 목표로 변환한다(색상 hue는 유지, 대비는 WCAG로 검증).

DARK_LIGHTNESS = {
    "background": 0.048,
    "surface": 0.105,
    "surface-sunken": 0.028,
    "ink": 0.97,
    "text": 0.95,
    "text-secondary": 0.78,
    "text-muted": 0.62,
    "text-faint": 0.45,
    "border": 0.26,
    "border-strong": 0.66,
    "accent": 0.66,
    "accent-strong": 0.72,
    "success": 0.66,
    "warning": 0.72,
    "danger": 0.64,
    "info": 0.68,
    "terminal": 0.8,
}


def hex_to_rgb(value):
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    return tuple(int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02x}" for c in rgb)


def luminance(value):
    def channel(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in hex_to_rgb(value))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def to_dark(colors):
    import colorsys

    out = dict(colors)
    accent = colors.get("accent")
    for key, value in colors.items():
        if not isinstance(value, str) or not value.startswith("#"):
            continue
        target = DARK_LIGHTNESS.get(key)
        if target is None:
            continue
        r, g, b = hex_to_rgb(value)
        hue, light, sat = colorsys.rgb_to_hls(r, g, b)
        if key in ("accent", "accent-strong") and sat < 0.06 and light < 0.25:
            # 검정 악센트(브루탈리스트·스케치)는 다크에서 흰색이 된다
            target = 0.95
        elif key not in ("accent", "accent-strong") and sat < 0.06:
            sat = 0.0
        nr, ng, nb = colorsys.hls_to_rgb(hue, target, min(sat, 0.85))
        out[key] = rgb_to_hex((nr, ng, nb))
    if accent:
        base = out.get("accent", accent)
        out["accent-ink"] = "#0d0d0d" if luminance(base) > 0.18 else "#f7f7f7"
    return out


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
        self.ornament = style.get("ornament") or {"motif": "none", "frame": "none"}
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
        self.output_only = []
        self._clip_seq = 0
        self.bp = "desktop"
        self.M = 56
        self.K = 1.0
        # 래스터 임베드 방식: embed(기본, data URI) | link(파일 1벌 + 상대 경로)
        self.raster_mode = "embed"
        self.raster_dir = "assets"
        self.out_dir = None
        self.raster_written = {}

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
        scope = item.get("license_scope")
        if scope == "blocked" and self.strict:
            raise SystemExit(f"asset blocked: {name} (scope={scope}, license={item.get('license')})")
        if scope == "output":
            # 결과물에는 쓸 수 있지만 파일 재배포는 금지 → 매니페스트에 남긴다
            self.output_only.append(name)
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
                "annotation": item.get("annotation"),
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

    def raster_href(self, raw, mime):
        """래스터 페이로드의 참조를 만든다.

        embed: data URI(파일 단독으로 열린다)
        link: `assets/<내용해시>-<폭>.jpg` 상대 경로(같은 이미지는 1벌만 쓴다)
        """
        if self.raster_mode != "link":
            return f"data:{mime};base64,{base64.b64encode(raw).decode()}"

        digest = hashlib.sha256(raw).hexdigest()[:12]
        ext = "png" if mime == "image/png" else "jpg"
        name = f"{digest}.{ext}"
        target = Path(self.out_dir or ".") / self.raster_dir / name
        if name not in self.raster_written:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            self.raster_written[name] = len(raw)
        return f"{self.raster_dir}/{name}"

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
        href = self.raster_href(raw, mime)
        # href 하나만 쓴다. xlink:href를 함께 넣으면 같은 base64가 두 번 들어가
        # SVG가 정확히 2배가 된다(ASSET-3). Chromium·Figma 모두 href를 읽는다.
        return (
            f'<g id="illo-raster" clip-path="url(#{clip})">'
            f'<image x="{x}" y="{y}" width="{w}" height="{h}" preserveAspectRatio="xMidYMid slice" '
            f'href="{href}"/></g>'
        )

    def illustration(self, spec, x, y, w, h):
        if not spec:
            return ""
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
            # 같은 자산을 여러 번 쓰면 clipPath id가 겹쳐 두 번째가 사라진다
            self._clip_seq += 1
            clip = f"clip-{name}-{self._clip_seq}"
            clip_def = f'<clipPath id="{clip}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{self.radius}"/></clipPath>'
            return clip_def + self.raster_image(host_path(item["path"]), x, y, w, h, clip)
        body, vb = inner_svg(host_path(item["path"]))
        self._clip_seq += 1
        clip = f"clip-{name}-{self._clip_seq}"
        clip_def = f'<clipPath id="{clip}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{self.radius}"/></clipPath>'
        filt = ' filter="url(#mono)"' if self.illustration_mode == "mono" else ""
        return (
            clip_def
            + f'<g id="illo-{name}" clip-path="url(#{clip})"><g{filt}>'
            + f'<svg x="{x}" y="{y}" width="{w}" height="{h}" viewBox="{vb}" '
            + f'preserveAspectRatio="xMidYMid slice">{body}</svg></g></g>'
        )

    # --- text --------------------------------------------------------------
    @staticmethod
    def measure(text, size):
        """글자 폭을 대략 재서 줄바꿈에 쓴다(CJK 1em, 라틴 0.55em)."""
        total = 0.0
        for ch in str(text):
            if ch == "\n":
                continue
            if ord(ch) >= 0x2E80:
                total += size
            elif ch == " ":
                total += size * 0.3
            else:
                total += size * 0.55
        return total

    def wrap(self, text, size, max_width):
        lines, current = [], ""
        for word in str(text).split(" "):
            trial = (current + " " + word).strip()
            if not current or self.measure(trial, size) <= max_width:
                current = trial
                continue
            lines.append(current)
            current = word
            # 공백 없는 긴 덩어리는 글자 단위로 자른다
            while self.measure(current, size) > max_width:
                cut = max(1, int(len(current) * max_width / max(self.measure(current, size), 1)))
                lines.append(current[:cut])
                current = current[cut:]
        if current:
            lines.append(current)
        return "\n".join(lines) or str(text)

    def wrap_title(self, text, size, max_width):
        """작가가 넣은 줄바꿈은 유지하고, 넘치는 줄만 접는다."""
        return "\n".join(self.wrap(line, size, max_width) for line in str(text).split("\n"))

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
        if self.bp == "mobile":
            m = self.M
            return (
                f'<g id="header">{self.text(m, 44, self.case(block["brand"]), 15, 700, family=self.f_display)}'
                f'<line x1="0" y1="70" x2="{W}" y2="70" stroke="{self.colors["border"]}" stroke-width="1"/></g>'
            )
        parts = [self.text(56, 52, self.case(block["brand"]), 20, 700, family=self.f_display)]
        x = W - 56
        for label in reversed(block.get("nav", [])):
            parts.append(self.text(x, 52, self.case(label), 15, 500, self.colors["text-muted"], anchor="end"))
            x -= 96
        if self.style.get("header") == "rule":
            parts.append(f'<line x1="0" y1="88" x2="{W}" y2="88" stroke="{self.colors["border"]}" stroke-width="{rule_w}"/>')
        return f'<g id="header">{"".join(parts)}</g>'

    def header_height(self):
        """헤더는 페이지 최상단 고정 좌표를 쓴다. 아래 기준선을 돌려준다."""
        return 70 if self.bp == "mobile" else 88

    def footer_height(self):
        return 58 if self.bp == "mobile" else 46

    def render_block(self, kind, block, W, top):
        """블록 하나를 `top`에서 그리고 (svg, 내용 높이)를 돌려준다.

        반환하는 높이는 `top`부터 자기 내용이 끝나는 지점까지다. 블록 사이
        여백은 호출부가 BLOCK_GAP으로 더한다 — 블록이 여백을 직접 만들지 않는다.
        """
        renderers = {
            "hero": self.hero,
            "stats": self.stats_mobile if self.bp == "mobile" else self.stats,
            "features": self.features_mobile if self.bp == "mobile" else self.features,
            "logos": self.logos_mobile if self.bp == "mobile" else self.logos,
            "quote": self.quote,
            "faq": self.faq,
            "table": self.table_mobile if self.bp == "mobile" else self.table,
            "pricing": self.pricing_mobile if self.bp == "mobile" else self.pricing,
            "gallery": self.gallery,
            "cta": self.cta_band_mobile if self.bp == "mobile" else self.cta_band,
        }
        if kind not in renderers:
            raise SystemExit(f"unknown block: {kind}")
        return renderers[kind](block, W, top)

    def hero_mobile(self, block, W, y0):
        c = self.colors
        s = self.scale * self.K
        m = self.M
        big = self.bp == "tablet"
        size = (54 if big else 40) * s
        title = self.wrap_title(self.case(block["title"]), size, W - 2 * m)
        lines = title.count("\n") + 1
        title_h = size * 1.16 * lines
        parts = [
            self.text(m, y0 + 24, self.case(block["eyebrow"]), 10, 600, c["accent"], family=self.f_mono, tracking=2),
            self.text(m, y0 + 24 + size, title, size, 700, family=self.f_display, leading=1.16),
        ]
        body_y = y0 + 24 + 24 + title_h + 16
        parts.append(self.text(m, body_y, self.case(block["body"]), 14 * s, 400, c["text-secondary"], leading=1.6))
        illo_y = body_y + 34
        if block.get("illustration"):
            aspect = 0.58 if big else 0.72
            parts.append(self.illustration(block["illustration"], m, illo_y, W - 2 * m, (W - 2 * m) * aspect))
            by = illo_y + (W - 2 * m) * aspect + 28
        else:
            by = body_y + 34
        bw, bh = W - 2 * m, 52
        parts.append(
            f'<g id="cta">{self.card(m, by, bw, bh, c["accent"])}'
            + self.text(m + 20, by + 34, self.case(block["cta"]), 15, 700, c["accent-ink"])
            + self.icon(block["ctaIcon"], m + bw - 40, by + 16, 18, c["accent-ink"])
            + "</g>"
        )
        parts.append(self.text(m, by + bh + 22, self.case(block.get("note", "")), 11, 400, c["text-muted"]))
        return f'<g id="hero">{"".join(parts)}</g>', by + bh + 26 - y0

    def hero(self, block, W, y0):
        c = self.colors
        s = self.scale
        if self.bp in ("mobile", "tablet"):
            return self.hero_mobile(block, W, y0)
        if not block.get("illustration"):
            return self.hero_plain(block, W, y0)
        if self.hero_layout == "asymmetric":
            return self.hero_asymmetric(block, W, y0)
        if self.hero_layout == "poster":
            return self.hero_poster(block, W, y0)
        if self.hero_layout == "split-reverse":
            return self.hero_split_reverse(block, W, y0)
        if self.hero_layout == "center":
            cx = W / 2
            size = 86 * s
            lines = block["title"].count("\n") + 1
            title_y = y0 + 170
            # 제목이 두 줄이면 본문·CTA를 그만큼 내린다(고정 좌표면 겹친다)
            body_y = title_y + (lines - 1) * size * 1.08 + 70
            parts = [
                self.text(cx, y0 + 70, self.case(block["eyebrow"]), 12, 600, c["accent"], family=self.f_mono, anchor="middle", tracking=4),
                self.text(cx, title_y, self.case(block["title"]), size, 700, family=self.f_display, anchor="middle"),
                self.text(cx, body_y, self.case(block["body"]), 20 * s, 400, c["text-secondary"], anchor="middle"),
            ]
            bw, bh = 240, 64
            bx = cx - bw / 2
            by = body_y + 60
            parts.append(
                f'<g id="cta">{self.card(bx, by, bw, bh, c["accent"])}'
                + self.text(cx, by + 40, self.case(block["cta"]), 16, 700, c["accent-ink"], anchor="middle")
                + "</g>"
            )
            parts.append(self.text(cx, by + 104, self.case(block.get("note", "")), 13, 400, c["text-muted"], anchor="middle"))
            return f'<g id="hero">{"".join(parts)}</g>', by + 110 - y0

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
        return f'<g id="hero">{"".join(parts)}</g>', max(by + btn_h, y0 + 410) + 4 - y0

    def hero_split_reverse(self, block, W, y0):
        """글은 오른쪽, 그림은 왼쪽. split의 거울상."""
        c = self.colors
        s = self.scale
        col_w = 520
        tx = 56 + col_w + 40
        size = 64 * s
        lines = block["title"].count("\n") + 1
        title_h = size * 1.12 * lines
        body_y = y0 + 108 + (title_h - size) + 46
        parts = [
            self.text(tx, y0 + 40, self.case(block["eyebrow"]), 12, 600, c["accent"], family=self.f_mono, tracking=2.6),
            self.text(tx, y0 + 108, self.case(block["title"]), size, 700, family=self.f_display, leading=1.12),
            self.text(tx, body_y, self.case(block["body"]), 18 * s, 400, c["text-secondary"]),
        ]
        btn_w, btn_h = 208, 56
        by = body_y + 46
        parts.append(
            f'<g id="cta">{self.card(tx, by, btn_w, btn_h, c["accent"])}'
            + self.text(tx + 28, by + 36, self.case(block["cta"]), 16, 700, c["accent-ink"])
            + self.icon(block["ctaIcon"], tx + btn_w - 46, by + 19, 18, c["accent-ink"])
            + "</g>"
        )
        parts.append(self.text(tx + btn_w + 24, by + 36, self.case(block.get("note", "")), 13, 400, c["text-muted"]))
        parts.append(self.illustration(block["illustration"], 56, y0 + 30, 520, 380))
        return f'<g id="hero">{"".join(parts)}</g>', max(by + btn_h, y0 + 410) + 4 - y0

    def hero_plain(self, block, W, y0):
        c = self.colors
        s = self.scale
        m = self.M
        if self.hero_layout == "center":
            cx = W / 2
            size = 76 * s
            lines = block["title"].count("\n") + 1
            title_y = y0 + 196
            body_y = title_y + (lines - 1) * size * 1.12 + 60
            bw, bh = 232, 58
            by = body_y + 44
            parts = [
                '<g id="hero">',
                self.text(cx, y0 + 96, self.case(block.get("eyebrow", "")), 11, 600, c["accent"], family=self.f_mono, anchor="middle", tracking=3.2),
                self.text(cx, title_y, self.case(block["title"]), size, 700, family=self.f_display, anchor="middle", leading=1.12),
                self.text(cx, body_y, self.case(block["body"]), 17 * s, 400, c["text-secondary"], anchor="middle", leading=1.55),
                f'<g id="cta">{self.card(cx - bw / 2, by, bw, bh, c["accent"])}'
                + self.text(cx, by + 37, self.case(block["cta"]), 15, 700, c["accent-ink"], anchor="middle")
                + "</g>",
                self.text(cx, by + bh + 32, self.case(block.get("note", "")), 11, 400, c["text-muted"], anchor="middle"),
                "</g>",
            ]
            return "".join(parts), by + bh + 38 - y0
        size = 84 * s
        lines = block["title"].count("\n") + 1
        body_y = y0 + 140 + size + (lines - 1) * size * 1.12 + 40
        parts = [
            '<g id="hero">',
            self.text(m, y0 + 140, self.case(block.get("eyebrow", "")), 12, 600, c["accent"], family=self.f_mono, tracking=3.2),
            self.text(m, y0 + 140 + size, self.case(block["title"]), size, 700, family=self.f_display, leading=1.12),
            self.text(m, body_y, self.case(block["body"]), 18 * s, 400, c["text-secondary"], leading=1.5),
        ]
        bw, bh = 232, 58
        by = body_y + 46
        parts.append(
            f'<g id="cta">{self.card(m, by, bw, bh, c["accent"])}'
            + self.text(m + 26, by + 37, self.case(block["cta"]), 16, 700, c["accent-ink"])
            + self.icon(block["ctaIcon"], m + bw - 44, by + 20, 18, c["accent-ink"])
            + "</g>"
        )
        parts.append(self.text(m + bw + 24, by + 37, self.case(block.get("note", "")), 13, 400, c["text-muted"]))
        parts.append("</g>")
        return "".join(parts), by + bh + 4 - y0

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
        return f'<g id="hero">{"".join(parts)}</g>', max(y0 + 450, by + bh + 4) - y0

    def hero_poster(self, block, W, y0):
        c = self.colors
        s = self.scale
        h = 600
        panel_w = 660
        size = 68 * s
        lines = block["title"].count("\n") + 1
        title_h = size * 1.06 * lines
        parts = [
            self.illustration(block["illustration"], panel_w, y0, W - panel_w, h),
            f'<rect id="panel" x="0" y="{y0}" width="{panel_w}" height="{h}" fill="{c["background"]}"/>',
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
        return f'<g id="hero">{"".join(parts)}</g>', max(h, by + 106 - y0)

    def features(self, block, W, y0):
        if self.bp == "mobile":
            return self.features_mobile(block, W, y0)
        if self.features_layout == "list":
            return self.features_list(block, W, y0)
        if self.features_layout == "columns":
            return self.features_columns(block, W, y0)
        if self.features_layout == "magazine":
            return self.features_magazine(block, W, y0)
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
                + self.text(
                    x + 28,
                    y + 108,
                    self.wrap(self.case(item["title"]), 22, card_w - 56),
                    22,
                    700,
                    family=self.f_display,
                )
                + self.text(
                    x + 28,
                    y + 146,
                    self.wrap(self.case(item["body"]), 15, card_w - 56),
                    15,
                    400,
                    c["text-secondary"],
                    leading=1.45,
                )
                + "</g>"
            )
        return f'<g id="features">{"".join(parts)}</g>', 252

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
        return f'<g id="features">{"".join(parts)}</g>', 56 + 108 * min(len(block["items"]), 3) - 108 + 84

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
            parts.append(
                self.text(
                    x,
                    y + 112,
                    self.wrap(self.case(item["body"]), 14, col_w),
                    14,
                    400,
                    c["text-secondary"],
                    leading=1.5,
                )
            )
            parts.append("</g>")
        return f'<g id="features">{"".join(parts)}</g>', 194

    def features_magazine(self, block, W, y0):
        """2단 비대칭: 왼쪽 큰 카드 하나 + 오른쪽 작은 카드 둘."""
        c = self.colors
        parts = [self.text(56, y0, self.case(block["title"]), 34 * self.scale, 700, family=self.f_display)]
        items = block["items"][:3]
        gap = 24
        left_w = (W - 112) * 0.58
        right_w = (W - 112) - left_w - gap
        top = y0 + 40
        if items:
            item = items[0]
            parts.append(
                '<g id="feature-1">'
                + self.card(56, top, left_w, 260)
                + self.icon(item["icon"], 56 + 32, top + 36, 30, c["text"])
                + self.text(56 + 32, top + 130, self.case(item["title"]), 26, 700, family=self.f_display)
                + self.text(56 + 32, top + 172, self.case(item["body"]), 16, 400, c["text-secondary"], leading=1.6)
                + "</g>"
            )
        for i, item in enumerate(items[1:], start=2):
            y = top + (i - 2) * 156
            parts.append(
                f'<g id="feature-{i}">'
                + self.card(56 + left_w + gap, y, right_w, 132)
                + self.icon(item["icon"], 56 + left_w + gap + 24, y + 24, 22, c["text"])
                + self.text(56 + left_w + gap + 60, y + 44, self.case(item["title"]), 18, 700, family=self.f_display)
                + self.text(56 + left_w + gap + 60, y + 76, self.case(item["body"]), 13, 400, c["text-secondary"], leading=1.5)
                + "</g>"
            )
        return f'<g id="features">{"".join(parts)}</g>', 40 + 260

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
        return f'<g id="stats">{"".join(parts)}</g>', 112 * self.scale + 10

    def quote(self, block, W, y0):
        c = self.colors
        m = self.M
        size = 36 * self.scale * self.K
        wrapped = self.wrap(self.case(block["text"]), size, W - 2 * m - 48)
        lines = wrapped.count("\n") + 1
        body_h = lines * size * 1.35
        author_y = y0 + 44 + body_h + 14
        parts = [
            '<g id="quote">',
            f'<line x1="{m}" y1="{y0}" x2="{m}" y2="{author_y + 6}" stroke="{c["accent"]}" stroke-width="{self.border_w * 2}"/>',
            self.text(m + 24, y0 + 44, wrapped, size, 400, family=self.f_display, leading=1.35),
            self.text(m + 24, author_y, self.case(block.get("author", "")), 12, 600, c["text-muted"], family=self.f_mono, tracking=1.6),
        ]
        parts.append("</g>")
        return f"{''.join(parts)}", author_y + 6 - y0

    def logos(self, block, W, y0):
        c = self.colors
        names = block.get("items", [])[:5]
        gap = 24
        col_w = (W - 112 - gap * (len(names) - 1)) / max(1, len(names))
        parts = []
        for i, name in enumerate(names):
            x = 56 + i * (col_w + gap) + col_w / 2
            parts.append(self.text(x, y0 + 40, self.case(name), 18, 700, c["text-muted"], family=self.f_display, anchor="middle", tracking=1.2))
        return f'<g id="logos">{"".join(parts)}</g>', 46

    def faq(self, block, W, y0):
        c = self.colors
        m = self.M
        parts = [self.text(m, y0, self.case(block.get("title", "자주 묻는 질문")), 30 * self.scale * self.K, 700, family=self.f_display)]
        for i, item in enumerate(block["items"][:3]):
            y = y0 + 56 + i * 92
            parts.append(f'<g id="faq-{i + 1}">')
            parts.append(self.text(m, y + 24, self.case(item["q"]), 16 * self.K, 700, family=self.f_display))
            parts.append(self.text(m, y + 52, self.case(item["a"]), 13 * self.K, 400, c["text-secondary"], leading=1.5))
            parts.append(f'<line x1="{m}" y1="{y + 76}" x2="{W - m}" y2="{y + 76}" stroke="{c["border"]}" stroke-width="1"/>')
            parts.append("</g>")
        # 항목 수에 맞춰 높이를 잡는다(2개일 때 빈 공간이 남던 문제)
        count = min(len(block["items"]), 3)
        return f'<g id="faq">{"".join(parts)}</g>', count * 92 + 42

    def cta_band(self, block, W, y0):
        c = self.colors
        h = 220
        parts = [
            '<g id="cta-band">',
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
        return "".join(parts), h

    def table(self, block, W, y0):
        c = self.colors
        m = self.M
        k = self.K
        cols = block["columns"] or [""]
        rows = block["rows"]
        n = len(cols)
        width = W - 2 * m
        col_w = width / n
        featured = block.get("featured", 0)
        y = y0
        parts = ['<g id="table">']
        if block.get("title"):
            parts.append(
                self.text(
                    m,
                    y + 30 * self.scale * k,
                    self.case(block["title"]),
                    28 * self.scale * k,
                    700,
                    family=self.f_display,
                )
            )
            y += 58
        header_h = 44
        body_h = header_h + len(rows) * 54
        if featured and 1 <= featured <= n:
            fx = m + (featured - 1) * col_w
            parts.append(f'<rect id="table-featured" x="{fx}" y="{y}" width="{col_w}" height="{body_h}" fill="{c["surface"]}"/>')
        for i, col in enumerate(cols):
            on = featured == i + 1
            parts.append(
                self.text(
                    m + i * col_w + 16,
                    y + 28,
                    self.case(col),
                    11 * k,
                    700 if on else 600,
                    c["accent"] if on else c["text-muted"],
                    family=self.f_mono,
                    tracking=1.6,
                )
            )
        parts.append(
            f'<line x1="{m}" y1="{y + header_h}" x2="{W - m}" y2="{y + header_h}" '
            f'stroke="{c["text"]}" stroke-width="{2 if self.border_w <= 2 else self.border_w}"/>'
        )
        for r, cells in enumerate(rows):
            ry = y + header_h + r * 54
            for i, cell in enumerate(cells[:n]):
                on = featured == i + 1
                parts.append(
                    self.text(
                        m + i * col_w + 16,
                        ry + 34,
                        cell if i else self.case(cell),
                        13 * k,
                        700 if on else (600 if i == 0 else 400),
                        c["text"] if (on or i == 0) else c["text-secondary"],
                        family=self.f_display if i == 0 else None,
                    )
                )
            parts.append(f'<line x1="{m}" y1="{ry + 54}" x2="{W - m}" y2="{ry + 54}" stroke="{c["border"]}" stroke-width="1"/>')
        if block.get("note"):
            parts.append(
                self.text(
                    m,
                    y + header_h + len(rows) * 54 + 22,
                    self.case(block["note"]),
                    11,
                    400,
                    c["text-muted"],
                )
            )
        parts.append("</g>")
        # 표 아래 여백은 남기고 블록 사이 여백은 호출부가 더한다
        return "".join(parts), (y - y0) + body_h + (26 if block.get("note") else 4)

    def table_mobile(self, block, W, y0):
        c = self.colors
        m = self.M
        k = self.K
        cols = block["columns"] or [""]
        rows = block["rows"]
        step = 36 + (len(cols) - 1) * 21
        parts = ['<g id="table">']
        y = y0
        if block.get("title"):
            parts.append(self.text(m, y + 22 * k, self.case(block["title"]), 22 * k, 700, family=self.f_display))
            y += 44
        for r, cells in enumerate(rows):
            ry = y + r * step
            parts.append(self.text(m, ry + 18, self.case(cells[0]), 13.5 * k, 700, family=self.f_display))
            for i, col in enumerate(cols[1:], start=1):
                value = cells[i] if i < len(cells) else ""
                parts.append(self.text(m, ry + 18 + i * 21, f"{col}  {value}", 11 * k, 400, c["text-muted"]))
            parts.append(f'<line x1="{m}" y1="{ry + step - 12}" x2="{W - m}" y2="{ry + step - 12}" stroke="{c["border"]}" stroke-width="1"/>')
        parts.append("</g>")
        return "".join(parts), (y - y0) + len(rows) * step + 2

    def price_card(self, item, x, y, w, h):
        c = self.colors
        featured = item.get("featured")
        bullets = item.get("features", [])
        parts = [
            '<g id="plan">',
            self.card(x, y, w, h, c["surface"] if featured else c["background"]),
        ]
        if featured:
            parts.append(
                f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{self.radius}" fill="none" '
                f'stroke="{c["accent"]}" stroke-width="{max(2, self.border_w)}"/>'
            )
        parts.append(
            self.text(
                x + 20,
                y + 32,
                self.case(item["title"]),
                12,
                700,
                c["accent"] if featured else c["text-muted"],
                family=self.f_mono,
                tracking=1.8,
            )
        )
        parts.append(self.text(x + 20, y + 78, item["price"], 32 * self.scale, 700, family=self.f_display))
        if item.get("period"):
            parts.append(self.text(x + 20, y + 98, item["period"], 11, 400, c["text-muted"]))
        for i, line in enumerate(bullets):
            parts.append(self.text(x + 20, y + 134 + i * 26, f"· {line}", 12.5, 400, c["text-secondary"]))
        bw, bh = w - 40, 40
        by = y + h - 26 - bh
        parts.append(
            '<g id="plan-cta">'
            + self.card(x + 20, by, bw, bh, c["accent"] if featured else c["surface"])
            + self.text(x + 36, by + 26, self.case(item["cta"]), 13, 700, c["accent-ink"] if featured else c["text"])
            + "</g>"
        )
        parts.append("</g>")
        return "".join(parts)

    def pricing(self, block, W, y0):
        m = self.M
        items = block["items"][:3]
        gap = 20
        cols = max(1, len(items))
        card_w = (W - 2 * m - gap * (cols - 1)) / cols
        bullets = max((len(item.get("features", [])) for item in items), default=0)
        h = 134 + bullets * 26 + 66
        parts = ['<g id="pricing">']
        y = y0
        if block.get("title"):
            parts.append(self.text(m, y + 30 * self.scale * self.K, self.case(block["title"]), 28 * self.scale * self.K, 700, family=self.f_display))
            y += 58
        for i, item in enumerate(items):
            parts.append(self.price_card(item, m + i * (card_w + gap), y, card_w, h))
        if block.get("note"):
            parts.append(self.text(m, y + h + 26, self.case(block["note"]), 11, 400, self.colors["text-muted"]))
        parts.append("</g>")
        return "".join(parts), (y - y0) + h + (30 if block.get("note") else 0)

    def pricing_mobile(self, block, W, y0):
        m = self.M
        items = block["items"][:3]
        parts = ['<g id="pricing">']
        y = y0
        if block.get("title"):
            parts.append(self.text(m, y + 22 * self.K, self.case(block["title"]), 22 * self.K, 700, family=self.f_display))
            y += 44
        for item in items:
            bullets = len(item.get("features", []))
            h = 130 + bullets * 26 + 66
            parts.append(self.price_card(item, m, y, W - 2 * m, h))
            y += h + 16
        if block.get("note"):
            parts.append(self.text(m, y + 6, self.case(block["note"]), 11, 400, self.colors["text-muted"]))
            y += 26
        parts.append("</g>")
        return "".join(parts), (y - y0) - 16 + (26 if block.get("note") else 0)

    def gallery(self, block, W, y0):
        c = self.colors
        m = self.M
        names = block["items"][:6]
        cols = 3 if self.bp == "tablet" else 3
        if self.bp == "mobile":
            cols = 2
        cols = min(cols, max(1, len(names)))
        gap = 16
        cell_w = (W - 2 * m - gap * (cols - 1)) / cols
        cell_h = cell_w * 0.78
        rows = (len(names) + cols - 1) // cols
        parts = ['<g id="gallery">']
        y = y0
        if block.get("title"):
            parts.append(self.text(m, y + 30 * self.scale * self.K, self.case(block["title"]), 28 * self.scale * self.K, 700, family=self.f_display))
            y += 58
        for i, name in enumerate(names):
            row, col = divmod(i, cols)
            x = m + col * (cell_w + gap)
            ty = y + row * (cell_h + gap)
            parts.append(self.illustration(name, x, ty, cell_w, cell_h))
        height = rows * cell_h + (rows - 1) * gap
        if block.get("note"):
            parts.append(self.text(m, y + height + 26, self.case(block["note"]), 11, 400, c["text-muted"]))
        parts.append("</g>")
        return "".join(parts), (y - y0) + height + (30 if block.get("note") else 0)

    def features_mobile(self, block, W, y0):
        c = self.colors
        m = self.M
        parts = [self.text(m, y0, self.case(block["title"]), 24 * self.scale, 700, family=self.f_display)]
        for i, item in enumerate(block["items"][:3]):
            y = y0 + 40 + i * 96
            parts.append(f'<g id="feature-{i + 1}">')
            parts.append(self.icon(item["icon"], m, y + 6, 20, c["text"]))
            parts.append(self.text(m + 32, y + 22, self.case(item["title"]), 17, 700, family=self.f_display))
            parts.append(self.text(m + 32, y + 48, self.case(item["body"]), 12.5, 400, c["text-secondary"], leading=1.5))
            parts.append(f'<line x1="{m}" y1="{y + 74}" x2="{W - m}" y2="{y + 74}" stroke="{c["border"]}" stroke-width="1"/>')
            parts.append("</g>")
        return f'<g id="features">{"".join(parts)}</g>', 40 + 96 * (min(len(block["items"]), 3) - 1) + 74

    def stats_mobile(self, block, W, y0):
        c = self.colors
        m = self.M
        parts = []
        for i, item in enumerate(block["items"][:3]):
            y = y0 + i * 92
            parts.append(f'<g id="stat-{i + 1}">')
            parts.append(self.text(m, y + 42, self.case(item["value"]), 38 * self.scale, 700, family=self.f_display))
            parts.append(self.text(m, y + 66, self.case(item["label"]), 12, 400, c["text-muted"]))
            parts.append(f'<line x1="{m}" y1="{y + 84}" x2="{W - m}" y2="{y + 84}" stroke="{c["border"]}" stroke-width="1"/>')
            parts.append("</g>")
        return f'<g id="stats">{"".join(parts)}</g>', 92 * (min(len(block["items"]), 3) - 1) + 84

    def logos_mobile(self, block, W, y0):
        c = self.colors
        m = self.M
        names = block.get("items", [])[:4]
        parts = []
        for i, name in enumerate(names):
            row, col = divmod(i, 2)
            x = m + col * ((W - 2 * m) / 2)
            parts.append(self.text(x, y0 + 24 + row * 34, self.case(name), 13, 700, c["text-muted"], family=self.f_display, tracking=1))
        return f'<g id="logos">{"".join(parts)}</g>', 24 + 34 * ((len(names) - 1) // 2) + 20

    def cta_band_mobile(self, block, W, y0):
        c = self.colors
        m = self.M
        h = 260
        parts = [
            '<g id="cta-band">',
            self.card(m, y0, W - 2 * m, h, c["surface"]),
            self.text(m + 24, y0 + 48, self.case(block.get("eyebrow", "")), 10, 600, c["accent"], family=self.f_mono, tracking=2),
            self.text(m + 24, y0 + 82, self.case(block["title"]), 24 * self.scale, 700, family=self.f_display),
            self.text(m + 24, y0 + 110, self.case(block.get("body", "")), 12.5, 400, c["text-secondary"]),
        ]
        bw, bh = W - 2 * m - 48, 48
        by = y0 + 140
        parts.append(f'<g id="cta">{self.card(m + 24, by, bw, bh, c["accent"])}')
        parts.append(self.text(m + 44, by + 31, self.case(block["cta"]), 15, 700, c["accent-ink"]))
        parts.append(self.icon(block.get("ctaIcon", "arrow-right"), m + 24 + bw - 40, by + 14, 18, c["accent-ink"]))
        parts.append("</g></g>")
        return "".join(parts), h

    # --- 장식(ornament) ----------------------------------------------------
    # 모티프는 데이터다: styles/ornaments.json의 SVG 템플릿을 그리고,
    # 스타일의 `ornament` 축은 {motif, frame, weight, height}만 정한다.

    def ornament_divider(self, x1, x2, y):
        motif = self.ornament.get("motif", "none")
        if motif == "none":
            return "", 0
        height = int(self.ornament.get("height", 46))
        offset = int(self.ornament.get("offset", 0))
        variables = {
            "x1": x1,
            "x2": x2,
            "cx": (x1 + x2) / 2,
            "y": y + offset,
            "weight": self.ornament.get("weight", 1),
            "accent": self.colors["accent"],
        }
        body = ornament_data.draw("divider", motif, variables)
        if not body:
            return "", 0
        return f'<g id="ornament">{body}</g>', height + offset

    def background_layer(self, W, H):
        """스타일이 background 패턴을 선언하면 본문 뒤에 반복 장식을 깐다."""
        name = self.ornament.get("background") if isinstance(self.ornament, dict) else None
        if not name:
            return ""
        body = ornament_data.draw(
            "background",
            name,
            {
                "W": W,
                "H": H,
                "accent": self.colors.get("text-faint") or self.colors["border"],
                "weight": self.ornament.get("weight", 1),
            },
        )
        return f'<g id="background-pattern">{body}</g>' if body else ""

    def ornament_frame(self, W, H):
        motif = self.ornament.get("frame", "none")
        if motif == "none":
            return ""
        variables = {
            "W": W,
            "H": H,
            "i": 8 if self.bp == "mobile" else 18,
            "weight": self.ornament.get("weight", 1),
            "accent": self.colors["accent"],
        }
        body = ornament_data.draw("frame", motif, variables)
        return f'<g id="ornament-frame">{body}</g>' if body else ""

    def footer(self, block, W, y):
        c = self.colors
        if self.bp == "mobile":
            m = self.M
            return (
                f'<g id="footer"><line x1="{m}" y1="{y}" x2="{W - m}" y2="{y}" stroke="{c["border"]}" stroke-width="1"/>'
                + self.text(m, y + 32, self.case(block.get("left", "")), 11, 400, c["text-muted"], family=self.f_mono)
                + self.text(m, y + 54, self.case(block.get("right", "")), 11, 400, c["text-muted"], family=self.f_mono)
                + "</g>"
            )
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
    seen = set()
    for a in manifest["assets"]:
        key = (a["name"], a["kind"], a["license"], a["origin"], a["scope"])
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"| {a['name']} | {a['kind']} | {a['license']} | {a['origin']} | {a['scope']} |")
    generated = []
    for a in manifest["assets"]:
        meta = a.get("annotation")
        if a["origin"] != "generated" or not meta:
            continue
        try:
            info = json.loads(meta).get("generator", {})
        except (TypeError, ValueError):
            continue
        if info and (a["name"], info) not in generated:
            generated.append((a["name"], info))
    if generated:
        lines += ["", "## 생성 정보", ""]
        for name, info in generated:
            parts = [f"`{name}`", f"모델 `{info.get('model')}`"]
            if info.get("generated_at"):
                parts.append(f"생성 {info['generated_at']}")
            lines.append("- " + " · ".join(parts))
            if info.get("prompt"):
                lines.append(f"  - 프롬프트: {info['prompt']}")

    output_only = manifest.get("output_only") or []
    if output_only:
        lines += ["", "## 재배포 제한", ""]
        lines += [f"- `{name}`: 결과물에만 사용. 파일 재배포·에셋 팩 포함 금지" for name in output_only]
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
    ap.add_argument("--breakpoint", default="desktop", choices=("desktop", "tablet", "mobile"))
    ap.add_argument("--dark", action="store_true", help="팔레트를 다크로 변환(레시피의 dark:true 보다 우선)")
    ap.add_argument("--raster-mode", default="embed", choices=("embed", "link"), help="래스터 임베드(embed) 또는 파일 1벌 참조(link)")
    ap.add_argument("--raster-dir", default="assets", help="link 모드에서 이미지를 둘 하위 폴더")
    ap.add_argument(
        "--pattern-mode",
        default="tile",
        choices=("tile", "line"),
        help="배경 패턴: tile=SVG pattern(작음, Figma는 버림) · line=선 그리드(큼, Figma 안전)",
    )
    args = ap.parse_args()

    try:
        recipe, schema = normalize(json.loads(Path(args.recipe).read_text()), name=args.recipe)
    except RecipeError as exc:
        raise SystemExit(str(exc)) from exc
    if schema != "blocks":
        print(f"참고: 레거시 레시피를 blocks로 변환했습니다 ({args.recipe})", file=sys.stderr)
    try:
        contract.validate(recipe.get("contract"), name=f"{args.recipe}: contract")
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    catalog = json.loads(Path(args.catalog).read_text())
    tokens = json.loads(Path(args.tokens).read_text())

    style_path = args.style or recipe.get("style")
    style = DEFAULT_STYLE
    if style_path:
        style = deep_merge(DEFAULT_STYLE, load_style(style_path))

    W = recipe["canvas"]["width"]
    if args.breakpoint == "tablet":
        W = 768
    elif args.breakpoint == "mobile":
        W = 390
    H = recipe["canvas"]["height"]
    auto_height = (H == "auto" or bool(style.get("auto_height"))) and args.force_height == 0
    if args.force_height:
        H = args.force_height
    ornament = style.get("ornament") or {}
    if isinstance(ornament, dict) and ornament.get("background"):
        background = ornament["background"]
        if args.pattern_mode == "line" and background in ("dots", "hatch"):
            ornament["background"] = f"{background}-lines"
            style["ornament"] = ornament
        elif args.pattern_mode == "tile" and background in ("dots", "hatch"):
            print(
                "참고: 배경 패턴을 <pattern> 타일로 그립니다. Figma는 이 채우기를 버립니다 — 피그마 왕복이면 --pattern-mode line",
                file=sys.stderr,
            )

    theme = style.get("theme") or recipe["theme"]
    r = Renderer(catalog, tokens, theme, style, strict=not args.allow_blocked)
    dark = args.dark or bool(recipe.get("dark"))
    if dark:
        r.colors = to_dark(r.colors)
    r.embed_max_width = args.embed_max_width
    r.raster_mode = args.raster_mode
    r.raster_dir = args.raster_dir
    r.out_dir = Path(args.out)
    r.bp = args.breakpoint
    r.M = 56 if args.breakpoint == "desktop" else (32 if args.breakpoint == "tablet" else 20)
    r.K = 1.0 if args.breakpoint == "desktop" else (0.88 if args.breakpoint == "tablet" else 0.72)

    body = []
    body.append('<defs><filter id="mono"><feColorMatrix type="saturate" values="0"/></filter></defs>')
    y = 0
    ornament_types = {"stats", "features", "quote", "faq", "table", "pricing", "gallery", "logos", "cta"}
    for index, block in enumerate(recipe["blocks"]):
        kind = block["type"]
        if kind == "header":
            body.append(r.header(block, W))
            y = r.header_height()
            continue
        if r.ornament.get("motif", "none") != "none" and index > 0 and kind in ornament_types:
            # 장식은 블록 사이에 자기 자리를 차지한다(앞뒤로 BLOCK_GAP)
            y += BLOCK_GAP
            divider, adv = r.ornament_divider(56, W - 56, y)
            body.append(divider)
            y += adv
        top = y + BLOCK_GAP
        if kind == "footer":
            body.append(r.footer(block, W, top))
            y = top + r.footer_height()
            continue
        svg, adv = r.render_block(kind, block, W, top)
        body.append(svg)
        y = top + adv

    if auto_height:
        H = int(y + 110)
    # 배경은 최종 높이가 정해진 뒤에 그린다(auto 높이에서 height="auto"가 되던 버그)
    body.insert(0, f'<rect id="background" width="{W}" height="{H}" fill="{r.colors["background"]}"/>')
    pattern = r.background_layer(W, H)
    if pattern:
        body.insert(1, pattern)
    if r.ornament.get("frame", "none") != "none":
        body.append(r.ornament_frame(W, H))
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

    def file_hash(path):
        from pathlib import Path as _P

        return hashlib.sha256(_P(path).read_bytes()).hexdigest() if path and _P(path).is_file() else ""

    manifest = {
        "contract": contract.stamp(style, args.tokens),
        "recipe": recipe.get("name"),
        "inputs": {
            "recipe": file_hash(args.recipe),
            "style": file_hash(args.style),
            "tokens": file_hash(args.tokens),
            "catalog": file_hash(args.catalog),
        },
        "style": style.get("name"),
        "seed": recipe.get("seed"),
        "theme": theme,
        "dark": dark,
        "canvas": {"width": W, "height": H},
        "embed_max_width": args.embed_max_width,
        "raster_mode": r.raster_mode,
        "raster_assets": dict(sorted(r.raster_written.items())),
        "output": svg_path.name,
        "sha256": hashlib.sha256(svg.encode()).hexdigest(),
        "layers": re.findall(r'<g id="([^"]+)"', svg),
        "assets": r.used,
        "license_ok": all(a["scope"] != "blocked" for a in r.used),
        "output_only": sorted(set(r.output_only)),
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
