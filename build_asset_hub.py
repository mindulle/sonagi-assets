import fcntl
import json
import os
import sqlite3
import sys

from tqdm import tqdm

LOCK_FILE = "asset_hub.lock"
DB_PATH = "asset_hub.db"
LIBRARY_PATH = os.environ.get("GALLERY_LIBRARY_PATH", "/mnt/monitoring/@GP66_D드라이브 백업/my-eagle/Design.library/images")
AI_ASSETS_PATH = os.environ.get("AI_ASSETS_PATH", "/app/data/ai-assets/images")


def acquire_lock():
    lock = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock
    except OSError:
        lock.close()
        return None


def release_lock(lock):
    fcntl.flock(lock, fcntl.LOCK_UN)
    lock.close()
    try:
        os.remove(LOCK_FILE)
    except OSError:
        pass


def init_db():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.execute("PRAGMA journal_mode=WAL;")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS items
                 (id TEXT PRIMARY KEY, name TEXT, ext TEXT, tags TEXT,
                  annotation TEXT, url TEXT, thumbnail_path TEXT, original_path TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS tags
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE)""")
    c.execute("""CREATE TABLE IF NOT EXISTS item_tags
                 (item_id TEXT NOT NULL, tag_id INTEGER NOT NULL,
                  PRIMARY KEY (item_id, tag_id),
                  FOREIGN KEY (item_id) REFERENCES items(id),
                  FOREIGN KEY (tag_id) REFERENCES tags(id))""")
    conn.commit()
    return conn


def process_tags(c, item_id, tags_list):
    for tag in tags_list:
        c.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
        c.execute("SELECT id FROM tags WHERE name = ?", (tag,))
        tag_id = c.fetchone()[0]
        c.execute("INSERT OR IGNORE INTO item_tags (item_id, tag_id) VALUES (?, ?)", (item_id, tag_id))


def scan_library(library_path: str, c, batch_data: list, count: int) -> tuple[list, int]:
    if not os.path.exists(library_path):
        print(f"Skipping (not found): {library_path}")
        return batch_data, count

    print(f"Scanning {library_path}...")
    info_dirs = [d for d in os.listdir(library_path) if d.endswith(".info")]

    for info_dir in tqdm(info_dirs):
        dir_path = os.path.join(library_path, info_dir)
        meta_path = os.path.join(dir_path, "metadata.json")

        if not os.path.exists(meta_path):
            continue

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)

            item_id = meta.get("id", info_dir.replace(".info", ""))
            name = meta.get("name", "")
            ext = meta.get("ext", "")
            tags_list = meta.get("tags", [])
            annotation = meta.get("annotation", "")
            url = meta.get("url", "")

            files = os.listdir(dir_path)
            thumbnail = next((f for f in files if "_thumbnail." in f), None)
            original = next(
                (f for f in files if f != "metadata.json" and not f.endswith(".info") and "_thumbnail" not in f),
                None,
            )

            thumb_path = os.path.join(dir_path, thumbnail) if thumbnail else ""
            orig_path = os.path.join(dir_path, original) if original else ""

            batch_data.append((item_id, name, ext, json.dumps(tags_list), annotation, url, thumb_path, orig_path))
            process_tags(c, item_id, tags_list)

            count += 1
            if count % 1000 == 0:
                c.executemany("INSERT OR REPLACE INTO items VALUES (?,?,?,?,?,?,?,?)", batch_data)
                batch_data = []

        except Exception:
            pass

    return batch_data, count


def build_index():
    conn = init_db()
    c = conn.cursor()

    count = 0
    batch_data = []

    # Eagle.cool 원본 라이브러리 스캔
    batch_data, count = scan_library(LIBRARY_PATH, c, batch_data, count)

    # AI 생성 에셋 스캔
    batch_data, count = scan_library(AI_ASSETS_PATH, c, batch_data, count)

    if batch_data:
        c.executemany("INSERT OR REPLACE INTO items VALUES (?,?,?,?,?,?,?,?)", batch_data)

    conn.commit()
    conn.close()
    print(f"Indexed {count} items into {DB_PATH}")


if __name__ == "__main__":
    lock = acquire_lock()
    if lock is None:
        print("Already running, skipping.", flush=True)
        sys.exit(0)
    try:
        build_index()
    finally:
        release_lock(lock)
