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

## 다음 작업

1. 스타일 태깅 (상위 500개부터)
3. 폰트 2,075개 중 미매칭 1,806개 수동 확인 (상용 폰트 가능성)
4. legacy 에셋 중 판매 대상만 개별 라이선스 확인
