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

# Cleveland Museum of Art API endpoints
SEARCH_URL = "https://openaccess-api.clevelandart.org/api/artworks/"


def ensure_dirs():
    ORIGINALS_PATH.mkdir(parents=True, exist_ok=True)
    THUMBNAILS_PATH.mkdir(parents=True, exist_ok=True)


def download_image(url: str, dest_path: Path):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Sonagi Asset Hub)"})
        with urllib.request.urlopen(req) as response, open(dest_path, "wb") as out_file:
            out_file.write(response.read())
        return True
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return False


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def harvest_cma(query: str, limit: int = 10):
    print(f"\n--- Harvesting Cleveland Museum of Art for: {query} ---")

    params = urllib.parse.urlencode(
        {
            "q": query,
            "has_image": 1,
            "limit": limit,
            # Only public domain (CC0) works
            "cc0": 1,
        }
    )

    try:
        req = urllib.request.Request(f"{SEARCH_URL}?{params}", headers={"User-Agent": "Mozilla/5.0"})
        response = urllib.request.urlopen(req)
        data = json.loads(response.read())

        artworks = data.get("data", [])
        if not artworks:
            print(f"No artworks found for query: {query}")
            return

        print(f"Found {len(artworks)} artworks. Processing...")

        conn = get_db()
        cursor = conn.cursor()

        fetched = 0
        for art in artworks:
            if fetched >= limit:
                break

            images = art.get("images", {})
            web_image = images.get("web", {}).get("url")

            if not web_image:
                continue

            title = art.get("title", "Untitled")
            artwork_type = art.get("type", "")
            department = art.get("department", "")
            technique = art.get("technique", "")

            # Taxonomy Mapping
            tags = ["src:cma"]

            if department:
                tags.append(f"dept:{department.lower().replace(' ', '-')}")
            if artwork_type:
                tags.append(f"category:{artwork_type.lower().replace(' ', '-')}")

            if technique:
                tech_lower = technique.lower()
                if "watercolor" in tech_lower:
                    tags.append("medium:watercolor")
                elif "oil" in tech_lower:
                    tags.append("medium:oil")
                elif "woodcut" in tech_lower or "woodblock" in tech_lower:
                    tags.append("medium:woodblock")
                elif "graphite" in tech_lower or "pencil" in tech_lower:
                    tags.append("medium:graphite")

            tags.append(f"topic:{query.lower().replace(' ', '-')}")

            # Download Image
            asset_id = str(uuid.uuid4())
            ext = "jpg"
            file_name = f"{asset_id}.{ext}"
            orig_path = ORIGINALS_PATH / file_name

            print(f"Downloading [{title}]...")
            if not download_image(web_image, orig_path):
                continue

            # Create Symlink for thumbnail
            thumb_path = THUMBNAILS_PATH / file_name
            if not thumb_path.exists():
                os.symlink(orig_path, thumb_path)

            # Insert into DB
            cursor.execute("SELECT id FROM items WHERE url = ?", (web_image,))
            if cursor.fetchone():
                print("Already exists in DB. Skipping.")
                continue

            tags_json = json.dumps(tags)
            cursor.execute(
                "INSERT INTO items (id, name, ext, tags, annotation, url, created_at, thumbnail_path, original_path) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (asset_id, title, ext, tags_json, technique, web_image, int(time.time()), str(thumb_path), str(orig_path)),
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

            time.sleep(0.5)

    except Exception as e:
        print(f"Error during harvest: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    ensure_dirs()
    # Harvest beautiful modern-friendly classic art
    harvest_cma("Landscape", limit=5)
    harvest_cma("Abstract", limit=5)
    harvest_cma("Texture", limit=5)
    harvest_cma("Botanical", limit=5)
    print("Harvest complete!")
