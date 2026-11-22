# 레시피 파이프라인

`f(assets, recipe, seed) → layered SVG`

생성 AI 없이 보유 자산과 토큰만으로 화면을 만든다. 같은 레시피·시드는 항상 같은 바이트를
만들고, 결과 SVG는 `<g id>` 그룹으로 구성되어 Figma에서 레이어로 풀린다.

## 계약

| 항목 | 내용 |
| --- | --- |
| 입력 | `recipes/*.json` (블록·카피·자산 이름), `tokens/semantic.json`, `catalog.json` |
| 출력 | `<name>.svg`, `<name>.manifest.json` |
| 결정성 | 동일 입력 → 동일 sha256 (세트 우선순위 lucide > tabler > phosphor 로 고정) |
| 라이선스 | 참조 자산이 `scope:bundle`이 아니면 렌더 중단 |
| 레이어 | 최상위 `<g id>`: header·hero·cta·features·feature-N·footer·icon-*·illo-* |

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

| 스타일 팩 | 색 | 기하 | 서체 | 히어로 | 피처 |
| --- | --- | --- | --- | --- | --- |
| `editorial` | 크림·잉크·앰버 | 2px, r8 | 나눔스퀘어 | split | cards |
| `brutalist` | 순흑백 | 4px, r0 | Archivo·대문자 | center | cards |
| `minimal` | 화이트·블루 | 1px, r4 | Archivo+나눔 | split | cards |
| `magazine` | 크림·황토 | 1px, r0 | Gowun Batang | **asymmetric** | **list** |
| `swiss` | 화이트·레드 | 2px, r0 | Archivo·대문자 | split | **columns** |
| `poster` | 다크·앰버 | 2px, r0 | Archivo | **poster** | cards |
| `sketch` | 화이트·블랙 | 2px, r2 | Archivo | split | list |
| `etching` | 아이보리·황토 | 1px, r0 | Gowun Batang | asymmetric | list |

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

| 세트 | 라이선스 | 수 | 그림체 |
| --- | --- | --- | --- |
| `illlustrations` | MIT | 133 | flat color |
| `opendoodles` | CC0 | 33 | line drawing |
| `etchings` | CC0(PD) | 25 | 동판화 래스터 |

레시피: `"illustration": ["open-vault", "float", "<etching 이름>"]` → 스타일에 맞는 후보를 선택.

래스터(jpg/png)는 SVG에 base64로 임베드한다. 외부 참조가 없어 파일 단독으로 열린다.

| 임베드 폭 | SVG 크기(동판화 1장) | 용도 |
| --- | --- | --- |
| 1600px (원본) | 2.5MB | 인쇄 원본 보관 |
| 1200px (기본) | 1.3MB | Figma 임포트 권장 상한 |
| 900px | 636KB | 화면 시안·클라이언트 전달 |

```bash
render_recipe.py ... --embed-max-width 900
```

`--embed-max-width 0`이면 원본 그대로 넣는다.

### 레이아웃 문법

| 블록 | 변형 |
| --- | --- |
| hero | `split`(좌우) · `center`(중앙) · `asymmetric`(이미지 우측 블리드) · `poster`(패널+전면 이미지) |
| features | `cards`(카드 3열) · `list`(번호+룰) · `columns`(상단 룰 3단) |

`canvas.height`가 `"auto"`이거나 스타일 팩에 `auto_height: true`가 있으면
콘텐츠 높이에 맞춰 캔버스를 늘린다(magazine·poster가 사용).

한계: 블록 조합 자체(섹션 순서·개수)는 아직 레시피가 고정한다.

## 레시피 형식

```json
{
  "name": "landing-hero",
  "seed": 7,
  "theme": "editorial",
  "canvas": { "width": 1440, "height": 1024 },
  "blocks": [
    { "type": "header", "brand": "...", "nav": ["..."] },
    { "type": "hero", "eyebrow": "...", "title": "...", "body": "...",
      "cta": "...", "ctaIcon": "arrow-right", "illustration": "open-vault" },
    { "type": "features", "title": "...", "items": [{ "icon": "...", "title": "...", "body": "..." }] },
    { "type": "footer", "left": "...", "right": "..." }
  ]
}
```

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

| 검사 | 결과 |
| --- | --- |
| 없는 타입·필드(오타) | 오류 + 유사 이름 제안 |
| 필수 필드 누락 | 오류 |
| 목록 수 초과 | 오류 |
| 카탈로그에 없는 아이콘·일러스트 | 오류 + 유사 이름 제안 |
| `scope`가 `bundle` 아님 | 오류 |
| 문장 길이 초과 | 경고 |

지원 블록 12종: header · hero · stats · features · logos · quote · faq · cta · footer ·
table · pricing · gallery.

렌더 단계에서 터지던 `asset not found`·`asset blocked`를 **임포트 단계로 앞당긴다**.
생성된 레시피는 `content.source`·`content.sha256`으로 원본을 추적한다.

같은 `content.md`로 스타일만 바꿔 뽑는 것이 목적이다.

```bash
for s in editorial brutalist minimal magazine swiss poster sketch etching; do
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
{ "recipe": "landing-hero", "seed": 7, "theme": "editorial",
  "sha256": "...", "layers": ["header", "hero", "..."],
  "assets": [{ "name": "open-vault", "kind": "illustration", "license": "mit", "scope": "bundle" }],
  "license_ok": true }
```

납품 시 매니페스트를 함께 보내면 "이 결과물에 무엇이 들어갔는지"가 자동으로 증명된다.

## 출처(origin)와 사용 범위

라이선스는 "무엇을 해도 되는가", 출처는 "어디서 왔는가"다. 둘을 분리해 태그한다.

| origin | 뜻 | 기본 scope | 쓰이는 곳 |
| --- | --- | --- | --- |
| `open-source` | OFL·MIT·ISC·Apache | bundle | 폰트·아이콘·오픈 일러스트 |
| `public-domain` | CC0·PD | bundle | 박물관 이미지·동판화 |
| `in-house` | 자체 제작 | bundle | 직접 만든 컴포넌트·레시피 |
| `freeware` | 무료지만 재배포 제한 | output | KOTRA·롯데마트 등 |
| `generated` | AI 생성·합성 | **output 강제** | 히어로 삽화 등 1회성 |
| `commercial` | 유료 라이선스 | blocked | 구매 전 사용 금지 |
| `unknown` | 출처 불명 | blocked | 납품·판매 금지 |

### 어디에 쓰이는가

| 산출물 | 사용 가능 origin |
| --- | --- |
| **판매용 에셋 팩** (파일 재배포) | open-source · public-domain · in-house |
| **클라이언트 납품물** (화면·인쇄) | 위 + freeware · generated(고지) |
| **내부 작업** | 전부(commercial 제외) |
| **재배포 금지 계약** | above minus generated |

납품 시 `render_recipe.py`가 `<name>-CREDITS.md`를 자동 생성한다.
`origin:generated` 자산은 등록 단계에서 `scope:output`이 강제되므로 판매 팩에 들어갈 수 없다.

```bash
# AI 생성 자산을 등록할 때
sudo python3 scripts/import_image_pack.py ... \
  --origin generated --license generated --apply
```

### 구현 규칙

| 지점 | 규칙 |
| --- | --- |
| `license_policy.py` | `generated` → `output` (파일 재배포 금지) |
| `import_image_pack.py` | `--origin generated`면 `scope:bundle`을 붙이지 않는다 |
| `build_asset_catalog.py` | scope 태그가 충돌하면 `bundle < output < blocked` 순으로 보수 판정, generated는 무조건 `output` |
| `render_recipe.py` | `blocked`만 중단. `output`은 결과물에 허용하고 `output_only`로 매니페스트·CREDITS에 남긴다 |
| `import_content.py` | `output` 자산은 경고("에셋 팩에 넣을 수 없습니다"), `blocked`는 오류 |

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

| 산출 | 내용 |
| --- | --- |
| `<name>-vN.svg` | 조합별 결과 |
| `<name>-vN-CREDITS.md` | 자산 출처 |
| `variants.json` | 조합·점수·sha256 목록 |

고른 1종은 `blocks` 레시피로 동결하면 이후 결정론적으로 재생된다.

## 반응형

같은 레시피를 `--breakpoint`로 3개 캔버스에 렌더한다.

```bash
render_recipe.py --recipe recipes/resp-v2.json --breakpoint desktop   # 1440
render_recipe.py ... --breakpoint tablet                               # 768
render_recipe.py ... --breakpoint mobile                               # 390
```

| 블록 | mobile 재배치 |
| --- | --- |
| header | 브랜드만, 내비 숨김 |
| hero (mobile·tablet) | 텍스트 → 일러스트 → 풀폭 CTA (tablet은 더 큰 활자·가로형 이미지) |
| stats | 세로 스택 |
| features | 아이콘 + 제목 + 본문 리스트 |
| logos | 2열 |
| cta | 카드 안 세로 배치 |
| footer | 2줄 스택 |

여백은 breakpoint별로 56/32/20, 본문 스케일은 1.0/0.88/0.72를 쓴다.

## 납품 export (PDF·PNG·WebP)

렌더된 SVG를 화면(브레이크포인트)별로 내보낸다.

```bash
python3 scripts/export_recipe.py --src out/ --pattern '*.svg' --out dist/ \
  --formats pdf,png,webp --scale 2 --fonts-css fonts/fonts.css
```

| 형식 | 내용 |
| --- | --- |
| PDF | 화면당 1페이지, 폰트 임베드(Chromium 인쇄) |
| PNG | `@2x` (예: 1440×2293 → 2880×4586) |
| WebP | PNG에서 변환 |

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

| 산출물 | 고정 방법 |
| --- | --- |
| SVG·manifest | 입력 해시(recipe·style·tokens·catalog) 기록, 경로 대신 파일명 |
| PDF | pypdf로 `CreationDate`/`ModDate` 고정, `/ID`를 내용 해시로 교체 |
| PNG·WebP | Chromium·Pillow 출력이 이미 결정론적 |
| ZIP | 항목 타임스탬프 `1980-01-01`, 정렬된 순서, 권한 고정 |

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
