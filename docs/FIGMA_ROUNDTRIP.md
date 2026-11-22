# Figma 왕복 검증 (2026-11-22)

생성 SVG가 Figma에서 **편집 가능한 레이어**로 살아남는지 확인했다.
검증 파일: `Pipeline Test` (`TZeo0UtPiLWnhj1nyfeeEj`), Desktop Bridge 사용.

## 1. 구조 — 통과

| SVG 구성 | Figma 임포트 결과 |
| --- | --- |
| `<g id="header">`, `<g id="hero">` | 이름이 유지된 **GROUP** |
| `<text>` | 편집 가능한 **TEXT** 노드 (문자열 보존) |
| 아이콘 `<path>` | **VECTOR** |
| 중첩 `<svg viewBox>` | **FRAME** |
| `<image href="data:image/jpeg;base64,…">` | **RECTANGLE + IMAGE fill (CROP)** |
| `clipPath` | 클립 적용됨 |

즉 "그룹 구조 유지, 텍스트 편집 가능, 이미지 임베드"라는 전제는 **사실로 확인**됐다.

## 2. 타이포그래피 — 실패 (환경 문제)

| 확인 | 결과 |
| --- | --- |
| `NanumSquare` | Figma에 **미설치** → Inter로 대체 |
| `Archivo`, `JetBrains Mono`, `Gowun Batang`, `Pretendard` | 설치됨 |
| 라틴 전용 서체(Archivo)에 한글 | 글자가 깨짐. Figma는 폰트 폴백을 하지 않음 |
| `Pretendard Bold` 64px | **Figma 기본 텍스트로 만들어도 깨짐** (환경 폰트 문제) |
| `Gowun Batang` 64px | 정상 |

핵심: Pretendard Bold가 이 환경에서 깨지는 것은 **우리 SVG 문제가 아니라 설치된 폰트 문제**다.
같은 문자열을 Figma에서 직접 만들어도 동일하게 깨졌다.

## 3. 적용한 수정

- 렌더러에 **한글 폴백 규칙** 추가: 라틴 전용 서체(display/mono)에 한글이 오면
  `style.type.korean`(기본 Pretendard)으로 교체
- 스타일 팩 기본 sans를 `NanumSquare` → `Pretendard`로 변경 (Figma 설치본 기준)

## 4. 남은 제약

| 항목 | 상태 |
| --- | --- |
| 2.5MB 래스터 임베드 | 전송 한계로 미검증. data URI 자체는 소용량에서 확인 |
| Pretendard Bold | 이 환경에서 깨짐 → 폰트 재설치 또는 헤드라인은 Gowun Batang/NanumSquare |
| 텍스트 기준선 | SVG `y`는 baseline, Figma는 박스 상단 기준 → 미세 오프셋 발생 |
| placeholder 슬롯 | 좁은 캔버스에서 제목과 겹침(레이아웃 폭 문제) |

## 5. 납품 판정

- **구조·레이어·이미지: 납품 가능**
- **타이포: 폰트 설치·선택 규칙 없이는 납품 불가**

다음 조치: Pretendard 재설치(또는 Bold 대체) + 납품 전 사용 폰트 목록을 클라이언트와 합의.


## 2차 검증 (폰트 설치 후, 2026-11-22)

Windows 머신(`mindulle-gp66-windows`)에 폰트 8종을 설치하고 Figma를 재시작한 뒤 재검증했다.

| 항목 | 결과 |
| --- | --- |
| 패밀리 해석 | Archivo·Pretendard·JetBrains Mono·NanumSquare **모두 정상 매핑** (Inter 폴백 없음) |
| NanumSquare | 설치 후 정상 렌더 |
| Gowun Batang | 정상 |
| Pretendard Bold | Figma **기본 텍스트와 동일하게** 두껍게 렌더 (임포트 문제 아님) |
| 임포트 vs 네이티브 | 같은 속성·같은 모양 → **임포트 손실 없음** |

### 결론

- SVG 임포트는 폰트를 정확히 전달한다. 깨짐은 **설치된 Pretendard Bold의 렌더링 특성**이었다.
- 한글 헤드라인은 **NanumSquare Bold**(또는 Gowun Batang)를 쓰는 편이 안전하다.
- 스타일 팩의 `type.korean`을 NanumSquare/Gowun으로 고정했다.

### 운영 메모

- 폰트는 Figma가 도는 머신에 설치해야 한다(브리지는 SSH 터널로 연결됨).
- 설치 위치: `%LOCALAPPDATA%\Microsoft\Windows\Fonts` + `HKCU` 레지스트리.
- 설치 후 Figma 완전 재시작 필요. 재시작하면 Desktop Bridge 플러그인을 다시 열어야 한다.
