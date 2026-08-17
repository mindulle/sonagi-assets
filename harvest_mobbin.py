import asyncio
import json
import os
import time
import urllib.request
import uuid
from pathlib import Path

from mcp.client.session import ClientSession

# MCP Imports
from mcp.client.sse import sse_client

# CDN Uploader
from cdn_uploader import upload_to_cdn

# Playwright for Stealth Browsing
try:
    from playwright.async_api import async_playwright

    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

MOBBIN_MCP_URL = "https://api.mobbin.com/mcp"


def get_mobbin_token():
    auth_path = Path("/home/ubuntu/.local/share/opencode/mcp-auth.json")
    if auth_path.exists():
        data = json.loads(auth_path.read_text())
        return data.get("mobbin", {}).get("tokens", {}).get("accessToken")
    return None


def download_file(url: str, dest_path: str):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as response, open(dest_path, "wb") as out_file:
            out_file.write(response.read())
        return True
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return False


def route_and_upload(file_path: str, tags: list, source: str = "mobbin"):
    ext = os.path.splitext(file_path)[1].lower()
    asset_extensions = [".svg", ".json", ".fig"]
    is_asset = ext in asset_extensions

    bucket = "assets" if is_asset else "references"
    parsed_tags = {t.split(":")[0]: t.split(":")[1] for t in tags if ":" in t}
    platform = parsed_tags.get("platform", "unknown")
    flow = parsed_tags.get("flow", "general")

    prefix = f"{source}/{platform}/{flow}"
    file_name = os.path.basename(file_path)
    object_name = f"{prefix}/{file_name}"

    cdn_url = upload_to_cdn(file_path, bucket=bucket, object_name=object_name)
    return bucket, cdn_url


async def extract_deep_data(url: str, token: str):
    if not HAS_PLAYWRIGHT:
        return {"image": None, "video": None}

    print(f"  [Playwright] 딥 추출 시작: {url}")
    media_urls = {"image": None, "video": None}

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            )

            if token:
                await context.add_cookies([{"name": "mobbin_jwt", "value": token, "domain": ".mobbin.com", "path": "/"}])

            page = await context.new_page()

            async def handle_response(response):
                req_url = response.url
                if "supabase.co/storage/v1/object/public" in req_url:
                    content_type = response.headers.get("content-type", "")
                    if ".mp4" in req_url or "video" in content_type:
                        media_urls["video"] = req_url
                    elif (".png" in req_url or ".jpg" in req_url or ".webp" in req_url) and not media_urls["image"]:
                        media_urls["image"] = req_url

            page.on("response", handle_response)

            await page.goto(url, wait_until="networkidle")
            await asyncio.sleep(2)

            if not media_urls["video"]:
                # Try finding video tag directly
                try:
                    video_element = await page.query_selector("video source")
                    if video_element:
                        media_urls["video"] = await video_element.get_attribute("src")
                except:
                    pass

            await browser.close()
            return media_urls

    except Exception as e:
        print(f"  [Playwright] 추출 중 오류 발생: {e}")
        return media_urls


async def harvest_mobbin_category(session_mcp, query: str, flow_tag: str, limit: int = 5):
    print(f"\n--- Harvesting Mobbin for: {query} ---")
    token = get_mobbin_token()

    try:
        result = await session_mcp.call_tool(
            "mobbin_search_screens", arguments={"query": query, "platform": "ios", "limit": limit, "mode": "standard"}
        )

        content_text = result.content[0].text
        data = json.loads(content_text)
        screens = data.get("screens", [])

        if not screens:
            print(f"No screens found for query: {query}")
            return

        print(f"✅ Found {len(screens)} screens via MCP. Starting Deep Extraction...")

        for screen in screens:
            app_name = screen.get("app_name", "Unknown")
            platform = screen.get("platform", "ios")
            mobbin_url = screen.get("mobbin_url")

            if not mobbin_url:
                continue

            tags = ["src:mobbin", f"platform:{platform}", f"flow:{flow_tag}", f"app:{app_name.lower().replace(' ', '-')}"]

            media_data = await extract_deep_data(mobbin_url, token)

            target_url = media_data.get("video") or media_data.get("image") or screen.get("image_url")
            if not target_url:
                print(f"  ❌ Media URL 찾을 수 없음: {mobbin_url}")
                continue

            asset_id = str(uuid.uuid4())
            ext = "mp4" if (".mp4" in target_url or "video" in target_url) else "jpg"

            tmp_media_path = f"/tmp/{asset_id}.{ext}"
            tmp_json_path = f"/tmp/{asset_id}.json"

            print(f"  ⬇️ Downloading [{app_name}] ({ext})...")
            if not download_file(target_url, tmp_media_path):
                continue

            bucket, cdn_media_url = route_and_upload(tmp_media_path, tags)

            meta = {
                "id": asset_id,
                "name": f"{app_name} - {query.capitalize()}",
                "ext": ext,
                "bucket": bucket,
                "tags": tags,
                "cdn_url": cdn_media_url,
                "source_url": mobbin_url,
                "has_video": ext == "mp4",
                "created_at": int(time.time()),
            }

            with open(tmp_json_path, "w", encoding="utf-8") as jf:
                json.dump(meta, jf, ensure_ascii=False, indent=2)

            _, cdn_json_url = route_and_upload(tmp_json_path, tags)

            print(f"  🚀 Uploaded to CDN [{bucket}]: {cdn_media_url}")

            if os.path.exists(tmp_media_path):
                os.remove(tmp_media_path)
            if os.path.exists(tmp_json_path):
                os.remove(tmp_json_path)
            time.sleep(1)

    except Exception as e:
        print(f"Error during harvest: {e}")
        import traceback

        traceback.print_exc()


async def main():
    token = get_mobbin_token()
    if not token:
        print("⚠️ Warning: mcp-auth.json에서 Mobbin 토큰을 찾을 수 없습니다. Free 모드로 진행될 수 있습니다.")

    print("Connecting to Mobbin MCP SSE endpoint...")
    # Add token header if available
    headers = {"Authorization": f"Bearer {token}"} if token else None

    async with sse_client(MOBBIN_MCP_URL, headers=headers) as (read_stream, write_stream):
        print("Connected! Initializing session...")
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # 테스트를 위해 2개 플로우, 각각 1개의 데이터만 수집
            await harvest_mobbin_category(session, "beautiful onboarding", "onboarding", limit=1)
            await harvest_mobbin_category(session, "shopping cart checkout", "checkout", limit=1)

            print("\n🎉 Mobbin Harvest & CDN Upload Complete!")


if __name__ == "__main__":
    asyncio.run(main())
