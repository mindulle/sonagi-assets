# Deployment (docker)

k3s는 2026-10-31에 비활성화되었다. 현재 배포 기준은 **devops 단일 노드의 docker compose**다.
(호스트: `devops` / `100.82.121.40`, 앱 포트: `34920`, host network)

## 레이아웃

| 경로 | 역할 |
| --- | --- |
| `/opt/sonagi-assets/docker-compose.yml` | compose 정의 (이 저장소의 `docker-compose.yml`) |
| `/srv/sonagi-assets/library` | 7.1GB 갤러리 라이브러리 → 컨테이너 `/app/data` |
| `/srv/sonagi-assets/asset_hub.db` | SQLite DB → 컨테이너 `/app/asset_hub.db` |

경로는 `ASSETS_LIBRARY_DIR`, `ASSETS_DB_FILE` 환경변수로 바꿀 수 있다.

## 최초 준비

```bash
sudo mkdir -p /srv/sonagi-assets /opt/sonagi-assets
sudo install -m 644 docker-compose.yml /opt/sonagi-assets/docker-compose.yml

# asset_hub.db 는 file bind mount 다. 파일이 없으면 docker 가 디렉터리를 만들어 앱이 죽는다.
sudo test -f /srv/sonagi-assets/asset_hub.db || echo "asset_hub.db 를 먼저 배치하세요"
```

## 릴리즈와 배포

CI는 **이미지만 발행**한다. 배포는 이 문서의 수동 절차를 따른다.

| 트리거 | 산출물 |
| --- | --- |
| `main` push | 이미지 `:latest`, `:sha-<7>` |
| `fix·feat` 커밋 포함 | 위 + semantic-release 태그/노트, 이미지 `:<version>` |

2026-11-23 이전에는 릴리즈 워크플로가 `k8s/deployment.yaml`을 갱신하는 잡을
가지고 있었다. k3s를 내리면서(PR #55) 매니페스트가 사라졌지만 잡이 남아 매
릴리즈가 실패했다. 해당 잡은 제거했다.

## 배포 / 갱신

```bash
cd /opt/sonagi-assets
sudo docker compose pull            # :latest
sudo docker compose up -d
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:34920/   # 200
```

버전을 고정하려면 `ASSET_IMAGE_TAG`를 준다(롤백에도 같은 방법을 쓴다).

```bash
sudo ASSET_IMAGE_TAG=1.69.0 docker compose up -d
```

## 수집 잡 (구 CronJob 대체)

```bash
cd /opt/sonagi-assets
sudo docker compose --profile jobs run --rm harvest
```

## 왜 host network 인가

앱이 `34920`을 직접 열고, `draw.sonagi.space`(public origin)에서 오는 요청이
Private Network Access 프리플라이트를 통과해야 한다. 포트 매핑을 거치면
출발지/포트가 달라져 PNA·CORS 동작이 바뀐다.

## 모니터

Uptime Kuma `sonagi-assets UI (Internal)` → `http://100.82.121.40:34920/`,
timeout 10s, maxretries 3.

## 보안 패치 빌드 (2026-11-21)

베이스 이미지 OS 패키지를 올린 이미지를 따로 빌드해 배포한다.

```bash
# 소스 동기화 후 (data/, *.db 제외)
docker build -t ghcr.io/mindulle/sonagi-assets:1.16.6-security .
# devops /opt/sonagi-assets/.env
ASSET_IMAGE_TAG=1.16.6-security
docker compose up -d
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:34920/
```

- 결과: Trivy critical 34 → 8 (no-fix 잔여), high 712 → 349
- 이미지는 로컬 태그로만 존재한다. 레지스트리에 올리려면 별도 push 필요.
