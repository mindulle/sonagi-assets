#!/usr/bin/env bash
# 클라이언트 자산·카탈로그를 devops로 동기화하고 원격에서 검증한다.
#
#   scripts/sync_assets.sh --catalog catalog/catalog.json --library library \
#       --verify-render mindulle-master-seal-light-svg
#
# 절대 --delete를 쓰지 않는다. 원격에만 있는 파일은 그대로 둔다.
set -euo pipefail

REMOTE="devops"
REMOTE_ROOT="/srv/sonagi-assets"
RENDER_ROOT="/home/ubuntu/sonagi-entry-render"
CATALOG="catalog/catalog.json"
LIBRARY="library"
EXPECT_REMOTE_SHA=""
VERIFY_RENDER=""

usage() {
  cat <<'EOF'
사용: sync_assets.sh [옵션]

  --remote NAME              ssh 대상 (기본: devops)
  --remote-root PATH         원격 루트 (기본: /srv/sonagi-assets)
  --render-root PATH         원격 렌더러 루트 (기본: /home/ubuntu/sonagi-entry-render)
  --catalog PATH             로컬 카탈로그 (기본: catalog/catalog.json)
  --library PATH             로컬 라이브러리 루트 (기본: library)
  --expect-remote-catalog-sha SHA
                             동기화 전 원격 카탈로그 해시. 다르면 중단한다.
  --verify-render NAME       동기화 후 이 자산 이름으로 원격 렌더를 돌려 사용 여부를 확인
  -h, --help                 이 도움말
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --remote) REMOTE="$2"; shift 2 ;;
    --remote-root) REMOTE_ROOT="$2"; shift 2 ;;
    --render-root) RENDER_ROOT="$2"; shift 2 ;;
    --catalog) CATALOG="$2"; shift 2 ;;
    --library) LIBRARY="$2"; shift 2 ;;
    --expect-remote-catalog-sha) EXPECT_REMOTE_SHA="$2"; shift 2 ;;
    --verify-render) VERIFY_RENDER="$2"; shift 2 ;;
    -h | --help) usage; exit 0 ;;
    *) echo "알 수 없는 옵션: $1" >&2; usage >&2; exit 2 ;;
  esac
done

for cmd in rsync ssh find; do
  command -v "$cmd" >/dev/null || {
    echo "필요한 명령이 없습니다: $cmd" >&2
    exit 1
  }
done
[[ -f "$CATALOG" ]] || {
  echo "카탈로그가 없습니다: $CATALOG" >&2
  exit 1
}
[[ -d "$LIBRARY/clients" ]] || {
  echo "클라이언트 라이브러리가 없습니다: $LIBRARY/clients" >&2
  exit 1
}

local_files="$(find "$LIBRARY/clients" -type f | wc -l | tr -d ' ')"
if [[ "$local_files" -eq 0 ]]; then
  echo "동기화할 클라이언트 파일이 없습니다: $LIBRARY/clients" >&2
  exit 1
fi

if [[ -n "$EXPECT_REMOTE_SHA" ]]; then
  # 경로는 로컬 설정값이라 클라이언트에서 펼치는 것이 맞다.
  # shellcheck disable=SC2029
  remote_sha="$(ssh "$REMOTE" sudo sha256sum "$REMOTE_ROOT/catalog/catalog.json" | awk '{print $1}')"
  if [[ "$remote_sha" != "$EXPECT_REMOTE_SHA" ]]; then
    echo "원격 카탈로그가 바뀌었습니다. 동기화를 중단합니다." >&2
    echo "  기대: $EXPECT_REMOTE_SHA" >&2
    echo "  실제: $remote_sha" >&2
    exit 1
  fi
fi

# 1) 파일: 원격에 없는 것만 더한다. --delete 없음.
rsync -a --rsync-path="sudo rsync" "$LIBRARY/clients/" "$REMOTE:$REMOTE_ROOT/library/clients/"

# 2) 카탈로그: append-only 결과물을 그대로 올린다.
rsync -a --rsync-path="sudo rsync" "$CATALOG" "$REMOTE:$REMOTE_ROOT/catalog/catalog.json"

# 3) 파일 개수 검증
remote_files="$(ssh "$REMOTE" sudo find "$REMOTE_ROOT/library/clients" -type f | wc -l | tr -d ' ')"
if [[ "$local_files" != "$remote_files" ]]; then
  echo "원격 파일 수가 다릅니다: 로컬 $local_files / 원격 $remote_files" >&2
  exit 1
fi
echo "파일 동기화 OK: $remote_files개"

# 4) 카탈로그 검증: client 항목이 있고 blocked가 없는지
ssh "$REMOTE" python3 - "$REMOTE_ROOT/catalog/catalog.json" <<'PY'
import json
import sys

catalog = json.load(open(sys.argv[1], encoding="utf-8"))
items = catalog.get("items", [])
client = [item for item in items if item.get("origin") == "client"]
if not client:
    raise SystemExit("client 항목이 없습니다")
blocked = [item["id"] for item in client if item.get("license_scope") == "blocked"]
if blocked:
    raise SystemExit(f"blocked client 항목: {blocked}")
print(json.dumps({"total": len(items), "client": len(client), "generated_at": catalog.get("generated_at")}, ensure_ascii=False))
PY

# 5) 선택: 원격 렌더러가 자산을 실제로 집어 쓰는지 확인
if [[ -n "$VERIFY_RENDER" ]]; then
  ssh "$REMOTE" python3 - "$RENDER_ROOT" "$REMOTE_ROOT/catalog/catalog.json" "$VERIFY_RENDER" <<'PY'
import json
import os
import subprocess
import sys
import tempfile

root, catalog, name = sys.argv[1], sys.argv[2], sys.argv[3]
recipe = {
    "name": "client-asset-check",
    "theme": "editorial",
    "canvas": {"width": 1440, "height": 820},
    "blocks": [
        {"type": "header", "brand": "MINDULLE", "nav": ["브랜드", "작업"]},
        {
            "type": "hero",
            "eyebrow": "CLIENT ASSET CHECK",
            "title": "우리 자산으로\n만든 화면",
            "body": "카탈로그에서 클라이언트 자산을 실제로 집어 쓰는지 확인합니다.",
            "cta": "확인",
            "ctaIcon": "arrow-right",
            "illustration": [name],
        },
    ],
}
with tempfile.TemporaryDirectory() as tmp:
    recipe_path = os.path.join(tmp, "recipe.json")
    out = os.path.join(tmp, "out")
    with open(recipe_path, "w", encoding="utf-8") as handle:
        json.dump(recipe, handle, ensure_ascii=False)
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/render_recipe.py",
            "--recipe",
            recipe_path,
            "--catalog",
            catalog,
            "--tokens",
            "tokens/semantic.json",
            "--style",
            "styles/editorial.json",
            "--out",
            out,
            "--breakpoint",
            "desktop",
        ],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stdout, proc.stderr, sep="\n", file=sys.stderr)
        raise SystemExit(proc.returncode)
    manifest = json.load(open(os.path.join(out, "client-asset-check.manifest.json"), encoding="utf-8"))
    used = [asset["name"] for asset in manifest.get("assets", [])]
    if name not in used:
        raise SystemExit(f"렌더가 자산을 쓰지 않았습니다: {name} / used={used}")
    if not manifest.get("license_ok"):
        raise SystemExit("license_ok=false")
    print(json.dumps({"rendered": name, "used": used, "license_ok": True}, ensure_ascii=False))
PY
fi

echo "동기화·검증 완료"
