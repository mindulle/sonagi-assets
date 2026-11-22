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

## 배포처 근거 분류 (2026-11-22)

폰트 파일에 라이선스 문구·URL이 없어도 배포처의 공식 정책으로 확정할 수 있다.
이름 규칙 + 근거 URL을 코드에 남기고, 확정된 85개 파일에 적용했다.

| 배포처 | 라이선스 | 파일 수 |
| --- | --- | --- |
| Google Fonts (OFL·Apache) | ofl 17, apache 1 | 18 |
| KBIZ 한마음 | free | 9 |
| 문체부 | free | 8 |
| 조선일보 | free | 7 |
| 눈서리 (SF싸락눈 등) | free | 7 |
| LINE Seed | ofl | 6 |
| EBS | free | 6 |
| 토끼네활자공장 (HS) | free | 6 |
| Mapo | free | 4 |
| Ubuntu | free | 4 |
| utoimage·123RF (비비트리) | free | 11 |
| Cafe24·Pretendard·나눔 | ofl/free | 5 |
| 성신여대 | internal-only | 2 |
| 다온폰트 | commercial | 2 |

- 태그: `license:<값>`, `license_src:provider`, `license_provider:<slug>`, `license_url:<근거 URL>`
- `license_src:copyright`(저작권 문구 휴리스틱)·`license_src:site`(도메인 추정)로 붙은 값은
  배포처 근거가 있으면 덮어쓴다. 공공 폰트가 "All rights reserved"를 달고 있는 경우를 교정한다.
- DB 백업: `asset_hub.db.bak-provider-20261122T114446Z`

### 국내 기관·기업 폰트 확인 (2026-11-22)

공공기관·지자체·기업 배포 서체 28개 파일을 공식 페이지로 확인해 추가했다.

| 배포처 | 판정 | 조건 |
| --- | --- | --- |
| 경기도 (경기천년제목) | free | 판매 금지 |
| 부산바다체 | free | 수정·재배포 가능 |
| 김제시체 | free | 임베딩·변형은 협의 |
| KOTRA | free | 공공누리 1유형, 재배포 금지 |
| KDB고딕Pro | free | 수정·판매·CI/BI 금지 |
| 롯데마트 드림체 | free | 수정·판매·CI/BI 금지 |
| 배스킨라빈스체 | free | 수정·재배포 금지 |
| 땅스부대찌개체 | free | 요식업 프랜차이즈 사용 제한 |
| 샌드박스 어그로체 | free | 수정·재배포 가능 |
| 검은고딕 · 한글틀고딕 | OFL | — |
| DOS 계열 · 삼국지3 · 미래로 | MIT | 출처 표기 권장 |
| Kirsty (Typodermic) | free | 파일 재배포·임베딩 불가 |
| 빙그레체 | internal-only | 해외 사용 불가 |
| HJ한전서 | internal-only | 저작권자·사용범위 불명 |

- 백업: `asset_hub.db.bak-provider-20261122T1149*`
- Kirsty·KOTRA·KDB·롯데마트·배스킨라빈스는 **결과물 사용은 가능하지만 폰트 파일 재배포는 불가**하다.
  판매용 팩에 폰트 파일을 넣을 때는 OFL·MIT·Apache·CC0만 사용해야 한다.

### 남은 65개

| 성격 | 수 | 예시 |
| --- | --- | --- |
| 영문 novelty/display (개인용 배포) | 63 | `ButterFly`, `starthings`, `tender kittens`, `HARLEQUI` |
| TRGothic 2종 | 2 | 배포처 불명 |

## 일러스트 세트 수급 (2026-11-22)

온보딩 3화면의 빈 영역을 채우기 위해 flat 스타일 세트 1종을 임포트했다.
스타일을 하나로 고정해야 이후 세트가 섞이지 않는다.

| 세트 | 라이선스 | 파일 | 스타일 |
| --- | --- | --- | --- |
| illlustrations (vijay verma) | MIT | 146 | flat · color |

```bash
sudo python3 scripts/import_icon_pack.py \
  --db /srv/sonagi-assets/asset_hub.db \
  --library-root /srv/sonagi-assets/library \
  --src /tmp/stage --set illlustrations --license mit \
  --provider illlustrations --url https://github.com/realvjy/illlustrations \
  --kind illustration --topic illustration --style flat --palette color --form none --apply
```

- 태그: `kind:illustration`, `topic:illustration`, `style:flat`, `palette:color`, `scope:bundle`
- 카탈로그 **14,876**, `bundle` **10,413**
- 임포터가 `--kind/--topic/--style/--palette`를 받도록 일반화됨

**주의**: 원본 SVG에 자체 배경색과 제작자 크레딧 텍스트가 들어 있다.
그대로 배치하면 카드 안에 카드가 생기고 크레딧이 노출된다.
현재는 `object-fit: cover`로 크롭해 쓰고 있고, 제대로 쓰려면 배경 제거·크레딧 제거
전처리 단계가 필요하다. 컬러 토큰이 없어 임시로 흑백 처리했다.

## 아이콘 팩 수급 (2026-11-22)

브리프 테스트에서 아이콘 슬롯 17개 중 0개가 채워진 것이 확인되어, 라이선스가 명확한
오픈 아이콘 팩 3종을 개별 SVG로 임포트했다.

| 팩 | 라이선스 | 파일 | 형태 |
| --- | --- | --- | --- |
| Lucide | ISC | 2,410 | line |
| Tabler (outline) | MIT | 5,491 | line |
| Phosphor (regular) | MIT | 1,512 | line |
| **합계** | | **9,413** | |

```bash
sudo python3 scripts/import_icon_pack.py \
  --db /srv/sonagi-assets/asset_hub.db \
  --library-root /srv/sonagi-assets/library \
  --src /tmp/packs/lucide --set lucide --license isc \
  --provider lucide --url https://lucide.dev/license --apply
```

- 160px PNG 썸네일 9,413개 생성 (`cairosvg`)
- 태그: `kind:icon`, `topic:icon`, `set:<pack>`, `form:line`, `license:*`, `scope:bundle`
- 카탈로그 5,317 → **14,730**, `bundle` 10,267
- 검색: `GET /api/items?search=arrow-left`
- DB 백업: `asset_hub.db.bak-icons-20261122T1427*`

카탈로그 빌더는 이제 폰트 외 자산도 명시적 `license:` 태그를 우선한다
(`explicit-tag`). 아이콘 9,413개가 internal-only로 떨어지던 문제를 고쳤다.

## 라이선스 사용 범위 3단계 (2026-11-22)

"무료"와 "파일을 줘도 됨"은 다르다. 결과물 사용과 파일 재배포를 분리했다.

| scope | 의미 | 해당 라이선스 |
| --- | --- | --- |
| `bundle` | 결과물 + 폰트 파일 재배포 가능 | OFL, MIT, Apache, CC0 |
| `output` | 결과물 제작만. 파일 재배포·임베딩 금지 | free (KOTRA·KDB·롯데마트·Kirsty 등) |
| `blocked` | 사용 불가 | commercial, personal, GPL, internal-only |

정책 단일 출처는 `scripts/license_policy.py`다. 카탈로그의 모든 항목에
`license_scope`가 붙고, 폰트 allow-list는 별도 파일로 만든다.

```bash
sudo python3 scripts/build_font_allowlist.py \
  --db /srv/sonagi-assets/asset_hub.db \
  --library-root /srv/sonagi-assets/library \
  --out /srv/sonagi-assets/catalog/font-allowlist.json --apply
```

| 구분 | 패밀리 | 파일 |
| --- | --- | --- |
| bundle | 329 | 813 |
| output | 133 | 162 |
| blocked | 458 | 810 |

- 폰트 파일을 포함한 판매 팩: `bundle` 813개만
- 디자인 결과물(PNG·SVG·PDF) 제작: `bundle` + `output` 975개
- DB 백업: `asset_hub.db.bak-scope-20261122T135802Z`

### 앱 API

```bash
# 파일 재배포 가능한 폰트만
curl "http://127.0.0.1:34920/api/fonts/allowlist?scope=bundle&limit=20"

# 이름 검색 (scope=all 로 전체 대상)
curl "http://127.0.0.1:34920/api/fonts/allowlist?scope=all&search=kotra"

# 에셋 목록을 scope로 필터
curl "http://127.0.0.1:34920/api/items?license_scope=bundle"
```

allow-list는 `/app/catalog/font-allowlist.json`(호스트 `/srv/sonagi-assets/catalog`)을
읽고, 파일 mtime이 바뀌면 자동으로 다시 읽는다. 파일이 없으면 503.

### 팩 검사 게이트

```bash
python3 scripts/check_pack.py \
  --allowlist catalog/font-allowlist.json \
  pack/fonts/*.ttf
```

`bundle`이 아닌 파일이나 목록에 없는 파일이 하나라도 있으면 **exit 1**.
`--sha256`을 주면 파일 해시로 먼저 대조한다.

**팩에 넣을 파일만 뽑기**

```bash
jq -r '.entries[] | select(.scope=="bundle") | .files[].path' \
  catalog/font-allowlist.json
```

각 파일에는 `bytes`, `sha256`, `license`, `provider`, `license_url`이 함께 기록된다.

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
