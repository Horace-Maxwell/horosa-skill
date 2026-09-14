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


# --- v0.38.0 B1: spaced / CJK paths, loopback bind, JSON-escaped bootstrap ---------------------------
#
# Start-Process joins -ArgumentList elements with spaces and does NOT quote them: a runtime root under
# `C:\Users\John Doe\…` split the bootstrap path in two and neither service ever started. The Java line
# also lacked --server.address=127.0.0.1 (Spring Boot binds 0.0.0.0 → Firewall prompt + LAN exposure).

import ast
import importlib.util
import json
import re
import runpy
import sys

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_runtime_scripts.py"
_spec = importlib.util.spec_from_file_location("verify_runtime_scripts", _SCRIPT)
_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_guard)

START = TEMPLATE_ROOT / "start_horosa_local.ps1"
_JSON_EMBED = re.compile(r"\$\(ConvertTo-Json \$(?P<name>[A-Za-z_]+) -Compress\)")
_SPACED_CJK = {
    "FlatlibRoot": r"C:\Users\张 三\AppData\Local\Horosa\runtime\current\Horosa-Web\flatlib-ctrad2",
    "AstropyRoot": r"C:\Users\张 三\AppData\Local\Horosa\runtime\current\Horosa-Web\astropy",
    "VendorRoot": r"C:\Users\张 三\AppData\Local\Horosa\runtime\current\Horosa-Web\vendor",
    "ChartEntry": r"C:\Users\张 三\AppData\Local\Horosa\runtime\current\Horosa-Web\astropy\websrv\webchartsrv.py",
}


def _start_text() -> str:
    return START.read_text(encoding="utf-8-sig")


def _bootstrap_body(text: str) -> str:
    head = text.index('$PyBootCode = @"\n') + len('$PyBootCode = @"\n')
    tail = text.index('\n"@', head)
    return text[head:tail]


def _render(body: str, values: dict[str, str]) -> str:
    """Simulate PowerShell's here-string expansion of `$(ConvertTo-Json $X -Compress)` with json.dumps."""
    return _JSON_EMBED.sub(lambda m: json.dumps(values[m.group("name")], ensure_ascii=False), body)


def test_windows_launcher_binds_java_to_loopback() -> None:
    java_line = next(line for line in _start_text().splitlines() if line.startswith("$JavaProc = Start-Process"))
    assert "--server.port=$BackendPort" in java_line
    assert "--server.address=127.0.0.1" in java_line, "Spring Boot binds 0.0.0.0 without it: Firewall prompt + LAN exposure"


def test_windows_launcher_quotes_every_path_argument() -> None:
    text = _start_text()
    py_line = next(line for line in text.splitlines() if line.startswith("$PyProc = Start-Process"))
    java_line = next(line for line in text.splitlines() if line.startswith("$JavaProc = Start-Process"))
    assert "('\"{0}\"' -f $PyBootstrapPath)" in py_line
    assert "('\"{0}\"' -f $JarPath)" in java_line
    code = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
    assert "-ArgumentList @($" not in code, "a bare path element is split on the first space by Start-Process"


def test_guard_catches_the_unquoted_and_unbound_forms() -> None:
    """Negative control: the template exactly as shipped before v0.38.0 must be red on every count."""
    good = _start_text()
    legacy = (
        good.replace("('\"{0}\"' -f $PyBootstrapPath)", "@($PyBootstrapPath)")
        .replace("('\"{0}\"' -f $JarPath)", "$JarPath")
        .replace('"--server.address=127.0.0.1", ', "")
        .replace("$(ConvertTo-Json $ChartEntry -Compress)", 'r"$ChartEntry"')
    )
    errors = _guard.audit_windows_launcher(legacy)
    joined = "\n".join(errors)
    assert "--server.address" in joined and "-jar" in joined and "bootstrap 路径没带引号" in joined and "raw" in joined, errors
    assert _guard.audit_windows_launcher(good) == []


def test_windows_bootstrap_renders_valid_python_for_cjk_and_spaced_roots(monkeypatch: pytest.MonkeyPatch) -> None:
    body = _bootstrap_body(_start_text())
    rendered = _render(body, _SPACED_CJK)
    ast.parse(rendered)  # a JSON string literal is a valid Python string literal
    captured: dict[str, object] = {}
    monkeypatch.setattr(runpy, "run_path", lambda path, run_name=None: captured.setdefault("path", path))
    monkeypatch.setattr(sys, "path", list(sys.path))
    exec(compile(rendered, "<bootstrap>", "exec"), {"__name__": "__main__"})
    assert captured["path"] == _SPACED_CJK["ChartEntry"]
    for key in ("FlatlibRoot", "AstropyRoot", "VendorRoot"):
        assert _SPACED_CJK[key] in sys.path[:3], key


@pytest.mark.parametrize(
    "value",
    ["D:\\horosa\\runtime\\current\\", 'C:\\Users\\a"b\\webchartsrv.py'],
    ids=["trailing-backslash", "embedded-quote"],
)
def test_legacy_raw_string_embed_breaks_on_these_paths(value: str) -> None:
    """Negative control for the old r"$Var" form: a trailing backslash or an embedded quote is a syntax error."""
    legacy = 'runpy.run_path(r"{ChartEntry}", run_name="__main__")\n'.replace("{ChartEntry}", value)
    with pytest.raises(SyntaxError):
        ast.parse(legacy)
    ok = 'runpy.run_path(' + json.dumps(value) + ', run_name="__main__")\n'
    ast.parse(ok)


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 只在 Windows 上可用")
def test_windows_bootstrap_renders_under_real_powershell(tmp_path: Path) -> None:
    """The real engine: PowerShell 5.1 expands the here-string with a spaced+CJK root, CPython must compile it."""
    powershell = shutil.which("powershell")
    if not powershell:
        pytest.skip("powershell.exe not on PATH")
    body = _bootstrap_body(_start_text())
    assignments = "\n".join(f"${name} = '{value}'" for name, value in _SPACED_CJK.items())
    out = tmp_path / "bootstrap.py"
    script = f"{assignments}\n$PyBootCode = @\"\n{body}\n\"@\nSet-Content -LiteralPath '{out}' -Value $PyBootCode -Encoding utf8\n"
    probe = tmp_path / "render.ps1"
    probe.write_bytes(BOM + script.encode("utf-8"))
    subprocess.run([powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(probe)], check=True, timeout=120)
    rendered = out.read_text(encoding="utf-8-sig")
    tree = ast.parse(rendered)
    strings = [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)]
    assert _SPACED_CJK["ChartEntry"] in strings


@pytest.mark.parametrize("name", LAUNCHERS)
def test_launcher_template_sets_utf8_output_encoding(name: str) -> None:
    """v0.38.1 A1：Windows PowerShell 5.1 往管道写 OEM 代码页；启动器首行把 Console 编码改成 UTF-8，
    `launcher.log` 与 `startup_warning.details.stdout` 才真是 UTF-8（manager 按 UTF-8 读它们）。"""
    text = (TEMPLATE_ROOT / name).read_text(encoding="utf-8-sig")
    first_code = next(line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#"))
    assert "[Console]::OutputEncoding = [Text.Encoding]::UTF8" in first_code, first_code
    assert first_code.isascii(), "这一行必须在 BOM 之后第一行且纯 ASCII —— 它自己不能依赖任何编码"
    assert first_code.lstrip().startswith("try {") and "catch" in first_code, "老 PowerShell / 受限主机上失败也不能挡启动"
