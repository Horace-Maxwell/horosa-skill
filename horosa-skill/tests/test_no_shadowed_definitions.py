"""一个模块里同名的顶层函数 / 类定义两次：后一个静默顶掉前一个（审计 F06 顺带查出：input_fields 里钟点用的 _cn_number
被农历那个 _cn_number 顶掉，「二十三点」KeyError、「十二三点」读成 12 点）。ruff F811 抓不到——前一个在函数体里被引用过就算「用过」。

负向对照（实跑过）：把 input_fields._cn_lunar_number 改回 _cn_number → 红。
"""
from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

ROOTS = [Path(__file__).resolve().parents[1] / "src" / "horosa_skill", Path(__file__).resolve().parents[1] / "scripts"]


def test_no_module_defines_the_same_top_level_name_twice() -> None:
    clashes = []
    for root in ROOTS:
        for path in sorted(root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            names = Counter(node.name for node in tree.body
                            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))
            clashes += [f"{path.relative_to(root.parent)}: {name} ×{count}" for name, count in names.items() if count > 1]
    assert not clashes, clashes
