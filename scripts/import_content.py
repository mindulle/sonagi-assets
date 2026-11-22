#!/usr/bin/env python3
"""content.md → recipe.json 변환기.

내용(문장·항목)과 배치(블록 목록)를 분리해 적은 마크다운을 레시피로 바꾼다.
렌더 전에 오타·누락·차단 자산을 잡는 것이 목적이다. 규격은 CONTENT_FORMAT.md.

사용::

    import_content.py content/atelier-landing.md --check
    import_content.py content/atelier-landing.md --catalog catalog/catalog.json \\
        --out recipes/atelier-landing.json
"""

import argparse
import difflib
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

FIELDS = {
    "header": ({"brand"}, {"nav"}),
    "hero": ({"title", "cta"}, {"eyebrow", "body", "ctaIcon", "note", "illustration"}),
    "stats": ({"items"}, set()),
    "features": ({"items"}, {"title"}),
    "logos": ({"items"}, set()),
    "quote": ({"text"}, {"author"}),
    "faq": ({"items"}, {"title"}),
    "cta": ({"title", "cta"}, {"eyebrow", "body", "ctaIcon", "note"}),
    "footer": ({"left"}, {"right"}),
    "table": ({"columns", "items"}, {"title", "note", "featured"}),
    "pricing": ({"items"}, {"title", "note"}),
    "gallery": ({"items"}, {"title", "note"}),
}

LIMITS = {
    "hero.title": 40,
    "hero.body": 70,
    "features.title": 16,
    "faq.title": 16,
    "quote.text": 120,
}

FIELD_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):\s?(.*)$")


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, line, msg):
        where = f"{line}행: " if line else ""
        self.errors.append(f"{where}{msg}")

    def warn(self, line, msg):
        where = f"{line}행: " if line else ""
        self.warnings.append(f"{where}{msg}")


def split_front(text):
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                meta = yaml.safe_load("\n".join(lines[1:i])) or {}
                return meta, lines[i + 1 :], i + 2
    return {}, lines, 1


def split_sections(body, start, report):
    sections = []
    current = None
    for offset, raw in enumerate(body):
        line = start + offset
        if raw.startswith("## "):
            current = {"type": raw[3:].strip(), "line": line, "body": []}
            sections.append(current)
        elif raw.startswith("# "):
            report.error(line, "`## 타입` 형식으로 섹션을 시작하세요")
        elif current is None:
            if raw.strip():
                report.error(line, f"섹션 밖의 문장입니다: {raw.strip()[:30]}")
        else:
            current["body"].append((line, raw))
    if not sections:
        report.error(None, "섹션이 하나도 없습니다")
    return sections


def tokenize(section, report):
    fields, lists, groups = {}, {}, []
    last = None
    for line, raw in section["body"]:
        if not raw.strip():
            continue
        stripped = raw.lstrip()

        if stripped.startswith("### "):
            groups.append({"title": stripped[4:].strip(), "line": line, "fields": {}, "body": []})
            last = ("group", len(groups) - 1)
            continue

        if stripped.startswith("- "):
            item = stripped[2:].strip()
            if last and last[0] == "field":
                lists.setdefault(last[1], []).append(item)
            elif last and last[0] == "group":
                groups[last[1]]["body"].append(item)
            else:
                lists.setdefault("items", []).append(item)
                last = ("field", "items")
            continue

        match = FIELD_RE.match(raw)
        if match:
            key, value = match.group(1), match.group(2).strip()
            if last and last[0] == "group":
                groups[last[1]]["fields"][key] = value
            else:
                fields[key] = value
                last = ("field", key)
            continue

        if raw.startswith(" "):
            text = stripped
            if last and last[0] == "field":
                key = last[1]
                fields[key] = (fields.get(key, "") + "\n" + text).strip("\n")
            elif last and last[0] == "group":
                groups[last[1]]["body"].append(text)
            else:
                report.error(line, f"이어 붙일 필드가 없습니다: {text[:30]}")
            continue

        if last and last[0] == "group":
            groups[last[1]]["body"].append(raw.strip())
        else:
            report.error(line, f"해석할 수 없는 줄입니다: {raw.strip()[:40]}")
    return fields, lists, groups


def all_items(lists):
    """섹션 안의 모든 목록 항목을 적힌 순서대로 모은다.

    `- ` 줄은 마지막으로 읽은 필드에 붙으므로(table의 `columns:`, gallery의 `title:`),
    목록이 하나뿐인 타입은 키를 따지지 않고 모으는 편이 안전하다.
    """
    return [item for values in lists.values() for item in values]


def build_header(sec, fields, lists, groups, report):
    nav = lists.get("nav", [])
    if len(nav) > 4:
        report.error(sec["line"], f"header.nav는 4개까지입니다 (지금 {len(nav)}개)")
    return {"type": "header", "brand": fields.get("brand", ""), "nav": nav}


def build_hero(sec, fields, lists, groups, report):
    illustration = lists.get("illustration", [])
    if len(illustration) > 2:
        report.error(sec["line"], f"hero.illustration은 2개까지입니다 (지금 {len(illustration)}개)")
    block = {
        "type": "hero",
        "eyebrow": fields.get("eyebrow", ""),
        "title": fields.get("title", ""),
        "body": fields.get("body", ""),
        "cta": fields.get("cta", ""),
        "ctaIcon": fields.get("ctaIcon", "arrow-right"),
        "note": fields.get("note", ""),
        "illustration": illustration,
    }
    for key in ("title", "body"):
        limit = LIMITS[f"hero.{key}"]
        longest = max((len(x) for x in block[key].split("\n")), default=0)
        if longest > limit:
            report.warn(sec["line"], f"hero.{key}가 깁니다({longest}자). 기준 {limit}자")
    return block


def build_stats(sec, fields, lists, groups, report):
    items = []
    for entry in all_items(lists):
        value, _, label = entry.partition("|")
        if not label.strip():
            report.error(sec["line"], f"stats 항목은 `값 | 라벨` 형식입니다: {entry}")
        items.append({"value": value.strip(), "label": label.strip()})
    if len(items) > 4:
        report.warn(sec["line"], f"stats는 3개를 권장합니다 (지금 {len(items)}개)")
    return {"type": "stats", "items": items}


def build_features(sec, fields, lists, groups, report):
    items = []
    for group in groups:
        body = " ".join(group["body"]).strip()
        items.append(
            {
                "icon": group["fields"].get("icon", "check"),
                "title": group["title"],
                "body": body,
            }
        )
        if len(body) > 60:
            report.warn(group["line"], f"features 본문이 깁니다({len(body)}자): {group['title']}")
    title = fields.get("title", "")
    if len(title) > LIMITS["features.title"]:
        report.warn(sec["line"], f"features.title이 깁니다({len(title)}자)")
    return {"type": "features", "title": title, "items": items}


def build_logos(sec, fields, lists, groups, report):
    items = all_items(lists)
    if len(items) > 5:
        report.error(sec["line"], f"logos는 5개까지입니다 (지금 {len(items)}개)")
    return {"type": "logos", "items": items}


def build_quote(sec, fields, lists, groups, report):
    text = fields.get("text", "")
    if len(text) > LIMITS["quote.text"]:
        report.warn(sec["line"], f"quote.text가 깁니다({len(text)}자)")
    return {"type": "quote", "text": text, "author": fields.get("author", "")}


def build_faq(sec, fields, lists, groups, report):
    items = []
    for group in groups:
        answer = " ".join(group["body"]).strip()
        items.append({"q": group["title"], "a": answer})
        if len(answer) > 120:
            report.warn(group["line"], f"faq 답변이 깁니다({len(answer)}자): {group['title']}")
    title = fields.get("title", "자주 묻는 질문")
    return {"type": "faq", "title": title, "items": items}


def build_cta(sec, fields, lists, groups, report):
    return {
        "type": "cta",
        "eyebrow": fields.get("eyebrow", ""),
        "title": fields.get("title", ""),
        "body": fields.get("body", ""),
        "cta": fields.get("cta", ""),
        "ctaIcon": fields.get("ctaIcon", "arrow-right"),
        "note": fields.get("note", ""),
    }


def build_footer(sec, fields, lists, groups, report):
    return {"type": "footer", "left": fields.get("left", ""), "right": fields.get("right", "")}


def build_table(sec, fields, lists, groups, report):
    raw_columns = fields.get("columns", "")
    if "|" not in raw_columns:
        report.error(sec["line"], "table.columns는 `열 | 열 | 열` 형식입니다")
    columns = [c.strip() for c in raw_columns.split("|") if c.strip()]
    # `columns:` 바로 뒤의 `- ` 줄은 열 목록이 아니라 행으로 읽는다
    entries = all_items(lists)
    rows = []
    for index, entry in enumerate(entries, start=1):
        cells = [c.strip() for c in entry.split("|")]
        if len(cells) != len(columns):
            report.error(
                sec["line"],
                f"table {index}행의 열 개수가 다릅니다(열 {len(columns)}개, 행 {len(cells)}개): {entry}",
            )
        rows.append(cells)
    featured = fields.get("featured", "").strip()
    if featured:
        if not featured.isdigit() or not 1 <= int(featured) <= len(columns):
            report.error(sec["line"], f"table.featured는 1~{len(columns)} 사이 숫자입니다: {featured}")
    if len(rows) > 8:
        report.warn(sec["line"], f"table은 8행 이하를 권장합니다 (지금 {len(rows)}행)")
    return {
        "type": "table",
        "title": fields.get("title", ""),
        "columns": columns,
        "rows": rows,
        "featured": int(featured) if featured.isdigit() else 0,
        "note": fields.get("note", ""),
    }


def build_pricing(sec, fields, lists, groups, report):
    items = []
    for group in groups:
        bullets = [line for line in group["body"] if line.strip()]
        featured = str(group["fields"].get("featured", "")).lower() in ("true", "yes", "1", "y")
        items.append(
            {
                "title": group["title"],
                "price": group["fields"].get("price", ""),
                "period": group["fields"].get("period", ""),
                "features": bullets,
                "cta": group["fields"].get("cta", "시작하기"),
                "featured": featured,
            }
        )
        if not group["fields"].get("price"):
            report.error(group["line"], f"pricing/{group['title']}: price가 비어 있습니다")
    if len(items) > 3:
        report.error(sec["line"], f"pricing 카드는 3개까지입니다 (지금 {len(items)}개)")
    featured_count = sum(1 for item in items if item["featured"])
    if featured_count > 1:
        report.error(sec["line"], "pricing에서 featured는 하나만 지정할 수 있습니다")
    return {"type": "pricing", "title": fields.get("title", ""), "note": fields.get("note", ""), "items": items}


def build_gallery(sec, fields, lists, groups, report):
    items = all_items(lists)
    if len(items) > 6:
        report.error(sec["line"], f"gallery는 6개까지입니다 (지금 {len(items)}개)")
    return {"type": "gallery", "title": fields.get("title", ""), "note": fields.get("note", ""), "items": items}


BUILDERS = {
    "header": build_header,
    "hero": build_hero,
    "stats": build_stats,
    "features": build_features,
    "logos": build_logos,
    "quote": build_quote,
    "faq": build_faq,
    "cta": build_cta,
    "footer": build_footer,
    "table": build_table,
    "pricing": build_pricing,
    "gallery": build_gallery,
}

CARD_TYPES = {"features", "faq", "pricing"}


def check_fields(sec, fields, kind, report):
    required, optional = FIELDS[kind]
    allowed = required | optional
    for key in fields:
        if key not in allowed:
            suggestion = difflib.get_close_matches(key, sorted(allowed), n=1)
            hint = f" (`{suggestion[0]}` 아닌가요?)" if suggestion else ""
            report.error(sec["line"], f"{kind}.{key}는 없는 필드입니다{hint}")
    for key in required:
        if key in ("items",) and kind in CARD_TYPES:
            continue
        if not fields.get(key) and key not in ("items",):
            report.error(sec["line"], f"{kind}.{key}가 비어 있습니다")


def asset_index(catalog_path, report):
    data = json.loads(Path(catalog_path).read_text())
    index = {}
    for item in data["items"]:
        kinds = {t.split(":", 1)[1] for t in item.get("tags", []) if t.startswith("kind:")}
        for kind in kinds:
            index.setdefault(kind, {})[item["name"]] = item
    return index


def check_assets(blocks, index, report):
    def lookup(name, kind, where):
        table = index.get(kind, {})
        if name in table:
            item = table[name]
            if item.get("license_scope") != "bundle":
                report.error(
                    None,
                    f"{where}: `{name}` 사용 불가 (scope={item.get('license_scope')}, license={item.get('license')})",
                )
            return
        suggestion = difflib.get_close_matches(name, sorted(table), n=1)
        hint = f" (`{suggestion[0]}` 아닌가요?)" if suggestion else ""
        report.error(None, f"{where}: {kind} `{name}`을 카탈로그에서 찾을 수 없습니다{hint}")

    for block in blocks:
        kind = block["type"]
        if kind == "hero":
            for name in block["illustration"]:
                lookup(name, "illustration", "hero.illustration")
        if kind == "gallery":
            for name in block["items"]:
                lookup(name, "illustration", "gallery")
        if kind == "features":
            for item in block["items"]:
                lookup(item["icon"], "icon", f"features/{item['title']}")
        if kind == "cta" and block.get("ctaIcon"):
            lookup(block["ctaIcon"], "icon", "cta.ctaIcon")
        if kind == "header" and block.get("nav"):
            continue
        if kind == "hero" and block.get("ctaIcon"):
            lookup(block["ctaIcon"], "icon", "hero.ctaIcon")


def parse(path, report):
    text = Path(path).read_text()
    meta, body, start = split_front(text)
    sections = split_sections(body, start, report)

    blocks = []
    seen = {}
    for sec in sections:
        kind = sec["type"]
        if kind not in FIELDS:
            suggestion = difflib.get_close_matches(kind, sorted(FIELDS), n=1)
            hint = f" (`{suggestion[0]}` 아닌가요?)" if suggestion else ""
            report.error(sec["line"], f"알 수 없는 섹션 타입입니다: {kind}{hint}")
            continue
        fields, lists, groups = tokenize(sec, report)
        check_fields(sec, fields, kind, report)
        seen[kind] = seen.get(kind, 0) + 1
        if seen[kind] > 1 and kind not in CARD_TYPES:
            report.error(sec["line"], f"{kind} 섹션이 두 번 나옵니다")
        if kind in CARD_TYPES and not groups:
            report.error(sec["line"], f"{kind}에 `### 항목`이 없습니다")
        blocks.append(BUILDERS[kind](sec, fields, lists, groups, report))

    if "header" not in seen:
        report.warn(None, "header 섹션이 없습니다")
    if "footer" not in seen:
        report.warn(None, "footer 섹션이 없습니다")
    return meta, blocks


def build_recipe(path, meta, blocks):
    name = meta.get("name") or Path(path).stem
    canvas = meta.get("canvas") or {"width": 1440, "height": "auto"}
    if isinstance(canvas, int):
        canvas = {"width": canvas, "height": "auto"}
    return {
        "name": name,
        "seed": meta.get("seed", 7),
        "theme": meta.get("theme", "editorial"),
        "canvas": canvas,
        "content": {
            "source": Path(path).name,
            "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        },
        "blocks": blocks,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("content")
    ap.add_argument("--out", default=None)
    ap.add_argument("--catalog", default=None)
    ap.add_argument("--check", action="store_true", help="검사만 하고 파일을 쓰지 않는다")
    args = ap.parse_args()

    report = Report()
    meta, blocks = parse(args.content, report)
    if args.catalog and Path(args.catalog).is_file():
        check_assets(blocks, asset_index(args.catalog, report), report)
    elif args.catalog:
        report.error(None, f"카탈로그를 찾을 수 없습니다: {args.catalog}")

    for warning in report.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if report.errors:
        for error in report.errors:
            print(f"error: {error}", file=sys.stderr)
        print(f"\n{len(report.errors)}개 오류로 중단했습니다.", file=sys.stderr)
        return 1

    recipe = build_recipe(args.content, meta, blocks)
    payload = json.dumps(recipe, indent=4, ensure_ascii=False) + "\n"
    if args.check:
        print(json.dumps({"blocks": len(blocks), "errors": 0, "warnings": len(report.warnings)}, ensure_ascii=False))
        return 0
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload)
        print(
            json.dumps(
                {"recipe": str(out), "blocks": len(blocks), "warnings": len(report.warnings)},
                ensure_ascii=False,
            )
        )
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
