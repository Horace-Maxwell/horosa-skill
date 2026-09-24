"""子进程文本解码必须显式：`subprocess.run(..., text=True)` 而不带 `encoding=` 在 Windows 上按控制台代码页解。

v0.37.0 CI 上 `text=True` 解 CJK 子进程输出炸成 UnicodeDecodeError（cp1252），v0.38.1 复审又发现归属判定
按 UTF-8 解 OEM 代码页的 PowerShell 输出（非 ASCII 用户名的健康机器被判 foreign）。两次的根因同一个：
Python 在 Windows 上的默认文本编码不是 UTF-8。AST 扫描 src/，基线 0；合成负向对照证明守卫抓得住。
"""
from __future__ import annotations

import ast

import pytest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "horosa_skill"
_SUBPROCESS_CALLS = {"run", "Popen", "check_output", "check_call", "call"}


def text_mode_calls_without_encoding(source: str, filename: str = "<memory>") -> list[str]:
    hits: list[str] = []
    for node in ast.walk(ast.parse(source, filename=filename)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else (func.id if isinstance(func, ast.Name) else "")
        if name not in _SUBPROCESS_CALLS:
            continue
        keywords = {kw.arg for kw in node.keywords}
        text_mode = any(
            kw.arg in {"text", "universal_newlines"} and isinstance(kw.value, ast.Constant) and kw.value.value is True
            for kw in node.keywords
        )
        if text_mode and "encoding" not in keywords:
            hits.append(f"{filename}:{node.lineno}")
    return hits


def test_no_text_mode_subprocess_call_relies_on_the_console_code_page() -> None:
    hits: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        hits.extend(text_mode_calls_without_encoding(path.read_text(encoding="utf-8"), str(path.relative_to(SRC.parent))))
    assert hits == [], "这些子进程调用 text=True 却没写 encoding=：Windows 上会按 cp1252/cp936 解码 → " + ", ".join(hits)


def test_guard_catches_the_old_shape() -> None:
    """负向对照：把一处旧写法放回去必红；带 encoding= 或非文本模式的调用不误报。"""
    bad = "import subprocess\nsubprocess.run(['x'], capture_output=True, text=True, timeout=5)\n"
    assert len(text_mode_calls_without_encoding(bad)) == 1
    bad2 = "import subprocess\nsubprocess.Popen(['x'], universal_newlines=True)\n"
    assert len(text_mode_calls_without_encoding(bad2)) == 1
    good = "import subprocess\nsubprocess.run(['x'], text=True, encoding='utf-8', errors='replace')\n"
    assert text_mode_calls_without_encoding(good) == []
    binary = "import subprocess\nsubprocess.run(['x'], capture_output=True)\n"
    assert text_mode_calls_without_encoding(binary) == []


# ── v0.40.0 首推 CI（windows-smoke）：tests/ 里 7 处 `subprocess.run(["node", …], text=True)` 没给 encoding，node 吐 CJK 的
# JSON 按 cp1252 解 → UnicodeDecodeError（读线程里炸成 stdout=None → 再炸 json.loads）。src/ 的守卫盯不到 tests/，而这类
# 「测试自己起 node 复算金标」的用例是 v0.40.0 同步新增的主要测试形态。守卫只盯 node 调用（node 恒 UTF-8 输出）。
TESTS_DIR = Path(__file__).resolve().parent


def node_spawns_without_encoding(source: str, filename: str = "<memory>") -> list[str]:
    hits: list[str] = []
    for node in ast.walk(ast.parse(source, filename=filename)):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else (func.id if isinstance(func, ast.Name) else "")
        if name not in _SUBPROCESS_CALLS:
            continue
        argv = node.args[0]
        spawns_node = isinstance(argv, (ast.List, ast.Tuple)) and any(
            isinstance(el, ast.Constant) and el.value == "node" for el in argv.elts
        )
        if not spawns_node:
            continue
        keywords = {kw.arg for kw in node.keywords}
        text_mode = any(
            kw.arg in {"text", "universal_newlines"} and isinstance(kw.value, ast.Constant) and kw.value.value is True
            for kw in node.keywords
        )
        if text_mode and "encoding" not in keywords:
            hits.append(f"{filename}:{node.lineno}: subprocess.{name}([\"node\", …], text=True) without encoding=")
    return hits


def test_tests_that_spawn_node_decode_its_output_as_utf8() -> None:
    hits: list[str] = []
    for path in sorted(TESTS_DIR.glob("*.py")):
        hits.extend(node_spawns_without_encoding(path.read_text(encoding="utf-8"), path.name))
    assert hits == [], "\n".join(hits)


def test_node_spawn_guard_catches_the_old_shape() -> None:
    old = 'import subprocess\nout = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout\n'
    assert node_spawns_without_encoding(old, "x.py") == ['x.py:2: subprocess.run(["node", …], text=True) without encoding=']
    fixed = old.replace("text=True", 'text=True, encoding="utf-8"')
    assert node_spawns_without_encoding(fixed, "x.py") == []
    # 不是 node 的子进程（python 自身、bash）不在本守卫范围（由 src 守卫与各自测试负责）。
    assert node_spawns_without_encoding('subprocess.run(["bash", "-c", "x"], text=True)', "y.py") == []


# ── v0.40.0 首推 windows-smoke 第二轮：node ESM `import(process.argv[1])` 在 Windows 上不接受裸盘符绝对路径
# （ERR_UNSUPPORTED_ESM_URL_SCHEME ×18），只认 file:// URL；macOS / Linux 的 /abs/x.js 恰好能过 → 本机全绿。
# 统一走 tests/node_esm.py（Path → as_uri），并禁止别处再写 --input-type=module。
from pathlib import PureWindowsPath, PurePosixPath  # noqa: E402

import node_esm  # noqa: E402


def test_esm_spawns_in_tests_all_go_through_the_node_esm_helper() -> None:
    offenders = [
        f"{path.name}:{lineno}"
        for path in sorted(TESTS_DIR.glob("*.py"))
        if path.name not in {"node_esm.py", Path(__file__).name}
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if "--input-type=module" in line
    ]
    assert offenders == [], f"use node_esm.run_node_esm(...) instead of spawning node ESM by hand: {offenders}"


def test_node_esm_helper_turns_module_paths_into_file_urls_and_rejects_bare_strings(tmp_path: Path) -> None:
    module = tmp_path / "m.js"
    module.write_text("export const x = 1;", encoding="utf-8")
    argv = node_esm.esm_argv("import(process.argv[1])", module, "plain-arg", "42")
    assert argv[:3] == ["node", "--input-type=module", "-e"] and argv[4] == module.resolve().as_uri()
    assert argv[4].startswith("file:///") and argv[5:] == ["plain-arg", "42"]
    # Windows 盘符路径 → file:///D:/… （as_uri 的规范形）；POSIX 同理。
    assert PureWindowsPath("D:/a/horosa-skill/x.js").as_uri() == "file:///D:/a/horosa-skill/x.js"
    assert PurePosixPath("/Users/x/y.mjs").as_uri() == "file:///Users/x/y.mjs"
    # 负向对照：Windows 上会炸的形状（字符串形式的绝对 .js 路径）在三平台都直接拒绝。
    for bad in ("/Users/x/vendor/GuaZhanMain.js", "D:\\a\\horosa-skill\\x.js", "C:/a/b.mjs"):
        with pytest.raises(ValueError):
            node_esm.esm_argv("import(process.argv[1])", bad)

