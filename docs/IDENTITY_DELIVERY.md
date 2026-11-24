# 로고·브랜딩 납품 규격

라우드소싱 콘테스트(브랜딩·로고) 납품을 전제로 한 산출물 규격.
저작은 VectorCraft/DesignCraft에서 하고, **시스템화·검사·export는 press가 맡는다.**

## 1. 역할 분담

| 단계 | 도구 | 산출물 |
| --- | --- | --- |
| 저작 | VectorCraft | 심볼·워드마크 벡터 원본 |
| 조판 | DesignCraft | 락업 배치, 브랜드 시트 레이아웃 |
| 시스템화 | **press** | 락업 세트·변형·규격표·export·라이선스 게이트 |
| 제출 | 사람 | 콘테스트 양식 업로드 |

press는 **로고를 만들지 않는다.** 이미 만든 벡터를 규격에 맞춰 전개하고 검사한다.

## 2. 납품 폴더

```
<brand>/
├─ 01_logo/
│  ├─ primary-horizontal.svg / .pdf / .eps
│  ├─ primary-stacked.svg / .pdf / .eps
│  ├─ symbol.svg / .pdf / .eps
│  ├─ mono-black.svg · mono-white.svg
│  └─ one-color.svg
├─ 02_spec/
│  ├─ clearspace.svg          # 여백 그리드
│  ├─ construction.svg        # 작도 그리드
│  └─ minimum-size.svg        # 최소 크기 예시
├─ 03_color/
│  ├─ palette.svg / .pdf
│  └─ palette.ase            # 교환용(가능하면)
├─ 04_typography/
│  └─ type-specimen.pdf
├─ 05_guide/
│  ├─ brand-sheet.pdf        # A4 세로, 다페이지
│  └─ do-dont.pdf
├─ 06_source/
│  ├─ source.ai (또는 source.pdf)
│  └─ source.svg
├─ CREDITS.md                 # 폰트·자산 출처, 라이선스
└─ manifest.json              # 파일 해시, 규격 검사 결과
```

번호 접두사는 제출 순서와 심사 편의를 위한 것이다. 콘테스트가 다른 구조를 요구하면 그쪽을 따른다.

## 3. 락업·변형 매트릭스

| 락업 | 필수 | 비고 |
| --- | --- | --- |
| 가로형(primary) | ✅ | 심볼 + 워드마크, 기본 사용 |
| 세로형(stacked) | ✅ | 정사각형·좁은 지면 |
| 심볼 단독 | ✅ | 파비콘·앱 아이콘 |
| 워드마크 단독 | ⚠️ | 서체가 로고의 핵심일 때 |

| 변형 | 필수 | 비고 |
| --- | --- | --- |
| 풀컬러 | ✅ | 지정 배경 위 |
| 흑백(1도) | ✅ | 인쇄·각인 |
| 반전(밝은 배경/어두운 배경) | ✅ | 두 배경 모두 검증 |
| 단색(별색 지정) | ⚠️ | 팬톤 지정 시 |

**검증 규칙**: 반전 로고는 실제 배경색에서 대비 4.5:1 이상. 1도 변환 시 형태가 무너지지 않아야 한다(가는 선 0.25pt 이상).

## 4. 규격

| 항목 | 기준 | 표기 |
| --- | --- | --- |
| 클리어 스페이스 | 심볼 높이의 50% (x-height 기준 명시) | 도해 필수 |
| 최소 크기 | 인쇄 15mm, 화면 24px (심볼 기준) | 실물 예시 |
| 색 | HEX · RGB · CMYK (+Pantone) | 4종 병기 |
| 서체 | 로고타입 서체명·웨이트·자간 | 아웃라인 여부 명시 |
| 작도 | 그리드·비율·각도 | 선택(권장) |

색은 **한 표에 4종을 병기**한다. CMYK는 근사값임을 명시하고, 인쇄 지정이 필요하면 Pantone을 적는다.

## 5. 브랜드 시트 구성

| 페이지 | 내용 |
| --- | --- |
| 1 | 표지 (브랜드명, 버전, 날짜) |
| 2 | 로고 소개 + 락업 3종 |
| 3 | 클리어 스페이스 · 최소 크기 |
| 4 | 색 팔레트 (4종 병기) |
| 5 | 타이포그래피 |
| 6 | 적용 예시 (명함·간판·앱 아이콘) |
| 7 | Do / Don't |
| 8 | 자산·라이선스 고지 |

A4 세로, 300dpi 상당의 벡터. PDF로 납품하고 원본 SVG를 함께 둔다.

## 6. Export 형식과 `.ai`의 현실

| 형식 | press | 비고 |
| --- | --- | --- |
| SVG | ✅ | 원본·웹·Figma 재편집 |
| PDF | ✅ | 인쇄·심사용, 벡터 유지 |
| EPS | ⚠️ | 외부 변환 필요할 수 있음 |
| PNG | ✅ | 미리보기·목업 |
| **`.ai` 네이티브** | ❌ | Illustrator에서만 생성 |

`.ai` 요구 대응:

1. **PDF를 `.ai`로 제출** — Illustrator에서 열리고 편집된다. 네이티브는 아니지만 대부분 통과
2. **PDF + SVG + EPS 묶음** — 실무 표준. 콘테스트 대부분 허용
3. **Illustrator 단계 추가** — 사람이 열어 저장. 가장 확실하지만 자동화 밖

> 제출 전에 콘테스트가 `.ai`만 요구하는지 확인한다. "벡터 원본(SVG/PDF/EPS/AI 중 1)"이면 1·2번으로 충분하다.

### 실측: Illustrator 2027(31.0.0) 왕복 (2026-11-23)

`press lockup --lockup-dir`로 뽑은 단일 락업 6종과 브랜드 시트 PDF를 Illustrator에서 열어 확인했다.

| 대상 | 결과 | 판정 |
| --- | --- | --- |
| 브랜드 시트 PDF | 아트보드 **8**, 텍스트 프레임 **720**, 패스 **2002**, 배치(placed) 0 | 8페이지가 그대로 들어오고 **텍스트·벡터가 살아 있다**. 뭉개지지 않음 |
| 락업 SVG (텍스트 5종) | 텍스트 프레임 **1**, 패스 4 | 워드마크가 **텍스트로** 들어온다 → 아웃라인 전 상태 |
| 락업 SVG (`symbol`) | 텍스트 0, 패스 4 | 순수 벡터 |
| 아웃라인 후 `.ai` | 텍스트 **0**, 패스 **12**, 크기 유지(640×200 등) | `CreateOutline` → `SaveAs(pdfCompatible)` → **재오픈 성공** |

**폰트 대체 경고가 실제로 뜬다** — Archivo-SemiBold가 없는 PC에서 PDF를 열면 "없는 글꼴" 대화상자가
뜨고 기본 글꼴로 대체된다. 임베드된 서브셋으로 보기·인쇄는 되지만, **그 상태로 아웃라인하면
엉뚱한 모양이 굳는다.**

운영 규칙:

1. **`.ai` 제출본은 SVG 경로에서 만든다.** 텍스트를 포함한 SVG → Illustrator → Create Outlines →
   `.ai` 저장. 폰트가 없어도 결과가 정확하다(아웃라인 전에 대체 경고만 확인).
2. **PDF는 보기·인쇄용**으로 둔다. 임베드 폰트로 렌더되므로 제출 자체는 문제없다.
3. PDF를 **편집 가능한 원본**으로 넘겨야 하면 폰트를 설치하거나, 아웃라인 PDF를 별도로 만든다
   (현재 press는 아웃라인 PDF를 만들지 않는다).
4. 제출 전에 Archivo · Pretendard · JetBrains Mono를 설치해 두면 대체 경고 없이 확인할 수 있다.

## 7. 라이선스·법적 게이트

| 항목 | 규칙 |
| --- | --- |
| 폰트 | `scope:bundle`만 파일 동봉. 상업 폰트는 **아웃라인 처리**하고 파일 미포함 |
| 자산 | `blocked` 금지, `output`은 결과물에만(재배포 금지) |
| AI 생성 | `origin:generated`는 `output` 강제, CREDITS에 모델·프롬프트 기록 |
| 저작권 | 낙찰 시 **저작재산권 이전** 조항 확인. 이전 전 원본 전달 금지 |
| 상표 | 상표 검색은 파이프라인 밖. 사람이 KIPRIS/USPTO 확인 |
| 유사성 | 콘테스트는 유사 시안 리스크가 크다. 참고 이미지 출처를 남긴다 |

`CREDITS.md`에 폰트·자산·AI 사용 내역을 자동 생성한다(현재 press의 CREDITS 로직 재사용).

## 8. 파일명·매니페스트

```
primary-horizontal.svg
primary-horizontal@2x.png
mono-black.svg
brand-sheet.pdf
```

- 소문자·하이픈. 공백·한글 파일명 금지(업로드 시스템 호환)
- `manifest.json`에 파일별 sha256, 규격 검사 결과, 사용 폰트·자산을 기록
- 결정론: 같은 원본 + 같은 규격이면 같은 바이트

## 9. 제출 전 체크리스트

- [ ] 락업 3종이 모두 있다
- [ ] 흑백·반전 변형이 실제 배경에서 읽힌다
- [ ] 클리어 스페이스·최소 크기 도해가 있다
- [ ] 색이 HEX/RGB/CMYK로 병기되어 있다
- [ ] 로고타입 폰트가 아웃라인 처리됐다
- [ ] 브랜드 시트 PDF가 8페이지 구성을 갖췄다
- [ ] `CREDITS.md`에 폰트·자산·AI 내역이 있다
- [ ] 저작권 이전 조항을 확인했다
- [ ] 상표 검색을 사람이 확인했다
- [ ] 파일명이 규칙을 지킨다(소문자·하이픈)

## 10. press에 필요한 신규 문서 타입

| 타입 | 내용 | 현재 |
| --- | --- | --- |
| `page` | 웹·랜딩 | ✅ 구현 |
| `lockup` | 락업·변형 시트 | ✅ 구현 (`press lockup`) |
| `brand-sheet` | 8페이지 가이드 | ✅ 구현 (`press brandsheet`) |
| `spec-diagram` | 클리어 스페이스·작도 | ✅ 구현 (`press spec`) |
| `brand-kit` | 위 전부를 한 zip으로 | ✅ 구현 (`press brandkit`) |

`lockup`·`spec-diagram`은 SVG 블록으로 비교적 쉽게 만들 수 있다. `brand-sheet`는 A4 다페이지 PDF 조판이 필요해 별도 작업이다.

### brand kit (구현됨, 2026-11-24)

브랜드 산출물은 명령마다 흩어져 있어 남에게 건넬 때 네 번 실행하고 폴더를 손으로 합쳐야 했다.
`press brandkit`은 스펙 하나로 **한 벌**을 만든다.

```bash
press brandkit --spec brand.json --out out/brandkit --name sonagi-brand-kit [--pdf]
```

```
logo/    락업·변형 시트 (render_lockup)
spec/    클리어 스페이스·작도·최소 크기 (render_spec)
color/   palette.json · palette.css  ← 스펙 색만 옮긴다(발명하지 않음)
type/    type-scale.json             ← 스펙에 있는 단계만
print/   브랜드 시트 PDF (--pdf, 폰트 필요 · 없으면 SKIP 사유 기록)
manifest.json (정렬된 목록 + sha256) · CREDITS.md · <name>.zip
```

결정론: 같은 스펙이면 **같은 zip 바이트**. 생성 시각을 넣지 않고, zip 엔트리를 정렬하고
타임스탬프를 1980-01-01로 고정한다(`test_brandkit.py`가 두 번 빌드해 해시를 비교한다).

렌더 실패는 조용히 넘기지 않는다. `manifest.skipped`에 사유가 남는다(예: 폰트 없는 호스트의 PDF).

### lockup 시트 (구현됨)

스펙 JSON 하나로 락업 × 변형 매트릭스를 전개한다. press는 로고를 만들지 않고,
받은 심볼 벡터를 다시 칠해 배치하고 **실제 배경 대비를 계산**한다.

```json
{
    "brand": "SONAGI",
    "version": "v1.0",
    "symbol": "assets/logo/symbol.svg",
    "wordmark": "SONAGI",
    "type": { "family": "Archivo", "weight": 700, "tracking": 0.14 },
    "colors": {
        "primary": "#1f4536",
        "ink": "#161616",
        "paper": "#fbf9f5",
        "accent": "#b4551f"
    },
    "backgrounds": { "light": "#fbf9f5", "dark": "#12100e" },
    "lockups": ["horizontal", "stacked", "symbol"],
    "variants": ["color", "mono", "inverse", "one-color"],
    "clearspace": 0.5,
    "minimum": { "print_mm": 15, "screen_px": 24 }
}
```

```bash
press lockup --spec brand/lockup.json --out out/lockup --name sonagi-lockup
press lockup --spec brand/lockup.json --check      # 파일 없이 검사만
```

- 셀마다 전경·배경·대비를 매니페스트에 남긴다. 4.5:1 미만이면 exit 1
  (`--allow-low-contrast`로 강제 진행)
- 심볼은 `stroke`/`fill`의 hex만 다시 칠한다. `none`·그라디언트 정의는 건드리지 않는다
- 워드마크는 텍스트로 그린다. **제출용은 벡터 아웃라인을 권장** — `wordmark` 대신
  별도 SVG를 쓰는 경로는 아직 없다
- 파일명은 브랜드명을 소문자·하이픈으로 바꿔 만든다(8절 규칙)
- `--lockup-dir`로 **제출용 단일 락업**을 함께 뽑는다: `primary-horizontal` ·
  `primary-stacked` · `symbol` · `mono-black` · `mono-white` · `one-color`.
  배경 없는 투명 SVG이고, 파일명은 2절 폴더 규칙과 같다

### 규격 도해 (구현됨)

lockup 스펙 하나로 세 장을 뽑는다. 값은 스펙의 `clearspace`·`minimum`을 그대로 쓴다.

```bash
press spec --spec brand/lockup.json --out out/spec
```

| 파일 | 내용 | 결정하는 값 |
| --- | --- | --- |
| `clearspace.svg` | 심볼 높이 기준 여백 + 치수선 | `clearspace` (기본 0.5h) |
| `construction.svg` | 12u 그리드·중심축·대각선·내접원 | 심볼 비율 |
| `minimum-size.svg` | 인쇄 mm / 화면 px 실물 크기 + ×5 확대 | `minimum` |

`spec.manifest.json`에 파일별 해시와 계산된 여백(px)을 남긴다. 심볼이 바뀌면 해시가 바뀐다.

### 브랜드 시트 (구현됨)

5절의 8페이지를 A4 세로(794×1123px 벡터)로 조판하고 한 PDF로 묶는다.

```bash
press brandsheet --spec brand/lockup.json --out out/brandsheet --name sonagi-brand-sheet --pdf
```

| 페이지 | 내용 | 근거 데이터 |
| --- | --- | --- |
| 1 | 표지 | 브랜드·버전·`date`·`tagline` |
| 2 | 락업 3종 | `symbol`·`wordmark` |
| 3 | 클리어 스페이스·최소 크기 | `clearspace`·`minimum` |
| 4 | 색 (HEX·RGB·CMYK) | `colors` 또는 `palette` |
| 5 | 타이포그래피 | `type` |
| 6 | 적용 예시 | 심볼·색 |
| 7 | Do / Don't | 심볼·색 |
| 8 | 자산·라이선스 | 파일 해시·폰트·권리 |

- `export_recipe.py --pdf-mode single`로 같은 크기 페이지를 한 PDF에 묶는다
- `brandsheet.manifest.json`에 페이지별 해시·팔레트(HEX/RGB/CMYK)·검사값을 남긴다
- 인쇄는 RGB 기준이다. CMYK·도련은 6절 이후 별도 경로(ASSET-6)

## 11. 남은 구멍

- 상표 검색 자동화 없음 (사람)
- 목업(명함·간판·앱 아이콘) 자동 합성 없음
- `.ai` 네이티브 export 없음 (Illustrator 단계)
- 팬톤 매핑은 수동
- 콘테스트별 양식 차이는 사람이 맞춰야 함
