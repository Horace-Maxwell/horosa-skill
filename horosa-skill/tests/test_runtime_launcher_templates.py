"""Windows 启动器模板的编码守卫 —— 让「启动器根本解析不了」这类事故在 CI 就红。

事故（v0.25.0 Windows 半边补建时发现）：`runtime_templates/windows/start_horosa_local.ps1` 是
**无 BOM** 的 UTF-8。runtime manager 用的是 `powershell`（Windows PowerShell 5.1，见
`manager._platform_command`），它对无 BOM 的 .ps1 按**系统 ANSI 代码页**解码；UTF-8 的 `—`(U+2014)
在 CP1252 下解成 `â€` + **U+201D**，而 PowerShell 的词法分析器把 U+201D 当**字符串定界符** ——
字符串就地截断 → 4 个 parse error → 启动器还没跑就死 → 整个 Windows runtime 起不来
（`runtime.start_failed`）。注释里的 `—` 无害（注释到行尾），字符串字面量里的才致命。

两道守卫：BOM + 「非 ASCII 只许出现在注释行」到处跑；真解析只在 Windows 上跑（CI 的
windows-smoke job 会执行）。
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "scripts" / "runtime_templates" / "windows"
LAUNCHERS = ("start_horosa_local.ps1", "stop_horosa_local.ps1")
BOM = b"\xef\xbb\xbf"


@pytest.mark.parametrize("name", LAUNCHERS)
def test_launcher_template_starts_with_a_utf8_bom(name: str) -> None:
    raw = (TEMPLATE_ROOT / name).read_bytes()
    assert raw.startswith(BOM), (
        f"{name} 缺 UTF-8 BOM：Windows PowerShell 5.1 会按 ANSI 代码页解码它，任何非 ASCII 字符都可能"
        "变成 U+201D（PowerShell 认它作字符串定界符）→ 启动器解析失败 → runtime.start_failed"
    )


@pytest.mark.parametrize("name", LAUNCHERS)
def test_launcher_template_keeps_non_ascii_inside_comments(name: str) -> None:
    """BOM 是正解，这条是第二层：字符串字面量里不留非 ASCII，BOM 万一被工具剥掉也不会炸成 parse error。"""
    text = (TEMPLATE_ROOT / name).read_text(encoding="utf-8-sig")
    offenders = [
        (lineno, line)
        for lineno, line in enumerate(text.splitlines(), start=1)
        if any(ord(ch) > 127 for ch in line) and not line.lstrip().startswith("#")
    ]
    assert offenders == [], f"{name} 的非注释行含非 ASCII 字符（BOM 一旦丢失即 parse error）: {offenders}"


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 只在 Windows 上可用")
@pytest.mark.parametrize("name", LAUNCHERS)
def test_launcher_template_parses_under_windows_powershell(name: str) -> None:
    """真解析：用 runtime manager 实际调用的那个 `powershell`（5.1），不是 pwsh 7。"""
    powershell = shutil.which("powershell")
    if not powershell:
        pytest.skip("powershell.exe not on PATH")
    target = TEMPLATE_ROOT / name
    probe = (
        "$errors = $null; $tokens = $null; "
        f"[void][System.Management.Automation.Language.Parser]::ParseFile('{target}', [ref]$tokens, [ref]$errors); "
        "if ($errors -and $errors.Count) { Write-Output ('PARSE_ERRORS ' + $errors.Count + ' :: ' + $errors[0].Message) } "
        "else { Write-Output 'PARSE_OK' }"
    )
    completed = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-Command", probe],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    assert "PARSE_OK" in completed.stdout, f"{name} 在 Windows PowerShell 下解析失败: {completed.stdout}{completed.stderr}"
