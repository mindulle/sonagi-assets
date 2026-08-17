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

# Art Institute of Chicago API endpoints
SEARCH_URL = "https://api.artic.edu/api/v1/artworks/search"
IIIF_BASE_URL = "https://www.artic.edu/iiif/2"


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


def harvest_aic(query: str, limit: int = 10):
    print(f"\n--- Harvesting Art Institute of Chicago for: {query} ---")

    # query param is 'q'
    params = urllib.parse.urlencode(
        {
            "q": query,
            "limit": limit,
            # Only fetch public domain images that have an image_id
            "query[term][is_public_domain]": "true",
            "fields": "id,title,image_id,artwork_type_title,medium_display,subject_titles,is_public_domain",
        }
    )

    # AIC doesn't support complex nested queries easily in simple GET, so we filter in python
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

            if not art.get("is_public_domain") or not art.get("image_id"):
                continue

            image_id = art["image_id"]
            # 843 pixels wide is a good web-friendly size
            image_url = f"{IIIF_BASE_URL}/{image_id}/full/843,/0/default.jpg"

            title = art.get("title", "Untitled")
            artwork_type = art.get("artwork_type_title", "")
            medium = art.get("medium_display", "")
            subject_titles = art.get("subject_titles", [])

            # Taxonomy Mapping
            tags = ["src:aic"]

            if artwork_type:
                tags.append(f"dept:{artwork_type.lower().replace(' ', '-')}")

            if medium:
                medium_lower = medium.lower()
                if "watercolor" in medium_lower:
                    tags.append("medium:watercolor")
                elif "oil" in medium_lower:
                    tags.append("medium:oil")
                elif "woodblock" in medium_lower:
                    tags.append("medium:woodblock")
                elif "graphite" in medium_lower or "pencil" in medium_lower:
                    tags.append("medium:graphite")

            for subject in subject_titles:
                if subject:
                    tags.append(f"topic:{subject.lower().replace(' ', '-')}")

            # Download Image
            asset_id = str(uuid.uuid4())
            ext = "jpg"
            file_name = f"{asset_id}.{ext}"
            orig_path = ORIGINALS_PATH / file_name

            print(f"Downloading [{title}]...")
            if not download_image(image_url, orig_path):
                continue

            # Create Symlink for thumbnail
            thumb_path = THUMBNAILS_PATH / file_name
            if not thumb_path.exists():
                os.symlink(orig_path, thumb_path)

            # Insert into DB
            cursor.execute("SELECT id FROM items WHERE url = ?", (image_url,))
            if cursor.fetchone():
                print("Already exists in DB. Skipping.")
                continue

            tags_json = json.dumps(tags)
            cursor.execute(
                "INSERT INTO items (id, name, ext, tags, annotation, url, created_at, thumbnail_path, original_path) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
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

            time.sleep(0.5)

    except Exception as e:
        print(f"Error during harvest: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    ensure_dirs()
    # Harvest some high-quality textures, patterns, and modern-friendly classic art
    harvest_aic("Texture", limit=5)
    harvest_aic("Pattern", limit=5)
    harvest_aic("Geometric", limit=5)
    harvest_aic("Impressionism", limit=5)
    print("Harvest complete!")
