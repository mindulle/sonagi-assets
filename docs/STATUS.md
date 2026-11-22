# 현재 상태 (2026-11-22)

자산 라이브러리 → 결정론 렌더 → 납품 번들까지 한 줄로 이어진 상태.
이 문서는 "무엇이 되고, 무엇이 안 되는가"만 적는다. 사용법은 `PIPELINE.md`,
`CONTENT_FORMAT.md`, `docs/FIGMA_ROUNDTRIP.md`에 있다.

## 1. 한눈에

```
자산 14,938 (devops 7.2GB)
   │  catalog.json + license/scope/origin 태그
   ▼
content.md ──import──▶ recipe.json ──render──▶ SVG (+manifest, CREDITS)
   │                    │  style 10종
   │                    │  breakpoint 3종
   │                    └  light | dark
   ▼
package ──▶ PDF(폰트 임베드) · PNG@2x · WebP ──▶ zip + index.html
                                                (CDN 30일 보존)
```

세 가지 경로로 실행한다.

| 경로 | 명령 | 쓰는 곳 |
| --- | --- | --- |
| 로컬/호스트 | `python3 scripts/*.py` | 개발·검증 |
| devops | 같은 스크립트 (자산이 있는 곳) | 대량 렌더 |
| Gemini 앱 | `compose_page` → `package_page` (MCP 게이트웨이) | 실제 사용 |

## 2. 자산

| 구분 | 수 |
| --- | --- |
| 전체 | **14,938** |
| scope `bundle` / `output` / `blocked` | 10,458 / 166 / 4,314 |
| origin `open-source` | 10,371 |
| `unknown` | 3,575 |
| `commercial` | 726 |
| `freeware` | 162 |
| `public-domain` | 100 |
| `generated` | 4 (sd-turbo 2 + gemini 2) |
| `kind:glyph` (숨김) | 3,001 |

- 아이콘: Lucide(ISC) 2,410 · Tabler(MIT) 5,491 · Phosphor(MIT) 1,512
- 일러스트: illlustrations(flat) 133 · Open Doodles(line) 33 · 동판화(raster) 25
- 폰트: 813패밀리 (상업 787 · OFL 714 · free 47 · apache 46 · cc0 42 · mit 7 · gpl 1 · personal 2)
- 브랜드 로고 13개는 `kind:logo` + `scope:blocked`

라이선스 판정은 `scripts/license_policy.py` 한 곳에서 나온다.
scope 태그가 충돌하면 `bundle < output < blocked` 순으로 보수적으로 판정하고,
`origin:generated`는 무조건 `output`이다.

## 3. 렌더

| 축 | 값 |
| --- | --- |
| 블록 | 12종 (header·hero·stats·features·logos·quote·faq·cta·footer·table·pricing·gallery) |
| 스타일 | 10종 (editorial·brutalist·minimal·magazine·swiss·poster·sketch·etching·sonagi-blog·art-nouveau) |
| 브레이크포인트 | desktop 1440 · tablet 768 · mobile 390 |
| 테마 | light · dark (`dark: true`) |
| 장식 | `ornament`: nouveau · deco (섹션 구분선·페이지 프레임) |

결정론:

| 산출물 | 재현 |
| --- | --- |
| SVG · manifest | ✅ 입력 해시 4종(recipe·style·tokens·catalog) 기록 |
| PNG @2x · WebP | ✅ |
| PDF | ✅ (pypdf로 날짜·ID 고정) |
| ZIP | ✅ (1980 타임스탬프, 정렬) |

`embed_max_width`도 매니페스트에 기록한다.

## 4. 납품

```
dist/
├─ <name>.pdf            화면별 1페이지, 폰트 임베드
├─ <name>@2x.png
├─ <name>@2x.webp
├─ <name>.svg + manifest
└─ index.html · CREDITS.md · README.md · export.json
```

- export 단계에서 `origin:commercial`은 중단, `blocked`는 렌더 단계에서 중단
- CREDITS에 자산 출처·범위·AI 생성 정보(모델·프롬프트·시각)·재배포 제한이 자동으로 들어간다

## 5. AI 생성 자산

| 항목 | 상태 |
| --- | --- |
| 모델 | `gemini-3.1-flash-image` (cliproxyapi 경유), 로컬 `sd-turbo`(CPU) 대안 |
| 해상도 | 1408×768 (gemini) / 384~512 (sd-turbo) |
| 메타데이터 | `items.annotation`에 모델·프롬프트·생성일 |
| scope | `output` 강제 (파일 재배포 금지) |
| 고지 | CREDITS "생성 정보" + "재배포 제한" 절 |
| 워터마크 | gemini 출력 JPEG에 C2PA 메타데이터 포함 |

## 6. Gemini 앱 연결

게이트웨이(`https://mcp.sonagi.space/mcp`)에 Google 커스텀 MCP 클라이언트 9개가 등록되어
`run`(888회)·`asset_upload`(28회) 등을 이미 사용 중이다. 이번에 추가한 도구:

| 도구 | 실행 | 시간 | 결과 |
| --- | --- | --- | --- |
| `compose_page` | devops | 3~14초 | SVG + CDN URL |
| `package_page` | 호스트 | 8~32초 | zip + CDN URL |

제약: 호출당 승인 1회, 100초 한도, 분당 40회.
`compose_page`는 80초를 넘으면 남은 브레이크포인트를 `not_rendered`로 돌려준다.

## 7. 보존

| 대상 | 기간 | 방식 |
| --- | --- | --- |
| 로컬 `jobs/compose/<name>/` | 7일 | `compose_page` 프루닝 |
| CDN `releases/compose/` | 30일 | MinIO lifecycle `compose-artifacts-30d` |

`releases/compose/`만 익명 읽기 허용. zip 이름은 내용 해시라 덮어쓰지 않는다.

## 8. 검증된 것

- 같은 입력 2회 → SVG·manifest·PDF·PNG·WebP·zip 해시 동일
- content.md → 레시피 → 손으로 쓴 레시피와 **바이트 동일** SVG
- Figma 재임포트: `<g id>` → GROUP, 텍스트 → TEXT, 아이콘 → VECTOR, 이미지 → IMAGE fill
- 폰트 4종 설치 후 Figma에서 대체 없이 렌더 (Pretendard Bold는 과중 → 한글 제목은 NanumSquare/Gowun)
- 다크 대비: 본문 17.2~17.7, 보조 11.4~11.7, 흐린 글자 7.1~7.4
- 게이트웨이 도구로 3브레이크포인트 랜딩 생성 → zip 16.6MB (embed 900)

## 9. 알려진 부채

| 항목 | 내용 | 영향 |
| --- | --- | --- |
| 블록 30px 오프셋 | 모든 블록이 `y+30`으로 호출되는데 advance가 보정하지 않음. 표만 여백으로 우회 | 섹션 간 리듬이 스타일마다 미세하게 어긋남 |
| SVG 이미지 중복 | 같은 래스터가 브레이크포인트마다 base64로 들어감. zip의 약 60% | 납품 용량 (900에서 16.6MB) |
| 레시피 v1/v2 공존 | `blocks`(v1)와 `content`(v2) 스키마가 함께 존재 | 신규 작성자는 v2만 쓰면 됨 |
| CI 결정론 미검증 | 2회 실행 비교를 수동으로만 함 | 회귀 시 사람이 발견 |
| 인쇄 미지원 | RGB·96dpi 기준. CMYK·도련 없음 | 인쇄 발주 불가 |
| 갤러리 4개 배치 | 3열 그리드라 4번째가 빈 칸과 함께 남음 | 미관 |
| 다크 + 래스터 | 동판화가 밝은 종이색으로 남음 | 갤러리 눈부심 |
| devops 폰트 없음 | export는 호스트에서만 가능 | 도구가 두 단계로 나뉨 |
| 보존 밖 자산 | 이전 `assets/` 업로드분은 lifecycle 미적용 | 수동 정리 필요 |

## 10. 다음 후보

1. **30px 오프셋 근본 수정** — 블록 호출 규약을 정리하고 12블록 × 3bp 재검수
2. **이미지 외부 참조** — zip 25MB → 5MB (단일 파일 성질 포기)
3. **CI 결정론 검증** — 골든 SVG 해시 비교를 GitHub Actions에 추가
4. **인쇄용 출력** — CMYK 변환·도련·재단선 (별도 경로)
5. **레시피 v1 정리** — v2로 통일하고 v1은 읽기 전용으로 동결

## 11. 재현 체크리스트

```bash
# 1. content 검증 (카탈로그는 devops의 /srv/sonagi-assets/catalog/catalog.json)
python3 scripts/import_content.py content/studio-plan.md \
  --catalog /srv/sonagi-assets/catalog/catalog.json --check

# 2. 렌더 (devops, 자산이 있는 곳)
sudo python3 scripts/render_recipe.py --recipe recipes/<name>.json --style styles/etching.json \
  --catalog /srv/sonagi-assets/catalog/catalog.json --tokens tokens/semantic.json \
  --out out/<name> --breakpoint mobile --embed-max-width 900

# 3. 납품 (호스트, 폰트가 있는 곳)
python3 scripts/export_recipe.py --src out/<name> --out dist --formats pdf,png,webp \
  --scale 2 --fonts-css /home/ubuntu/brief/fonts/fonts.css
python3 scripts/bundle_delivery.py --src dist --out delivery/<name> --name "<제목>" --zip
```

## 12. 파일 지도

| 경로 | 역할 |
| --- | --- |
| `scripts/render_recipe.py` | 렌더러·스타일·다크 변환·매니페스트 |
| `scripts/import_content.py` | content.md → recipe + 검증 |
| `scripts/export_recipe.py` | PDF·PNG·WebP + 라이선스 게이트 |
| `scripts/bundle_delivery.py` | zip·index.html·CREDITS |
| `scripts/build_asset_catalog.py` | DB → catalog.json (scope 판정 포함) |
| `scripts/import_image_pack.py` | 래스터 등록 + 생성 메타데이터 |
| `scripts/license_policy.py` | 라이선스 → scope 단일 출처 |
| `CONTENT_FORMAT.md` · `PIPELINE.md` | 규격·계약 |
| `docs/FIGMA_ROUNDTRIP.md` | Figma 재임포트 검증 |
| `content/*.md` | 실제 콘텐츠 예시 5종 |
| `styles/*.json` | 스킨 10종 |
| `tokens/` | 프리미티브·시맨틱·Figma 변수 |
