import json
import os
import sqlite3
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

# Paths configuration matching asset_hub_app.py
LIBRARY_PATH = os.environ.get("GALLERY_LIBRARY_PATH", "/app/data")
ORIGINALS_PATH = Path(LIBRARY_PATH) / "originals"
THUMBNAILS_PATH = Path(LIBRARY_PATH) / "thumbnails"
DB_PATH = os.environ.get("DB_PATH", "asset_hub.db")

# The Met API base URLs
SEARCH_URL = "https://collectionapi.metmuseum.org/public/collection/v1/search"
OBJECT_URL = "https://collectionapi.metmuseum.org/public/collection/v1/objects/"


def ensure_dirs():
    ORIGINALS_PATH.mkdir(parents=True, exist_ok=True)
    THUMBNAILS_PATH.mkdir(parents=True, exist_ok=True)


def download_image(url: str, dest_path: Path):
    try:
        urllib.request.urlretrieve(url, dest_path)
        return True
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return False


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def harvest_the_met(query: str, limit: int = 10):
    print(f"Harvesting The Met API for: {query}")
    params = urllib.parse.urlencode({"isPublicDomain": "true", "hasImages": "true", "q": query})

    try:
        req = urllib.request.urlopen(f"{SEARCH_URL}?{params}")
        data = json.loads(req.read())
        object_ids = data.get("objectIDs", [])
        if not object_ids:
            print(f"No objects found for query: {query}")
            return

        print(f"Found {data['total']} objects. Fetching top {limit}...")

        conn = get_db()
        cursor = conn.cursor()

        fetched = 0
        for obj_id in object_ids:
            if fetched >= limit:
                break

            try:
                obj_req = urllib.request.urlopen(f"{OBJECT_URL}{obj_id}")
                obj_data = json.loads(obj_req.read())
            except Exception as e:
                print(f"Failed to fetch object {obj_id}: {e}")
                continue

            image_url = obj_data.get("primaryImageSmall") or obj_data.get("primaryImage")
            if not image_url:
                continue

            title = obj_data.get("title", "Untitled")
            medium = obj_data.get("medium", "")
            department = obj_data.get("department", "")

            # Generate tags
            raw_tags = obj_data.get("tags", [])
            tags = ["src:the-met"]
            if department:
                tags.append(f"dept:{department.lower().replace(' ', '-')}")
            if medium:
                # Add simplified medium tag
                if "watercolor" in medium.lower():
                    tags.append("medium:watercolor")
                elif "woodblock" in medium.lower():
                    tags.append("medium:woodblock")
                elif "oil" in medium.lower():
                    tags.append("medium:oil")

            if raw_tags:
                tags.extend([f"topic:{t['term'].lower().replace(' ', '-')}" for t in raw_tags])

            # Download Image
            asset_id = str(uuid.uuid4())
            ext = "jpg"  # The Met API usually returns JPGs
            file_name = f"{asset_id}.{ext}"
            orig_path = ORIGINALS_PATH / file_name

            print(f"Downloading [{title}]...")
            if not download_image(image_url, orig_path):
                continue

            # Since we download small image, we can use it as both original and thumbnail
            thumb_path = THUMBNAILS_PATH / file_name
            if not thumb_path.exists():
                os.symlink(orig_path, thumb_path)  # Link to save space

            # Insert into DB
            cursor.execute("SELECT id FROM items WHERE url = ?", (image_url,))
            if cursor.fetchone():
                print("Already exists in DB. Skipping.")
                continue

            tags_json = json.dumps(tags)
            cursor.execute(
                "INSERT INTO items (id, name, ext, tags, annotation, url, created_at, thumbnail_path, original_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (asset_id, title, ext, tags_json, medium, image_url, int(time.time()), str(thumb_path), str(orig_path)),
            )

            # Update normalized tags
            for tag in tags:
                cursor.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
                cursor.execute("SELECT id FROM tags WHERE name = ?", (tag,))
                tag_id_row = cursor.fetchone()
                if tag_id_row:
                    cursor.execute("INSERT OR IGNORE INTO item_tags (item_id, tag_id) VALUES (?, ?)", (asset_id, tag_id_row[0]))

            conn.commit()
            fetched += 1
            print(f"Saved {asset_id} - {title}")

            time.sleep(0.5)  # Be nice to the API

    except Exception as e:
        print(f"Error during harvest: {e}")


if __name__ == "__main__":
    ensure_dirs()
    # Let's seed with a few different diverse categories
    harvest_the_met("Botanical", limit=5)
    harvest_the_met("Woodblock print", limit=5)
    harvest_the_met("Texture", limit=5)
    harvest_the_met("Landscape", limit=5)
    print("Harvest complete!")
