# Asset Catalog

`asset_hub.db`(8,768 items)를 읽기 전용으로 스캔해 정규화된 카탈로그를 만든다.

## 생성

```bash
# devops
sudo python3 scripts/build_asset_catalog.py \
  --db /srv/sonagi-assets/asset_hub.db \
  --library-root /srv/sonagi-assets/library \
  --out-dir /srv/sonagi-assets/catalog
```

산출물(저장소에 커밋하지 않음, 서버에만 둠):

| 파일 | 내용 |
| --- | --- |
| `catalog.json` | 8,768개 항목. id·이름·확장자·category·topics·source·format·style·license·path·sha256·svg_groups |
| `summary.json` | 집계와 결손(style/license/그룹 없는 SVG) |
| `tag-map.json` | 정규화 규칙 (DB에는 아직 미적용) |

## 정규화 규칙 (2026-11-22)

| 기존 | 변경 |
| --- | --- |
| `icons` | `category:ui-component`, `topic:icon` |
| `components`, `category:components` | `category:ui-component` |
| `typography` | `category:typography` |
| `mockups` | `category:mockups` |
| `Auto-Ingested` | `src:auto-ingested` |
| `topic:landscapes` | `topic:landscape` |

## 현재 결손

- `style`: 8,768 / 8,768 미분류
- `license`: 8,768 / 8,768 미확인
- SVG 그룹 없음: 3,360 / 6,586 (Figma에서 그룹 보존 불가)
- 파일 경로 없음: 120
- category 2개 이상: 다수 (우선순위 규칙 필요)
