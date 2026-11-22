# Design tokens

브랜드 시각 언어(`mindulle-visual-style`)를 코드 토큰으로 옮긴 결과물. 직접 수정하지 말고
`scripts/build_design_tokens.py`로 다시 생성한다.

```bash
python3 scripts/build_design_tokens.py \
  --radix node_modules/@radix-ui/colors \
  --out tokens
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
| 배경 | `#fbf9f5` | `#060911` |
| 표면 | `#ffffff` | `#090d16` |
| 텍스트 | `#161616` | `#ffffff` |
| 보조 텍스트 | `#3a3a36` | `#c9d1d9` |
| 악센트 | `#d97706` (Dandelion Gold) | `#4a90e2` (Sonagi Rain) |
| 2차 악센트 | `#f59e0b` | `#ffd166` (Dandelion Amber) |
| 구조선 | `#dcd7cc` | `#30363d` |

`data-theme="architecture"` 한 속성으로 화면 전체가 전환된다.

## 고정 스케일

- 스페이스: 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64
- 반경: 4 / 6 / 8 (풀필 금지)
- 보더: 구조 2px, 지면 헤어라인 1px
- 그림자: `2px 2px 0` 단색(crisp), 블러 금지
- 타입: 64 / 36 / 24 / 16 / 12 / 10 (6단계 외 값 금지)

## 라이선스

- 색상 램프: Radix Colors — MIT
- 브랜드 역할값·타입 스케일: 사내 SSOT (`mindulle-visual-style`)
