import json
import os
import shutil
import sqlite3
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import List, Optional

import sentry_sdk
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

try:
    from PIL import Image

    HAS_PIL = True
except ImportError:
    HAS_PIL = False

AI_ASSETS_PATH = os.environ.get("AI_ASSETS_PATH", "/app/data/ai-assets/images")
THUMBNAIL_SIZE = (256, 256)


class ImportUrlRequest(BaseModel):
    imageUrl: str
    author: Optional[str] = ""
    content: Optional[str] = ""
    messageUrl: Optional[str] = ""
    tags: List[str] = []


def generate_id():
    return str(uuid.uuid4()).upper()


def make_thumbnail(src_path: Path, dest_path: Path):
    if not HAS_PIL:
        shutil.copy2(src_path, dest_path)
        return
    try:
        with Image.open(src_path) as img:
            img.thumbnail(THUMBNAIL_SIZE)
            if dest_path.suffix.lower() in [".jpg", ".jpeg"]:
                img = img.convert("RGB")
            img.save(dest_path)
    except Exception:
        shutil.copy2(src_path, dest_path)


sentry_dsn = os.environ.get("SENTRY_DSN")
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )

app = FastAPI()

Instrumentator().instrument(app).expose(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "asset_hub.db"


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/api/items")
def get_items(limit: int = Query(50, le=100), offset: int = Query(0, ge=0), search: str = ""):
    conn = get_db()
    try:
        c = conn.cursor()
        base_query = "FROM items"
        where_clause = ""
        params = []

        if search:
            where_clause = " WHERE name LIKE ? OR tags LIKE ? OR ext LIKE ?"
            search_term = "%" + search + "%"
            params.extend([search_term, search_term, search_term])
            base_query += where_clause

        count_query = f"SELECT COUNT(*) as total {base_query}"
        c.execute(count_query, params)
        total_count = c.fetchone()["total"]

        query = f"SELECT * {base_query} ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        c.execute(query, params)
        rows = c.fetchall()

        items = []
        for r in rows:
            items.append(
                {
                    "id": r["id"],
                    "name": r["name"],
                    "ext": r["ext"],
                    "tags": json.loads(r["tags"]) if r["tags"] else [],
                    "has_thumbnail": bool(r["thumbnail_path"]),
                }
            )
        return {"total": total_count, "items": items}
    finally:
        conn.close()


@app.get("/api/items/{item_id}")
def get_item_detail(item_id: str):
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM items WHERE id = ?", (item_id,))
        row = c.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Item not found")

        return {
            "id": row["id"],
            "name": row["name"],
            "ext": row["ext"],
            "tags": json.loads(row["tags"]) if row["tags"] else [],
            "annotation": row["annotation"],
            "url": row["url"],
            "has_thumbnail": bool(row["thumbnail_path"]),
        }
    finally:
        conn.close()


@app.get("/api/tags")
def get_tags(limit: int = Query(20, le=100)):
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute(
            """
            SELECT t.name as tag, count(it.item_id) as count
            FROM tags t
            JOIN item_tags it ON t.id = it.tag_id
            GROUP BY t.id
            ORDER BY count DESC
            LIMIT ?
        """,
            (limit,),
        )
        tags = [{"tag": row["tag"], "count": row["count"]} for row in c.fetchall()]
        return tags
    finally:
        conn.close()


@app.get("/api/exts")
def get_exts(limit: int = Query(20, le=100)):
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute(
            """
            SELECT ext, count(*) as count
            FROM items
            WHERE ext != '' AND ext IS NOT NULL
            GROUP BY ext
            ORDER BY count DESC
            LIMIT ?
        """,
            (limit,),
        )
        exts = [{"ext": row["ext"], "count": row["count"]} for row in c.fetchall()]
        return exts
    finally:
        conn.close()


@app.get("/api/image/{item_id}/{type}")
def get_image(item_id: str, type: str):
    if type not in ["thumbnail", "original"]:
        raise HTTPException(status_code=400, detail="Invalid image type")

    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("SELECT thumbnail_path, original_path FROM items WHERE id = ?", (item_id,))
        row = c.fetchone()

        if not row:
            return HTMLResponse(status_code=404, content="Not found")

        path = row["thumbnail_path"] if type == "thumbnail" else row["original_path"]
        if path and os.path.exists(path):
            return FileResponse(path)
        return HTMLResponse(status_code=404, content="File not found")
    finally:
        conn.close()


@app.post("/api/import-url")
def import_url(req: ImportUrlRequest):
    asset_id = generate_id()
    path = urllib.parse.urlparse(req.imageUrl).path
    ext = path.split(".")[-1].lower()
    if ext not in ["jpg", "jpeg", "png", "gif", "webp"]:
        ext = "png"

    info_dir = Path(AI_ASSETS_PATH) / f"{asset_id}.info"
    info_dir.mkdir(parents=True, exist_ok=True)

    asset_name = f"discord_{asset_id[:8]}"
    dest_original = info_dir / f"{asset_name}.{ext}"

    try:
        req_obj = urllib.request.Request(req.imageUrl, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req_obj) as response, open(dest_original, "wb") as out_file:
            shutil.copyfileobj(response, out_file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to download image: {str(e)}")

    thumb_ext = "jpg" if ext not in ("png", "gif", "webp") else ext
    dest_thumbnail = info_dir / f"{asset_id}_thumbnail.{thumb_ext}"
    make_thumbnail(dest_original, dest_thumbnail)

    annotation_parts = []
    if req.content:
        annotation_parts.append(req.content)
    if req.author:
        annotation_parts.append(f"Author: {req.author}")
    if req.messageUrl:
        annotation_parts.append(f"Message: {req.messageUrl}")
    annotation = "\n".join(annotation_parts)

    metadata = {
        "id": asset_id,
        "name": asset_name,
        "ext": ext,
        "tags": req.tags,
        "folders": [],
        "isDeleted": False,
        "url": req.messageUrl,
        "annotation": annotation,
        "modificationTime": int(time.time() * 1000),
    }

    meta_path = info_dir / "metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    conn = get_db()
    try:
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO items VALUES (?,?,?,?,?,?,?,?)",
            (
                asset_id,
                asset_name,
                ext,
                json.dumps(req.tags),
                annotation,
                req.messageUrl,
                str(dest_thumbnail),
                str(dest_original),
            ),
        )

        for tag in req.tags:
            c.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
            c.execute("SELECT id FROM tags WHERE name = ?", (tag,))
            tag_id_row = c.fetchone()
            if tag_id_row:
                tag_id = tag_id_row[0]
                c.execute(
                    "INSERT OR IGNORE INTO item_tags (item_id, tag_id) VALUES (?, ?)",
                    (asset_id, tag_id),
                )

        conn.commit()
    finally:
        conn.close()

    return {"success": True, "id": asset_id}


@app.get("/")
def index():
    return FileResponse("static/index.html")


app.mount("/static", StaticFiles(directory="static"), name="static")
