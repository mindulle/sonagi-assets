#!/usr/bin/env python3
"""장식 모티프를 데이터(SVG 템플릿)로 그린다.

`styles/ornaments.json`의 항목은 요소 목록이다.

    {
      "el": "line",
      "attrs": {"x1": "{x1}", "y1": "{y}", "stroke": "{accent}"},
      "repeat": [{"s": -1}, {"s": 1}]        // 선택: 변수 묶음을 반복
    }

`{표현식:포맷}`은 숫자·문자 모두 가능하다. 표현식은 사칙연산과 변수만
허용하고(함수 호출·속성 접근 금지), `ast`로 검사한 뒤 계산한다.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "styles" / "ornaments.json"

_ALLOWED = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Constant,
    ast.Name,
    ast.Load,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.USub,
    ast.UAdd,
)
_OPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
}


def _eval(expr: str, variables: dict):
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise ValueError(f"장식 표현식에 허용되지 않은 구문: {expr}")
        if isinstance(node, ast.Name) and node.id not in variables:
            raise ValueError(f"장식 표현식의 알 수 없는 변수: {node.id}")

    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return variables[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = walk(node.operand)
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](walk(node.left), walk(node.right))
        raise ValueError(f"장식 표현식에 허용되지 않은 구문: {expr}")

    return walk(tree)


def _fill(template: str, variables: dict) -> str:
    out = []
    i = 0
    while i < len(template):
        ch = template[i]
        if ch != "{":
            out.append(ch)
            i += 1
            continue
        end = template.find("}", i + 1)
        if end < 0:
            raise ValueError(f"장식 템플릿의 닫히지 않은 중괄호: {template}")
        body = template[i + 1 : end]
        expr, _, spec = body.partition(":")
        value = _eval(expr.strip(), variables)
        out.append(format(value, spec.strip()) if spec else str(value))
        i = end + 1
    return "".join(out)


def load(path: Path | None = None) -> dict:
    return json.loads((path or DATA_PATH).read_text())


def draw(kind: str, name: str, variables: dict, data: dict | None = None) -> str:
    data = data or load()
    elements = (data.get(kind) or {}).get(name)
    if not elements:
        return ""
    parts = []
    for element in elements:
        if "elements" in element:
            # 한 변수 묶음 안에서 여러 요소를 순서대로 그린다(모서리 path+circle 등)
            for binding in element.get("repeat") or [{}]:
                local = dict(variables)
                for key, value in binding.items():
                    if isinstance(value, str) and "{" in value:
                        text = _fill(value, variables)
                        try:
                            local[key] = float(text) if "." in text else int(text)
                        except ValueError:
                            local[key] = text
                    else:
                        local[key] = value
                for child in element["elements"]:
                    attrs = " ".join(f'{key}="{_fill(str(val), local)}"' for key, val in child["attrs"].items())
                    parts.append(f"<{child['el']} {attrs}/>")
            continue
        tag = element["el"]
        repeats = element.get("repeat") or [{}]
        for binding in repeats:
            variables_local = dict(variables)
            for key, value in binding.items():
                if isinstance(value, str) and "{" in value:
                    text = _fill(value, variables)
                    try:
                        variables_local[key] = float(text) if "." in text else int(text)
                    except ValueError:
                        variables_local[key] = text
                else:
                    variables_local[key] = value
            attrs = " ".join(f'{key}="{_fill(str(val), variables_local)}"' for key, val in element["attrs"].items())
            parts.append(f"<{tag} {attrs}/>")
    return "".join(parts)
