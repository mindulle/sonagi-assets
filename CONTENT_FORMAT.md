# content.md 규격

화면의 **내용**을 배치(레시피)와 분리해 적는 파일 형식.

```
content.md  ──import_content.py──▶  recipe.json  ──render──▶  SVG
 (사람이 씀)                        (자동 생성)                (3 브레이크포인트)
```

같은 `content.md`로 스타일만 바꿔 여러 시안을 뽑는 것이 목적이다.

## 1. 파일 구조

```markdown
---
name: atelier-landing
theme: editorial
seed: 7
canvas: { width: 1440, height: auto }
---

## header
brand: ATELIER SONAGI
nav:
  - 아카이브
  - 프린트

## hero
title: 종이 위에 남는
  풍경
body: 19세기 풍경화 아카이브를 무광 페이퍼에 옮겼습니다.
cta: 컬렉션 보기
```

- `---` 사이는 YAML frontmatter. `name`만 필수.
- `## 타입`이 블록 하나. **파일에 적힌 순서가 그대로 화면 순서**가 된다.
- `## ` 바깥의 문장은 오류다(조용히 무시하지 않는다).

## 2. 문법

| 표기 | 의미 |
| --- | --- |
| `key: 값` | 필드 하나 |
| 2칸 들여쓴 줄 | 앞 필드에 **줄바꿈으로 이어 붙임** |
| `- 값` | 앞 필드의 목록 항목 |
| `### 제목` | 반복 항목(카드·질문) 하나 시작 |
| `- 값 \| 라벨` | stats 전용, 좌우 분리 |
| 빈 줄 | 무시 |

목록 대상이 없는 `- 값`은 `items`로 들어간다.

## 3. 타입

| 타입 | 필수 | 선택 |
| --- | --- | --- |
| `header` | `brand` | `nav` (≤4) |
| `hero` | `title`, `cta` | `eyebrow`, `body`, `ctaIcon`, `note`, `illustration` (1–2) |
| `stats` | `items` | — |
| `features` | `items` | `title` |
| `logos` | `items` (≤5) | — |
| `quote` | `text` | `author` |
| `faq` | `items` | `title` |
| `cta` | `title`, `cta` | `eyebrow`, `body`, `ctaIcon`, `note` |
| `footer` | `left` | `right` |
| `table` | `columns`, `items` | `title`, `note`, `featured` |
| `pricing` | `items` (≤3) | `title`, `note` |
| `gallery` | `items` (≤6) | `title`, `note` |

`features`·`faq`의 `items`는 `### 제목`으로 만든다.

```markdown
## features
title: 고르는 기준

### 원본 그대로
icon: package
박물관 공개 스캔을 색보정 없이 인쇄합니다.

### 실물 확인
icon: eye
주문 전 샘플 컷으로 질감을 확인할 수 있습니다.
```

```markdown
## faq
title: 자주 묻는 질문

### 원본은 어디에서 오나요?
메트로폴리탄·클리블랜드 등 CC0 컬렉션에서만 가져옵니다.
```

`### 제목`이 질문, 아래 문장이 답이 된다.

### table — 비교표

```markdown
## table
title: 포함 범위
columns: 항목 | 무료 | 스탠다드 | 프로
featured: 4
- 원본 색보정 | 기본 | 정밀 | 정밀
- 인화 크기 | A4 | A3 | A2
- 소스 파일 | ✕ | ✓ | ✓
note: 모든 요금은 1점 기준입니다.
```

- **첫 열은 행 이름**, 나머지가 값이다. `columns` 개수와 행의 칸 수가 같아야 한다.
- `featured`는 강조할 열 번호(1부터). 해당 열에 배경과 강조색이 들어간다.

### pricing — 요금 카드

```markdown
## pricing
title: 요금제

### 스탠다드
price: 49,000원
period: A3 · 1점
- 색보정 2회
- 소스 파일 제공
cta: 주문하기
featured: true
```

- `### 카드명` 아래 `- ` 줄이 포함 항목이 된다.
- `featured: true`는 한 카드에만. 강조 테두리와 채워진 버튼이 된다.

### gallery — 이미지 격자

```markdown
## gallery
title: 최근 에디션
- angelica-kauffman-self-portrait-etching--46884898
- a-dog-fight-rowlandson-1811-68643479
note: CC0 · 메트로폴리탄 미술관
```

카탈로그의 일러스트 이름만 쓴다. 3열(모바일 2열)로 배치된다.

## 4. 검증

`import_content.py`가 렌더 전에 막는 것.

| 검사 | 결과 |
| --- | --- |
| 알 수 없는 타입·필드 (오타) | 오류 |
| 필수 필드 누락 | 오류 |
| 목록 항목 수 초과 (nav 4, logos 5, illustration 2) | 오류 |
| 아이콘·일러스트 이름이 카탈로그에 없음 | 오류 + 유사 이름 제안 |
| `scope`가 `bundle`이 아님(차단·생성 자산) | 오류 |
| table 열 개수와 행 칸 수 불일치 | 오류 |
| `table.featured` 범위 밖 | 오류 |
| pricing 카드 4개 이상, featured 중복 | 오류 |
| gallery 7개 이상 | 오류 |
| 문장 길이 초과 | 경고 |

`--catalog`를 주면 자산 검사까지 한다. 없으면 구조 검사만 한다.

## 5. 실행

```bash
# 검사만
python3 scripts/import_content.py content/atelier-landing.md --check

# 레시피 생성
python3 scripts/import_content.py content/atelier-landing.md \
  --catalog catalog/catalog.json --out recipes/atelier-landing.json

# 이어서 렌더
python3 scripts/render_recipe.py --recipe recipes/atelier-landing.json \
  --style styles/etching.json --catalog catalog/catalog.json \
  --tokens tokens/semantic.json --out out/atelier --breakpoint mobile
```

생성된 레시피에는 `content` 키가 붙는다(원본 파일명·해시). 렌더 매니페스트가 레시피 해시를 기록하므로 **어떤 문장으로 만든 화면인지** 추적된다.

## 6. 하지 않는 것

- 문장을 만들어 주지 않는다. 사람이 쓴 문장을 옮기고 검사할 뿐이다.
- 배치를 바꾸지 않는다. 순서와 블록 타입만 정한다. 위치·간격은 스타일 팩이 정한다.
- 이미지 생성·검색을 하지 않는다. 일러스트는 카탈로그 이름으로만 지정한다.

## 7. 길이 기준

| 필드 | 기준 |
| --- | --- |
| `hero.title` | 한 줄 20자 내외, 최대 2줄 |
| `hero.body` | 60자 내외 |
| `stats.label` | 12자 내외 |
| `features.title` | 14자 내외 |
| `features` item `body` | 50자 내외 |
| `faq` 답변 | 100자 내외 |

넘으면 경고만 하고 생성은 계속한다. 판단은 사람이 한다.
