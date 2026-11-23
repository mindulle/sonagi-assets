# 토큰 SSOT 대조 (2026-11-23)

두 저장소가 각자 토큰을 단일 소스라고 부른다. 실제로 같은 색인지 재봤다.

```bash
python3 scripts/compare_tokens.py
```

| 저장소 | 파일 | 테마 |
| --- | --- | --- |
| `sonagi-assets` | `tokens/semantic.json` | `editorial` · `architecture` |
| `mindulle-design-system` | `packages/tokens/tokens/*.json` | `light` · `dark` |

## 1. 결과

ΔE는 CIE76(1~2는 눈으로 구분 어려움, 3 이상은 구분됨).

| 테마 | 역할 | assets | MDS | ΔE | 대비(a) | 대비(m) |
| --- | --- | --- | --- | ---: | ---: | ---: |
| editorial | background | `#fbf9f5` | `#fbfbfa` | 1.8 | 1.00 | 1.00 |
| editorial | surface | `#ffffff` | `#ffffff` | 0.0 | 1.05 | 1.04 |
| editorial | ink | `#161616` | `#18181b` | 2.5 | 17.21 | 17.11 |
| editorial | text-secondary | `#3a3a36` | `#52525b` | 13.7 | 10.86 | 7.47 |
| editorial | text-muted | `#63635e` | `#71717a` | 10.3 | 5.74 | 4.67 |
| editorial | border | `#dcd7cc` | `#e4e4e7` | 8.8 | 1.36 | 1.23 |
| editorial | **accent** | `#d97706` | `#9e5a03` | **22.0** | 3.03 | 5.18 |
| editorial | accent-strong | `#f59e0b` | `#eab308` | 16.4 | 2.04 | 1.85 |
| architecture | background | `#060911` | `#12151d` | 4.9 | 1.00 | 1.00 |
| architecture | surface | `#090d16` | `#1b202c` | 9.3 | 1.02 | 1.12 |
| architecture | ink | `#ffffff` | `#f1f5f9` | 4.4 | 19.91 | 16.66 |
| architecture | text-secondary | `#c9d1d9` | `#94a3b8` | 18.6 | 12.90 | 7.12 |
| architecture | text-muted | `#9aa4b2` | `#64748b` | 19.6 | 7.89 | 3.83 |
| architecture | border | `#30363d` | `#2c3547` | 7.4 | 1.63 | 1.48 |
| architecture | **accent** | `#4a90e2` | `#ffc837` | **124.8** | 6.05 | 11.79 |
| architecture | accent-strong | `#ffd166` | `#ffd166` | 0.0 | 13.81 | 12.66 |

**같음 2 · 근접 3 · 다름 13 (18역할)**. 표면만 우연히 같고, 나머지는 다르다.

## 2. 읽히는 것

**① 두 벌은 같은 것의 복사본이 아니라 서로 다른 축이다.**
`editorial`·`architecture`는 브랜드 모드(신문지 / 밤비)이고, MDS `light`·`dark`는 UI
테마 모드다. 역할 이름이 겹쳐서 "같은 것"처럼 보였을 뿐이다.

**② 결정적 충돌은 다크 accent다.**

| | 값 | 뜻 |
| --- | --- | --- |
| assets `architecture` accent | `#4a90e2` | 소나기 블루 |
| MDS `dark` brand.primary | `#ffc837` | 골드 |

ΔE 124.8은 "조금 다른 색"이 아니라 **다른 아이덴티티**다. 이건 코드로 합칠 수
없고 브랜드 결정이 필요하다.

**③ 라이트 accent는 MDS가 접근성에 유리하다.**
assets `#d97706`은 크림 배경에서 3.03:1(12px 텍스트 AA 미달 — 판정 골든에서
찾은 그 부채), MDS `#9e5a03`은 5.18:1로 통과한다. 다만 MDS 값은 눈에 띄게
어둡다. "브랜드 골드"와 "작은 글자용 골드"를 한 값으로 쓰려는 시도가 문제다.

**④ 본문·보조 텍스트는 축이 다르다.**
assets는 따뜻한 뉴스프린트 계열(`#3a3a36`), MDS는 중성 그레이(`#52525b`).
이건 통일 대상이 아니라 각자의 매체에 맞는 선택으로 보인다.

## 3. 제안

색을 지금 합치지 않는다. 대신 **역할을 두 층으로 나눈다.**

```
Tier 0  브랜드 역할 (두 모드의 값이 유일해야 함)
        brand.primary   editorial #d97706 | architecture #4a90e2
        brand.accent    editorial #f59e0b | architecture #ffd166

Tier 1  매체별 파생 (같을 필요 없음, 문서로만 연결)
        UI 중성 그레이(MDS) ↔ 인쇄 뉴스프린트(assets)
```

즉 **brand.\* 역할만 단일화하고, 중성·텍스트 역할은 각 매체에 남긴다.**
그러면 다크 accent 충돌만 결정하면 되고, 나머지 13개 차이는 "다른 매체"로
설명된다.

### 결정이 필요한 것

1. **다크 accent**: 소나기 블루(`#4a90e2`)를 유지할 것인가, 골드(`#ffc837`)로
   통일할 것인가.
2. **라이트 accent**: 브랜드 골드(`#d97706`)를 유지하고 작은 글자만 별도
   역할(`accent-text`)로 뺄 것인가, MDS의 어두운 골드(`#9e5a03`)로 바꿀 것인가.

둘 중 하나를 정하면, 그때 `packages/tokens`를 정본으로 두고 `tokens/semantic.json`을
생성물로 강등하는 작업(빌드 스크립트 교체 + 골든 갱신)을 한다.

## 4. 재현

```bash
python3 scripts/compare_tokens.py --json
python3 scripts/compare_tokens.py --mds /path/to/mindulle-design-system/packages/tokens
```

값을 바꾸지 않는다. 판정만 한다.
