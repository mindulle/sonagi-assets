#!/usr/bin/env python3
"""라이선스 → 사용 범위(scope) 정책 단일 출처.

세 단계로 나눈다.

- bundle: 결과물 제작 + 폰트 파일 재배포(패키지·번들) 가능
- output: 결과물 제작만 가능. 파일 재배포·임베딩 금지
- blocked: 사용 불가(유료·개인용·내부용·권리 불명)

새 라이선스를 추가할 때는 LICENSE_SCOPE만 고치면 카탈로그·allow-list·
패키징 스크립트가 함께 따라온다.

사용 예::

    from license_policy import scope_for_license, is_pack_ready
    scope_for_license("ofl")   # "bundle"
    is_pack_ready("free")      # False
"""

SCOPE_BUNDLE = "bundle"
SCOPE_OUTPUT = "output"
SCOPE_BLOCKED = "blocked"

LICENSE_SCOPE = {
    # 파일 재배포까지 허용
    "ofl": SCOPE_BUNDLE,
    "mit": SCOPE_BUNDLE,
    "isc": SCOPE_BUNDLE,
    "apache": SCOPE_BUNDLE,
    "cc0": SCOPE_BUNDLE,
    # 결과물 사용만 허용
    "free": SCOPE_OUTPUT,
    # 사용 불가
    "gpl": SCOPE_BLOCKED,
    "commercial": SCOPE_BLOCKED,
    "personal": SCOPE_BLOCKED,
    "internal-only": SCOPE_BLOCKED,
    "cleared": SCOPE_BLOCKED,
    "n/a": SCOPE_BLOCKED,
    "unknown": SCOPE_BLOCKED,
}

BUNDLE_LICENSES = tuple(sorted(k for k, v in LICENSE_SCOPE.items() if v == SCOPE_BUNDLE))
OUTPUT_LICENSES = tuple(sorted(k for k, v in LICENSE_SCOPE.items() if v == SCOPE_OUTPUT))


def scope_for_license(license_value):
    """라이선스 문자열을 scope로 변환한다. 모르는 값은 blocked."""
    return LICENSE_SCOPE.get((license_value or "").strip().lower(), SCOPE_BLOCKED)


def is_pack_ready(license_value):
    """판매용 팩에 폰트 파일을 넣어도 되는지."""
    return scope_for_license(license_value) == SCOPE_BUNDLE


def license_from_tags(tags):
    """items.tags에서 대표 라이선스를 고른다. 없으면 unknown."""
    for tag in tags or []:
        if tag.startswith("license:") and tag != "license:unknown":
            return tag.split(":", 1)[1]
    return "unknown"


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("usage: license_policy.py <license>")
        raise SystemExit(2)
    value = sys.argv[1]
    print(f"{value}: {scope_for_license(value)}")
