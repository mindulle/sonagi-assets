#!/usr/bin/env python3
"""폰트 이름의 배포처(provider)를 근거로 라이선스를 확정한다.

폰트 파일에 라이선스 문구·URL이 없어도, 배포처의 공식 라이선스 정책을
확인한 경우 이름 규칙으로 분류할 수 있다. 각 규칙에는 근거 URL을 남긴다.

- 기본 dry-run, --apply 시 DB 백업 후 반영
- license:<값> / license_src:provider / license_provider:<slug> 태그를 쓴다
"""

import argparse
import collections
import datetime
import json
import re
import sqlite3

# (name pattern, license, provider slug, official evidence URL, note)
RULES = [
    (r"^NanumSquare", "ofl", "naver-nanum", "https://hangeul.naver.com/font", "OFL"),
    (r"^Pretendard", "ofl", "pretendard", "https://github.com/orioncactus/pretendard", "OFL"),
    (r"^BlackHanSans$", "ofl", "google-fonts", "https://fonts.google.com/specimen/Black+Han+Sans", "OFL"),
    (r"^NotoSans", "ofl", "google-fonts", "https://fonts.google.com/noto", "OFL"),
    (r"^Roboto", "apache", "google-fonts", "https://fonts.google.com/specimen/Roboto+Mono", "Apache-2.0"),
    (r"^Josefin", "ofl", "google-fonts", "https://fonts.google.com/specimen/Josefin+Slab", "OFL"),
    (r"^Lato", "ofl", "google-fonts", "https://fonts.google.com/specimen/Lato", "OFL"),
    (r"^Archivo", "ofl", "google-fonts", "https://fonts.google.com/specimen/Archivo", "OFL"),
    (r"^ZillaSlab", "ofl", "google-fonts", "https://fonts.google.com/specimen/Zilla+Slab", "OFL"),
    (r"^BioRhyme", "ofl", "google-fonts", "https://fonts.google.com/specimen/BioRhyme", "OFL"),
    (r"^Ubuntu", "free", "ubuntu", "https://ubuntu.com/legal/font-licence", "Ubuntu Font Licence"),
    (r"^LINESeed", "ofl", "line-seed", "https://seed.line.me/index_kr.html", "OFL, 파일 판매 금지"),
    (r"^Cafe24", "free", "cafe24", "https://www.cafe24.com", "상업 사용 가능, 파일 판매 금지"),
    (r"^Mapo", "free", "mapo", "https://mapofont.or.kr/", "상업 사용 가능, 출처 표시, 수정·판매 금지"),
    (r"^EBS", "free", "ebs", "https://about.ebs.co.kr/kor/organization/font", "상업 사용 가능, 재배포·판매 금지"),
    (r"^KBIZ", "free", "kbiz", "https://www.kbiz.or.kr/ko/mobile/contents/contents/contents.do?mnSeq=452", "상업 사용 가능, 파일 판매 금지"),
    (r"^문체부", "free", "mcst", "https://gongu.copyright.or.kr/gongu/bbs/B0000018/list.do?menuNo=200195", "공공누리 1유형(출처표시)"),
    (r"^Chosun", "free", "chosun", "https://event.chosun.com/100/100font.html", "상업 사용 가능, 수정·판매 금지"),
    (r"^HS", "free", "tokkine", "https://blog.naver.com/hp0", "상업 사용 가능, 파일 판매 금지"),
    (r"^SF(싸락눈|레몬빙수|망고빙수|함박눈)", "free", "nunseori", "https://blog.naver.com/snowfrost001", "상업 사용 가능, 파일 판매 금지"),
    (r"^utoimage|^123RF", "free", "bbtree", "https://www.utoimage.com/?m=service.license", "상업 사용 가능, 재배포·임베딩 별도 허가"),
    (r"^성신여대", "internal-only", "sungshin-restricted", "https://www.sungshin.ac.kr/main_kor/10930/subview.do", "성신 구성원 한정 배포"),
    (r"^DAONFONT", "commercial", "daonfont", "http://www.daonfont.com/guide/license2.php", "유료 폰트사(무료 일부만 상업 허용)"),
]

COMPILED = [(re.compile(p), lic, slug, url, note) for p, lic, slug, url, note in RULES]


def match(name):
    for pattern, lic, slug, url, note in COMPILED:
        if pattern.search(name or ""):
            return lic, slug, url, note
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    rows = list(conn.execute("select id,name,ext,tags from items where ext in ('ttf','otf','woff','woff2')"))
    conn.close()

    resolved = {"ofl", "apache", "gpl", "cc0", "commercial", "personal", "free", "internal-only"}
    updates = []
    stats = collections.Counter()
    providers = collections.Counter()
    unmatched = []
    for row_id, name, _ext, tags_json in rows:
        try:
            tags = json.loads(tags_json) if tags_json else []
        except json.JSONDecodeError:
            tags = []
        lic = [t.split(":", 1)[1] for t in tags if t.startswith("license:")]
        if lic and lic[0] in resolved:
            continue
        hit = match(name)
        if not hit:
            unmatched.append(name)
            continue
        lic_value, slug, url, note = hit
        tags = [t for t in tags if not t.startswith(("license:", "license_src:", "license_provider:", "license_url:", "license_note:"))]
        tags += [
            f"license:{lic_value}",
            "license_src:provider",
            f"license_provider:{slug}",
            f"license_url:{url}",
            f"license_note:{note}",
        ]
        updates.append((row_id, sorted(set(tags))))
        stats[lic_value] += 1
        providers[slug] += 1

    print(
        json.dumps(
            {
                "resolved": len(updates),
                "by_license": dict(stats),
                "by_provider": dict(providers),
                "still_unknown": len(unmatched),
                "apply": args.apply,
            },
            ensure_ascii=False,
        )
    )
    if not args.apply:
        print(json.dumps({"sample_unmatched": unmatched[:10]}, ensure_ascii=False))
        return 0

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = f"{args.db}.bak-provider-{stamp}"
    src = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    dst = sqlite3.connect(backup)
    src.backup(dst)
    dst.close()
    src.close()

    conn = sqlite3.connect(args.db, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    for row_id, tags in updates:
        conn.execute("update items set tags=? where id=?", (json.dumps(tags, ensure_ascii=False), row_id))
    conn.commit()
    conn.close()
    print(json.dumps({"updated": len(updates), "backup": backup}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
