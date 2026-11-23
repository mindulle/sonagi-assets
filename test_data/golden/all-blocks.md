---

name: golden-all-blocks
theme: editorial
seed: 7
canvas: { width: 1440, height: auto }
---

## header

brand: GOLDEN FIXTURE
nav:

- 기준선
- 검수
- 기록

## hero

eyebrow: 렌더 기준선
title: 열두 블록을 한 번에 고정한다
body: 간격 회귀를 잡기 위한 고정 픽스처. 문장은 검수용이며 배포하지 않는다.
cta: 기준선 보기
ctaIcon: arrow-right
illustration:
- fixture-plate-raster

## stats

- 12 | 블록
- 3 | 브레이크포인트
- 2 | 테마

## features

title: 검수 항목

### 블록 간격

icon: ruler
블록이 반환하는 advance와 호출부 오프셋이 일치하는지 본다.

### 자산 경로

icon: package
아이콘·일러스트가 픽스처 카탈로그에서 해석되는지 본다.

### 시각 확인

icon: eye
해시가 달라진 항목만 눈으로 다시 본다.

## logos

- FIXTURE ONE
- FIXTURE TWO
- FIXTURE THREE
- FIXTURE FOUR

## quote

text: 기준선이 없으면 좋아졌는지 나빠졌는지 말할 수 없다.
author: 검수 노트

## faq

title: 자주 묻는 질문

### 왜 픽스처를 따로 두나요?

실제 카탈로그는 7.2GB라 CI에서 쓸 수 없습니다. 여기 있는 7개 자산만으로 렌더합니다.

### 해시가 바뀌면 실패인가요?

의도된 변경이면 기준선을 갱신합니다. 갱신 커밋에 이유를 남깁니다.

## table

title: 기준선 범위
columns: 항목 | 이전 | 이후
featured: 2

- 블록 | 12 | 12
- 브레이크포인트 | 3 | 3
- 테마 | 2 | 2
note: 픽스처는 배포 대상이 아닙니다.

## pricing

title: 검수 단계

### 해시 비교

price: 1단계
period: 자동

- 18개 렌더 해시
- 실패 시 목록 출력
cta: 실행
featured: true

### 시각 검수

price: 2단계
period: 사람

- 달라진 항목만 확인
- 판단 근거 기록
cta: 확인

## gallery

title: 픽스처 도판

- fixture-plate-a
- fixture-plate-raster
- fixture-plate-b
note: 자체 제작 · CC0

## cta

eyebrow: 다음 단계
title: 기준선을 먼저 떠 둔다
body: 수정 전 해시가 있어야 회귀와 의도된 변경을 구분할 수 있습니다.
cta: 기준선 갱신
ctaIcon: arrow-right

## footer

left: GOLDEN FIXTURE
right: 검수용 · 배포 금지
