"""子进程文本解码必须显式：`subprocess.run(..., text=True)` 而不带 `encoding=` 在 Windows 上按控制台代码页解。

v0.37.0 CI 上 `text=True` 解 CJK 子进程输出炸成 UnicodeDecodeError（cp1252），v0.38.1 复审又发现归属判定
按 UTF-8 解 OEM 代码页的 PowerShell 输出（非 ASCII 用户名的健康机器被判 foreign）。两次的根因同一个：
Python 在 Windows 上的默认文本编码不是 UTF-8。AST 扫描 src/，基线 0；合成负向对照证明守卫抓得住。
"""
from __future__ import annotations

import ast
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
