#!/usr/bin/env python3
"""SVG 스타일 특징 추출 + 결정론적 클러스터링 (순수 파이썬)

- 외부 ML 라이브러리 없이 z-score 정규화 + k-means(고정 시드)
- 클러스터별 특징으로 스타일 후보 라벨을 제안
- 상위 500개(Figma → CC0 → 나머지)에 후보 라벨을 붙여 검토용 JSON 생성
"""

import argparse
import collections
import json
import math
import os
import random
import re

COLOR_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)")
STROKE_W_RE = re.compile(r"stroke-width\s*[:=]\s*\"?([0-9.]+)")
PATH_CMD_RE = re.compile(r"[A-Za-z]")
CURVE_CMDS = set("CcSsQqTtAa")
LINE_CMDS = set("MmLlHhVv")
ELEMENT_TAGS = ("path", "rect", "circle", "ellipse", "polygon", "polyline", "line")


def features_of(path):
    try:
        if os.path.getsize(path) > 2 * 1024 * 1024:
            return None
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    except OSError:
        return None

    colors = COLOR_RE.findall(text)
    widths = [float(x) for x in STROKE_W_RE.findall(text) if float(x) > 0]
    n_paths = len(re.findall(r"<path\b", text))
    n_elements = sum(len(re.findall(rf"<{tag}\b", text)) for tag in ELEMENT_TAGS)
    d_attrs = re.findall(r"\bd=\"([^\"]{0,20000})\"", text)
    cmd_counts = collections.Counter()
    for d in d_attrs:
        cmd_counts.update(PATH_CMD_RE.findall(d))
    curve = sum(cmd_counts[c] for c in CURVE_CMDS)
    total_cmds = sum(cmd_counts.values())

    return {
        "n_elements": n_elements,
        "n_paths": n_paths,
        "n_colors": len(set(c.lower() for c in colors)),
        "has_gradient": int("Gradient" in text),
        "has_text": int("<text" in text),
        "has_stroke": int(bool(widths)),
        "stroke_avg": sum(widths) / len(widths) if widths else 0.0,
        "stroke_max": max(widths) if widths else 0.0,
        "curve_ratio": curve / total_cmds if total_cmds else 0.0,
        "cmds_per_path": total_cmds / n_paths if n_paths else 0.0,
        "has_opacity": int("opacity" in text),
        "bytes": len(text),
    }


VECTOR_KEYS = ["n_elements", "n_paths", "n_colors", "stroke_avg", "stroke_max", "curve_ratio", "cmds_per_path", "bytes"]


def zscores(vectors):
    n = len(vectors)
    stats = {}
    for key in VECTOR_KEYS:
        vals = [v[key] for v in vectors]
        mean = sum(vals) / n
        var = sum((x - mean) ** 2 for x in vals) / n
        stats[key] = (mean, math.sqrt(var) or 1.0)
    return [[(v[k] - stats[k][0]) / stats[k][1] for k in VECTOR_KEYS] for v in vectors], stats


def kmeans(points, k, seed, iterations=60):
    rng = random.Random(seed)
    centers = [list(p) for p in rng.sample(points, k)]
    labels = [0] * len(points)
    for _ in range(iterations):
        changed = False
        for i, p in enumerate(points):
            best = min(range(k), key=lambda c: sum((p[d] - centers[c][d]) ** 2 for d in range(len(p))))
            if labels[i] != best:
                labels[i] = best
                changed = True
        sums = [[0.0] * len(points[0]) for _ in range(k)]
        counts = [0] * k
        for p, lab in zip(points, labels):
            counts[lab] += 1
            for d, val in enumerate(p):
                sums[lab][d] += val
        for c in range(k):
            if counts[c]:
                centers[c] = [s / counts[c] for s in sums[c]]
        if not changed:
            break
    return labels


def propose_style(centroid):
    """정규화 전 원시 특징 평균으로 스타일 후보를 규칙적으로 제안."""
    c = centroid
    if c["has_gradient"] >= 0.5:
        return "glass"
    if c["stroke_max"] >= 6 or c["stroke_avg"] >= 4:
        return "neo-brutal"
    if c["n_colors"] <= 2.5 and c["has_gradient"] < 0.2:
        return "minimal"
    if c["curve_ratio"] >= 0.55 and c["cmds_per_path"] >= 12:
        return "organic"
    if c["n_colors"] >= 6 and c["has_gradient"] < 0.3:
        return "retro"
    if c["stroke_avg"] > 0 and c["stroke_avg"] <= 1.6 and c["n_colors"] <= 3:
        return "technical"
    if c["n_elements"] >= 8 and c["cmds_per_path"] <= 10:
        return "geometric"
    return "editorial"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--k", type=int, default=6)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--top", type=int, default=500)
    args = ap.parse_args()

    catalog = json.load(open(args.catalog))
    svgs = [i for i in catalog["items"] if i["ext"] == "svg" and not i.get("junk") and i.get("kind") == "asset"]
    vectors, kept = [], []
    for item in svgs:
        f = features_of(item["path"]) if item.get("path") else None
        if f:
            vectors.append(f)
            kept.append(item)

    points, stats = zscores(vectors)
    labels = kmeans(points, args.k, args.seed)

    clusters = collections.defaultdict(list)
    for item, f, lab in zip(kept, vectors, labels):
        clusters[lab].append((item, f))

    summaries = []
    for lab, members in sorted(clusters.items()):
        centroid = {k: sum(f[k] for _, f in members) / len(members) for k in members[0][1]}
        style = propose_style(centroid)
        rng = random.Random(args.seed + lab)
        names = sorted(m["name"] for m, _ in members)
        samples = rng.sample(names, min(6, len(names)))
        summaries.append(
            {"cluster": lab, "size": len(members), "style": style, "centroid": {k: round(v, 3) for k, v in centroid.items()}, "samples": samples}
        )

    # 상위 500: figma → cc0 → 나머지(그룹 많고 이름순)
    def priority(item):
        src = item.get("source")
        return (0 if src == "figma" else 1 if item.get("license") == "cc0" else 2, -(item.get("svg_groups") or 0), item["name"])

    by_priority = sorted(kept, key=priority)[: args.top]
    index = {id(item): lab for item, lab in zip(kept, labels)}
    style_of = {s["cluster"]: s["style"] for s in summaries}
    assignments = [
        {
            "id": item["id"],
            "name": item["name"],
            "source": item.get("source"),
            "license": item.get("license"),
            "cluster": index[id(item)],
            "style": style_of[index[id(item)]],
            "svg_groups": item.get("svg_groups"),
        }
        for item in by_priority
    ]

    os.makedirs(args.out_dir, exist_ok=True)
    json.dump(
        {
            "count": len(kept),
            "k": args.k,
            "seed": args.seed,
            "features": VECTOR_KEYS,
            "stats": {k: [round(a, 4), round(b, 4)] for k, (a, b) in stats.items()},
            "clusters": summaries,
        },
        open(os.path.join(args.out_dir, "style-clusters.json"), "w"),
        ensure_ascii=False,
        indent=2,
    )
    json.dump(
        {"count": len(assignments), "clusters": style_of, "assignments": assignments},
        open(os.path.join(args.out_dir, "style-assignments.json"), "w"),
        ensure_ascii=False,
        indent=2,
    )

    print(
        json.dumps(
            {
                "svgs": len(kept),
                "clusters": [{k: s[k] for k in ("cluster", "size", "style", "samples")} for s in summaries],
                "assigned": len(assignments),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
