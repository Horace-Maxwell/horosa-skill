"""service 包的结构约束（v0.41.1 可维护性重构：service.py 18k 行拆成包）。

拆分只搬不改；这些测试锁住「搬完以后还能被安全地继续搬」的几条前提——每条都对应一种会让测试安静变绿的错法。
"""
from __future__ import annotations

import ast
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parents[1] / "src" / "horosa_skill" / "service"


def _modules() -> dict[str, ast.Module]:
    return {
        path.relative_to(SERVICE_DIR).as_posix(): ast.parse(path.read_text(encoding="utf-8"))
        for path in sorted(SERVICE_DIR.rglob("*.py"))
    }


def test_the_service_reads_the_clock_only_through_the_clock_seam() -> None:
    # 冻结时间的测试 patch 的是 service._clock.datetime；任何直接 `datetime.now(` 都会绕过它，
    # 那几条金标测试就会在真实「今天」上跑（今天对、明年错）。
    offenders = [
        f"{name}:{node.lineno}"
        for name, tree in _modules().items()
        if name != "_clock.py"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"now", "utcnow", "today"}
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in {"datetime", "date"}
    ]
    assert not offenders, f"read the time via `_clock.now(...)`: {offenders}"
