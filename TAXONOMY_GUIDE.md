# Sonagi Unified Taxonomy Guide

이 문서는 Sonagi 생태계의 두 핵심 축인 **Asset Hub (`assets.sonagi.space`)** 와 **Reference Hub (`ref.sonagi.space`)** 의 명확한 역할 분리와 일관된 태깅(Tagging) 체계를 정의합니다.
과거 하나로 묶여 있던 21,500여 개의 레거시 데이터는 이 가이드를 기준으로 두 개의 플랫폼으로 분리 라우팅됩니다.

---

## 1. 아키텍처 역할 분리 (Routing Rules)

| 특성 | Asset Hub (`assets.sonagi.space`) | Reference Hub (`ref.sonagi.space`) |
| :--- | :--- | :--- |
| **목적** | 실무에 즉시 가져다 쓸 수 있는 **재사용 가능한 부품** | 기획/디자인 영감을 얻기 위한 **참고용 완성본** |
| **주요 데이터** | 폰트, 아이콘(SVG), 텍스처, 3D 오브젝트, 목업 파일 | 앱/웹 캡처 화면, 포트폴리오 샷, Dribbble/Mobbin 이미지 |
| **허용 확장자** | `ttf`, `otf`, `svg`, `psd`, 투명 배경 `png`/`webp` | `jpg`, `png`, `webp` (주로 캡처된 평면 이미지) |
| **태그 포커스**| 재질(Medium), 확장자(Format), 감성(Style) | 플랫폼(Platform), 화면 패턴(Pattern), 산업(Industry) |

---

## 2. 공통 태그 스키마 (Common Prefixes)

두 플랫폼 모두 출처를 명확히 하기 위해 아래 태그를 공통으로 사용합니다.
- `src:the-met`, `src:cma` (공공 박물관 / 오픈소스 API)
- `src:mobbin`, `src:dribbble`, `src:pinterest` (크롤링 소스)
- `src:sonagi-legacy` (사내 기존 Eagle 백업본)

---

## 3. Asset Hub 전용 스키마 (`assets.sonagi.space`)

박물관 큐레이션 및 에셋 스토어 구조를 차용한 "재료" 중심의 분류입니다.

- `category:` (대분류) - `category:typography`, `category:mockups`, `category:3d-object`, `category:ui-component`
- `medium:` / `format:` (매체/포맷) - `medium:watercolor`, `medium:oil`, `format:vector`, `format:transparent`
- `topic:` (주제) - `topic:botanical`, `topic:landscape`, `topic:nature`
- `style:` (아트스타일) - `style:minimal`, `style:retro`, `style:claymorphism`

---

## 4. Reference Hub 전용 스키마 (`ref.sonagi.space`)

Mobbin 등 글로벌 레퍼런스 사이트의 UI/UX 탐색 구조를 차용한 "화면" 중심의 분류입니다.

- `platform:` (구동 환경) - `platform:ios`, `platform:android`, `platform:web`, `platform:desktop`
- `pattern:` (UI 컴포넌트 패턴) - `pattern:bottom-sheet`, `pattern:modal`, `pattern:hero-section`, `pattern:carousel`
- `flow:` (사용자 여정) - `flow:onboarding`, `flow:checkout`, `flow:login`, `flow:settings`
- `industry:` (도메인/산업군) - `industry:fintech`, `industry:ecommerce`, `industry:productivity`, `industry:healthcare`

---

## 🛠 레거시 데이터 마이그레이션 적용 (Best Practices)
21,500개의 기존 데이터를 처리할 때 아래 규칙을 따릅니다:
1. 기존 `metadata.json`의 폴더명이나 해상도를 분석하여 **화면 캡처본(가로가 긴 웹 캡처, 세로가 긴 모바일 캡처)**은 Reference Hub용 스키마로 매핑합니다.
2. 배경이 투명하거나, 확장자가 폰트/벡터인 경우 Asset Hub용 스키마로 매핑합니다.
3. 알 수 없는 찌꺼기 데이터는 버리거나 `status:needs-review` 태그를 달아 보류합니다.
