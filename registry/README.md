# Registry — 이름 대신 id

이 폴더는 손으로 고치지 않는다. `scripts/build_registry.py`가 만든다.

```bash
python3 scripts/build_registry.py          # 다시 쓰기
python3 scripts/build_registry.py --check  # 커밋된 명부와 현재 파일 비교 (CI)
```

## 왜

스타일 29종은 손으로 쓴 29장이 아니라 축 조합이다. 그래서 `victorian`이라는
이름만 보고는 어떤 팔레트·서체·기하인지 알 수 없고, 파일 내용이 바뀌어도
이름은 그대로다. 그래프가 `--style victorian`이라고 부르면 **어느 빅토리안**인지
기록에 남지 않는다.

`style_id`는 `<이름>@<축 병합이 끝난 스타일 해시 12>`다. 1px만 달라도 다른 id가
나오므로, 산출물 매니페스트의 `contract.style_id`와 이 명부를 맞대면 "이 SVG가
어느 스타일이었나"를 정확히 복원할 수 있다.

## 파일

| 파일          | 내용                                                    |
| ------------- | ------------------------------------------------------- |
| `styles.json` | `id` · `name` · `file` · `sha256` · `theme` · 선언된 축 |
| `blocks.json` | 렌더 가능한 12블록 `id`와 `order`                       |
| `rules.json`  | 판정 룰셋 `ruleset_version`과 룰 `id`/`severity`        |
| `index.json`  | `tokens_version` · `themes` · 개수 · 섹션 해시 · 중복 id · 레시피 참조 |

`index.json`의 `sections`는 나머지 세 파일 내용의 해시다. 명부 전체를 한 값으로
비교하고 싶을 때 쓴다.

## 소비 규칙

1. 그래프·스크립트는 스타일을 **이름이 아니라 `style_id`로** 기록한다.
   렌더는 여전히 `styles/<name>.json` 경로를 받는다.
2. 산출물 매니페스트의 `contract.style_id`가 명부에 없으면 그 스타일은
   명부 생성 이후에 생겼거나 이름이 바뀐 것이다. `--check`가 잡는다.
3. 룰을 고치면 `rules/ruleset.json`의 `version`을 올린다. `rules.json`과
   `contract.ruleset_version`이 함께 움직인다.
4. `tokens_version`이 바뀌면 팔레트가 바뀐 것이다. 판정 골든과 렌더 골든을
   둘 다 갱신해야 한다(`docs/GOLDEN.md`).

## 중복 id

두 스타일 파일이 같은 축 조합이면 같은 `style_id`가 나온다. `--check`는 이걸
실패로 본다. 별칭이 필요하면 파일을 복제하지 말고 이름을 바꾼다.
