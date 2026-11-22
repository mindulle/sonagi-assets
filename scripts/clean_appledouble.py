#!/usr/bin/env python3
"""macOS AppleDouble(`._*`) 행/파일 정리.

기본은 dry-run. --apply 를 주면:
  1) DB 백업
  2) 기존 `._*` 파일을 tar.gz로 아카이브
  3) 파일 삭제
  4) DB에서 해당 행 삭제
"""

import argparse
import datetime
import json
import os
import sqlite3
import tarfile

APPLEDOUBLE_MAGIC = b"\x00\x05\x16\x07"


def host_path(original_path, library_root):
    if not original_path:
        return None
    if original_path.startswith("/app/data/"):
        return os.path.join(library_root, original_path[len("/app/data/") :])
    return original_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--library-root", required=True)
    ap.add_argument("--archive-dir", default="/srv/archive")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    rows = list(conn.execute("select id,name,original_path from items where name like '._%'"))
    conn.close()

    files = []
    missing = 0
    for row_id, name, original in rows:
        path = host_path(original, args.library_root)
        if path and os.path.isfile(path):
            with open(path, "rb") as f:
                if f.read(4) != APPLEDOUBLE_MAGIC:
                    raise SystemExit(f"unexpected non-AppleDouble file: {path}")
            files.append((row_id, path))
        else:
            missing += 1

    summary = {"rows": len(rows), "files": len(files), "missing": missing, "apply": args.apply}
    if not args.apply:
        print(json.dumps(summary, ensure_ascii=False))
        return 0

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    os.makedirs(args.archive_dir, exist_ok=True)
    archive = os.path.join(args.archive_dir, f"appledouble-{stamp}.tar.gz")
    with tarfile.open(archive, "w:gz") as tar:
        for _, path in files:
            tar.add(path, arcname=os.path.relpath(path, args.library_root))

    db_backup = f"{args.db}.bak-appledouble-{stamp}"
    src = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    dst = sqlite3.connect(db_backup)
    src.backup(dst)
    dst.close()
    src.close()

    for _, path in files:
        os.remove(path)

    conn = sqlite3.connect(args.db, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    deleted = conn.execute("delete from items where name like '._%'").rowcount
    conn.commit()
    conn.close()

    summary.update({"deleted_rows": deleted, "archive": archive, "db_backup": db_backup})
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
