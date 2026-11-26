#!/usr/bin/env python3
"""자산 선호 사이드카 — JSONL/SQLite 원장, 최근성 감쇠, 30% 탐험 쿼터, /gallery 월간 뷰어 (GRAPH-39 / T5).

원본 `catalog.json`과 `items` 테이블은 절대 수정하지 않는다.
라이선스 필터(`license_scope != "blocked"`)는 선호 점수와 무관하게 항상 우선한다.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import math
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

try:
    from scripts.license_policy import SCOPE_BLOCKED, scope_for_license
except ImportError:
    from license_policy import SCOPE_BLOCKED, scope_for_license

VALID_EVENTS = ("proposed", "chosen", "rejected")
DEFAULT_EXPLORATION_QUOTA = 0.30
DEFAULT_HALF_LIFE_DAYS = 30.0


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(value: str) -> dt.datetime:
    raw = (value or "").strip()
    if not raw:
        return dt.datetime.now(dt.timezone.utc)
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    parsed = dt.datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def init_prefs_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS asset_prefs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id TEXT NOT NULL,
            brand TEXT NOT NULL DEFAULT '',
            event TEXT NOT NULL CHECK (event IN ('proposed', 'chosen', 'rejected')),
            context TEXT NOT NULL DEFAULT '',
            reason_tags TEXT NOT NULL DEFAULT '[]',
            run_id TEXT NOT NULL DEFAULT '',
            ts TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_asset_prefs_asset ON asset_prefs(asset_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_asset_prefs_brand_ts ON asset_prefs(brand, ts)")
    conn.commit()


def normalize_event(payload: Mapping[str, Any]) -> Dict[str, Any]:
    asset_id = str(payload.get("asset_id") or "").strip()
    if not asset_id:
        raise ValueError("asset_id is required")
    event = str(payload.get("event") or "").strip().lower()
    if event not in VALID_EVENTS:
        raise ValueError(f"event must be one of {VALID_EVENTS}, got {event!r}")
    raw_tags = payload.get("reason_tags") or []
    if isinstance(raw_tags, str):
        try:
            parsed = json.loads(raw_tags)
            raw_tags = parsed if isinstance(parsed, list) else [raw_tags]
        except ValueError:
            raw_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
    reason_tags = [str(t).strip() for t in raw_tags if str(t).strip()]
    ts = str(payload.get("ts") or "").strip() or utc_now_iso()
    parse_ts(ts)
    return {
        "asset_id": asset_id,
        "brand": str(payload.get("brand") or "").strip(),
        "event": event,
        "context": str(payload.get("context") or "").strip(),
        "reason_tags": reason_tags,
        "run_id": str(payload.get("run_id") or "").strip(),
        "ts": ts,
    }


def append_jsonl(jsonl_path: Path | str, record: Mapping[str, Any]) -> None:
    path = Path(jsonl_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(dict(record), ensure_ascii=False) + "\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)


def read_jsonl(jsonl_path: Path | str) -> List[Dict[str, Any]]:
    path = Path(jsonl_path)
    if not path.is_file():
        return []
    records: List[Dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
                if isinstance(obj, dict):
                    records.append(normalize_event(obj))
            except (ValueError, TypeError):
                continue
    return records


def insert_sqlite_event(conn: sqlite3.Connection, record: Mapping[str, Any]) -> int:
    init_prefs_table(conn)
    cur = conn.execute(
        """
        INSERT INTO asset_prefs (asset_id, brand, event, context, reason_tags, run_id, ts)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record["asset_id"],
            record["brand"],
            record["event"],
            record["context"],
            json.dumps(record["reason_tags"], ensure_ascii=False),
            record["run_id"],
            record["ts"],
        ),
    )
    conn.commit()
    return int(cur.lastrowid or 0)


def record_pref_event(
    payload: Mapping[str, Any],
    *,
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[Path | str] = None,
    jsonl_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    record = normalize_event(payload)
    if jsonl_path is not None:
        append_jsonl(jsonl_path, record)
    if conn is not None:
        insert_sqlite_event(conn, record)
    elif db_path is not None:
        local_conn = sqlite3.connect(str(db_path), timeout=20)
        try:
            insert_sqlite_event(local_conn, record)
        finally:
            local_conn.close()
    return record


def sync_jsonl_to_sqlite(jsonl_path: Path | str, conn: sqlite3.Connection) -> int:
    """JSONL 이벤트 로그를 SQLite `asset_prefs` 테이블로 적재한다(중복 방지)."""
    init_prefs_table(conn)
    records = read_jsonl(jsonl_path)
    inserted = 0
    for rec in records:
        exists = conn.execute(
            """
            SELECT 1 FROM asset_prefs
            WHERE asset_id = ? AND brand = ? AND event = ? AND run_id = ? AND ts = ?
            LIMIT 1
            """,
            (rec["asset_id"], rec["brand"], rec["event"], rec["run_id"], rec["ts"]),
        ).fetchone()
        if not exists:
            insert_sqlite_event(conn, rec)
            inserted += 1
    return inserted


def query_pref_events(
    conn: sqlite3.Connection,
    *,
    brand: str = "",
    asset_id: str = "",
    event: str = "",
    month: str = "",
    limit: int = 200,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    init_prefs_table(conn)
    clauses: List[str] = []
    params: List[Any] = []
    if brand:
        clauses.append("brand = ?")
        params.append(brand)
    if asset_id:
        clauses.append("asset_id = ?")
        params.append(asset_id)
    if event:
        clauses.append("event = ?")
        params.append(event)
    if month:
        clauses.append("substr(ts, 1, 7) = ?")
        params.append(month)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        f"SELECT id, asset_id, brand, event, context, reason_tags, run_id, ts "
        f"FROM asset_prefs {where} ORDER BY ts DESC, id DESC LIMIT ? OFFSET ?"
    )
    params.extend([limit, offset])
    rows = conn.execute(sql, params).fetchall()
    out: List[Dict[str, Any]] = []
    for row in rows:
        if isinstance(row, sqlite3.Row):
            raw_tags = row["reason_tags"]
            item = {
                "id": row["id"],
                "asset_id": row["asset_id"],
                "brand": row["brand"],
                "event": row["event"],
                "context": row["context"],
                "reason_tags": json.loads(raw_tags) if raw_tags else [],
                "run_id": row["run_id"],
                "ts": row["ts"],
            }
        else:
            raw_tags = row[5]
            item = {
                "id": row[0],
                "asset_id": row[1],
                "brand": row[2],
                "event": row[3],
                "context": row[4],
                "reason_tags": json.loads(raw_tags) if raw_tags else [],
                "run_id": row[6],
                "ts": row[7],
            }
        out.append(item)
    return out


def recency_weight(ts_str: str, *, now: Optional[dt.datetime] = None, half_life_days: float = DEFAULT_HALF_LIFE_DAYS) -> float:
    if half_life_days <= 0:
        return 1.0
    ref = now or dt.datetime.now(dt.timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=dt.timezone.utc)
    event_dt = parse_ts(ts_str)
    age_days = max(0.0, (ref - event_dt).total_seconds() / 86400.0)
    return math.exp(-math.log(2.0) * age_days / half_life_days)


def summarize_prefs(
    events: Iterable[Mapping[str, Any]],
    *,
    now: Optional[dt.datetime] = None,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
    brand: str = "",
) -> Dict[str, Dict[str, Any]]:
    """자산별 선호 요약(원시 횟수 + 최근성 감쇠 가중치 + 부스트)을 계산한다."""
    ref = now or dt.datetime.now(dt.timezone.utc)
    summary: Dict[str, Dict[str, Any]] = {}

    for ev in events:
        if brand and str(ev.get("brand") or "") != brand:
            continue
        aid = str(ev.get("asset_id") or "").strip()
        kind = str(ev.get("event") or "").strip().lower()
        if not aid or kind not in VALID_EVENTS:
            continue
        ts_str = str(ev.get("ts") or "")
        w = recency_weight(ts_str, now=ref, half_life_days=half_life_days)

        entry = summary.setdefault(
            aid,
            {
                "asset_id": aid,
                "proposed": 0,
                "chosen": 0,
                "rejected": 0,
                "decayed_proposed": 0.0,
                "decayed_chosen": 0.0,
                "decayed_rejected": 0.0,
                "reason_tags": Counter(),
                "last_ts": ts_str,
            },
        )
        entry[kind] += 1
        entry[f"decayed_{kind}"] += w
        if ts_str > entry["last_ts"]:
            entry["last_ts"] = ts_str
        if kind == "chosen":
            for tag in ev.get("reason_tags") or ():
                if str(tag).strip():
                    entry["reason_tags"][str(tag).strip()] += 1

    for entry in summary.values():
        dc = entry["decayed_chosen"]
        dr = entry["decayed_rejected"]
        dp = entry["decayed_proposed"]
        denom = max(1.0, dc + dr, dp * 0.5)
        raw_boost = 0.25 * ((dc - dr) / denom)
        entry["boost"] = round(max(-0.25, min(0.25, raw_boost)), 4)
        entry["reason_tags"] = dict(entry["reason_tags"])
        if entry["chosen"] >= 1 and dc >= dr:
            entry["status"] = "preferred"
        elif entry["chosen"] == 0 and entry["rejected"] >= 3:
            entry["status"] = "demoted"
        elif dr > dc * 1.5 and entry["rejected"] >= 2:
            entry["status"] = "demoted"
        else:
            entry["status"] = "neutral"

    return summary


def is_license_allowed(item: Mapping[str, Any]) -> bool:
    """선호와 무관하게 라이선스 차단(`blocked`) 에셋은 제외한다."""
    if item.get("junk"):
        return False
    scope = str(item.get("license_scope") or "").strip().lower()
    if scope == SCOPE_BLOCKED:
        return False
    lic = str(item.get("license") or "").strip().lower()
    if not lic:
        return scope in ("public", "bundle", "output")
    return scope_for_license(lic) != SCOPE_BLOCKED


def export_catalog_with_prefs(
    catalog_path: Path | str,
    out_path: Path | str,
    *,
    events: Sequence[Mapping[str, Any]] = (),
    brand: str = "",
    exploration_quota: float = DEFAULT_EXPLORATION_QUOTA,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
    limit: Optional[int] = None,
    now: Optional[dt.datetime] = None,
) -> Dict[str, Any]:
    """원본 `catalog.json`을 수정하지 않고 선호 부스트 + 탐험 쿼터가 반영된 렌더용 카탈로그를 내보낸다."""
    src = Path(catalog_path)
    catalog = json.loads(src.read_text(encoding="utf-8"))
    raw_items = catalog.get("items") or []

    prefs_summary = summarize_prefs(events, now=now, half_life_days=half_life_days, brand=brand)

    eligible = [dict(it) for it in raw_items if is_license_allowed(it)]
    explored: List[Dict[str, Any]] = []
    unexplored: List[Dict[str, Any]] = []

    for idx, item in enumerate(eligible):
        aid = str(item.get("id") or "")
        pref = prefs_summary.get(aid)
        if pref is None:
            item["preference_boost"] = 0.0
            item["preference_status"] = "unexplored"
            item["explored"] = False
            item["_sort_key"] = (0.0, -idx)
            unexplored.append(item)
        else:
            boost = float(pref["boost"])
            item["preference_boost"] = boost
            item["preference_status"] = pref["status"]
            item["explored"] = True
            item["_sort_key"] = (boost, -idx)
            explored.append(item)

    explored.sort(key=lambda x: x["_sort_key"], reverse=True)
    total_target = min(len(eligible), limit) if limit is not None else len(eligible)
    quota = max(0.0, min(1.0, float(exploration_quota)))
    min_explore = min(len(unexplored), math.ceil(total_target * quota))

    selected_unexplored = unexplored[:min_explore]
    remaining_pool = explored + unexplored[min_explore:]
    remaining_pool.sort(key=lambda x: x["_sort_key"], reverse=True)

    merged: List[Dict[str, Any]] = []
    u_idx = 0
    e_idx = 0
    step = max(1, round(1.0 / quota)) if quota > 0 and min_explore > 0 else total_target + 1

    for pos in range(total_target):
        need_explore_slot = (
            u_idx < len(selected_unexplored)
            and ((pos + 1) % step == 0 or e_idx >= len(remaining_pool))
        )
        if need_explore_slot:
            merged.append(selected_unexplored[u_idx])
            u_idx += 1
        elif e_idx < len(remaining_pool):
            merged.append(remaining_pool[e_idx])
            e_idx += 1
        elif u_idx < len(selected_unexplored):
            merged.append(selected_unexplored[u_idx])
            u_idx += 1

    for item in merged:
        item.pop("_sort_key", None)

    out_obj = {
        "generated_at": utc_now_iso(),
        "source_catalog": str(src),
        "brand": brand or None,
        "exploration_quota": quota,
        "half_life_days": half_life_days,
        "counts": {
            "source_total": len(raw_items),
            "license_allowed": len(eligible),
            "exported": len(merged),
            "unexplored_exported": sum(1 for x in merged if not x["explored"]),
            "explored_exported": sum(1 for x in merged if x["explored"]),
        },
        "items": merged,
    }
    dst = Path(out_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_obj


def render_gallery_html(
    events: Sequence[Mapping[str, Any]],
    *,
    month: str = "",
    brand: str = "",
    items_by_id: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> str:
    """월간 선택/거절 대비 HTML 뷰어를 생성한다."""
    all_months = sorted({str(ev.get("ts") or "")[:7] for ev in events if len(str(ev.get("ts") or "")) >= 7}, reverse=True)
    active_month = month or (all_months[0] if all_months else dt.datetime.now(dt.timezone.utc).strftime("%Y-%m"))

    filtered = [
        ev
        for ev in events
        if str(ev.get("ts") or "").startswith(active_month) and (not brand or str(ev.get("brand") or "") == brand)
    ]

    chosen = [ev for ev in filtered if ev.get("event") == "chosen"]
    rejected = [ev for ev in filtered if ev.get("event") == "rejected"]
    proposed_cnt = sum(1 for ev in filtered if ev.get("event") == "proposed")

    tag_counts: Counter[str] = Counter()
    for ev in chosen:
        for t in ev.get("reason_tags") or ():
            tag_counts[str(t)] += 1

    def _card(ev: Mapping[str, Any], kind_cls: str) -> str:
        aid = str(ev.get("asset_id") or "")
        meta = (items_by_id or {}).get(aid) or {}
        name = str(meta.get("name") or aid)
        ext = str(meta.get("ext") or "")
        lic = str(meta.get("license") or "")
        tags = ", ".join(str(t) for t in (ev.get("reason_tags") or ()))
        ctx = str(ev.get("context") or "")
        ts_val = str(ev.get("ts") or "")
        brand_val = str(ev.get("brand") or "-")
        badge = f"{ext.upper()} · {lic}" if ext or lic else "asset"
        return (
            f'<article class="card {kind_cls}">'
            f'<div class="card-head"><strong>{html.escape(name)}</strong>'
            f'<span class="badge">{html.escape(badge)}</span></div>'
            f'<div class="meta">id: <code>{html.escape(aid)}</code> · brand: {html.escape(brand_val)}</div>'
            f'<div class="ctx">{html.escape(ctx) if ctx else "맥락 없음"}</div>'
            f'<div class="tags">{html.escape(tags) if tags else "태그 없음"}</div>'
            f'<div class="ts">{html.escape(ts_val)}</div>'
            f"</article>"
        )

    chosen_html = "".join(_card(ev, "chosen") for ev in chosen) or '<p class="empty">이 달의 선택 기록이 없습니다.</p>'
    rejected_html = "".join(_card(ev, "rejected") for ev in rejected) or '<p class="empty">이 달의 거절 기록이 없습니다.</p>'
    month_options = "".join(
        f'<option value="{html.escape(m)}"{" selected" if m == active_month else ""}>{html.escape(m)}</option>'
        for m in (all_months or [active_month])
    )
    top_tags_html = ", ".join(f"{html.escape(k)} ({v})" for k, v in tag_counts.most_common(5)) or "없음"
    win_rate = f"{(len(chosen) / max(1, len(chosen) + len(rejected)) * 100):.1f}%"

    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Sonagi Asset Preference Gallery — {html.escape(active_month)}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Pretendard", sans-serif; margin: 0; padding: 24px; background: #faf9f6; color: #1c1917; }}
  header {{
    display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center;
    gap: 16px; border-bottom: 1px solid #e7e5e4; padding-bottom: 16px; margin-bottom: 20px;
  }}
  h1 {{ margin: 0; font-size: 20px; }}
  .kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 24px; }}
  .kpi {{ background: #fff; border: 1px solid #e7e5e4; border-radius: 10px; padding: 12px 14px; }}
  .kpi .label {{ font-size: 12px; color: #78716c; }}
  .kpi .val {{ font-size: 20px; font-weight: 700; margin-top: 4px; }}
  .cols {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  @media (max-width: 820px) {{ .cols {{ grid-template-columns: 1fr; }} }}
  .col h2 {{ font-size: 16px; margin: 0 0 12px; }}
  .card {{ background: #fff; border: 1px solid #e7e5e4; border-radius: 10px; padding: 12px 14px; margin-bottom: 10px; }}
  .card.chosen {{ border-left: 4px solid #15803d; }}
  .card.rejected {{ border-left: 4px solid #b91c1c; }}
  .card-head {{ display: flex; justify-content: space-between; align-items: center; gap: 8px; }}
  .badge {{ font-size: 11px; background: #f5f5f4; padding: 2px 8px; border-radius: 999px; color: #57534e; }}
  .meta, .ts {{ font-size: 12px; color: #78716c; margin-top: 4px; }}
  .ctx {{ font-size: 13px; margin-top: 6px; }}
  .tags {{ font-size: 12px; color: #44403c; margin-top: 4px; }}
  .empty {{ color: #78716c; font-size: 14px; }}
  form {{ display: flex; gap: 8px; align-items: center; }}
  input, select, button {{ padding: 6px 10px; border: 1px solid #d6d3d1; border-radius: 6px; font-size: 13px; }}
  button {{ background: #1c1917; color: #fff; cursor: pointer; }}
</style>
</head>
<body>
  <header>
    <h1>자산 선호 월간 갤러리 ({html.escape(active_month)})</h1>
    <form method="get" action="/gallery">
      <select name="month">{month_options}</select>
      <input type="text" name="brand" placeholder="brand 필터" value="{html.escape(brand)}" />
      <button type="submit">적용</button>
    </form>
  </header>
  <section class="kpis">
    <div class="kpi"><div class="label">제안 (Proposed)</div><div class="val">{proposed_cnt}</div></div>
    <div class="kpi"><div class="kpi-label label">선택 (Chosen)</div><div class="val">{len(chosen)}</div></div>
    <div class="kpi"><div class="label">거절 (Rejected)</div><div class="val">{len(rejected)}</div></div>
    <div class="kpi"><div class="label">선택률</div><div class="val">{win_rate}</div></div>
    <div class="kpi"><div class="label">상위 선택 태그</div><div class="val" style="font-size:13px;font-weight:500;">{top_tags_html}</div></div>
  </section>
  <section class="cols">
    <div class="col">
      <h2>선택된 자산 ({len(chosen)})</h2>
      {chosen_html}
    </div>
    <div class="col">
      <h2>거절된 자산 ({len(rejected)})</h2>
      {rejected_html}
    </div>
  </section>
</body>
</html>
"""
