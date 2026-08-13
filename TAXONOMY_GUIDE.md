# Sonagi Asset Hub Taxonomy Guide

이 문서는 `sonagi-assets`에 저장되는 에셋들의 일관된 검색과 관리를 보장하기 위한 다차원 태그(Multi-faceted Tagging) 기반 분류 체계를 정의합니다.
폴더 기반의 계층적 구조(Hierarchical)를 지양하고, 언제든 조합하여 필터링할 수 있는 **접두사(Prefix)** 기반 태그 구조를 사용합니다.

## 📌 핵심 태그 스키마 (Prefixes)

### 1. `src:` (출처 / Source)
에셋의 태생과 라이선스(저작권) 추적을 위한 태그입니다.
- `src:the-met` (메트로폴리탄 미술관 - CC0)
- `src:aic` (시카고 미술관 - CC0)
- `src:unsplash` (Unsplash)
- `src:sonagi-legacy` (사내 기존 보유 에셋)

### 2. `dept:` / `category:` (대분류 / Department)
에셋의 근본적인 성격이나 소속을 나타냅니다.
- `dept:paintings` (회화)
- `dept:drawings-and-prints` (드로잉 및 판화)
- `category:ui-component` (UI 구성요소)
- `category:mockups` (목업 템플릿)

### 3. `medium:` / `format:` (매체 및 포맷)
디자이너가 실무에서 시각적 질감이나 확장자를 구별할 때 가장 많이 찾는 태그입니다.
- `medium:watercolor` (수채화 질감)
- `medium:oil` (유화 질감)
- `medium:woodblock` (목판화)
- `format:vector` (확대해도 깨지지 않는 SVG, AI 등)
- `format:3d-object` (3D 렌더링된 사물)

### 4. `topic:` (주제)
에셋에 무엇이 묘사되어 있는지(Subject)를 나타냅니다.
- `topic:botanical` (식물, 꽃, 나뭇잎)
- `topic:landscape` (풍경, 산, 바다)
- `topic:dashboard` (UI 대시보드 화면)
- `topic:login` (로그인 화면)

### 5. `style:` / `mood:` (분위기 및 아트스타일)
검색 시 특정한 "느낌"을 찾을 때 사용되는 감성/스타일 태그입니다.
- `style:minimal` (미니멀, 여백이 많은)
- `style:retro` (레트로, 빈티지)
- `mood:dark` (다크모드 특화)
- `mood:playful` (발랄하고 둥글둥글한 느낌)

---

## 🛠 태깅 룰 (Best Practices)
1. **소문자 및 케밥 케이스(kebab-case) 사용:** 태그 이름에 띄어쓰기가 필요할 경우 항상 하이픈(`-`)을 사용합니다. (예: `topic:user-interface`)
2. **자동화 권장:** 봇이나 스크립트를 통해 에셋을 대량으로 Ingest할 때, 원본 소스(API)의 메타데이터를 반드시 이 규칙에 맞추어 변환(Mapping)한 뒤 삽입해야 합니다.
