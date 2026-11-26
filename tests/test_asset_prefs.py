"""Offline tests for T5 (GRAPH-39): asset_prefs sidecar, recency decay, 30% exploration quota, and /gallery."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import asset_prefs  # noqa: E402


class AssetPrefsSidecarTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self.tmp.name)
        self.db_path = self.tmpdir / "asset_hub.db"
        self.jsonl_path = self.tmpdir / "asset_prefs.jsonl"
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        asset_prefs.init_prefs_table(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def test_record_jsonl_and_sqlite_and_query(self) -> None:
        ev = asset_prefs.record_pref_event(
            {
                "asset_id": "svg-01",
                "brand": "mindulle",
                "event": "chosen",
                "context": "hero botanical mark",
                "reason_tags": ["calm", "minimal"],
                "run_id": "run-100",
                "ts": "2026-11-25T10:00:00Z",
            },
            conn=self.conn,
            jsonl_path=self.jsonl_path,
        )
        self.assertEqual(ev["asset_id"], "svg-01")
        self.assertTrue(self.jsonl_path.is_file())

        rows = asset_prefs.query_pref_events(self.conn, brand="mindulle", month="2026-11")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["reason_tags"], ["calm", "minimal"])

        with self.assertRaises(ValueError):
            asset_prefs.record_pref_event({"asset_id": "svg-01", "event": "invalid"}, conn=self.conn)

        # Idempotent sync from JSONL into a fresh DB
        db2 = sqlite3.connect(":memory:")
        inserted_first = asset_prefs.sync_jsonl_to_sqlite(self.jsonl_path, db2)
        inserted_second = asset_prefs.sync_jsonl_to_sqlite(self.jsonl_path, db2)
        self.assertEqual(inserted_first, 1)
        self.assertEqual(inserted_second, 0)
        db2.close()

    def test_recency_decay_favors_recent_choice(self) -> None:
        now = dt.datetime(2026, 11, 26, 0, 0, tzinfo=dt.timezone.utc)
        events = [
            {"asset_id": "a-old", "event": "chosen", "ts": "2026-07-01T00:00:00Z"},
            {"asset_id": "a-old", "event": "rejected", "ts": "2026-11-25T00:00:00Z"},
            {"asset_id": "a-new", "event": "chosen", "ts": "2026-11-25T00:00:00Z"},
        ]
        summary = asset_prefs.summarize_prefs(events, now=now, half_life_days=30.0)
        self.assertGreater(summary["a-new"]["boost"], summary["a-old"]["boost"])
        self.assertLess(summary["a-old"]["boost"], 0.0)

    def test_export_catalog_immutable_license_filter_and_exploration_quota(self) -> None:
        catalog_path = self.tmpdir / "catalog.json"
        out_path = self.tmpdir / "catalog.render.json"
        items = [
            {"id": f"pref-{i}", "name": f"Pref {i}", "ext": "svg", "license": "cc0", "license_scope": "bundle"}
            for i in range(7)
        ] + [
            {"id": f"new-{i}", "name": f"New {i}", "ext": "svg", "license": "ofl", "license_scope": "bundle"}
            for i in range(5)
        ] + [
            {"id": "blocked-1", "name": "Paid", "ext": "svg", "license": "commercial", "license_scope": "blocked"},
            {"id": "unknown-1", "name": "Unknown", "ext": "svg", "license": "unknown", "license_scope": "blocked"},
        ]
        catalog_path.write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8")
        before_hash = hashlib.sha256(catalog_path.read_bytes()).hexdigest()

        now = dt.datetime(2026, 11, 26, 0, 0, tzinfo=dt.timezone.utc)
        events = [
            {"asset_id": f"pref-{i}", "brand": "mindulle", "event": "chosen", "ts": "2026-11-25T00:00:00Z"}
            for i in range(7)
        ] + [
            {"asset_id": "blocked-1", "brand": "mindulle", "event": "chosen", "ts": "2026-11-25T00:00:00Z"},
            {"asset_id": "unknown-1", "brand": "mindulle", "event": "chosen", "ts": "2026-11-25T00:00:00Z"},
        ]

        exported = asset_prefs.export_catalog_with_prefs(
            catalog_path,
            out_path,
            events=events,
            brand="mindulle",
            exploration_quota=0.30,
            limit=10,
            now=now,
        )

        # Original catalog.json must remain byte-for-byte identical
        after_hash = hashlib.sha256(catalog_path.read_bytes()).hexdigest()
        self.assertEqual(before_hash, after_hash)

        exported_ids = [it["id"] for it in exported["items"]]
        self.assertNotIn("blocked-1", exported_ids)
        self.assertNotIn("unknown-1", exported_ids)
        self.assertEqual(len(exported_ids), 10)
        # At least 30% (3 out of 10) must be unexplored assets
        self.assertGreaterEqual(exported["counts"]["unexplored_exported"], 3)

    def test_render_gallery_html_chosen_vs_rejected_and_xss_escape(self) -> None:
        events = [
            {
                "asset_id": "svg-win",
                "brand": "mindulle",
                "event": "chosen",
                "context": "clean <script>alert(1)</script>",
                "reason_tags": ["calm"],
                "ts": "2026-11-20T12:00:00Z",
            },
            {
                "asset_id": "svg-lose",
                "brand": "mindulle",
                "event": "rejected",
                "context": "too noisy",
                "reason_tags": ["noisy"],
                "ts": "2026-11-20T12:05:00Z",
            },
            {
                "asset_id": "svg-oct",
                "brand": "mindulle",
                "event": "chosen",
                "context": "october",
                "reason_tags": [],
                "ts": "2026-10-10T12:00:00Z",
            },
        ]
        html_out = asset_prefs.render_gallery_html(
            events,
            month="2026-11",
            brand="mindulle",
            items_by_id={"svg-win": {"name": "Seal Mark", "ext": "svg", "license": "cc0"}},
        )
        self.assertIn("Seal Mark", html_out)
        self.assertIn("svg-lose", html_out)
        self.assertNotIn("svg-oct", html_out)
        self.assertNotIn("<script>alert(1)</script>", html_out)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html_out)


if __name__ == "__main__":
    unittest.main()
