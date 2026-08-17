import json
import os
import shutil
import sqlite3
import time
from pathlib import Path

# Paths configuration
LIBRARY_PATH = os.environ.get("GALLERY_LIBRARY_PATH", "/app/data")
IMAGES_PATH = Path(LIBRARY_PATH) / "Design.library" / "images"
DB_PATH = os.environ.get("DB_PATH", "/home/mindulle/design-tools-setup/asset_hub.db")
MINIO_REF_PATH = Path("/mnt/monitoring/minio-data/references")


def ensure_dirs():
    MINIO_REF_PATH.mkdir(parents=True, exist_ok=True)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def is_asset(ext, old_tags):
    """Determine if an item is an Asset (True) or Reference (False)."""
    ext = ext.lower() if ext else ""
    asset_exts = {"svg", "ai", "eps", "ttf", "otf", "woff", "woff2", "zip", "psd", "c4d", "blend"}
    if ext in asset_exts:
        return True

    asset_tags = {"icons", "typography", "mockups", "3d-objects", "components"}
    for t in old_tags:
        if t.lower() in asset_tags:
            return True

    # Default to reference for jpg/png/webp
    return False


def map_asset_tags(old_tags, ext):
    """Map legacy Eagle tags to the new Unified Taxonomy for Asset Hub."""
    new_tags = set(["src:sonagi-legacy"])
    ext = ext.lower() if ext else ""

    if ext in ["ttf", "otf", "woff", "woff2"]:
        new_tags.add("category:typography")
    elif ext in ["svg", "ai", "eps"]:
        new_tags.add("format:vector")
        new_tags.add("category:ui-component")
    elif ext in ["zip", "psd", "c4d", "blend"]:
        new_tags.add("category:mockups")

    for tag in old_tags:
        t = tag.lower()
        if t == "auto-ingested":
            continue
        elif t == "icons":
            new_tags.add("category:ui-component")
            new_tags.add("topic:icon")
        elif t in ["typography", "mockups", "components"]:
            new_tags.add(f"category:{t}")
        elif t == "3d-objects":
            new_tags.add("format:3d-object")
        else:
            new_tags.add(f"topic:{t.replace(' ', '-')}")
    return list(new_tags)


def map_reference_tags(old_tags):
    """Map legacy Eagle tags to the new Unified Taxonomy for Reference Hub."""
    new_tags = set(["src:sonagi-legacy"])

    for tag in old_tags:
        t = tag.lower()
        if t == "auto-ingested":
            continue
        # For references, we just map everything to topic for now, or guess pattern/platform
        if "ios" in t or "app" in t:
            new_tags.add("platform:ios")
        elif "web" in t:
            new_tags.add("platform:web")
        elif "onboarding" in t:
            new_tags.add("flow:onboarding")
        elif "login" in t:
            new_tags.add("flow:login")
        else:
            new_tags.add(f"topic:{t.replace(' ', '-')}")

    return list(new_tags)


def migrate_legacy(limit=None):
    print(f"--- Starting Split & Route Migration (Limit: {limit}) ---")

    # We must scan directly from devops physical path if we run this on devops
    # The script runs on devops via sudo, so IMAGES_PATH should be the physical PVC path
    PHYSICAL_IMAGES_PATH = Path(
        "/var/lib/rancher/k3s/storage/pvc-cf5be3f0-486e-404a-a54f-844886ab97c3_default_sonagi-gallery-library-pvc/Design.library/images"
    )

    if not PHYSICAL_IMAGES_PATH.exists():
        print(f"Error: Directory not found -> {PHYSICAL_IMAGES_PATH}")
        return

    ensure_dirs()
    conn = get_db()
    cursor = conn.cursor()

    asset_count = 0
    ref_count = 0
    processed_count = 0

    for item_dir in PHYSICAL_IMAGES_PATH.iterdir():
        if not item_dir.is_dir() or not item_dir.name.endswith(".info"):
            continue

        meta_file = item_dir / "metadata.json"
        if not meta_file.exists():
            continue

        with open(meta_file, "r", encoding="utf-8") as f:
            try:
                meta = json.load(f)
            except Exception:
                continue

        asset_id = meta.get("id")
        name = meta.get("name", "Untitled")
        ext = meta.get("ext", "png")
        old_tags = meta.get("tags", [])

        if not asset_id:
            continue

        # Check if already processed in Asset DB or MinIO
        cursor.execute("SELECT id FROM items WHERE id = ?", (asset_id,))
        if cursor.fetchone():
            continue
        if (MINIO_REF_PATH / f"{asset_id}.{ext}").exists():
            continue

        files_with_ext = list(item_dir.glob(f"*.{ext}"))
        if not files_with_ext:
            continue
        orig_path = next((f for f in files_with_ext if not f.name.endswith("_thumbnail.jpg")), files_with_ext[0])

        # Route: Asset vs Reference
        if is_asset(ext, old_tags):
            # >> Route to Asset Hub (DB Insert)
            new_tags = map_asset_tags(old_tags, ext)
            tags_json = json.dumps(new_tags)

            orig_container_path = f"/app/data/Design.library/images/{item_dir.name}/{orig_path.name}"
            thumb_path = item_dir / f"{asset_id}_thumbnail.jpg"
            thumb_container_path = f"/app/data/Design.library/images/{item_dir.name}/{thumb_path.name}" if thumb_path.exists() else ""

            cursor.execute(
                "INSERT INTO items (id, name, ext, tags, annotation, url, created_at, thumbnail_path, original_path) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    asset_id,
                    name,
                    ext,
                    tags_json,
                    meta.get("annotation", ""),
                    meta.get("url", ""),
                    int(time.time()),
                    thumb_container_path,
                    orig_container_path,
                ),
            )
            for tag in new_tags:
                cursor.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
                cursor.execute("SELECT id FROM tags WHERE name = ?", (tag,))
                tag_id_row = cursor.fetchone()
                if tag_id_row:
                    cursor.execute("INSERT OR IGNORE INTO item_tags (item_id, tag_id) VALUES (?, ?)", (asset_id, tag_id_row[0]))
            conn.commit()

            asset_count += 1
            print(f"[ASSET] Inserted DB: {name}.{ext} -> Tags: {new_tags}")

        else:
            # >> Route to Reference Hub (MinIO CDN Copy + JSON)
            new_tags = map_reference_tags(old_tags)

            dest_img = MINIO_REF_PATH / f"{asset_id}.{ext}"
            dest_json = MINIO_REF_PATH / f"{asset_id}.json"

            shutil.copy2(orig_path, dest_img)

            ref_meta = {
                "id": asset_id,
                "name": name,
                "ext": ext,
                "tags": new_tags,
                "annotation": meta.get("annotation", ""),
                "cdn_url": f"https://cdn.sonagi.space/references/{asset_id}.{ext}",
            }
            with open(dest_json, "w", encoding="utf-8") as jf:
                json.dump(ref_meta, jf, ensure_ascii=False, indent=2)

            ref_count += 1
            print(f"[REFERENCE] Copied to CDN: {name}.{ext} -> Tags: {new_tags}")

        processed_count += 1
        if limit is not None and processed_count >= limit:
            print(f"--- Reached limit of {limit}. Stopping. ---")
            break

    print(f"Summary: Processed {processed_count} items. Assets: {asset_count}, References: {ref_count}")
    conn.close()


if __name__ == "__main__":
    migrate_legacy(limit=None)
