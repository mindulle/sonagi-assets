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
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel
from starlette.requests import Request

try:
    from PIL import Image

    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# New Flat Cloud-Native Directory Structure
LIBRARY_PATH = os.environ.get("GALLERY_LIBRARY_PATH", "/app/data")
ORIGINALS_PATH = Path(LIBRARY_PATH) / "originals"
THUMBNAILS_PATH = Path(LIBRARY_PATH) / "thumbnails"
DB_PATH = os.environ.get("DB_PATH", "asset_hub.db")

ORIGINALS_PATH.mkdir(parents=True, exist_ok=True)
THUMBNAILS_PATH.mkdir(parents=True, exist_ok=True)

THUMBNAIL_SIZE = (256, 256)


class ImportUrlRequest(BaseModel):
    imageUrl: str
    author: Optional[str] = ""
    content: Optional[str] = ""
    messageUrl: Optional[str] = ""
    tags: List[str] = []


class UpdateItemRequest(BaseModel):
    name: Optional[str] = None
    tags: Optional[List[str]] = None
    annotation: Optional[str] = None


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


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS items
                 (id TEXT PRIMARY KEY, name TEXT, ext TEXT, tags TEXT,
                  annotation TEXT, url TEXT, created_at INTEGER,
                  thumbnail_path TEXT, original_path TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS tags
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE)""")
    c.execute("""CREATE TABLE IF NOT EXISTS item_tags
                 (item_id TEXT NOT NULL, tag_id INTEGER NOT NULL,
                  PRIMARY KEY (item_id, tag_id),
                  FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE,
                  FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE)""")
    conn.commit()
    conn.close()


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


init_db()

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

        query = f"SELECT * {base_query} ORDER BY created_at DESC LIMIT ? OFFSET ?"
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
            "created_at": row["created_at"],
        }
    finally:
        conn.close()


@app.put("/api/items/{item_id}")
def update_item(item_id: str, req: UpdateItemRequest):
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM items WHERE id = ?", (item_id,))
        row = c.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Item not found")

        name = req.name if req.name is not None else row["name"]
        annotation = req.annotation if req.annotation is not None else row["annotation"]
        tags_str = row["tags"]

        if req.tags is not None:
            tags_str = json.dumps(req.tags)
            # Update item_tags relations
            c.execute("DELETE FROM item_tags WHERE item_id = ?", (item_id,))
            for tag in req.tags:
                c.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
                c.execute("SELECT id FROM tags WHERE name = ?", (tag,))
                tag_id_row = c.fetchone()
                if tag_id_row:
                    c.execute("INSERT OR IGNORE INTO item_tags (item_id, tag_id) VALUES (?, ?)", (item_id, tag_id_row[0]))

        c.execute("UPDATE items SET name = ?, tags = ?, annotation = ? WHERE id = ?", (name, tags_str, annotation, item_id))
        conn.commit()
        return {"success": True}
    finally:
        conn.close()


@app.delete("/api/items/{item_id}")
def delete_item(item_id: str):
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("SELECT original_path, thumbnail_path FROM items WHERE id = ?", (item_id,))
        row = c.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Item not found")

        # 1. Delete DB records
        c.execute("DELETE FROM items WHERE id = ?", (item_id,))
        # cascading deletes item_tags
        conn.commit()

        # 2. Delete physical files
        if row["original_path"] and os.path.exists(row["original_path"]):
            os.remove(row["original_path"])
        if row["thumbnail_path"] and os.path.exists(row["thumbnail_path"]):
            os.remove(row["thumbnail_path"])

        return {"success": True}
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


def process_import(asset_id: str, asset_name: str, ext: str, src_file_path: Path, req_tags: List[str], req_annotation: str, req_url: str):
    dest_original = ORIGINALS_PATH / f"{asset_id}.{ext}"
    shutil.copy2(src_file_path, dest_original)

    thumb_ext = "jpg" if ext not in ("png", "gif", "webp", "svg") else ext
    dest_thumbnail = THUMBNAILS_PATH / f"{asset_id}_thumb.{thumb_ext}"
    make_thumbnail(dest_original, dest_thumbnail)

    created_at = int(time.time() * 1000)

    conn = get_db()
    try:
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO items VALUES (?,?,?,?,?,?,?,?,?)",
            (
                asset_id,
                asset_name,
                ext,
                json.dumps(req_tags),
                req_annotation,
                req_url,
                created_at,
                str(dest_thumbnail),
                str(dest_original),
            ),
        )

        for tag in req_tags:
            c.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
            c.execute("SELECT id FROM tags WHERE name = ?", (tag,))
            tag_id_row = c.fetchone()
            if tag_id_row:
                c.execute(
                    "INSERT OR IGNORE INTO item_tags (item_id, tag_id) VALUES (?, ?)",
                    (asset_id, tag_id_row[0]),
                )

        conn.commit()
    finally:
        conn.close()

    return {"success": True, "id": asset_id}


@app.post("/api/import-url")
def import_url(req: ImportUrlRequest):
    asset_id = generate_id()
    path = urllib.parse.urlparse(req.imageUrl).path
    ext = path.split(".")[-1].lower()
    if ext not in ["jpg", "jpeg", "png", "gif", "webp", "svg"]:
        ext = "png"

    asset_name = f"imported_{asset_id[:8]}"
    tmp_path = Path("/tmp") / f"{asset_id}.{ext}"

    try:
        req_obj = urllib.request.Request(req.imageUrl, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req_obj) as response, open(tmp_path, "wb") as out_file:
            shutil.copyfileobj(response, out_file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to download image: {str(e)}")

    annotation_parts = []
    if req.content:
        annotation_parts.append(req.content)
    if req.author:
        annotation_parts.append(f"Author: {req.author}")
    if req.messageUrl:
        annotation_parts.append(f"Message: {req.messageUrl}")
    annotation = "\n".join(annotation_parts)

    res = process_import(asset_id, asset_name, ext, tmp_path, req.tags, annotation, req.messageUrl)
    os.remove(tmp_path)
    return res


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), tags: str = Form(""), annotation: str = Form("")):
    asset_id = generate_id()
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else "png"
    asset_name = file.filename.rsplit(".", 1)[0] if "." in file.filename else file.filename

    tmp_path = Path("/tmp") / f"{asset_id}.{ext}"
    with open(tmp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    tag_list = [t.strip() for t in tags.split(",")] if tags else []

    res = process_import(asset_id, asset_name, ext, tmp_path, tag_list, annotation, "")
    os.remove(tmp_path)
    return res


@app.get("/")
def index():
    return FileResponse("static/index.html")


# ==========================================
# MCP (Model Context Protocol) Integration
# ==========================================

fast_mcp = FastMCP("sonagi-assets-mcp")
mcp = fast_mcp._mcp_server


@fast_mcp.tool()
async def assets_search(search: str = "") -> str:
    """Search assets by keyword (name, tags, or extension). Returns JSON array of assets."""
    conn = get_db()
    try:
        c = conn.cursor()
        query = "SELECT id, name, ext, tags, annotation FROM items WHERE name LIKE ? OR tags LIKE ? OR ext LIKE ? LIMIT 50"
        st = f"%{search}%"
        c.execute(query, (st, st, st))
        rows = c.fetchall()
        res = [
            {
                "id": r["id"],
                "name": r["name"],
                "ext": r["ext"],
                "tags": json.loads(r["tags"]) if r["tags"] else [],
                "annotation": r["annotation"],
            }
            for r in rows
        ]
        return json.dumps(res, ensure_ascii=False)
    finally:
        conn.close()


@fast_mcp.tool()
async def assets_update_tags(item_id: str, tags: list[str]) -> str:
    """Update (overwrite) the tags of a specific asset."""
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM items WHERE id = ?", (item_id,))
        row = c.fetchone()
        if not row:
            return f"Error: Item {item_id} not found."

        tags_str = json.dumps(tags)
        c.execute("DELETE FROM item_tags WHERE item_id = ?", (item_id,))
        for tag in tags:
            c.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
            c.execute("SELECT id FROM tags WHERE name = ?", (tag,))
            tag_id_row = c.fetchone()
            if tag_id_row:
                c.execute("INSERT OR IGNORE INTO item_tags (item_id, tag_id) VALUES (?, ?)", (item_id, tag_id_row[0]))

        c.execute("UPDATE items SET tags = ? WHERE id = ?", (tags_str, item_id))
        conn.commit()
        return f"Successfully updated tags for {item_id} to {tags}"
    finally:
        conn.close()


@fast_mcp.tool()
async def assets_delete(item_id: str) -> str:
    """Delete an asset permanently."""
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("SELECT original_path, thumbnail_path FROM items WHERE id = ?", (item_id,))
        row = c.fetchone()
        if not row:
            return f"Error: Item {item_id} not found."

        c.execute("DELETE FROM items WHERE id = ?", (item_id,))
        conn.commit()

        if row["original_path"] and os.path.exists(row["original_path"]):
            os.remove(row["original_path"])
        if row["thumbnail_path"] and os.path.exists(row["thumbnail_path"]):
            os.remove(row["thumbnail_path"])

        return f"Successfully deleted item {item_id}"
    finally:
        conn.close()


sse = SseServerTransport("/mcp/messages")


@app.get("/mcp/sse")
async def handle_sse(request: Request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await mcp.run(streams[0], streams[1], mcp.create_initialization_options())


@app.post("/mcp/messages")
async def handle_messages(request: Request):
    await sse.handle_post_message(request.scope, request.receive, request._send)


app.mount("/static", StaticFiles(directory="static"), name="static")
