"""字典字面量里的重复键：后写的那条静默覆盖先写的，Python 不报错，CI 也不跑 ruff。

v0.48.0 合并时发现 errors.RECOVERY_TABLE 里 `tool.invalid_payload` 写了两遍：后加的「参数没解析成对象」把
「按校验错误逐项改」盖掉，于是所有字段校验错误的 hint 都指错了方向。这里用 AST 扫 src/ 与 scripts/ 的全部
字典字面量（只认常量键；`**展开` 与计算键不算），有重复就红。
"""

from __future__ import annotations

import ast
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
ROOTS = (PKG / "src", PKG / "scripts")


def duplicate_constant_keys(source: str, filename: str = "<src>") -> list[tuple[int, object]]:
    found: list[tuple[int, object]] = []
    for node in ast.walk(ast.parse(source, filename=filename)):
        if not isinstance(node, ast.Dict):
            continue
        seen: set[object] = set()
        for key in node.keys:
            if not isinstance(key, ast.Constant):
                continue
            marker = (type(key.value).__name__, key.value)
            if marker in seen:
                found.append((key.lineno, key.value))
            seen.add(marker)
    return found


def test_detector_catches_a_repeated_key() -> None:
    assert duplicate_constant_keys('T = {"a": 1, "b": 2, "a": 3}') == [(1, "a")]
    assert duplicate_constant_keys('T = {"a": 1, **other, 1: 2, True: 3}') == []


def test_no_dict_literal_in_the_package_repeats_a_key() -> None:
    offenders = []
    for root in ROOTS:
        for path in sorted(root.rglob("*.py")):
            for line, key in duplicate_constant_keys(path.read_text(encoding="utf-8"), str(path)):
                offenders.append(f"{path.relative_to(PKG)}:{line} {key!r}")
    assert not offenders, "dict literal repeats a key (the later one silently wins):\n" + "\n".join(offenders)
