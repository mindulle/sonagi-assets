# recipes/

렌더 입력. **정본은 `blocks` 리스트**다.

| 파일                   | 스키마                | 용도                                  |
| ---------------------- | --------------------- | ------------------------------------- |
| `landing-hero.json`    | `blocks` (v1)         | 최소 예시 · 읽기 전용                 |
| `resp-v2.json`         | `blocks`              | 반응형 예시 · 읽기 전용               |
| `landing-hero-v2.json` | `content` 맵 (레거시) | 변환 경로 검증용 · **읽기 전용 동결** |

새 레시피는 손으로 쓰지 않는다.

```bash
python3 scripts/import_content.py content/<name>.md \
  --catalog catalog/catalog.json --out recipes/<name>.json
```

## 스키마 확인

```bash
python3 scripts/recipe_schema.py recipes/*.json
```

- `blocks`가 있으면 그대로 렌더한다.
- `content`가 블록 타입 맵이면 **순서를 유지한 채** `blocks`로 변환해 읽는다(레거시).
- `content`가 `{source, sha256}` 추적 정보뿐이면 블록이 없다는 오류를 낸다.

레거시 맵은 렌더는 되지만 새로 쓰지 않는다. 블록 순서·필드 검증은 `content.md` 경로가
더 강하다(`import_content.py`가 오타·누락·차단 자산을 먼저 잡는다).
