#!/usr/bin/env python3
"""브랜드 시트 — A4 세로 8페이지 조판(ASSET-11).

lockup 스펙 하나로 브랜드 가이드 8페이지를 SVG로 만들고, 한 PDF로 묶는다.
구성은 `docs/IDENTITY_DELIVERY.md` 5절을 따른다.

| 페이지 | 내용 |
| --- | --- |
| 1 | 표지 (브랜드명, 버전, 날짜) |
| 2 | 로고 소개 + 락업 3종 |
| 3 | 클리어 스페이스 · 최소 크기 |
| 4 | 색 팔레트 (HEX · RGB · CMYK 병기) |
| 5 | 타이포그래피 |
| 6 | 적용 예시 (명함 · 간판 · 앱 아이콘) |
| 7 | Do / Don't |
| 8 | 자산·라이선스 고지 |

A4 = 210×297mm. 96dpi 기준 794×1123px 벡터.

사용::

    render_brandsheet.py --spec test_data/identity/lockup.json --out out/brandsheet
    render_brandsheet.py --spec … --check
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from render_lockup import (  # noqa: E402
    MIN_CONTRAST,
    SpecError,
    contrast,
    hex_to_rgb,
    load_spec,
    load_symbol,
    symbol_svg,
)

A4_W, A4_H = 794, 1123
M = 56
MONO = "JetBrains Mono, monospace"
DISPLAY = "Archivo, sans-serif"
BODY = "Pretendard, sans-serif"


def cmyk(hex_color):
    """근사 CMYK(0~100). 인쇄 지정은 별색/Pantone으로 확정한다."""
    r, g, b = (c / 255 for c in hex_to_rgb(hex_color))
    k = 1 - max(r, g, b)
    if k >= 1:
        return 0, 0, 0, 100
    return (
        round((1 - r - k) / (1 - k) * 100),
        round((1 - g - k) / (1 - k) * 100),
        round((1 - b - k) / (1 - k) * 100),
        round(k * 100),
    )


def text(x, y, s, size, fill, family=BODY, weight=400, anchor="start", tracking=0, opacity=1.0):
    extra = f' letter-spacing="{tracking:.2f}"' if tracking else ""
    op = f' fill-opacity="{opacity}"' if opacity != 1.0 else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
        f'text-anchor="{anchor}"{extra}{op} fill="{fill}">{s}</text>'
    )


def page(spec, index, title, body_parts):
    ink = spec["colors"]["ink"]
    accent = spec["colors"]["accent"]
    paper = spec["backgrounds"]["light"]
    head = [
        f'<rect id="page" width="{A4_W}" height="{A4_H}" fill="{paper}"/>',
        text(M, 62, spec["brand"], 13, ink, DISPLAY, 700, tracking=2.4),
        text(A4_W - M, 62, title.upper(), 10, accent, MONO, 600, anchor="end", tracking=2),
        f'<line x1="{M}" y1="78" x2="{A4_W - M}" y2="78" stroke="{ink}" stroke-opacity="0.25"/>',
        text(M, A4_H - 40, f"{index:02d} / 08", 9, ink, MONO, 400, opacity=0.5),
        text(A4_W - M, A4_H - 40, spec.get("version", "v1"), 9, ink, MONO, 400, anchor="end", opacity=0.5),
    ]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{A4_W}" height="{A4_H}" viewBox="0 0 {A4_W} {A4_H}">' + "".join(head + body_parts) + "</svg>"
    )


def heading(spec, title, note):
    ink = spec["colors"]["ink"]
    return [
        text(M, 132, title, 22, ink, DISPLAY, 700),
        text(M, 162, note, 13, ink, BODY, 400, opacity=0.7),
    ]


def cover(spec, body_svg, view):
    ink, accent = spec["colors"]["ink"], spec["colors"]["accent"]
    parts = [
        # 표지 워터마크: 심볼을 크게, 낮은 불투명도로
        f'<g opacity="0.12">{symbol_svg(body_svg, view, 470, 180, 260, spec["colors"]["primary"])}</g>',
        text(M, 330, "BRAND GUIDELINES", 11, accent, MONO, 600, tracking=4),
        text(M, 424, spec["brand"], 76, ink, DISPLAY, 700, tracking=1),
        f'<line x1="{M}" y1="462" x2="{A4_W - M}" y2="462" stroke="{ink}" stroke-width="3"/>',
        text(M, 506, spec.get("tagline", ""), 17, ink, BODY, 400, opacity=0.75),
        text(M, 560, "로고 · 색 · 타이포그래피 · 적용 규칙", 12, ink, BODY, 400, opacity=0.55),
        f'<line x1="{M}" y1="{A4_H - 190}" x2="{A4_W - M}" y2="{A4_H - 190}" stroke="{ink}" stroke-opacity="0.2"/>',
        text(M, A4_H - 156, f"버전 {spec.get('version', 'v1')}", 12, ink, MONO, 400),
        text(M, A4_H - 134, f"발행 {spec.get('date', '—')}", 12, ink, MONO, 400),
        text(M, A4_H - 108, "이 문서는 브랜드 사용 규칙을 정의합니다.", 12, ink, BODY, 400, opacity=0.65),
        text(A4_W - M, A4_H - 108, "8 PAGES · A4", 10, ink, MONO, 400, anchor="end", opacity=0.45),
    ]
    return page(spec, 1, "cover", parts)


def logo_page(spec, body_svg, view):
    ink, accent = spec["colors"]["ink"], spec["colors"]["accent"]
    parts = heading(spec, "로고는 브랜드의 첫인상입니다.", "세 가지 락업을 용도에 맞게 사용합니다. 임의로 비율·색을 바꾸지 않습니다.")
    y = 200
    items = [
        ("가로형 · PRIMARY", "기본 사용. 웹 헤더·문서 머리", "horizontal"),
        ("세로형 · STACKED", "정사각 지면·좁은 폭", "stacked"),
        ("심볼 · SYMBOL", "파비콘·앱 아이콘", "symbol"),
    ]
    for label, note, kind in items:
        parts.append(f'<rect x="{M}" y="{y}" width="{A4_W - 2 * M}" height="196" fill="none" stroke="{ink}" stroke-opacity="0.18"/>')
        if kind == "horizontal":
            size = 64
            parts.append(symbol_svg(body_svg, view, M + 40, y + 66, size, spec["colors"]["primary"]))
            parts.append(
                text(M + 40 + size + 20, y + 110, spec.get("wordmark", spec["brand"]), 40, spec["colors"]["primary"], DISPLAY, 700, tracking=4)
            )
        elif kind == "stacked":
            size = 64
            parts.append(symbol_svg(body_svg, view, A4_W / 2 - size / 2, y + 36, size, spec["colors"]["primary"]))
            parts.append(
                text(A4_W / 2, y + 138, spec.get("wordmark", spec["brand"]), 26, spec["colors"]["primary"], DISPLAY, 700, anchor="middle", tracking=4)
            )
        else:
            size = 88
            parts.append(symbol_svg(body_svg, view, A4_W / 2 - size / 2, y + 36, size, spec["colors"]["primary"]))
        parts += [
            text(M + 16, y + 26, label, 10, accent, MONO, 600, tracking=1.6),
            text(M + 16, y + 180, note, 10, ink, BODY, 400, opacity=0.6),
        ]
        y += 212
    parts.append(text(M, y + 14, "풀컬러를 기본으로 하고, 흑백·반전은 별도 시트를 따른다.", 12, ink, BODY, 400, opacity=0.65))
    parts.append(text(M, y + 40, "색·여백·최소 크기는 3~5페이지 규격을 따른다.", 12, ink, BODY, 400, opacity=0.45))
    return page(spec, 2, "logo", parts)


def spec_page(spec, body_svg, view):
    ink, accent = spec["colors"]["ink"], spec["colors"]["accent"]
    factor = float(spec["clearspace"])
    size = 150
    m = size * factor
    x, y = M + 90, 300
    parts = heading(spec, "여백과 최소 크기", f"클리어 스페이스는 심볼 높이의 {int(factor * 100)}%입니다. 이 안에는 아무것도 넣지 않습니다.")
    parts += [
        f'<rect x="{x - m:.1f}" y="{y - m:.1f}" width="{size + 2 * m:.1f}" height="{size + 2 * m:.1f}" '
        f'fill="none" stroke="{accent}" stroke-width="1.4" stroke-dasharray="7 6"/>',
        symbol_svg(body_svg, view, x, y, size, spec["colors"]["primary"]),
        text(x + size / 2, y + size + m + 26, f"h × {factor} = {m:.0f}px", 10, ink, MONO, 400, anchor="middle"),
        text(x + size + m + 80, y - 6, "클리어 스페이스", 11, ink, MONO, 600, tracking=1.2),
        text(x + size + m + 80, y + 16, "심볼 주변 최소 여백. 텍스트·이미지·테두리 금지", 11, ink, BODY, 400, opacity=0.65),
        text(x + size + m + 80, y + 38, "최소 크기 미만으로 축소 금지", 11, ink, BODY, 400, opacity=0.65),
    ]

    minimum = spec["minimum"]
    parts += [
        f'<line x1="{M}" y1="600" x2="{A4_W - M}" y2="600" stroke="{ink}" stroke-opacity="0.2"/>',
        text(M, 636, "최소 크기", 14, ink, DISPLAY, 700),
        text(M, 660, f"인쇄 {minimum['print_mm']}mm · 화면 {minimum['screen_px']}px 이하로 줄이지 않습니다.", 12, ink, BODY, 400, opacity=0.7),
    ]
    px = minimum["print_mm"] * 3.7795
    parts.append(symbol_svg(body_svg, view, M, 700, px, spec["colors"]["primary"]))
    parts.append(text(M, 700 + px + 20, f"인쇄 {minimum['print_mm']}mm", 10, ink, MONO, 400))
    parts.append(symbol_svg(body_svg, view, M + 200, 700, minimum["screen_px"] * 2.5, spec["colors"]["primary"]))
    parts.append(text(M + 200, 700 + minimum["screen_px"] * 2.5 + 20, f"화면 {minimum['screen_px']}px (×2.5)", 10, ink, MONO, 400))
    parts.append(f'<line x1="{M}" y1="880" x2="{A4_W - M}" y2="880" stroke="{ink}" stroke-opacity="0.12"/>')
    parts.append(text(M, 912, "형태가 무너지지 않는 범위에서만 축소합니다. 가는 선은 0.25pt 이상 유지.", 12, ink, BODY, 400, opacity=0.6))
    return page(spec, 3, "clearspace", parts)


def palette(spec):
    return spec.get("palette") or [
        {"name": "Primary", "role": "주요 로고·버튼", "hex": spec["colors"]["primary"]},
        {"name": "Ink", "role": "본문·제목", "hex": spec["colors"]["ink"]},
        {"name": "Paper", "role": "배경", "hex": spec["colors"]["paper"]},
        {"name": "Accent", "role": "강조·링크", "hex": spec["colors"]["accent"]},
    ]


def palette_page(spec):
    ink = spec["colors"]["ink"]
    parts = heading(spec, "색", "같은 색을 화면(HEX·RGB)과 인쇄(CMYK)에 함께 적습니다. CMYK는 근사값입니다.")
    y = 200
    for row in palette(spec):
        r, g, b = hex_to_rgb(row["hex"])
        c, m_, yy, k = cmyk(row["hex"])
        ratio = max(contrast(row["hex"], "#ffffff"), contrast(row["hex"], "#000000"))
        parts += [
            f'<rect x="{M}" y="{y}" width="160" height="84" fill="{row["hex"]}" stroke="{ink}" stroke-opacity="0.25"/>',
            text(M + 178, y + 24, row["name"], 16, ink, DISPLAY, 700),
            text(M + 178, y + 46, row.get("role", ""), 11, ink, BODY, 400, opacity=0.65),
            text(M + 178, y + 68, f"HEX {row['hex'].upper()}  ·  RGB {r} {g} {b}", 10, ink, MONO, 400, opacity=0.8),
            text(
                M + 178, y + 84, f"CMYK {c} {m_} {yy} {k}" + (f"  ·  {row['pantone']}" if row.get("pantone") else ""), 10, ink, MONO, 400, opacity=0.8
            ),
            text(A4_W - M, y + 68, f"{ratio:.1f}:1", 10, ink, MONO, 400, anchor="end", opacity=0.55),
        ]
        y += 104

    # 대비 조합: 실제로 쓰는 배경-글자 조합만 검사한다
    combos = [
        ("본문", spec["colors"]["ink"], spec["colors"]["paper"]),
        ("반전", spec["colors"]["paper"], spec["colors"]["ink"]),
        ("버튼", spec["colors"]["paper"], spec["colors"]["primary"]),
    ]
    parts += [
        f'<line x1="{M}" y1="{y + 18}" x2="{A4_W - M}" y2="{y + 18}" stroke="{ink}" stroke-opacity="0.2"/>',
        text(M, y + 52, "대비 조합", 13, ink, DISPLAY, 700),
        text(M, y + 74, f"본문 텍스트는 배경 대비 {MIN_CONTRAST}:1 이상. 반전 로고는 실제 배경에서 검사합니다.", 11, ink, BODY, 400, opacity=0.65),
    ]
    chip_w = (A4_W - 2 * M - 24) / 3
    for i, (label, fg, bg) in enumerate(combos):
        cx = M + i * (chip_w + 12)
        cy = y + 96
        ratio = contrast(fg, bg)
        ok = ratio >= MIN_CONTRAST
        parts += [
            f'<rect x="{cx}" y="{cy}" width="{chip_w}" height="86" fill="{bg}" stroke="{ink}" stroke-opacity="0.15"/>',
            text(cx + 16, cy + 40, "가나다 Aa", 18, fg, BODY, 500),
            text(cx + 16, cy + 66, f"{label} · {ratio:.1f}:1", 10, fg, MONO, 400, opacity=0.8),
            text(cx + chip_w - 16, cy + 66, "OK" if ok else "LOW", 10, fg if ok else spec["colors"]["accent"], MONO, 600, anchor="end"),
        ]
    return page(spec, 4, "color", parts)


def type_page(spec):
    ink, accent = spec["colors"]["ink"], spec["colors"]["accent"]
    t = spec.get("type") or {}
    family = t.get("family", "Archivo")
    parts = heading(spec, "타이포그래피", f"로고타입은 {family} {t.get('weight', 700)}. 제출 시 아웃라인 처리합니다.")
    rows = [
        ("DISPLAY 40 / 700", 40, 700),
        ("HEADING 24 / 700", 24, 700),
        ("BODY 14 / 400", 14, 400),
        ("CAPTION 10 / 500", 10, 500),
    ]
    y = 230
    for label, size, weight in rows:
        parts += [
            text(M, y, "가나다 ABC 0123 sonagi", size, ink, BODY, weight),
            text(M, y + 18, label, 9, accent, MONO, 400, tracking=1.2),
            f'<line x1="{M}" y1="{y + 34}" x2="{A4_W - M}" y2="{y + 34}" stroke="{ink}" stroke-opacity="0.12"/>',
        ]
        y += 96
    parts += [
        text(M, y + 6, "본문 규칙", 13, ink, DISPLAY, 700),
        text(M, y + 32, "문장은 짧게 끊고, 한 줄에 60자 안쪽으로 유지합니다. 제목에는 자간을 조금 넓힙니다.", 12, ink, BODY, 400, opacity=0.7),
        text(M, y + 56, f"자간 {t.get('tracking', 0)}em · 대체 서체 Pretendard / Noto Sans KR", 11, ink, MONO, 400, opacity=0.55),
        f'<line x1="{M}" y1="{y + 84}" x2="{A4_W - M}" y2="{y + 84}" stroke="{ink}" stroke-opacity="0.12"/>',
        text(M, y + 116, "자간·행간", 11, ink, MONO, 600, tracking=1.2),
        text(M + 110, y + 116, "제목 1.16 · 본문 1.5~1.6. 자간은 제목에서만 0.02~0.06em.", 11, ink, BODY, 400, opacity=0.7),
        text(M, y + 140, "금지", 11, ink, MONO, 600, tracking=1.2),
        text(M + 110, y + 140, "로고타입을 다른 서체로 대체하거나 굵기를 바꾸지 않습니다.", 11, ink, BODY, 400, opacity=0.7),
    ]
    return page(spec, 5, "type", parts)


def mockup_page(spec, body_svg, view):
    ink = spec["colors"]["ink"]
    parts = heading(spec, "적용 예시", "실제 매체에서 로고가 읽히는지 확인합니다. 배경과 여백을 먼저 정합니다.")
    # 명함 (90×50mm 비율)
    cw, ch = 380, 212
    cy = 210
    parts += [
        f'<rect x="{M}" y="{cy}" width="{cw}" height="{ch}" fill="{spec["colors"]["paper"]}" stroke="{ink}" stroke-opacity="0.2"/>',
        text(M + 28, cy + 44, spec.get("wordmark", spec["brand"]), 13, spec["colors"]["primary"], DISPLAY, 700, tracking=3),
        f'<line x1="{M + 28}" y1="{cy + 58}" x2="{M + 28 + 120}" y2="{cy + 58}" stroke="{spec["colors"]["accent"]}" stroke-width="2"/>',
        text(M + 28, cy + 96, "김소나기", 15, ink, BODY, 600),
        text(M + 28, cy + 116, "브랜드 디렉터", 10, ink, MONO, 400, opacity=0.6),
        text(M + 28, cy + 150, "sonagi.space", 10, ink, MONO, 400, opacity=0.6),
        text(M + 28, cy + 166, "hello@sonagi.space", 10, ink, MONO, 400, opacity=0.6),
        symbol_svg(body_svg, view, M + cw - 28 - 40, cy + ch - 28 - 40, 40, spec["colors"]["primary"]),
        text(M, cy + ch + 26, "명함 90×50mm · 앞면", 10, ink, MONO, 400, opacity=0.6),
    ]
    # 간판 (가로 패널)
    sw, sh = A4_W - 2 * M, 150
    sy = 520
    parts += [
        f'<rect x="{M}" y="{sy}" width="{sw}" height="{sh}" fill="{spec["colors"]["ink"]}"/>',
        symbol_svg(body_svg, view, M + 32, sy + sh / 2 - 26, 52, spec["colors"]["paper"]),
        text(M + 32 + 66, sy + sh / 2 + 12, spec.get("wordmark", spec["brand"]), 30, spec["colors"]["paper"], DISPLAY, 700, tracking=6),
        text(M, sy + sh + 26, "간판 · 반전 락업", 10, ink, MONO, 400, opacity=0.6),
    ]
    # 앱 아이콘
    iy = 760
    parts += [
        f'<rect x="{M}" y="{iy}" width="104" height="104" rx="24" fill="{spec["colors"]["primary"]}"/>',
        symbol_svg(body_svg, view, M + 22, iy + 22, 60, spec["colors"]["paper"]),
        text(M, iy + 132, "앱 아이콘 · 심볼 단독", 10, ink, MONO, 400, opacity=0.6),
        text(M + 150, iy + 30, "아이콘은 심볼만 씁니다. 워드마크를 넣지 않습니다.", 12, ink, BODY, 400, opacity=0.7),
        text(M + 150, iy + 54, "모서리 반경은 24px 기준, 배경은 Primary.", 12, ink, BODY, 400, opacity=0.7),
        text(M + 150, iy + 78, "축소 시 안쪽 여백을 최소 10% 확보합니다.", 12, ink, BODY, 400, opacity=0.7),
    ]
    return page(spec, 6, "application", parts)


def do_dont_page(spec, body_svg, view):
    ink, accent = spec["colors"]["ink"], spec["colors"]["accent"]
    parts = heading(spec, "Do / Don't", "형태·비율·색을 바꾸지 않습니다. 로고는 항상 여백 안에 둡니다.")
    col = (A4_W - 2 * M - 24) / 2
    items = [
        (True, "여백을 지킨다", "클리어 스페이스 안에 다른 요소를 두지 않습니다.", "space"),
        (True, "지정 색만 쓴다", "풀컬러·흑백·반전·단색 중 하나.", "color"),
        (True, "어두운 배경엔 반전", "실제 배경 대비를 확인합니다.", "inverse"),
        (False, "늘리거나 눌러 변형", "비율을 유지합니다.", "stretch"),
        (False, "그림자·외곽선 추가", "효과를 넣지 않습니다.", "effect"),
        (False, "회전·기울이기", "수평을 유지합니다.", "rotate"),
    ]
    for i, (ok, title, note, kind) in enumerate(items):
        cx = M + (i % 2) * (col + 24)
        cy = 196 + (i // 2) * 246
        tone = spec["colors"]["primary"] if ok else accent
        tag = "DO" if ok else "DON'T"
        parts += [
            f'<rect x="{cx}" y="{cy}" width="{col}" height="216" fill="none" stroke="{ink}" stroke-opacity="0.18"/>',
            text(cx + 16, cy + 26, tag, 10, tone, MONO, 600, tracking=1.6),
        ]
        mid_x = cx + col / 2
        mid_y = cy + 108
        if kind == "space":
            parts += [
                f'<rect x="{mid_x - 62}" y="{mid_y - 62}" width="124" height="124" fill="none" stroke="{accent}" stroke-dasharray="5 5"/>',
                symbol_svg(body_svg, view, mid_x - 32, mid_y - 32, 64, spec["colors"]["primary"]),
            ]
        elif kind == "color":
            tints = [spec["colors"]["primary"], spec["colors"]["ink"], spec["colors"]["accent"]]
            for j, tint in enumerate(tints):
                parts.append(symbol_svg(body_svg, view, cx + 40 + j * 74, mid_y - 28, 56, tint))
        elif kind == "inverse":
            parts += [
                f'<rect x="{cx + 46}" y="{mid_y - 48}" width="{col - 92}" height="96" fill="{spec["colors"]["ink"]}"/>',
                symbol_svg(body_svg, view, mid_x - 88, mid_y - 22, 44, spec["colors"]["paper"]),
                text(mid_x - 34, mid_y + 8, spec.get("wordmark", spec["brand"]), 19, spec["colors"]["paper"], DISPLAY, 700, tracking=4),
            ]
        elif kind == "stretch":
            parts += [
                f'<svg x="{cx + 44}" y="{mid_y - 26}" width="150" height="52" viewBox="{view}" preserveAspectRatio="none">{body_svg}</svg>',
                f'<line x1="{cx + 36}" y1="{mid_y + 40}" x2="{cx + col - 36}" y2="{mid_y + 40}" stroke="{accent}" stroke-width="2"/>',
            ]
        elif kind == "effect":
            parts += [
                # offset shadow + 굵은 외곽선
                symbol_svg(body_svg, view, mid_x - 30, mid_y - 30, 64, spec["colors"]["ink"]).replace(
                    "<svg ", '<svg opacity="0.25" transform="translate(6 6)" ', 1
                ),
                f'<g stroke="{accent}" stroke-width="3" fill="none" opacity="0.6"><circle cx="{mid_x - 8}" cy="{mid_y + 6}" r="40"/></g>',
                symbol_svg(body_svg, view, mid_x - 40, mid_y - 40, 64, spec["colors"]["primary"]),
            ]
        else:
            parts += [
                f'<g transform="rotate(18 {mid_x} {mid_y})">'
                + symbol_svg(body_svg, view, mid_x - 32, mid_y - 32, 64, spec["colors"]["primary"])
                + "</g>",
                f'<line x1="{mid_x - 70}" y1="{mid_y + 56}" x2="{mid_x + 70}" y2="{mid_y - 56}" stroke="{accent}" stroke-width="2"/>',
            ]
        parts += [
            text(cx + 16, cy + 176, title, 13, ink, DISPLAY, 700),
            text(cx + 16, cy + 196, note, 11, ink, BODY, 400, opacity=0.65),
        ]
    return page(spec, 7, "usage", parts)


def credits_page(spec, files):
    ink = spec["colors"]["ink"]
    t = spec.get("type") or {}
    parts = heading(spec, "자산·라이선스 고지", "제출 전에 폰트·자산·저작권 조건을 확인합니다.")
    rows = [
        ("폰트", f"{t.get('family', 'Archivo')} · 제출 시 아웃라인 처리. 파일 동봉 금지(상업 폰트)"),
        ("심볼", "브랜드 자체 제작 벡터. 원본 SVG를 함께 납품"),
        ("AI 생성", "이 문서에는 AI 생성 이미지가 없습니다"),
        ("저작권", "낙찰 시 저작재산권 이전 조항 확인. 이전 전 원본 전달 금지"),
        ("상표", "상표 검색은 사람이 KIPRIS/USPTO에서 확인"),
    ]
    y = 210
    for label, note in rows:
        parts += [
            text(M, y, label, 11, ink, MONO, 600, tracking=1.2),
            text(M + 110, y, note, 12, ink, BODY, 400, opacity=0.75),
            f'<line x1="{M}" y1="{y + 16}" x2="{A4_W - M}" y2="{y + 16}" stroke="{ink}" stroke-opacity="0.12"/>',
        ]
        y += 58

    parts += [
        text(M, y + 12, "구성", 11, ink, MONO, 600, tracking=1.2),
    ]
    guide = [
        ("01", "표지"),
        ("02", "로고 · 락업 3종"),
        ("03", "클리어 스페이스 · 최소 크기"),
        ("04", "색 (HEX/RGB/CMYK)"),
        ("05", "타이포그래피"),
        ("06", "적용 예시"),
        ("07", "Do / Don't"),
        ("08", "자산·라이선스 고지"),
    ]
    for i, (num, label) in enumerate(guide):
        gx = M + 110 + (i % 2) * 300
        gy = y + 12 + (i // 2) * 26
        parts.append(text(gx, gy, f"{num}  {label}", 10, ink, MONO, 400, opacity=0.65))
    y += 140

    parts.append(text(M, y, "파일 해시", 11, ink, MONO, 600, tracking=1.2))
    y += 26
    for name, value in files.items():
        parts.append(text(M + 110, y, f"{name} · sha256 {value[:20]}…", 9, ink, MONO, 400, opacity=0.55))
        y += 18
    parts += [
        f'<line x1="{M}" y1="{A4_H - 130}" x2="{A4_W - M}" y2="{A4_H - 130}" stroke="{ink}" stroke-opacity="0.15"/>',
        text(M, A4_H - 100, "이 시트는 press로 생성되었습니다. 수치가 바뀌면 다시 뽑으세요.", 11, ink, BODY, 400, opacity=0.55),
        text(M, A4_H - 78, "인쇄는 RGB 기준입니다. CMYK·도련이 필요하면 별도 인쇄 경로를 사용하세요.", 11, ink, BODY, 400, opacity=0.45),
    ]
    return page(spec, 8, "credits", parts)


def build(spec):
    body_svg, view = load_symbol(spec["symbol"])
    pages = {
        "01-cover": cover(spec, body_svg, view),
        "02-logo": logo_page(spec, body_svg, view),
        "03-clearspace": spec_page(spec, body_svg, view),
        "04-color": palette_page(spec),
        "05-type": type_page(spec),
        "06-application": mockup_page(spec, body_svg, view),
        "07-usage": do_dont_page(spec, body_svg, view),
    }
    hashes = {name: hashlib.sha256(text.encode()).hexdigest() for name, text in pages.items()}
    files = {name: hashes[name] for name in ("01-cover", "02-logo")}
    files["symbol"] = hashlib.sha256(Path(spec["symbol"]).read_bytes()).hexdigest()
    pages["08-credits"] = credits_page(spec, files)
    hashes["08-credits"] = hashlib.sha256(pages["08-credits"].encode()).hexdigest()

    manifest = {
        "brand": spec["brand"],
        "version": spec.get("version", "v1"),
        "date": spec.get("date", ""),
        "format": "A4 portrait 210×297mm (794×1123px)",
        "pages": [{"file": f"{name}.svg", "sha256": hashes[name]} for name in pages],
        "palette": [
            {
                "name": row["name"],
                "hex": row["hex"].upper(),
                "rgb": list(hex_to_rgb(row["hex"])),
                "cmyk": list(cmyk(row["hex"])),
                "pantone": row.get("pantone"),
            }
            for row in palette(spec)
        ],
        "checks": {
            "min_contrast": MIN_CONTRAST,
            "page_count": len(pages),
            "clearspace": spec["clearspace"],
            "minimum": spec["minimum"],
        },
        "inputs": {"symbol": hashlib.sha256(Path(spec["symbol"]).read_bytes()).hexdigest()},
    }
    return pages, manifest


def main():
    ap = argparse.ArgumentParser(description="브랜드 시트(A4 8페이지)")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", default="out/brandsheet")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        spec = load_spec(args.spec)
        if not spec.get("date"):
            print("참고: spec.date가 없어 표지 날짜를 '—'로 둡니다", file=sys.stderr)
        pages, manifest = build(spec)
    except SpecError as exc:
        raise SystemExit(f"스펙 오류: {exc}") from exc

    if manifest["checks"]["page_count"] != 8:
        raise SystemExit(f"페이지 수가 8이 아닙니다: {manifest['checks']['page_count']}")

    if not args.check:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        for name, text in pages.items():
            (out / f"{name}.svg").write_text(text)
        (out / "brandsheet.manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    if args.json:
        print(json.dumps({"brand": spec["brand"], "pages": len(pages)}, ensure_ascii=False))
    else:
        for name in sorted(pages):
            print(f"  {name:16s} {len(pages[name]):6d}B")
        print(f"{spec['brand']}: {len(pages)}페이지 · A4 세로")
    return 0


if __name__ == "__main__":
    sys.exit(main())
