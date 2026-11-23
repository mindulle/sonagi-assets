# 골든 기준선

전체 SVG 바이트를 바꾸는 수정(30px 오프셋, 축 확장 등)에서 **회귀**와 **의도된 변경**을
구분하기 위한 스냅샷. 12블록 픽스처를 7스타일 × 3브레이크포인트 × 2테마 = 42렌더로 돌려
해시·높이·레이어 순서를 저장한다.

```bash
python3 scripts/golden_render.py             # 비교: 0=동일, 1=다름, 2=비교 범위 다름
python3 scripts/golden_render.py --update    # 의도된 변경일 때 기준선 갱신
python3 scripts/golden_render.py --styles editorial --breakpoints desktop
```

## 1. 구성

| 경로                                         | 역할                                                                           |
| -------------------------------------------- | ------------------------------------------------------------------------------ |
| `test_data/golden/all-blocks.md`             | 12블록 content.md 픽스처(배포 금지 문구 포함)                                  |
| `test_data/golden/catalog.json`              | 픽스처 자산 7개 — 아이콘 4 · 도판 3, 자체 제작 CC0                             |
| `test_data/golden/icons/` · `illustrations/` | 로컬 SVG. 경로는 저장소 루트 기준 상대 경로                                    |
| `test_data/golden/baseline.json`             | 18렌더의 `svg_sha256` · `manifest_sha256` · 바이트 · 캔버스 높이 · 레이어 순서 |
| `scripts/golden_render.py`                   | 렌더·비교                                                                      |
| `out/golden/`                                | 렌더 산출물(커밋하지 않음)                                                     |

픽스처 카탈로그만 쓰므로 devops의 7.2GB 라이브러리 없이 호스트에서 돌고,
CI에도 그대로 넣을 수 있다(ASSET-5). 스타일 7종은 렌더 경로를 갈라 놓는다.

| 스타일 | hero | features | 비고 |
| --- | --- | --- | --- |
| `editorial` | split | cards | 기준 |
| `brutalist` | center | cards | density 1.15 |
| `etching` | asymmetric | list | density 1.05 |
| `poster` | poster | cards | density 0.95 |
| `swiss` | split | columns | |
| `art-nouveau` | center | cards | 장식 축 |
| `minimal` | split | cards | density 0.92 |

## 2. 결과 읽는 법

| kind                | 의미                          | 대응                                       |
| ------------------- | ----------------------------- | ------------------------------------------ |
| `svg`               | SVG 바이트가 달라짐           | 렌더러·스타일 변경. 높이 delta를 함께 본다 |
| `manifest`          | SVG는 같고 입력 해시만 달라짐 | 스타일·토큰·카탈로그 파일 수정             |
| `layers`            | 블록·레이어 순서가 달라짐     | 블록 추가·순서 변경. 의도했는지 먼저 확인  |
| `added` / `removed` | 렌더 조합 자체가 달라짐       | `--styles`·`--breakpoints` 실수            |

높이 delta가 **블록 수 × 30px** 배수에 가까우면 30px 오프셋 수정이 반영된 것이다
(12블록이면 최대 약 330px). 0px인데 `svg`만 바뀌면 색·좌표 미세 변경이다.

## 3. CI

`.github/workflows/ci.yml`의 `determinism` 잡이 PR·main push마다 세 가지를 본다.

1. `golden_render.py` — 커밋된 기준선과 현재 코드가 같은가
2. `golden_render.py --update --baseline /tmp/...` 두 번 → JSON `diff` — 같은 입력 2회가
   같은가(결정론). 기준선 파일은 건드리지 않는다
3. `check_gaps.py out/golden --recursive` — 블록 겹침이 없는가

렌더 경로는 PyYAML만 쓰므로 CI에 Pillow·Chromium이 필요 없다. 42렌더 약 3초.

의도된 변경이면 로컬에서 `--update` 후 `baseline.json`을 같은 PR에 포함한다.
기준선을 갱신하지 않으면 CI가 실패하고, 어떤 조합이 얼마나 달라졌는지 출력한다.

간격 자체는 `scripts/check_gaps.py`가 본다. 렌더 결과의 블록 상·하단을 좌표에서
되살려 겹침을 찾고, `--max-gap`으로 리듬 상한을 건다.

```bash
python3 scripts/check_gaps.py out/golden --recursive            # 겹침만
python3 scripts/check_gaps.py out/sweep --recursive --max-gap 60
```

## 4. 한계

- 픽스처 카탈로그라 실제 Lucide·Tabler 자산 렌더를 대신하지 않는다. 자산 자체의
  회귀는 devops 카탈로그로 따로 확인한다.
- PDF·PNG·WebP는 대상이 아니다. SVG와 매니페스트만 비교한다(export 회귀는 별도).
- 기준선은 "지금 동작"의 스냅샷이지 "옳음"의 증명이 아니다. `--update`는 왜 바뀌었는지
  커밋 메시지에 남긴다.
