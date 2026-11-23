# 현재 상태 (2026-11-23)

자산 라이브러리 → 결정론 렌더 → 납품 번들까지 한 줄로 이어진 상태.
이 문서는 "무엇이 되고, 무엇이 안 되는가"만 적는다. 사용법은 `PIPELINE.md`,
`CONTENT_FORMAT.md`, `docs/FIGMA_ROUNDTRIP.md`에 있다.

## 1. 한눈에

```
자산 14,938 (devops 7.2GB)
   │  catalog.json + license/scope/origin 태그
   ▼
content.md ──import──▶ recipe.json ──render──▶ SVG (+manifest, CREDITS)
   │                    │  style 29종 (registry/styles.json)
   │                    │  breakpoint 3종
   │                    └  light | dark
   ▼
package ──▶ PDF(폰트 임베드) · PNG@2x · WebP ──▶ zip + index.html
                                                (CDN 30일 보존)
```

세 가지 경로로 실행한다.

| 경로        | 명령                                             | 쓰는 곳   |
| ----------- | ------------------------------------------------ | --------- |
| 로컬/호스트 | `python3 scripts/*.py`                           | 개발·검증 |
| devops      | 같은 스크립트 (자산이 있는 곳)                   | 대량 렌더 |
| Gemini 앱   | `compose_page` → `package_page` (MCP 게이트웨이) | 실제 사용 |

## 2. 자산

| 구분                                  | 수                        |
| ------------------------------------- | ------------------------- |
| 전체                                  | **14,938**                |
| scope `bundle` / `output` / `blocked` | 10,458 / 166 / 4,314      |
| origin `open-source`                  | 10,371                    |
| `unknown`                             | 3,575                     |
| `commercial`                          | 726                       |
| `freeware`                            | 162                       |
| `public-domain`                       | 100                       |
| `generated`                           | 4 (sd-turbo 2 + gemini 2) |
| `kind:glyph` (숨김)                   | 3,001                     |

- 아이콘: Lucide(ISC) 2,410 · Tabler(MIT) 5,491 · Phosphor(MIT) 1,512
- 일러스트: illlustrations(flat) 133 · Open Doodles(line) 33 · 동판화(raster) 25
- 폰트: 813패밀리 (상업 787 · OFL 714 · free 47 · apache 46 · cc0 42 · mit 7 · gpl 1 · personal 2)
- 브랜드 로고 13개는 `kind:logo` + `scope:blocked`

라이선스 판정은 `scripts/license_policy.py` 한 곳에서 나온다.
scope 태그가 충돌하면 `bundle < output < blocked` 순으로 보수적으로 판정하고,
`origin:generated`는 무조건 `output`이다.

## 3. 렌더

| 축             | 값                                                                                       |
| -------------- | ---------------------------------------------------------------------------------------- |
| 블록           | 12종 (header·hero·stats·features·logos·quote·faq·cta·footer·table·pricing·gallery)       |
| 스타일         | 29종(문서화 27 + 축 스모크 2) — palette 20 × type 11 × geometry 9 × layout 7 × ornament 15 |
| 브레이크포인트 | desktop 1440 · tablet 768 · mobile 390                                                   |
| 테마           | light · dark (`dark: true`)                                                              |
| 장식           | 축(`ornament`) 15종 + 배경 패턴(dots·hatch, 타일) — 템플릿은 JSON                        |
| 스타일 구조    | 축 조합(`palette × type × geometry × layout × ornament`) — 리팩터 2회 모두 SVG 해시 동일 |

결정론:

| 산출물         | 재현                                               |
| -------------- | -------------------------------------------------- |
| SVG · manifest | ✅ 입력 해시 4종(recipe·style·tokens·catalog) 기록 |
| PNG @2x · WebP | ✅                                                 |
| PDF            | ✅ (pypdf로 날짜·ID 고정)                          |
| ZIP            | ✅ (1980 타임스탬프, 정렬)                         |

`embed_max_width`도 매니페스트에 기록한다.

## 4. 납품

```
dist/
├─ <name>.pdf            화면별 1페이지, 폰트 임베드
├─ <name>@2x.png
├─ <name>@2x.webp
├─ <name>.svg + manifest
├─ *.decisions.json     선택 이유(있으면)
└─ index.html · CREDITS.md · README.md · export.json
```

- export 단계에서 `origin:commercial`은 중단, `blocked`는 렌더 단계에서 중단
- CREDITS에 자산 출처·범위·AI 생성 정보(모델·프롬프트·시각)·재배포 제한이 자동으로 들어간다

## 5. AI 생성 자산

| 항목       | 상태                                                                   |
| ---------- | ---------------------------------------------------------------------- |
| 모델       | `gemini-3.1-flash-image` (cliproxyapi 경유), 로컬 `sd-turbo`(CPU) 대안 |
| 해상도     | 1408×768 (gemini) / 384~512 (sd-turbo)                                 |
| 메타데이터 | `items.annotation`에 모델·프롬프트·생성일                              |
| scope      | `output` 강제 (파일 재배포 금지)                                       |
| 고지       | CREDITS "생성 정보" + "재배포 제한" 절                                 |
| 워터마크   | gemini 출력 JPEG에 C2PA 메타데이터 포함                                |

## 6. Gemini 앱 연결

게이트웨이(`https://mcp.sonagi.space/mcp`)에 Google 커스텀 MCP 클라이언트 9개가 등록되어
`run`(888회)·`asset_upload`(28회) 등을 이미 사용 중이다. 이번에 추가한 도구:

| 도구           | 실행   | 시간   | 결과          |
| -------------- | ------ | ------ | ------------- |
| `compose_page` | devops | 3~14초 | SVG + CDN URL |
| `package_page` | 호스트 | 8~32초 | zip + CDN URL |

제약: 호출당 승인 1회, 100초 한도, 분당 40회.
`compose_page`는 80초를 넘으면 남은 브레이크포인트를 `not_rendered`로 돌려준다.

## 7. 보존

| 대상                        | 기간 | 방식                                    |
| --------------------------- | ---- | --------------------------------------- |
| 로컬 `jobs/compose/<name>/` | 7일  | `compose_page` 프루닝                   |
| CDN `releases/compose/`     | 30일 | MinIO lifecycle `compose-artifacts-30d` |

`releases/compose/`만 익명 읽기 허용. zip 이름은 내용 해시라 덮어쓰지 않는다.

## 8. 검증된 것

- 같은 입력 2회 → SVG·manifest·PDF·PNG·WebP·zip 해시 동일
- content.md → 레시피 → 손으로 쓴 레시피와 **바이트 동일** SVG
- Figma 재임포트: `<g id>` → GROUP, 텍스트 → TEXT, 아이콘 → VECTOR, 이미지 → IMAGE fill
- 폰트 4종 설치 후 Figma에서 대체 없이 렌더 (Pretendard Bold는 과중 → 한글 제목은 NanumSquare/Gowun)
- 다크 대비: 본문 17.2~17.7, 보조 11.4~11.7, 흐린 글자 7.1~7.4
- 게이트웨이 도구로 3브레이크포인트 랜딩 생성 → zip 16.6MB (embed 900)
- 블록 간격: 27스타일 × 3브레이크포인트 81렌더에서 겹침 0, 간격은 `BLOCK_GAP`(44) 기준
- 래스터: `xlink:href` 중복 제거로 임베드 SVG 절반. PNG·PDF 해시는 그대로(동일 픽셀)
- 링크 모드: 같은 이미지 1벌. 3브레이크포인트 3장 SVG 합계 463KB → 11KB(이미지 85KB 1벌)
- 레시피: `blocks` 정본 + 레거시 `content` 맵 자동 변환. 레시피 4종 스키마 검사 통과
- 락업: 3락업 × 4변형 12셀 대비 계산(최저 4.69:1). 저대비 스펙은 exit 1, 2회 렌더 해시 동일
- 규격 도해: 클리어 스페이스(0.5h=119px)·작도 12u·최소 크기 15mm/24px. 3장 2회 렌더 해시 동일
- 브랜드 시트: 8페이지 A4(210×297mm) 단일 PDF. 페이지별 해시 동일, 8페이지 확인
- 인쇄: A4 8페이지 → 226×313mm(도련 3·여백 5), CMYK 연산자만, 2회 실행 해시 동일
- 패키지: 90×60mm 라벨 audit P001–P007 전부 통과, 승인 해시 변조 시 exit 1
- Figma: `<pattern>` 배경은 임포트에서 사라진다. `--pattern-mode line`이면 유지(168KB → 943KB)
- 축 확장: type 4종·layout 2종 추가. `split-reverse`·`magazine-grid` 렌더 확인(데모 스타일 2종)
- 계약 헤더: 매니페스트에 `schema_version`·`tokens_version`·`style_id`·`ruleset_version` 4칸.
  골든 42렌더 갱신이 `manifest`만 바꾸고 `0px`(시각 무변)임을 확인
- 판정 골든 16케이스(clean 2·good 6·bad 8) 기준선 고정. bad는 mutation으로 생성
- 토큰 정본 단일화: MDS light/dark → editorial/architecture 투영. `tokens_version` d73bbac048e2
- 판정 골든 good 6케이스 전부 PASS — 제목·본문 줄바꿈과 MDS 대비로 WARN 3건 해소
- 린트 tspan 수정: 여러 줄 텍스트를 한 줄로 이어 재던 오탐 제거
- MDS 적용으로 editorial 판정이 WARN→PASS (eyebrow 3.03:1 → 5.18:1)
- 명부 정합성: 29스타일 × 12블록 × 룰 1.0.0, 중복 `style_id` 0, 레시피 참조 오류 0
- 결정 원장: contract·style_id·references 삼중 대조 통과, 자동 3건 + 사람 결정
- L1 린트가 처음 찾은 부채 3건: 12px accent eyebrow AA 미달(3.03:1),
  모바일 hero 제목 미줄바꿈(+18~51px), 로고 워드마크 대비 3.34~4.12:1

## 9. 알려진 부채

| 항목              | 내용                                                                          | 영향                                      |
| ----------------- | ----------------------------------------------------------------------------- | ----------------------------------------- |
| 갤러리 4개 배치   | 3열 그리드라 4번째가 빈 칸과 함께 남음                                        | 미관                                      |
| 다크 + 벡터 도판  | swiss·art-nouveau 다크에서 선화 도판이 배경에 묻힘(토큰 변경 전부터)          | 갤러리 공백                               |
| minimal 대비      | 스타일 팩 muted가 2.85:1 (판정 골든 미포함 스타일)                            | 접근성                                    |
| 다크 + 래스터     | 동판화가 밝은 종이색으로 남음                                                 | 갤러리 눈부심                             |
| devops 폰트 없음  | export는 호스트에서만 가능                                                    | 도구가 두 단계로 나뉨                     |
| 토큰 이중 소스    | 해소 — MDS `packages/tokens`가 정본, `tokens/`는 생성물. 다크 accent가 블루→골드로 바뀜(ΔE 124.8) | `docs/TOKEN_SSOT.md` |
| 보존 밖 자산      | 이전 `assets/` 업로드분은 lifecycle 미적용                                    | 수동 정리 필요                            |

## 10. 다음 후보

1. **갤러리 4개 배치** — 3열 그리드에서 한 칸이 남는다
2. **PDF/X·별색** — 인쇄소 요구가 있으면 ICC·Pantone 경로 추가
3. **Figma 왕복 자동 검증** — 프로젝트에 figma-console MCP를 켜면 임포트·Fill 검사를 자동화

## 11. 작업 순서 (Plane `sonagi-assets`)

사이클은 쓰지 않는다. 모듈(범위)과 상태(Todo/Backlog)로만 관리한다.

| 순서 | 이슈                     | 모듈          | 이유                          |
| ---- | ------------------------ | ------------- | ----------------------------- |
| —    | (남은 이슈 없음)         | —             | 13건 모두 완료                |

납품 품질(ASSET-2·3·4·5) · 아이덴티티(ASSET-9·10·11·12) · 인쇄(ASSET-6) ·
Figma(ASSET-7) · 스타일 축(ASSET-8) · 패키지 audit(ASSET-13) 완료.
패키지 우선 전략(WORK-29)의 다음 단계는 전개도 템플릿과 packaging.schema 다.

## 12. 재현 체크리스트

```bash
# 0. 골든 기준선 (렌더러를 고치기 전후로 돌린다 — docs/GOLDEN.md)
python3 scripts/golden_render.py            # 기준선과 비교 (CI가 같은 명령을 돌린다)
python3 scripts/golden_render.py --update   # 의도된 변경일 때만

# 1. 블록 간격 검수 (겹침·리듬 — 수정 후 전 스타일)
python3 scripts/check_gaps.py out/sweep --recursive --max-gap 60

# 2. content 검증 (카탈로그는 devops의 /srv/sonagi-assets/catalog/catalog.json)
python3 scripts/import_content.py content/studio-plan.md \
  --catalog /srv/sonagi-assets/catalog/catalog.json --check

# 3. 렌더 (devops, 자산이 있는 곳)
sudo python3 scripts/render_recipe.py --recipe recipes/<name>.json --style styles/etching.json \
  --catalog /srv/sonagi-assets/catalog/catalog.json --tokens tokens/semantic.json \
  --out out/<name> --breakpoint mobile --embed-max-width 900

# 4. 납품 (호스트, 폰트가 있는 곳)
python3 scripts/export_recipe.py --src out/<name> --out dist --formats pdf,png,webp \
  --scale 2 --fonts-css /home/ubuntu/brief/fonts/fonts.css
python3 scripts/bundle_delivery.py --src dist --out delivery/<name> --name "<제목>" --zip
```

## 13. 파일 지도

| 경로                                                           | 역할                                          |
| -------------------------------------------------------------- | --------------------------------------------- |
| `press` · `scripts/press.py`                                   | 단일 CLI(check·render·package·print·lockup·spec·brandsheet·styles·preview) |
| `scripts/render_recipe.py`                                     | 렌더러·스타일·다크 변환·매니페스트            |
| `scripts/contract.py`                                          | 계약 헤더 4칸 생성·검사                        |
| `scripts/build_registry.py`                                    | 명부 생성·정합성 검사(`registry/`)             |
| `scripts/ledger.py`                                            | 결정 원장 생성·검사(`*.decisions.json`)        |
| `scripts/compare_tokens.py`                                    | 두 토큰 저장소 역할별 ΔE 대조                  |
| `scripts/lint_render.py`                                       | L1 기계 판정(대비·겹침·레이어·라이선스·계약)  |
| `scripts/judgment_golden.py`                                   | 판정 골든셋 16케이스 + mutation               |
| `rules/ruleset.json`                                           | 판정 룰 정의(version 1.0.0)                   |
| `test_data/judgment/`                                          | clean.md · cases.json · baseline.json         |
| `registry/`                                                     | 스타일·블록·룰 명부(생성물, `--check`로 검증)  |
| `scripts/import_content.py`                                    | content.md → recipe + 검증                    |
| `scripts/export_recipe.py`                                     | PDF·PNG·WebP + 라이선스 게이트                |
| `scripts/render_lockup.py`                                     | 락업·변형 시트(스펙 JSON → SVG + 대비 검사)   |
| `scripts/render_spec.py`                                       | 규격 도해(클리어 스페이스·작도·최소 크기)     |
| `scripts/render_brandsheet.py`                                 | 브랜드 시트(A4 8페이지 → 단일 PDF)            |
| `scripts/bundle_delivery.py`                                   | zip·index.html·CREDITS                        |
| `scripts/build_asset_catalog.py`                               | DB → catalog.json (scope 판정 포함)           |
| `scripts/import_image_pack.py`                                 | 래스터 등록 + 생성 메타데이터                 |
| `scripts/license_policy.py`                                    | 라이선스 → scope 단일 출처                    |
| `CONTENT_FORMAT.md` · `PIPELINE.md`                            | 규격·계약                                     |
| `docs/FIGMA_ROUNDTRIP.md`                                      | Figma 재임포트 검증                           |
| `docs/IDENTITY_DELIVERY.md`                                    | 로고·브랜딩 납품 규격(락업·규격·법적 게이트)  |
| `content/*.md`                                                 | 실제 콘텐츠 예시 5종                          |
| `styles/axes.json` · `styles/ornaments.json` · `styles/*.json` | 축 정의 + 장식 템플릿(2D·패턴) + 스킨 27종    |
| `tokens/`                                                      | 프리미티브·시맨틱·Figma 변수                  |
