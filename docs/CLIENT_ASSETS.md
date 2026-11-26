# 클라이언트 자산 인제스트

홈페이지 컴프에 쓸 **우리 사진·마크·목업**을 카탈로그에 넣는 경로.
공개 카탈로그는 UI 컴포넌트 13,011건·타이포 1,833건이 중심이라 사진·도판이
거의 없다. 클라이언트 자산은 별도 폴더에 두고 `origin=client`로 구분한다.

## 1. 폴더 구조

```
library/
└─ clients/
   └─ <brand>/
      └─ <category>/
         └─ <sha256>.<ext>       # id = 파일 내용 해시
catalog/
└─ catalog.json                  # items 끝에 append (기존 항목 수정 없음)
```

- `brand`·`category`는 소문자·숫자·하이픈만 쓴다. 예: `mindulle`, `brand-mark`, `photo`, `mockup`.
- 파일 이름은 복사 후 `sha256.<ext>`로 바뀐다. 카탈로그 `name`은
  `<brand>-<원본stem>-<ext>`이고, 같은 이름이 이미 있으면 `-<id 앞 8자리>`가 붙는다.
- 지원 형식은 `svg`, `png`, `jpg`, `jpeg`다. 렌더러가 슬롯에 넣을 수 없는
  `pdf`·`webp`·`ai`는 조용히 건너뛰고 요약의 `skipped_unsupported`에 센다.

## 2. 인제스트

```bash
# 계획만 본다(dry-run)
scripts/ingest_assets.sh --src ./photos --brand mindulle \
  --category photo --license owned

# 실제 복사 + 카탈로그 append
scripts/ingest_assets.sh --src ./photos --brand mindulle \
  --category photo --license owned --apply
```

| 옵션 | 기본 | 설명 |
| --- | --- | --- |
| `--src` | (필수) | 인제스트할 폴더. 하위 폴더 포함 |
| `--brand` | (필수) | 브랜드 슬러그 |
| `--category` | (필수) | 카테고리 슬러그 |
| `--license` | (필수) | `owned`(직접 보유) 또는 `given`(고객 제공) |
| `--kind` | `illustration` | `illustration` 또는 `icon`(icon은 SVG만) |
| `--catalog` | `catalog/catalog.json` | 카탈로그 경로 |
| `--library-root` | `library` | 라이브러리 루트 |
| `--apply` | 꺼짐 | 없으면 dry-run |

**id는 내용 해시다.** 같은 바이트는 파일 이름·경로가 달라도 같은 id가 되고,
같은 id가 이미 다른 브랜드/카테고리에 있으면 덮어쓰지 않고 실패한다.
한 번에 넣는 폴더 안에 바이트가 완전히 같은 파일이 둘 이상 있으면 1건만
등록하고 `skipped_duplicate`로 센다(예: dark/light 심볼 SVG가 같은 경우).
같은 폴더를 다시 돌리면 새 항목 0건으로 끝나고 카탈로그 바이트도 그대로다
(`generated_at`도 올리지 않는다).

## 3. 카탈로그 필드

새 항목은 기존 항목과 같은 키를 갖는다.

| 필드 | 클라이언트 자산 값 |
| --- | --- |
| `id` | 파일 내용 sha256 (64자리 hex) |
| `name` | `<brand>-<stem>-<ext>` (충돌 시 `-<id8>`) |
| `category` | `--category` 값 |
| `format` | `vector`(svg) / `raster`(png·jpg) |
| `license` | `owned` / `given` |
| `license_basis` | `client-owned` / `client-given` |
| `license_scope` | `public` |
| `origin` | `client` |
| `source` | `client:<brand>` |
| `kind` | `illustration` / `icon` |
| `tags` | `category:*`, `kind:*`, `format:*`, `license:*`, `origin:client`, `scope:public`, `src:client`, `set:client-<brand>`, `brand:<brand>` |
| `path` | `/app/data/clients/<brand>/<category>/<id>.<ext>` |
| `sha256` | `id`와 같음 |

`path`가 `/app/data/...`인 이유는 렌더러가 이 접두사를
`/srv/sonagi-assets/library/`로 바꾸기 때문이다. 로컬 라이브러리를 그대로
가리키면 devops에서 파일을 못 찾는다.

### 라이선스·scope

| license | scope | 의미 |
| --- | --- | --- |
| `owned` | `public` | 직접 보유. 계약 범위 안에서 결과물·팩에 사용 |
| `given` | `public` | 고객 제공. 재배포 범위는 계약서를 따른다 |
| `internal-only`·`commercial`·`personal` 등 | `blocked` | **인제스트 거부** |

`blocked` 자산은 클라이언트 팩에 절대 들어가지 않는다. 인제스트 스크립트가
`owned`/`given` 외의 라이선스를 받지 않고, 동기화 검증도 client 항목에
`license_scope=blocked`가 있으면 실패한다.

## 4. 선택 동작 (렌더러)

`scripts/render_recipe.py`에는 별도 "asset hint" 옵션이 없다.

1. 렌더러는 카탈로그 `items`를 `name`으로 인덱싱한다. 이름이 겹치면 먼저
   정렬된 항목이 이긴다.
2. 레시피의 `illustration`에 이름을 직접 적는 것이 유일한 지정 방법이다.
   예: `"illustration": ["mindulle-master-seal-light-svg"]`
3. `illustration`이 배열이면 스타일의 `illustration_set` 태그와 맞는 후보를
   먼저 고르고, 없으면 첫 후보를 쓴다. 클라이언트 자산은 `set:client-<brand>`
   태그를 갖지만, 스타일이 그 set을 지정하지 않는 한 첫 후보가 그대로 선택된다.

따라서 "우리 자산을 쓰게 한다"는 것은 **레시피에 그 이름을 쓰는 것**이다.
자동 선택 로직을 바꾸지 않는다.

## 5. devops 동기화

```bash
# 1) 원격 카탈로그 해시를 먼저 기록한다(덮어쓰기 사고 방지)
ssh devops 'sudo sha256sum /srv/sonagi-assets/catalog/catalog.json'

# 2) 파일 + 카탈로그를 올린다(--delete 없음)
scripts/sync_assets.sh --catalog catalog/catalog.json --library library \
  --expect-remote-catalog-sha <위에서_나온_해시> \
  --verify-render mindulle-master-seal-light-svg
```

스크립트가 하는 일:

1. `library/clients/`를 `devops:/srv/sonagi-assets/library/clients/`로 rsync
   (`--delete` 없음, `sudo rsync` 사용).
2. `catalog.json`을 `devops:/srv/sonagi-assets/catalog/catalog.json`으로 rsync.
3. 로컬·원격 클라이언트 파일 수가 같은지 확인.
4. 원격 카탈로그에 client 항목이 있고 blocked가 없는지 확인.
5. `--verify-render NAME`을 주면 원격 렌더러로 hero 한 장을 그려 매니페스트에
   그 이름이 실제로 들어갔는지(`license_ok=true`) 확인한다.

## 6. 롤백

인제스트가 카탈로그를 고칠 때 같은 폴더에
`catalog.json.bak-client-<UTC시각>` 백업을 남긴다.

```bash
# 카탈로그 되돌리기
cp catalog/catalog.json.bak-client-20261126T000000Z catalog/catalog.json

# 파일 되돌리기: 백업 이후에 추가된 id만 지운다
rm library/clients/<brand>/<category>/<id>.<ext>
```

원격은 같은 방식으로 백업을 올리거나, 이전 카탈로그를 다시 rsync한다.
`blocked` 자산이 섞였을 때도 같은 절차로 되돌린다.

## 7. 주의: DB 재생성

클라이언트 항목은 `catalog.json`에만 있다. `scripts/build_asset_catalog.py`는
`asset_hub.db`에서 카탈로그를 **새로 만들기** 때문에, 그대로 다시 돌리면
클라이언트 항목이 사라진다. 재생성 후에는 같은 폴더로 인제스트를 다시
실행하거나(파일 id가 같아 안전하다), 클라이언트 항목을 별도로 보존하는
마이그레이션을 먼저 만든다. DB에 직접 쓰지 않는 것은 의도된 선택이다.
