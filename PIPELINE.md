# 레시피 파이프라인

`f(assets, recipe, seed) → layered SVG`

생성 AI 없이 보유 자산과 토큰만으로 화면을 만든다. 같은 레시피·시드는 항상 같은 바이트를
만들고, 결과 SVG는 `<g id>` 그룹으로 구성되어 Figma에서 레이어로 풀린다.

## 계약

| 항목     | 내용                                                                           |
| -------- | ------------------------------------------------------------------------------ |
| 입력     | `recipes/*.json` (블록·카피·자산 이름), `tokens/semantic.json`, `catalog.json` |
| 출력     | `<name>.svg`, `<name>.manifest.json`                                           |
| 결정성   | 동일 입력 → 동일 sha256 (세트 우선순위 lucide > tabler > phosphor 로 고정)     |
| 라이선스 | 참조 자산이 `scope:bundle`이 아니면 렌더 중단                                  |
| 레이어   | 최상위 `<g id>`: header·hero·cta·features·feature-N·footer·`icon-*`·`illo-*`       |

## 실행

```bash
python3 scripts/render_recipe.py \
  --recipe recipes/landing-hero.json \
  --catalog /srv/sonagi-assets/catalog/catalog.json \
  --tokens tokens/semantic.json \
  --out out/
```

## 스타일 팩

스킨은 레시피가 아니라 `styles/*.json`이 결정한다. 같은 레시피로 다른 스타일을 뽑는다.

| 스타일 팩              | 색                   | 기하     | 서체                    | 히어로         | 피처        |
| ---------------------- | -------------------- | -------- | ----------------------- | -------------- | ----------- |
| `editorial`            | 크림·잉크·앰버       | 2px, r8  | 나눔스퀘어              | split          | cards       |
| `brutalist`            | 순흑백               | 4px, r0  | Archivo·대문자          | center         | cards       |
| `minimal`              | 화이트·블루          | 1px, r4  | Archivo+나눔            | split          | cards       |
| `magazine`             | 크림·황토            | 1px, r0  | Gowun Batang            | **asymmetric** | **list**    |
| `swiss`                | 화이트·레드          | 2px, r0  | Archivo·대문자          | split          | **columns** |
| `poster`               | 다크·앰버            | 2px, r0  | Archivo                 | **poster**     | cards       |
| `sketch`               | 화이트·블랙          | 2px, r2  | Archivo                 | split          | list        |
| `etching`              | 아이보리·황토        | 1px, r0  | Gowun Batang            | asymmetric     | list        |
| `sonagi-blog`          | 웨더드 페이퍼·브론즈 | 1px, r10 | Cormorant·Noto Serif KR | split          | cards       |
| `art-nouveau`          | 파치먼트·올리브·금   | 1px, r26 | Cormorant·Gowun Batang  | center         | cards       |
| `victorian`            | 크림·적갈·금         | 2px, r2  | Cormorant·Gowun Batang  | center         | cards       |
| `terracotta-editorial` | 테라코타·크림        | 2px, r8  | Cormorant·Gowun Batang  | asymmetric     | list        |
| `newsprint-victorian`  | 뉴스프린트·먹        | 1px, r0  | Cormorant·Noto Serif KR | split          | list        |
| `mint-swiss`           | 민트·딥그린          | 2px, r0  | Archivo·대문자          | split          | columns     |
| `floral-editorial`     | 테라코타·크림        | 2px, r8  | Gowun Batang            | asymmetric     | list        |
| `deco-noir`            | 뉴스프린트·먹        | 4px, r0  | Archivo·대문자          | center         | cards       |
| `star-editorial`       | 민트·딥그린          | 1px, r4  | Archivo                 | split          | cards       |
| `arch-classic`         | 테라코타·크림        | 2px, r8  | Cormorant·Gowun Batang  | split          | cards       |
| `paper-editorial`      | 뉴스프린트·먹        | 1px, r0  | Cormorant·Noto Serif KR | split          | list        |
| `bead-editorial`       | 테라코타·크림        | 2px, r8  | Gowun Batang            | asymmetric     | list        |
| `hatch-editorial`      | 뉴스프린트·먹        | 1px, r0  | Archivo                 | split          | list        |
| `burgundy-victorian`   | 버건디·크림          | 2px, r2  | Cormorant·Gowun Batang  | split          | cards       |
| `ocean-swiss`          | 오션·스틸            | 2px, r0  | Archivo·대문자          | split          | columns     |
| `sand-editorial`       | 샌드·토프            | 2px, r8  | Gowun Batang            | asymmetric     | list        |
| `charcoal-brutal`      | 차콜·오프화이트      | 4px, r0  | Archivo·대문자          | center         | cards       |
| `lilac-editorial`      | 라일락·플럼          | 1px, r10 | Cormorant·Noto Serif KR | split          | cards       |
| `forest-paper`         | 포레스트·크림        | 1px, r4  | Gowun Batang            | split          | list        |

```bash
python3 scripts/render_recipe.py --recipe recipes/landing-hero.json \
  --style styles/magazine.json --catalog catalog/catalog.json \
  --tokens tokens/semantic.json --out out/
```

### 일러스트 선택

스타일 팩의 `illustration_set`이 그림체를 고정한다. 레시피는 후보 목록을 주고,
렌더러가 그 세트에 있는 후보를 고른다.

```json
{ "illustration_set": "opendoodles", "illustration": "mono" }
```

| 세트             | 라이선스 | 수  | 그림체        |
| ---------------- | -------- | --- | ------------- |
| `illlustrations` | MIT      | 133 | flat color    |
| `opendoodles`    | CC0      | 33  | line drawing  |
| `etchings`       | CC0(PD)  | 25  | 동판화 래스터 |

레시피: `"illustration": ["open-vault", "float", "<etching 이름>"]` → 스타일에 맞는 후보를 선택.

래스터(jpg/png)는 기본적으로 SVG에 base64로 임베드한다. 외부 참조가 없어 파일 단독으로
열리고 Figma 재임포트도 그대로 된다. `<image>`의 `href` 하나만 쓴다 — `xlink:href`를 함께
넣으면 같은 base64가 두 번 들어가 SVG가 정확히 2배가 된다(ASSET-3).

납품 용량이 문제면 링크 모드를 쓴다. 이미지를 내용 해시 이름으로 **1벌만** 쓰고 SVG는
상대 경로로 가리킨다.

```bash
render_recipe.py ... --raster-mode link      # out/assets/<sha12>.jpg + href="assets/..."
press render content.md --raster link
```

| 모드 | SVG | 납품 zip | Figma 재임포트 |
| --- | --- | --- | --- |
| `embed`(기본) | 이미지 포함, 단독 열림 | 큼 | 그대로 됨 |
| `link` | 경로만 | 이미지 1벌 | `svg/assets/`를 함께 열어야 함 |

- export는 상대 경로를 절대 `file:` URI로 바꿔 PDF·PNG를 굽고, `dist/assets/`로 복사한다
- bundle은 `svg/assets/`에 넣어 `svg/*.svg`의 상대 경로가 풀리게 한다
- 같은 이미지를 여러 번·여러 브레이크포인트에서 써도 파일은 하나다

| 임베드 폭     | SVG 크기(동판화 1장) | 용도                      |
| ------------- | -------------------- | ------------------------- |
| 1600px (원본) | 2.5MB                | 인쇄 원본 보관            |
| 1200px (기본) | 1.3MB                | Figma 임포트 권장 상한    |
| 900px         | 636KB                | 화면 시안·클라이언트 전달 |

```bash
render_recipe.py ... --embed-max-width 900
```

`--embed-max-width 0`이면 원본 그대로 넣는다.

### 레이아웃 문법

| 블록     | 변형                                                                                           |
| -------- | ---------------------------------------------------------------------------------------------- |
| hero     | `split`(좌우) · `center`(중앙) · `asymmetric`(이미지 우측 블리드) · `poster`(패널+전면 이미지) |
| features | `cards`(카드 3열) · `list`(번호+룰) · `columns`(상단 룰 3단)                                   |

`canvas.height`가 `"auto"`이거나 스타일 팩에 `auto_height: true`가 있으면
콘텐츠 높이에 맞춰 캔버스를 늘린다(magazine·poster가 사용).

한계: 블록 조합 자체(섹션 순서·개수)는 아직 레시피가 고정한다.

## press CLI

단일 진입점. 기존 스크립트를 감싸기만 하고 로직은 그대로 둔다.

```bash
press styles                                  # 축·스타일 목록
press check content/atelier-landing.md        # 검증만
press render content/atelier-landing.md --style etching --breakpoints desktop,mobile
press package --src out/press/dist --out delivery/x --name atelier --title "Atelier"
press preview --sheet --png
```

| 환경변수          | 기본                                      |
| ----------------- | ----------------------------------------- |
| `PRESS_CATALOG`   | `/srv/sonagi-assets/catalog/catalog.json` |
| `PRESS_TOKENS`    | `tokens/semantic.json`                    |
| `PRESS_FONTS_CSS` | `/home/ubuntu/brief/fonts/fonts.css`      |

`sonagi press ...`는 이 CLI에 인자를 그대로 넘긴다(`@sonagi/cli`, PRESS_BIN으로 경로 지정 가능).

## 레시피 형식

```json
{
    "name": "landing-hero",
    "seed": 7,
    "theme": "editorial",
    "canvas": { "width": 1440, "height": 1024 },
    "blocks": [
        { "type": "header", "brand": "...", "nav": ["..."] },
        {
            "type": "hero",
            "eyebrow": "...",
            "title": "...",
            "body": "...",
            "cta": "...",
            "ctaIcon": "arrow-right",
            "illustration": "open-vault"
        },
        {
            "type": "features",
            "title": "...",
            "items": [{ "icon": "...", "title": "...", "body": "..." }]
        },
        { "type": "footer", "left": "...", "right": "..." }
    ]
}
```

`blocks`가 정본이다. 파일은 손으로 쓰지 않고 `content.md` → `import_content.py`로 만든다.
레거시 파일 중 `content`가 블록 타입 맵인 형태는 로더가 **순서를 유지한 채** `blocks`로
변환해 읽는다(읽기 전용, 신규 작성 금지). `content`가 `{source, sha256}` 추적 정보뿐이면
"블록이 없습니다" 오류로 멈춘다.

```bash
python3 scripts/recipe_schema.py recipes/*.json        # 스키마·블록 요약
```

## 스타일 축

스타일은 **손으로 쓴 덩어리**가 아니라 축의 조합이다. 축 정의는 `styles/axes.json`.

```json
{
    "name": "terracotta-editorial",
    "theme": "editorial",
    "palette": "terracotta",
    "type": "cormorant-nouveau",
    "geometry": "r8b2",
    "layout": "asymmetric-list",
    "illustration": "mono",
    "illustration_set": "etchings"
}
```

| 축         | 정의 위치                | 예                              |
| ---------- | ------------------------ | ------------------------------- |
| `palette`  | `axes.palette[*].colors` | 14종                            |
| `type`     | `axes.type[*]`           | 11종 (서체·자간·배율·한글 서체) |
| `geometry` | `axes.geometry[*]`       | 9종 (반경·선 두께·그림자)       |
| `layout`   | `axes.layout[*]`         | 7종 (hero·features·header)      |

해석은 `scripts/style_axes.py`가 한다. 순서는 palette → type → geometry → layout →
스타일 파일의 명시 값(우선). 기존 형태(`colors`·`type` 객체를 직접 가진 파일)도 그대로 동작한다.

새 스타일 = 축 참조 5줄. 축을 늘리면 조합이 곱으로 늘어난다.

리팩터 검증: 기존 11종을 조합 형태로 바꾼 뒤 같은 입력으로 렌더해 **11종 SVG 해시가 모두 동일**했다.

로고·브랜딩 납품은 `docs/IDENTITY_DELIVERY.md` 참조. 저작은 VectorCraft/DesignCraft,
시스템화·export는 이 파이프라인이 맡는다.

## 장식(ornament)

장식도 축이다. `styles/axes.json`의 `ornament` 항목이 `{motif, frame, weight, height}`를 정의하고,
스타일은 이름으로 참조하거나 객체로 덮어쓴다.

| 이름        | 구분선                       | 테두리                    |
| ----------- | ---------------------------- | ------------------------- |
| `none`      | 없음                         | 없음                      |
| `rule`      | 얇은 단일 선                 | 단일 선                   |
| `star`      | 중앙 8방 광선 + 선           | 이중 사각                 |
| `arch`      | 낮은 아치 + 양 끝 점         | 모서리 틱 사각            |
| `trellis`   | 마름모 반복                  | 모서리 틱 사각            |
| `wave`      | 폭에 맞춰 늘어나는 사인 곡선 | 없음                      |
| `bead`      | 마름모 반복                  | 얇은 사각 + 위아래 비드   |
| `nouveau`   | 곡선 줄기 + 봉오리           | 이중 가는 선 + 모서리 컬  |
| `victorian` | 굵은/가는 이중 괘선 + 로제트 | 이중 괘선 + 모서리 브래킷 |
| `deco`      | 전폭 직선 + 마름모           | 이중 직선                 |
| `floral`    | 잎 두 장 + 줄기              | 단일 선                   |

```json
{ "ornament": "floral" }
{ "ornament": { "motif": "nouveau", "frame": "nouveau", "weight": 1.6 } }
```

- `weight`는 선 두께 배율이다(1.0이면 원본).
- `height`는 구분선이 차지하는 세로 여백이다.
- `offset`은 선을 아래로 내리는 값이다(아치처럼 위로 솟는 모티프가 앞 블록을 침범하지 않게).
- `repeat` 대신 `grid`를 주면 2차원으로 반복한다: `{cols, rows, x, y}`에 표현식을 쓰고
  `col`·`row` 변수를 받는다.

### 배경 패턴과 Figma

배경 패턴은 두 가지로 그린다. `styles/ornaments.json`의 `background`에 있고, 스타일이 이름으로 고른다.

| 이름 | 방식 | 1440×3117 SVG |
| --- | --- | --- |
| `dots` · `hatch` | SVG `<pattern>` 타일 | 0.2~0.3KB |
| `dots-lines` · `hatch-lines` | 선·원 그리드(개별 요소) | 181~584KB |

**Figma는 `<pattern>` 채우기를 버린다**(2026-11-23 실측, ASSET-7). Figma에 드래그하면 패턴 사각형이
빈 상태로 들어오고, 선 기반 폴백만 남는다. 그래서 렌더 옵션으로 고른다.

```bash
render_recipe.py ... --pattern-mode tile   # 기본. 작지만 Figma에서 사라짐
render_recipe.py ... --pattern-mode line   # Figma 안전. 같은 페이지가 168KB → 943KB
press render content.md --pattern line
```

`tile` 모드로 패턴이 있는 스타일을 렌더하면 stderr에 안내가 한 줄 나온다.
- 장식 축에 `background`를 넣으면 본문 뒤에 패턴을 깐다(`dots`, `hatch`).
- 반복이 많으면 `pattern` 요소로 타일 한 장을 정의한다. `{el: "pattern", id, attrs, elements, rect}`.
  실측(1440×2400): `hatch` 0.3KB vs `hatch-lines` 447KB, `dots` 0.2KB vs `dots-lines` 141KB.
- Figma 재임포트에서 `pattern` 채우기가 다르게 보일 수 있어 선 기반 대체 축(`paper-lines`, `hatch-lines`)을 둔다.
- 모티프는 **데이터**다. `styles/ornaments.json`에 SVG 요소 목록을 추가하고 `axes.json`에 이름만 등록하면 끝난다.
  렌더러 코드는 건드리지 않는다.
- 요소는 `{el, attrs, repeat?, elements?}` 형태다. `repeat`는 변수 묶음 반복(모서리 4곳, 좌우 대칭),
  `elements`는 그 묶음 안에서 여러 요소를 순서대로 그린다.
- 좌표는 `{x1 + (cx - x1) * 0.35:.1f}` 같은 **표현식 템플릿**이다. 사칙연산·변수만 허용하고
  `ast`로 검사한다(함수 호출·속성 접근 불가).
- 색은 스타일 `accent`를 쓰므로 다크 변환도 자동이다.
- 모바일 프레임 여백은 8px로 줄여 본문(20px)과 겹치지 않게 한다.

미리보기(좌표를 고칠 때):

```bash
python3 scripts/preview_ornament.py --sheet --png          # 전체 시트
python3 scripts/preview_ornament.py --motif floral --frame plain --png
```

결과는 `previews/`에 남고 git에는 넣지 않는다.

리팩터 검증: 장식을 축으로 바꾸고, 이어서 데이터(ornaments.json)로 옮긴 뒤에도 기존 11종 SVG 해시가 모두 동일했다.

## 콘텐츠 임포터

화면의 문장과 배치를 분리한다. 규격은 `CONTENT_FORMAT.md`.

```markdown
## hero

title: 종이 위에 남는
풍경
cta: 컬렉션 보기
```

```bash
python3 scripts/import_content.py content/atelier-landing.md \
  --catalog catalog/catalog.json --out recipes/atelier-landing.json
```

| 검사                            | 결과                  |
| ------------------------------- | --------------------- |
| 없는 타입·필드(오타)            | 오류 + 유사 이름 제안 |
| 필수 필드 누락                  | 오류                  |
| 목록 수 초과                    | 오류                  |
| 카탈로그에 없는 아이콘·일러스트 | 오류 + 유사 이름 제안 |
| `scope`가 `bundle` 아님         | 오류                  |
| 문장 길이 초과                  | 경고                  |
| 들여쓴 필드(`  cta: ...`)       | 경고 + 필드로 처리    |
| `hero.illustration` 한 줄 표기  | 경고 + 목록으로 변환  |

지원 블록 12종: header · hero · stats · features · logos · quote · faq · cta · footer ·
table · pricing · gallery.

렌더 단계에서 터지던 `asset not found`·`asset blocked`를 **임포트 단계로 앞당긴다**.
생성된 레시피는 `content.source`·`content.sha256`으로 원본을 추적한다.

같은 `content.md`로 스타일만 바꿔 뽑는 것이 목적이다.

## 블록 배치 규약

블록 사이 세로 간격은 **호출부가 소유**한다. 블록 메서드는 `top`을 받아 그 자리에서
그리고, 자기 내용이 끝나는 높이만 돌려준다. 여백을 블록이 직접 만들지 않는다.

```
top = y + BLOCK_GAP          # BLOCK_GAP = 44
svg, height = render_block(kind, block, W, top)
y = top + height             # 다음 블록의 기준선
```

- `header`는 페이지 최상단 고정 좌표를 쓰고 `header_height()`(88 / 모바일 70)를 돌려준다.
- `footer`는 `footer_height()`(46 / 모바일 58)를 쓰고 페이지를 닫는다.
- 장식 구분선(`ornament_divider`)은 블록 사이에 **자기 자리**를 차지한다:
  앞뒤로 `BLOCK_GAP`을 두고 `height + offset`만큼 소비한다.
- 블록 높이는 그린 요소의 실제 하단이다. 카드·표처럼 상자가 있으면 상자 하단,
  글자로 끝나면 baseline + descender다. "느낌상 여백"을 높이에 넣지 않는다.

고치기 전에는 모든 블록이 `y + 30`으로 호출되면서 반환 높이가 30을 보정하지 않아
섹션 간격이 블록마다 어긋났다(ASSET-2). 검수는 `scripts/check_gaps.py`로 한다.

```bash
python3 scripts/check_gaps.py out/golden --recursive        # 겹침만 본다
python3 scripts/check_gaps.py out/sweep --recursive --max-gap 60
```

```bash
for s in editorial brutalist minimal magazine swiss poster sketch etching sonagi-blog art-nouveau victorian terracotta-editorial newsprint-victorian mint-swiss floral-editorial deco-noir star-editorial arch-classic paper-editorial bead-editorial hatch-editorial burgundy-victorian ocean-swiss sand-editorial charcoal-brutal lilac-editorial forest-paper; do
  render_recipe.py --recipe recipes/atelier-landing.json --style styles/$s.json ...
done
```

## 자산 삽입 규칙

- 아이콘: 원본 SVG의 `stroke="currentColor"`를 현재 텍스트 색으로 치환, 24 그리드 기준 스케일
- 일러스트: 중첩 `<svg viewBox>`로 배치(`preserveAspectRatio="slice"`)
- Illustrator의 `.stN{}` 클래스는 **속성으로 인라인**한다. `<style>`을 그대로 두면 여러
  일러스트가 섞일 때 클래스가 충돌하고, 지우면 색이 사라진다
- 원본 `id`는 제거해 레이어 이름 충돌을 막는다

## 매니페스트

```json
{
    "recipe": "landing-hero",
    "seed": 7,
    "theme": "editorial",
    "sha256": "...",
    "layers": ["header", "hero", "..."],
    "assets": [
        { "name": "open-vault", "kind": "illustration", "license": "mit", "scope": "bundle" }
    ],
    "license_ok": true
}
```

납품 시 매니페스트를 함께 보내면 "이 결과물에 무엇이 들어갔는지"가 자동으로 증명된다.

## 출처(origin)와 사용 범위

라이선스는 "무엇을 해도 되는가", 출처는 "어디서 왔는가"다. 둘을 분리해 태그한다.

| origin          | 뜻                   | 기본 scope      | 쓰이는 곳                 |
| --------------- | -------------------- | --------------- | ------------------------- |
| `open-source`   | OFL·MIT·ISC·Apache   | bundle          | 폰트·아이콘·오픈 일러스트 |
| `public-domain` | CC0·PD               | bundle          | 박물관 이미지·동판화      |
| `in-house`      | 자체 제작            | bundle          | 직접 만든 컴포넌트·레시피 |
| `freeware`      | 무료지만 재배포 제한 | output          | KOTRA·롯데마트 등         |
| `generated`     | AI 생성·합성         | **output 강제** | 히어로 삽화 등 1회성      |
| `commercial`    | 유료 라이선스        | blocked         | 구매 전 사용 금지         |
| `unknown`       | 출처 불명            | blocked         | 납품·판매 금지            |

### 어디에 쓰이는가

| 산출물                            | 사용 가능 origin                       |
| --------------------------------- | -------------------------------------- |
| **판매용 에셋 팩** (파일 재배포)  | open-source · public-domain · in-house |
| **클라이언트 납품물** (화면·인쇄) | 위 + freeware · generated(고지)        |
| **내부 작업**                     | 전부(commercial 제외)                  |
| **재배포 금지 계약**              | above minus generated                  |

납품 시 `render_recipe.py`가 `<name>-CREDITS.md`를 자동 생성한다.
`origin:generated` 자산은 등록 단계에서 `scope:output`이 강제되므로 판매 팩에 들어갈 수 없다.

```bash
# AI 생성 자산을 등록할 때
sudo python3 scripts/import_image_pack.py ... \
  --origin generated --license generated --apply
```

### 생성 메타데이터

AI 생성 자산은 모델·프롬프트·생성일을 `items.annotation`에 남긴다.
CREDITS의 "생성 정보" 절에 그대로 출력된다.

```bash
# 파일별 프롬프트가 다르면 meta-json으로 넘긴다
sudo python3 scripts/import_image_pack.py ... --origin generated \
  --meta-json /tmp/gen-ai/meta.json --apply

# 이미 등록된 자산의 메타데이터만 고칠 때
sudo python3 scripts/import_image_pack.py ... --origin generated \
  --meta-json /tmp/gen-ai/meta.json --refresh-meta --apply
```

```json
{
    "ai-archive-drawer": {
        "model": "gemini-3.1-flash-image",
        "prompt": "flat vector editorial illustration, wooden archive drawer ...",
        "generated_at": "2026-11-22T18:13:00Z"
    }
}
```

### 구현 규칙

| 지점                     | 규칙                                                                                            |
| ------------------------ | ----------------------------------------------------------------------------------------------- |
| `license_policy.py`      | `generated` → `output` (파일 재배포 금지)                                                       |
| `import_image_pack.py`   | `--origin generated`면 `scope:bundle`을 붙이지 않는다                                           |
| `build_asset_catalog.py` | scope 태그가 충돌하면 `bundle < output < blocked` 순으로 보수 판정, generated는 무조건 `output` |
| `render_recipe.py`       | `blocked`만 중단. `output`은 결과물에 허용하고 `output_only`로 매니페스트·CREDITS에 남긴다      |
| `import_content.py`      | `output` 자산은 경고("에셋 팩에 넣을 수 없습니다"), `blocked`는 오류                            |

`scope:bundle`과 `scope:output`이 동시에 붙으면 카탈로그가 알파벳 순으로 `bundle`을
먼저 집어 AI 자산을 판매 가능으로 승격시키는 버그가 있었다. 지금은 태그를 붙이지 않고,
카탈로그도 보수적으로 판정한다.

## 섹션 자동 구성과 베리에이션

레시피 v2는 `content`(재료)만 주고, `compose_sections.py`가 섹션 조합을 샘플링한다.

```bash
python3 scripts/compose_sections.py --recipe recipes/landing-hero-v2.json \
  --style styles/etching.json --catalog catalog/catalog.json \
  --tokens tokens/semantic.json --variants 6 --seed 7 --out variants/
```

- 섹션: `header` · `hero` · `stats` · `quote` · `logos` · `features` · `faq` · `cta` · `footer`
- 문법: `features` 필수, 증거 섹션(stats/quote/logos) 중 1개 이상, 증거 섹션 연속 금지
- 점수: 섹션 수·증거 유무·서사 순서 가중, 6개 이상이면 감점
- 같은 `seed`면 같은 6종이 나온다

| 산출                   | 내용                  |
| ---------------------- | --------------------- |
| `<name>-vN.svg`        | 조합별 결과           |
| `<name>-vN-CREDITS.md` | 자산 출처             |
| `variants.json`        | 조합·점수·sha256 목록 |

고른 1종은 `blocks` 레시피로 동결하면 이후 결정론적으로 재생된다.

## 반응형

같은 레시피를 `--breakpoint`로 3개 캔버스에 렌더한다.

```bash
render_recipe.py --recipe recipes/resp-v2.json --breakpoint desktop   # 1440
render_recipe.py ... --breakpoint tablet                               # 768
render_recipe.py ... --breakpoint mobile                               # 390
```

| 블록                 | mobile 재배치                                                    |
| -------------------- | ---------------------------------------------------------------- |
| header               | 브랜드만, 내비 숨김                                              |
| hero (mobile·tablet) | 텍스트 → 일러스트 → 풀폭 CTA (tablet은 더 큰 활자·가로형 이미지) |
| stats                | 세로 스택                                                        |
| features             | 아이콘 + 제목 + 본문 리스트                                      |
| logos                | 2열                                                              |
| cta                  | 카드 안 세로 배치                                                |
| footer               | 2줄 스택                                                         |

여백은 breakpoint별로 56/32/20, 본문 스케일은 1.0/0.88/0.72를 쓴다.

## 납품 export (PDF·PNG·WebP)

렌더된 SVG를 화면(브레이크포인트)별로 내보낸다.

```bash
python3 scripts/export_recipe.py --src out/ --pattern '*.svg' --out dist/ \
  --formats pdf,png,webp --scale 2 --fonts-css fonts/fonts.css
```

| 형식 | 내용                                       |
| ---- | ------------------------------------------ |
| PDF  | 화면당 1페이지, 폰트 임베드(Chromium 인쇄) |
| PNG  | `@2x` (예: 1440×2293 → 2880×4586)          |
| WebP | PNG에서 변환                               |

- 같은 폴더의 `*.manifest.json`을 읽어 **출처 게이트**를 통과해야 한다
  (`origin:commercial` 자산이 있으면 중단)
- 페이지 크기가 다른 캔버스를 한 PDF에 넣으면 Chromium이 한 크기로 합치므로
  **화면별 PDF를 따로 만든다**
- `export.json`에 파일 목록·해시·게이트 결과를 남긴다

전제: Chromium, Pillow. snap Chromium은 `/tmp`과 숨김 폴더를 읽지 못하므로
임시 HTML은 출력 폴더 아래에 만든다.

## 납품 번들

```bash
python3 scripts/bundle_delivery.py --src dist --out delivery/landing-v2 \
  --name "Atelier Landing v2" --zip
```

```
delivery/landing-v2/
├─ index.html      스크린별 미리보기 + 다운로드 링크
├─ svg/ pdf/ png/ webp/
├─ CREDITS.md      자산 출처·고지 통합
├─ export.json     해시·게이트 결과
└─ README.md
```

- 화면(SVG)이 있는 항목만 번들에 포함한다(중간 산출물 제외)
- zip은 폴더 루트를 포함해 풀었을 때 구조가 유지된다

## 인쇄 (별도 경로)

화면용 export와 섞지 않는다. 색 재현이 다르기 때문이다.

```
SVG ──조판(도련+재단선)──▶ Chromium PDF(RGB) ──Ghostscript──▶ CMYK PDF
```

```bash
press print --src out/brandsheet --trim 210x297 --bleed 3 --slug 5
press print --src out/brandsheet/01-cover.svg --check     # 조판만 검사
```

| 항목 | 기본값 | 설명 |
| --- | --- | --- |
| `--trim` | `210x297` | 재단 크기(mm). 원본 비율과 1% 넘게 다르면 중단 |
| `--bleed` | `3` | 도련. 배경색을 도련까지 깐다 |
| `--slug` | `5` | 재단선 바깥 여백. 모서리에 재단선 8개 |
| `--icc` | 없음 | 출력 ICC 지정(있으면 `-dOverrideICC`) |

- 페이지 크기 = 재단 + 2 × (도련 + 여백) → A4면 **226×313mm**
- 검증: 페이지 mm, 내용 스트림 색 연산자(`k`/`K`=CMYK, `rg`/`RG`=RGB), 임베드 래스터 실효 dpi
- 결정론: Ghostscript 출력의 생성 시각·ID를 고정값으로 바꿔 2회 실행 해시 동일
- 래스터는 `--embed-max-width`로 줄인 뒤 들어간다. 인쇄 전 300dpi 이상인지 확인한다
  (`raster_dpi_min` < 300이면 실패로 표시)

**한계**: PDF/X·별색(Pantone) 미지원. ICC를 지정하지 않으면 Ghostscript 기본 CMYK 변환이다.
색 교정이 필요하면 `--icc`로 프로파일을 넣고, 별색은 인쇄소와 직접 맞춘다.

## 다크 테마

`dark: true`(레시피) 또는 `--dark`(CLI)로 같은 레시피를 다크로 렌더한다.

```bash
render_recipe.py --recipe recipes/studio-plan-dark.json --style styles/swiss.json ...
```

- 스타일 팩의 라이트 hex를 **역할별 밝기**로 변환한다(hue 유지, 액센트 66%)
- 검정 액센트(브루탈리스트·스케치)는 흰색이 된다
- `accent-ink`는 액센트 휘도로 계산해 자동 대비
- 매니페스트에 `dark: true`가 기록된다

검증된 대비(8종): 본문 17.2–17.7 · 보조 11.4–11.7 · 흐린 글자 7.1–7.4 · 액센트 위 글자 5.9–17.4.
보더는 장식이라 1.9–2.1로 낮다(정보 전달에 쓰지 않는다).

주의: 래스터 일러스트는 다크에서도 밝다. 또 `height="auto"` 캔버스에서 배경 사각형이
`height="auto"`로 나가던 버그를 이 작업에서 고쳤다(이전에는 배경이 투명했다).

## 결정론

같은 입력이면 바이트까지 같은 산출물이 나온다.

| 산출물       | 고정 방법                                                       |
| ------------ | --------------------------------------------------------------- |
| SVG·manifest | 입력 해시(recipe·style·tokens·catalog) 기록, 경로 대신 파일명   |
| PDF          | pypdf로 `CreationDate`/`ModDate` 고정, `/ID`를 내용 해시로 교체 |
| PNG·WebP     | Chromium·Pillow 출력이 이미 결정론적                            |
| ZIP          | 항목 타임스탬프 `1980-01-01`, 정렬된 순서, 권한 고정            |

검증(같은 디렉터리 이름으로 두 번 실행):

```
svg    c2fcad7f0abebb98  c2fcad7f0abebb98
mani   c230eedfa2e003e8  c230eedfa2e003e8
pdf    88fa08b4ec1279c4  88fa08b4ec1279c4
png    67a8f094b87052ab  67a8f094b87052ab
webp   f24b8c2874b17f0e  f24b8c2874b17f0e
zip    0db8ff6aecb32b39  0db8ff6aecb32b39
```

주의: `export.json`에 절대 경로를 넣으면 실행 위치마다 해시가 달라진다.
번들 이름(`--name`)과 출력 폴더명은 zip 안 경로에 들어가므로 같아야 한다.

## 빌드업 타임랩스

레이어 조립 과정을 프레임으로 남긴다. 사람의 붓질 기록(스피드 페인팅)과는 다르다.

```bash
python3 scripts/animate_recipe.py --recipe recipes/landing-hero.json \
  --style styles/etching.json --catalog catalog/catalog.json \
  --tokens tokens/semantic.json --out frames/ --height 1350
```

- 프레임: 배경 → 헤더 → 히어로 → 피처(1·2·3) → 푸터 (7장)
- SVG를 PNG로 래스터화한 뒤 ffmpeg로 묶는다
- 고정 높이(`--height`)를 주면 프레임마다 캔버스가 흔들리지 않는다

```bash
ffmpeg -f concat -safe 0 -i frames/list.txt -vf "fps=24,format=yuv420p" \
  -c:v libx264 -crf 19 build-up.mp4
```

## Figma 재임포트

- 그룹 구조 유지: `<g id="hero">` → Frame/Group `hero`
- 텍스트는 `<text>`로 남으므로 편집 가능. 단 폰트가 설치돼 있어야 한다
- 외부 참조(`href`·`<image>`)가 없어 파일 단독으로 열린다
