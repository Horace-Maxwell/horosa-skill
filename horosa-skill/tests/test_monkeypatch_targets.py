"""monkeypatch 的目标必须真的被它所在的模块用到（2026-10 可维护性重构的前置护栏）。

**为什么旧检查抓不到**：把函数 `f` 从模块 A 挪到 B、A 里留一行 `from B import f` 做兼容时，测试里的
`monkeypatch.setattr("horosa_skill.A.f", fake)` 照样成功——但 B 里的代码查的是 B 自己的 `f`，替身从此不起作用，
测试继续绿，只是「因为错误的原因通过」。重构要动 service.py（18k 行）与 cli.py 等大模块，94 处这样的 patch 点
（审计计数）都可能悄悄失效。本守卫：被 patch 的名字若在目标模块里**只是被 import 进来**、模块自己的代码又从不使用它，
即判红——替身打在了一个没人查的名字上。负向对照见最后一条。
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest

PKG_ROOT = Path(__file__).resolve().parents[1]
SRC = PKG_ROOT / "src"
TESTS = PKG_ROOT / "tests"


def _module_file(dotted: str) -> Path | None:
    """Source file when `dotted` names a horosa_skill MODULE; None for classes / objects (`manager.HorosaRuntimeManager`)."""
    if not dotted.startswith("horosa_skill"):
        return None
    try:
        spec = importlib.util.find_spec(dotted)
    except (ModuleNotFoundError, AttributeError, ValueError):
        return None  # the last component is a class or other object inside a module
    return Path(spec.origin) if spec and spec.origin else None


def useless_patch_reason(module_source: str, name: str) -> str | None:
    """Why patching `module.name` would reach nothing (None = fine). Pure: works on source text."""
    tree = ast.parse(module_source)
    imported: set[str] = set()
    defined: set[str] = set()
    loads: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom | ast.Import):
            for alias in node.names:
                imported.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            defined.add(node.name)
        elif isinstance(node, ast.Name):
            (defined if isinstance(node.ctx, ast.Store) else loads).add(node.id)
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            loads.add(node.value.id)
    if name in defined or name in loads:
        return None
    if name in imported:
        return f"`{name}` is only imported into the module and never used by its own code — the patch reaches nothing"
    return None


def _patch_targets() -> list[tuple[str, int, str, str]]:
    """[(test file, line, module dotted path, attribute)] for every monkeypatch.setattr aimed at a horosa_skill module."""
    out: list[tuple[str, int, str, str]] = []
    for path in sorted(TESTS.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        aliases: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("horosa_skill"):
                for alias in node.names:
                    aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("horosa_skill"):
                        aliases[alias.asname or alias.name] = alias.name
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "setattr" and node.args):
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str) and first.value.startswith("horosa_skill."):
                module, _, attr = first.value.rpartition(".")
                out.append((path.name, node.lineno, module, attr))
            elif isinstance(first, ast.Name) and first.id in aliases and len(node.args) >= 2 \
                    and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                out.append((path.name, node.lineno, aliases[first.id], node.args[1].value))
    return out


def test_every_monkeypatch_target_is_used_by_its_module() -> None:
    targets = _patch_targets()
    assert len(targets) > 50, "the scanner found suspiciously few patch sites — did the test layout change?"
    problems = []
    for test_file, line, module, attr in targets:
        source_path = _module_file(module)
        if source_path is None or source_path.suffix != ".py":
            continue  # a class or a non-module object: attribute patches on objects are not this guard's concern
        reason = useless_patch_reason(source_path.read_text(encoding="utf-8"), attr)
        if reason:
            problems.append(f"{test_file}:{line} patches {module}.{attr}: {reason}")
    assert problems == [], "\n".join(problems)


def test_guard_flags_a_reexport_only_name_and_passes_a_used_one() -> None:
    """负向对照：只 re-export 不使用 → 红；模块自己调用 / 自己定义 → 绿。"""
    reexport_only = "from horosa_skill.service_parts import build_text\n__all__ = ['build_text']\n"
    assert useless_patch_reason(reexport_only, "build_text") is not None
    used_here = "from horosa_skill.service_parts import build_text\n\ndef run():\n    return build_text()\n"
    assert useless_patch_reason(used_here, "build_text") is None
    defined_here = "def build_text():\n    return ''\n"
    assert useless_patch_reason(defined_here, "build_text") is None
    module_attr_use = "import datetime\n\ndef now():\n    return datetime.datetime.now()\n"
    assert useless_patch_reason(module_attr_use, "datetime") is None


@pytest.mark.parametrize("dotted", ["horosa_skill.service", "horosa_skill.surfaces.cli", "horosa_skill.runtime.manager"])
def test_scanner_sees_the_big_modules(dotted: str) -> None:
    assert any(module == dotted for _f, _l, module, _a in _patch_targets()), f"no patch sites found on {dotted}"
