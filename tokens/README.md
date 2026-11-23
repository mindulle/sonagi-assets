# Design tokens

**생성물이다. 직접 수정하지 않는다.**

정본은 `mindulle-design-system/packages/tokens`(2026-11-23 결정)다. 이 폴더는 MDS의
`light`/`dark`를 이 저장소의 두 테마 `editorial`/`architecture`로 투영한 결과다.

```bash
python3 scripts/build_design_tokens.py \
  --mds ../mindulle-design-system/packages/tokens \
  --radix node_modules/@radix-ui/colors \
  --out tokens
```

`--radix`를 생략하면 기존 `primitives.json`을 유지한다(Radix는 프리뷰용 보조 스케일).
값을 바꾸려면 MDS를 고치고 이 스크립트를 다시 돌린 뒤, 골든과 판정 기준선을 갱신한다.

```bash
python3 scripts/golden_render.py --update
python3 scripts/judgment_golden.py --update
python3 scripts/build_registry.py
```

## 파일

| 파일 | 내용 |
| --- | --- |
| `primitives.json` | Radix Colors 램프(sand·amber·blue·cyan·red·green, light/dark 12단계) |
| `semantic.json` | 브랜드 역할값 2테마: `editorial`, `architecture` |
| `tokens.css` | `--mds-*` CSS 변수 (프리미티브 + 시맨틱 + 스페이스·반경·타입·보더) |
| `tokens.figma.json` | Tokens Studio 형식 (Figma 변수 임포트용) |

## 두 팔레트

| 역할 | Editorial | Architecture |
| --- | --- | --- |
| 배경 | `#fbfbfa` | `#12151d` |
| 표면 | `#ffffff` | `#1b202c` |
| 텍스트 | `#18181b` | `#f1f5f9` |
| 보조 텍스트 | `#52525b` | `#94a3b8` |
| 악센트 | `#9e5a03` (MDS gold.700) | `#ffc837` (MDS gold.300) |
| 2차 악센트 | `#eab308` (MDS yellow.500) | `#ffd166` (Dandelion Amber) |
| 구조선 | `#e4e4e7` | `#2c3547` |

`data-theme="architecture"` 한 속성으로 화면 전체가 전환된다.

## 고정 스케일

- 스페이스: 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64
- 반경: 4 / 6 / 8 (풀필 금지)
- 보더: 구조 2px, 지면 헤어라인 1px
- 그림자: `2px 2px 0` 단색(crisp), 블러 금지
- 타입: 64 / 36 / 24 / 16 / 12 / 10 (6단계 외 값 금지)

## 라이선스

- 색상 램프: Radix Colors — MIT
- 브랜드 역할값: `mindulle-design-system/packages/tokens`(정본)
