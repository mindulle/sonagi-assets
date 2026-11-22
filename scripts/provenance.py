#!/usr/bin/env python3
"""자산 출처(origin) 분류와 사용 범위 정책.

license는 "무엇을 해도 되는가", origin은 "어디서 왔는가"다. 둘은 직교한다.
origin은 납품·판매 시 고지와 사용 가능 범위를 결정한다.

| origin | 뜻 | 기본 scope |
| --- | --- | --- |
| open-source | OFL·MIT·ISC·Apache | bundle |
| public-domain | CC0·PD | bundle |
| freeware | 무료 배포지만 재배포 제한 | output |
| commercial | 유료 라이선스 | blocked |
| generated | AI 생성·합성 | output (강제) |
| in-house | 자체 제작 | bundle |
| unknown | 출처·권리 불명 | blocked |

사용::

    from provenance import origin_for_license, scope_for_origin
    origin_for_license("ofl")      # "open-source"
    scope_for_origin("generated")  # "output"
"""

ORIGIN_OPEN_SOURCE = "open-source"
ORIGIN_PUBLIC_DOMAIN = "public-domain"
ORIGIN_FREEWARE = "freeware"
ORIGIN_COMMERCIAL = "commercial"
ORIGIN_GENERATED = "generated"
ORIGIN_IN_HOUSE = "in-house"
ORIGIN_UNKNOWN = "unknown"

ORIGINS = (
    ORIGIN_OPEN_SOURCE,
    ORIGIN_PUBLIC_DOMAIN,
    ORIGIN_FREEWARE,
    ORIGIN_COMMERCIAL,
    ORIGIN_GENERATED,
    ORIGIN_IN_HOUSE,
    ORIGIN_UNKNOWN,
)

ORIGIN_SCOPE = {
    ORIGIN_OPEN_SOURCE: "bundle",
    ORIGIN_PUBLIC_DOMAIN: "bundle",
    ORIGIN_IN_HOUSE: "bundle",
    ORIGIN_FREEWARE: "output",
    ORIGIN_GENERATED: "output",
    ORIGIN_COMMERCIAL: "blocked",
    ORIGIN_UNKNOWN: "blocked",
}

# 계약·고지에 쓰는 문구
DISCLOSURE = {
    ORIGIN_OPEN_SOURCE: "오픈소스 라이선스 자산. 라이선스 원문을 함께 보관하세요.",
    ORIGIN_PUBLIC_DOMAIN: "퍼블릭 도메인 자산. 출처 표기를 권장합니다.",
    ORIGIN_FREEWARE: "무료 배포 자산. 파일 재배포·판매는 금지됩니다.",
    ORIGIN_COMMERCIAL: "유료 라이선스 자산. 납품 전 별도 구매·확인 필요.",
    ORIGIN_GENERATED: "AI 생성 자산. 사용 모델·일자·프롬프트를 기록하고, 계약상 고지 의무를 확인하세요.",
    ORIGIN_IN_HOUSE: "자체 제작 자산.",
    ORIGIN_UNKNOWN: "출처 불명. 납품·판매에 사용하지 마세요.",
}

_LICENSE_TO_ORIGIN = {
    "ofl": ORIGIN_OPEN_SOURCE,
    "apache": ORIGIN_OPEN_SOURCE,
    "mit": ORIGIN_OPEN_SOURCE,
    "isc": ORIGIN_OPEN_SOURCE,
    "cc0": ORIGIN_PUBLIC_DOMAIN,
    "free": ORIGIN_FREEWARE,
    "commercial": ORIGIN_COMMERCIAL,
}


def origin_for_license(license_value):
    return _LICENSE_TO_ORIGIN.get((license_value or "").strip().lower(), ORIGIN_UNKNOWN)


def scope_for_origin(origin):
    return ORIGIN_SCOPE.get(origin, "blocked")


def origin_from_tags(tags):
    for tag in tags or []:
        if tag.startswith("origin:"):
            return tag.split(":", 1)[1]
    return ORIGIN_UNKNOWN


def disclosure_for(origin):
    return DISCLOSURE.get(origin, DISCLOSURE[ORIGIN_UNKNOWN])


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("usage: provenance.py <license>")
        raise SystemExit(2)
    value = sys.argv[1]
    print(f"{value}: {origin_for_license(value)}")
