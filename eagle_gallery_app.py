import json
import os
import sqlite3

import sentry_sdk
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

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

DB_PATH = "eagle_gallery.db"


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


@app.get("/")
def index():
    return FileResponse("static/index.html")


app.mount("/static", StaticFiles(directory="static"), name="static")
