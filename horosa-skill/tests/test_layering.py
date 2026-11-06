"""分层：下层不 import 上层，包括躲在函数体里的 import（v0.47.2-dev）。

函数内 import 跑得通，所以这类向上的依赖不会让任何测试红：`western_options_doc` 曾在函数里 import `surfaces.mcp_schema` 与 `service`，
`client_config/payload.py` 为两个整数在模块顶层 import `surfaces.mcp_server`，于是生成客户端配置要先载入整个 MCP SDK。这里扫 AST，函数内外一视同仁。"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "horosa_skill"

# 入口：`python -m horosa_skill` 本来就从这里进 CLI。
SURFACE_IMPORT_ALLOWED = frozenset({"__main__.py"})
# 还没收拾的向上依赖，名单只许缩短：reports/ 与 knowledge/ 在别的工作线上，这一轮不动。
SERVICE_IMPORT_ALLOWED = frozenset({"reports/builder.py", "knowledge/user.py"})


def imported_modules(path: Path) -> list[tuple[int, str, str | None]]:
    """(行号, 模块, from 导入的名字)；函数体里的 import 也算，TYPE_CHECKING 里的不算。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skipped = {
        id(child)
        for node in ast.walk(tree)
        if isinstance(node, ast.If) and "TYPE_CHECKING" in ast.dump(node.test)
        for child in ast.walk(node)
    }
    found: list[tuple[int, str, str | None]] = []
    for node in ast.walk(tree):
        if id(node) in skipped:
            continue
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name, None) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.extend((node.lineno, node.module, alias.name) for alias in node.names)
    return found


def _modules_outside(*packages: str) -> list[Path]:
    return [
        path for path in sorted(PACKAGE.rglob("*.py"))
        if path.relative_to(PACKAGE).parts[0] not in packages and "__pycache__" not in path.parts
    ]


def upward_imports(paths: list[Path], target: str, allowed: frozenset[str]) -> list[str]:
    offenders: list[str] = []
    for path in paths:
        rel = path.relative_to(PACKAGE).as_posix()
        if rel in allowed:
            continue
        for lineno, module, name in imported_modules(path):
            if module == target or module.startswith(f"{target}.") or (module == "horosa_skill" and name == target.rsplit(".", 1)[-1]):
                offenders.append(f"{rel}:{lineno} -> {module}")
    return offenders


def test_nothing_below_surfaces_imports_a_surface() -> None:
    assert upward_imports(_modules_outside("surfaces"), "horosa_skill.surfaces", SURFACE_IMPORT_ALLOWED) == []


def test_only_surfaces_and_benchmark_import_the_service() -> None:
    paths = _modules_outside("surfaces", "service", "benchmark")
    assert upward_imports(paths, "horosa_skill.service", SERVICE_IMPORT_ALLOWED) == []


def test_the_scan_sees_imports_inside_functions(tmp_path: Path, monkeypatch) -> None:
    """负向对照：函数内 import 正是这条要抓的形状。"""
    monkeypatch.setattr(sys.modules[__name__], "PACKAGE", tmp_path)
    source = tmp_path / "low.py"
    source.write_text("def f():\n    from horosa_skill.surfaces.mcp_schema import x\n    return x\n", encoding="utf-8")
    assert upward_imports([source], "horosa_skill.surfaces", frozenset()) == ["low.py:2 -> horosa_skill.surfaces.mcp_schema"]


def test_the_allowlists_name_only_real_offenders() -> None:
    """名单只许缩短：修好了就从名单里删掉，别留一个不再需要的豁免。"""
    for rel in SERVICE_IMPORT_ALLOWED:
        assert upward_imports([PACKAGE / rel], "horosa_skill.service", frozenset()), f"{rel} 已不再 import service，从豁免名单删掉"


def test_surfaces_reach_the_runtime_through_public_names() -> None:
    offenders = [
        f"{path.relative_to(PACKAGE).as_posix()}:{lineno} -> {name}"
        for path in sorted((PACKAGE / "surfaces").glob("*.py")) + [PACKAGE / "config.py"]
        for lineno, module, name in imported_modules(path)
        if module.startswith("horosa_skill.runtime") and name and name.startswith("_")
    ]
    assert offenders == []


def test_config_does_not_call_a_private_runtime_helper() -> None:
    assert "_manager._platform_key" not in (PACKAGE / "config.py").read_text(encoding="utf-8")


def test_importing_the_cli_does_not_load_the_mcp_sdk() -> None:
    """`--version`、`--help`、`doctor` 用不到 MCP SDK，而它占 CLI 启动的三成。只有真子进程看得见 sys.modules。"""
    code = "import sys, horosa_skill.surfaces.cli; print(sorted(m for m in sys.modules if m == 'mcp' or m.startswith('mcp.'))[:3])"
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=dict(os.environ), timeout=120)
    assert done.returncode == 0, done.stderr[-400:]
    assert done.stdout.strip() == "[]"
