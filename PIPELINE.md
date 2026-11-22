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

## Figma 재임포트

- 그룹 구조 유지: `<g id="hero">` → Frame/Group `hero`
- 텍스트는 `<text>`로 남으므로 편집 가능. 단 폰트가 설치돼 있어야 한다
- 외부 참조(`href`·`<image>`)가 없어 파일 단독으로 열린다
