# Asset Catalog

`asset_hub.db`(8,768 rows)를 읽기 전용으로 스캔해 정규화된 카탈로그를 만든다.

## 생성

```bash
# devops
sudo python3 scripts/build_asset_catalog.py \
  --db /srv/sonagi-assets/asset_hub.db \
  --library-root /srv/sonagi-assets/library \
  --out-dir /srv/sonagi-assets/catalog \
  --google-fonts /tmp/google-fonts.json   # 선택: OFL 판별
```

산출물(서버에만 두고 저장소에는 커밋하지 않음):

| 파일 | 내용 |
| --- | --- |
| `catalog.json` | 항목별 id·이름·확장자·category·topics·source·format·style·license·license_basis·junk·path·sha256·svg_groups |
| `summary.json` | 집계와 결손 |
| `tag-map.json` | 태그 정규화 규칙 (DB에는 미적용) |

## 태그 정규화

| 기존 | 변경 |
| --- | --- |
| `icons` | `category:ui-component`, `topic:icon` |
| `components`, `category:components` | `category:ui-component` |
| `typography` | `category:typography` |
| `mockups` | `category:mockups` |
| `Auto-Ingested` | `src:auto-ingested` |
| `topic:landscapes` | `topic:landscape` |

## 라이선스 기본값

| 조건 | license | 근거 |
| --- | --- | --- |
| 이름이 `._` 로 시작 | `n/a` | macOS AppleDouble 메타데이터 (에셋 아님) |
| 폰트 + Google Fonts 패밀리 일치 | `ofl` | `--google-fonts` 목록 대조 |
| `src:the-met`, `src:cma` | `cc0` | 박물관 Open Access |
| 그 외 | `internal-only` | 출처 미확인 — 판매/배포 제외 |

> `internal-only`는 불법이라는 뜻이 아니라 **증명이 없다**는 뜻이다. D2C·외주 납품물에는 allow-list로만 포함한다.

## 현재 상태 (2026-11-22, `._` 정리 후)

| 항목 | 값 |
| --- | --- |
| 전체 row | **5,317** |
| macOS `._` 정리 | 3,451행 / 3,408파일 삭제 완료 |
| 스타일 미분류 | 5,317 / 5,317 |
| 라이선스 미확인 | 5,008 / 5,317 |
| CC0 | 40 |
| OFL 폰트 | 269 |
| SVG 그룹 없음 | **199** / 3,425 |
| 파일 경로 없음 | 77 |

## macOS `._` 정리

```bash
sudo python3 scripts/clean_appledouble.py \
  --db /srv/sonagi-assets/asset_hub.db \
  --library-root /srv/sonagi-assets/library --apply
```

- 아카이브: `/srv/archive/appledouble-20261122T102623Z.tar.gz`
- DB 백업: `/srv/sonagi-assets/asset_hub.db.bak-appledouble-20261122T102623Z`

## 심볼 시트 태깅 (2026-11-22)

`Dingbats·Symbols·Math·Music` 시트 74개에 3축 태그를 적용했다.

| 축 | 값 | 분포 |
| --- | --- | --- |
| `form:` | line / filled / mixed | filled 58, mixed 16 |
| `palette:` | mono / color | mono 74 |
| `theme:` | 이름의 `____` 뒤 슬러그 | military, food, navigation-signs … |

```bash
sudo python3 scripts/tag_symbol_sheets.py \
  --db /srv/sonagi-assets/asset_hub.db \
  --library-root /srv/sonagi-assets/library --apply
```

- DB 백업: `/srv/sonagi-assets/asset_hub.db.bak-symboltags-20261122T110332Z`

## 미확인 폰트 추가 단서 (2026-11-22)

폰트 안의 추가 필드(name ID 7~14, OS/2 vendor ID)와 URL을 조사했다.

| 단서 | 수량 |
| --- | --- |
| vendor ID 보유 | 989 / 989 |
| URL 보유 | 648 |
| designer 필드 | 734 |
| "All rights reserved" | 774 |
| 같은 폴더 문서 | 0 |

도메인 기반 분류(상용 파운드리/무료 배포처):

| 결과 | 파일 수 |
| --- | --- |
| commercial (fontfabric·yoon·sandoll 등) | 493 |
| free (naver·cafe24·woodcutter 등) | 47 |
| 도메인만 기록(license_site) | 108 |
| 도메인 없음 | 356 |

```bash
sudo python3 scripts/deep_font_clues.py ... --out catalog/font-clues.json
sudo python3 scripts/classify_font_sites.py ... --apply
```

DB 백업: `asset_hub.db.bak-fontsites-20261122T113432Z`

## 폰트 라이선스 실측 (2026-11-22)

폰트 파일에 내장된 name table(ID 0·13·14)을 읽어 라이선스를 분류했다.

```bash
sudo python3 scripts/audit_font_licenses.py \
  --db /srv/sonagi-assets/asset_hub.db \
  --library-root /srv/sonagi-assets/library --apply
```

| 라이선스 | 파일 수 |
| --- | --- |
| **Commercial** | **787** |
| internal-only (미확인) | 3,678 |
| OFL | 714 |
| Free (사이트 기준) | 47 |
| Apache | 46 |
| CC0 | 42 |
| Personal-use | 2 |
| GPL | 1 |

`All rights reserved` 문구가 있는 미분류 폰트 270개를 commercial로 확정했다.
(백업: `asset_hub.db.bak-rightsreserved-20261122T113851Z`)

- Commercial/Personal 폰트는 **D2C·외주 납품물에서 제외**해야 한다.
- WOFF2 분석에는 `brotli` 파이썬 패키지가 필요하다.
- DB 백업: `asset_hub.db.bak-fontlicense-20261122T112249Z`

## 아이콘/스펙시멘 분리 (2026-11-22)

- 실제 아이콘 24개만 `kind:icon|illustration` 유지
- 타이포 specimen·컬러 팔레트·프레임 49개는 `kind:specimen`으로 재분류

## 글리프 처리 (2026-11-22)

폰트 글리프 SVG 2,818개에 `kind:glyph` 태그를 붙이고, 앱 기본 목록에서 제외했다.

- `GET /api/items` → 2,499개 (글리프 제외)
- `GET /api/items?include_glyphs=1` → 5,317개 (전체)
- 파일은 삭제하지 않음 (6.7MB, 아이콘 소스로 재사용 가능)

```bash
sudo python3 scripts/tag_glyphs.py --db /srv/sonagi-assets/asset_hub.db --apply
```

DB 백업: `asset_hub.db.bak-glyphtags-20261122T111506Z`

## 아이콘·일러스트 태깅 (2026-11-22)

심볼 시트/글리프/타이포 specimen/색상 팔레트를 제외한 벡터 에셋 73개에 4축 태그를 적용했다.

| 축 | 값 |
| --- | --- |
| `kind:` | icon / illustration |
| `form:` | line / filled / mixed |
| `palette:` | mono / color |
| `shape:` | geometric / organic |
| `detail:` | simple / detailed |

```bash
sudo python3 scripts/tag_vector_assets.py \
  --db /srv/sonagi-assets/asset_hub.db \
  --library-root /srv/sonagi-assets/library --apply
```

- DB 백업: `asset_hub.db.bak-vectortags-20261122T110744Z`
- 주의: 코퍼스에 타이포/프레임 잔재가 섞여 있어 73개 중 일부는 수동 확인 필요

## 폰트 라이선스 리포트 (2026-11-22)

```bash
sudo python3 scripts/font_license_report.py \
  --db /srv/sonagi-assets/asset_hub.db \
  --google-fonts google-fonts.json \
  --out /srv/sonagi-assets/catalog/font-license-report.json
```

| 항목 | 값 |
| --- | --- |
| 폰트 파일 | 1,785 |
| 고유 패밀리 | 920 |
| Google OFL 패밀리 | 67 |
| 알려진 무료(Korean 등) | 84 |
| **미확인** | **769 패밀리 / 1,307 파일** |

## 폰트 글리프 발견 (2026-11-22)

스타일 클러스터링을 돌린 결과, SVG 3,425개 중 **2,954개가 `uniXXXX` 형태의 유니코드 글리프**였습니다.
(폰트를 글리프 단위 SVG로 내보낸 것 — 디자인 에셋이 아님)

- `kind: glyph`로 분리 (`^uni[0-9a-f]{4,6}` 또는 1~2글자 이름)
- 실제 스타일 클러스터링 대상: 파일이 읽히는 벡터 에셋 **346개**
- 6개 클러스터로 묶었지만, `colon`, `less`, `wakorean` 같은 기호 글리프가 섞여 라벨 신뢰도는 낮음

```bash
python3 scripts/style_cluster.py --catalog catalog.json --out-dir .
# → style-clusters.json, style-assignments.json (검토용, DB 미반영)
```

## 다음 작업

1. `kind` 정교화 (glyph / icon / illustration / mockup) — 기호 글리프 추가 분리
2. 남은 벡터 에셋(~350개) 스타일 태깅
3. 폰트 2,075개 중 미매칭 1,806개 수동 확인 (상용 폰트 가능성)
4. legacy 에셋 중 판매 대상만 개별 라이선스 확인
