# 톤 태그 계획 (스카우트용)

2026-11-23. `asset_craft` 그래프의 레퍼런스 스카우트가 실카탈로그에서 오매칭을
일으킨 뒤, "톤을 수집하자"는 논의를 문서로 고정한다. **아직 실행 전이다** — 모델
엔드포인트와 이미지가 서로 다른 머신에 있다(§6).

## 1. 왜 필요한가

카탈로그 태그는 기계적으로 뽑을 수 있는 것만 있다.

```
topics: icon 12,694 · illustration 195 · color 89 · landscape 12 · botanical 5
kind:   asset 11,937 · glyph 3,001
```

"미니멀·따뜻·대담"은 미학 판단이라 빌드 스크립트가 만들 수 없고, 아무도 넣지
않았다. 그래서 스카우트는 `none`·`arch`·`rule` 같은 **조판 용어**를 이름에
부분 매칭해 `border-none`, `Archivo-Black`, `BigelowRules`를 골랐다.

톤 태그는 이 빈칸을 채운다. 단, **주제어 스카우트를 대체하지 않는다.** 톤은
"민들레 그림"을 찾아주지 않는다. 둘은 직교한다.

## 2. 택소노미 (초안 v0.1)

6개 축. 각 자산에 **최대 2개**만 붙인다(1개 권장). 다 붙이면 변별력이 사라진다.

| 키 | 뜻 | 예 | 반례 |
| --- | --- | --- | --- |
| `minimal` | 장식 최소, 여백 큼, 단색 위주 | 스위스 포스터, 선 아이콘 | 장식 테두리, 다색 일러스트 |
| `warm` | 따뜻한 색온도(황토·크림·테라코타) | 빈티지 도판, 크림 배경 | 순백·순흑, 차가운 블루 |
| `bold` | 큰 활자, 강한 대비, 굵은 선 | 브루탈리스트, 캡션 대문자 | 얇은 세리프, 파스텔 |
| `editorial` | 신문·잡지 조판, 세리프, 컬럼 | 에디토리얼 랜딩 | 앱 UI, 카드 그리드 |
| `ornate` | 장식 모티프, 곡선, 프레임 | 아르누보, 빅토리안 | 미니멀, 스위스 |
| `calm` | 낮은 채도, 넓은 여백, 느린 리듬 | 오션·포레스트 팔레트 | 네온, 고채도 |

택소노미는 **버전을 올려서만** 바꾼다(`taxonomy_version`). 정의를 고치면 기존
태그와 비교할 수 없다.

## 3. 스키마

`catalog.json` 항목에 두 필드를 더한다. 스키마 변경은 `build_asset_catalog.py`가
아니라 **별도 태깅 패스**가 담당한다(카탈로그 재빌드와 분리해야 재현이 쉽다).

```json
{
  "tones": ["editorial", "warm"],
  "tone_basis": {
    "taxonomy_version": "0.1",
    "method": "vision-model",
    "model": "<모델명>",
    "prompt_version": "tone-1",
    "reviewed_by": "human",
    "reviewed_at": "2026-11-24"
  }
}
```

- `tones`가 없으면 "미태깅"이다. 빈 배열과 구분한다(빈 배열 = "해당 없음").
- `tone_basis` 없는 `tones`는 **쓰지 않는다.** 이번에 토큰 출처를 문제 삼아
  정본화한 것과 같은 기준이다. 출처 없는 값은 근거가 아니다.

## 4. 대상

전체 14,938건이 아니라 **비아이콘부터**.

| 묶음 | 수 | 이유 |
| --- | --- | --- |
| illustration | 195 | 톤이 실제로 작동하는 유일한 규모 |
| texture·landscape 등 주제 태그 | ~30 | 수가 적어 수동 검수 가능 |
| icon | 12,694 | 톤보다 `outline/filled`·stroke·corner 같은 **측정 피처**가 유용 |

아이콘은 이 계획의 범위 밖이다. 필요하면 별도로 "피처 태깅"을 설계한다.

## 5. 스파이크와 합격 기준

1. **샘플 50건** — `sha256(id)` 정렬 상위 50. 무작위처럼 보이되 재현된다.
2. **태깅** — vision 모델에 썸네일 + 택소노미 정의를 주고 `tones` 2개 + 근거 1줄.
3. **검수** — 사람이 50건을 독립 채점.
4. **합격** — top-1 일치율 **≥ 80%**. 미달이면 프롬프트·택소노미를 고쳐 1회 재시도.
5. **확장** — 통과 시 비아이콘 전체(≈225건)에 적용하고 `tone_basis`를 채운다.

합격 기준을 못 넘으면 태깅을 접고, 스카우트는 주제어·역할 쿼터로만 간다.

## 6. 실행 환경 (현재 막힘)

| 요소 | 위치 |
| --- | --- |
| cliproxy(모델 API) | `llmops-instance` |
| 자산 이미지(7.2GB) | `devops:/srv/sonagi-assets/library` |
| 카탈로그 | `devops:/srv/sonagi-assets/catalog/catalog.json` |
| 스카우트 코드 | `sonagi-graph` |

이 머신에서는 `llmops-instance` SSH가 publickey로 거부되고 cliproxy도 닿지
않는다. 따라서 스파이크는 **llmops-instance에서 시작하는 세션**에서 돌려야 한다.

```bash
# 1) llmops에서 샘플 목록 뽑기
python3 - <<'PY'
import json, hashlib
items = json.load(open('/tmp/catalog-real.json'))['items']
targets = [i for i in items if i.get('kind') != 'glyph' and 'icon' not in (i.get('topics') or [])]
targets.sort(key=lambda i: hashlib.sha256(i['id'].encode()).hexdigest())
print(json.dumps(targets[:50], ensure_ascii=False, indent=2))
PY

# 2) devops에서 썸네일 50장 가져오기 (경로는 catalog.item.path 기준)
# 3) cliproxy로 태깅 → tones.json
# 4) 사람 검수 → agreement.json
```

## 7. 스카우트 통합 (태그가 생긴 뒤)

`craft.select_references`에 한 단계만 더한다.

| 신호 | 점수 |
| --- | --- |
| 주제어 매칭(현재) | 3 |
| 역할 쿼터(현재) | 유지 |
| `tones`가 브리프 톤과 교집합 | +2 (최대 1회) |
| `tone_basis` 없음 | 0 (태그 무시) |

톤은 **가산**이지 대체가 아니다. 주제어가 0인 자산이 톤만으로 1순위가 되면
다시 "엉뚱한 참조"로 돌아간다.

## 8. 위험

- **주관성** — 같은 자산을 두 사람이 다르게 태깅한다. 합격 기준을 사람 검수로 둔 이유.
- **드리프트** — 택소노미 정의를 고치면 기존 태그가 오염된다. 버전으로 막는다.
- **태그 인플레이션** — 6개를 다 붙이면 변별력이 사라진다. 최대 2개 규칙.
- **비용** — 225건이면 이미지 225장. 전체 15,000건으로 넓히지 않는다.
