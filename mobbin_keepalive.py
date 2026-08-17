import asyncio
import json
import random
import time
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Playwright not installed.")
    exit(1)

AUTH_FILE = Path("/home/ubuntu/.local/share/opencode/mcp-auth.json")
PROFILE_DIR = "/home/ubuntu/sonagi-assets/mobbin_profile"


async def update_auth_json(jwt_token: str):
    if AUTH_FILE.exists():
        data = json.loads(AUTH_FILE.read_text())
    else:
        data = {"mobbin": {"tokens": {}}}

    if "mobbin" not in data:
        data["mobbin"] = {"tokens": {}}

    data["mobbin"]["tokens"]["accessToken"] = jwt_token
    # Set a dummy expiry for 24h later to prevent immediate re-fetching by other scripts
    data["mobbin"]["tokens"]["expiresAt"] = time.time() + 86400

    AUTH_FILE.write_text(json.dumps(data, indent=2))
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ✅ mcp-auth.json JWT 업데이트 완료")


async def keepalive_loop():
    print("🚀 Mobbin 세션 유지(Keep-Alive) 봇 시작...")

    async with async_playwright() as p:
        # 1. Persistent Context (쿠키/세션 유지) 및 스텔스 모드
        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=True,
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )

        page = await context.new_page()

        while True:
            try:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 🔄 Mobbin 메인 페이지 접속 중...")
                await page.goto("https://mobbin.com", wait_until="domcontentloaded", timeout=60000)

                # 2. 쿠키 검사 (JWT 탈취)
                cookies = await context.cookies("https://mobbin.com")
                jwt_cookie = next((c for c in cookies if c["name"] == "mobbin_jwt"), None)

                if jwt_cookie:
                    await update_auth_json(jwt_cookie["value"])
                else:
                    print("⚠️ mobbin_jwt 쿠키를 찾을 수 없습니다. 로그인이 풀렸거나 봇 탐지에 걸렸을 수 있습니다.")
                    # TODO: 필요시 슬랙/디스코드 알림 혹은 자동 로그인 분기

                # 3. 적응형 크롤링 (사람처럼 행동 - Micro-actions)
                print("사람처럼 피드를 둘러보는 중 (Session Warming)...")
                for _ in range(random.randint(3, 6)):
                    await page.keyboard.press("PageDown")
                    await asyncio.sleep(random.uniform(2.0, 5.0))

                # 랜덤한 피드 아이템 하나 클릭해보기 (적응형 클릭)
                try:
                    cards = await page.query_selector_all('a[href^="/apps/"]')
                    if cards:
                        target = random.choice(cards[:5])
                        await target.click()
                        await page.wait_for_load_state("domcontentloaded")
                        await asyncio.sleep(random.uniform(3.0, 6.0))
                        await page.go_back()
                except Exception as e:
                    print(f"클릭 상호작용 중 무시 가능한 에러: {e}")

                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 💤 활동 완료. 6시간 대기...")

            except Exception as e:
                print(f"❌ 순회 중 에러 발생: {e}")

            # 6시간마다 갱신 (6 * 3600 = 21600초)
            await asyncio.sleep(21600)


if __name__ == "__main__":
    asyncio.run(keepalive_loop())
