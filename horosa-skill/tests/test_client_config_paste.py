"""`client config` 打印给人复制的命令：粘进 cmd 与 PowerShell 各读成什么（v0.50.2-dev，Windows 本机粘贴矩阵）。

- claude-code 的 `command`（README 教的那条）此前走 _format_cli_command：光写的 `--` 在 PowerShell + npm 装的 claude.ps1 里被吃掉，
  任何路径都坏；现在与 setup 同一个 claude_cli.shell_text。`alternative_http` 的提示里多拼了一个 `serve`。
- VS Code 的 JSON 参数没有共同写法：cmd 一条、PowerShell 一条；`code` 是 code.cmd，会被 cmd 再拆一遍，路径里有 & | < > ^ % 时
  两条都不给。旧的 cmd 写法在路径以 \\ 结尾时 JSON 坏掉，PowerShell 里一律坏。
- wheel 装出来的包跑 `client config` 不带 --launcher，此前报「Path must point to …」；现在缺省与 setup 同。
Windows 上另有一条真起 cmd / Windows PowerShell / pwsh 的用例（替身记录 argv）。
"""
from __future__ import annotations

import functools
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import winshell
from typer.testing import CliRunner

from horosa_skill.client_config import claude_cli
from horosa_skill.client_config import payload as client_payload
from horosa_skill.surfaces.cli import app

runner = CliRunner()
_UVX = r"C:\Users\O'Neil 张 (三)\AppData\Local\uv\uvx.exe"


def _payload(*args: str) -> dict:
    result = runner.invoke(app, ["client", "config", *args])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in [name for name in os.environ if name.startswith("HOROSA_")]:
        monkeypatch.delenv(key)


def _claude_add_argv(payload: dict) -> list[str]:
    entry = payload["mcpServers"]["horosa"]
    env = [item for key, value in entry.get("env", {}).items() for item in ("-e", f"{key}={value}")]
    return ["claude", "mcp", "add", "horosa", *env, "--", entry["command"], *entry["args"]]


def test_claude_code_command_reads_the_same_in_cmd_and_powershell(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setattr(client_payload, "resolve_uvx_command", lambda: [_UVX])
    monkeypatch.setattr(claude_cli, "shell_text", functools.partial(claude_cli.shell_text, os_name="nt"))
    payload = _payload("--format", "claude-code", "--launcher", "uvx-wheel", "--output-script", "zh-Hant")
    wanted = _claude_add_argv(payload)
    assert "-e" in wanted and wanted[-1] == "stdio"
    assert winshell.cmd_argv(payload["command"]) == wanted
    assert winshell.powershell_argv(payload["command"]) == wanted, "PowerShell + claude.ps1 吃掉光写的 --"
    http = payload["alternative_http"]
    assert winshell.powershell_argv(http["command"]) == winshell.cmd_argv(http["command"])
    assert "serve serve" not in http["note"] and claude_cli.shell_text([_UVX, "--from"]) in http["note"]


def test_cmd_fallback_still_quotes_the_double_dash() -> None:
    """没有共同写法（这里是 %）时退回 cmd 写法，`--` 仍写成 "--"：路径只含 % 时 PowerShell 那边照样粘得进去。"""
    command = ["claude", "mcp", "add", "horosa", "-e", r"HOROSA_SKILL_DATA_DIR=C:\100%\data", "--", r"C:\uv\uvx.exe", "serve"]
    text = claude_cli.shell_text(command, os_name="nt")
    assert ' "--" ' in text and winshell.crt_argv(text) == command
    assert winshell.powershell_argv(text) == command


def _vscode_entry(data_dir: str) -> dict:
    return {"name": "horosa", "command": r"C:\Program Files\uv\uvx.exe", "args": ["--from", "https://x/y.whl", "horosa-skill", "serve"],
            "env": {"HOROSA_SKILL_DATA_DIR": data_dir}}


def _through_code_cmd(native_args: str) -> list[str]:
    """code.cmd 那一跳：cmd 拆一遍（引号外的 & | < > ^、%），%* 原样转给 Code.exe，再按 C 运行库拆。"""
    return winshell.cmd_argv("code " + native_args)[1:]


def _powershell_single_quoted(text: str) -> str:
    """PowerShell 单引号字面量 → 调 .cmd 时旧式传参写出的那段命令行（含空格就整段加双引号）。"""
    prefix = "code --add-mcp '"
    assert text.startswith(prefix) and text.endswith("'") and "'" not in text[len(prefix):-1].replace("''", "")
    value = text[len(prefix):-1].replace("''", "'")
    return "--add-mcp " + (f'"{value}"' if " " in value else value)


SAFE_DIRS = [r"C:\Users\x\data", r"C:\Users\John Smith 测试\data", r"C:\Users\O'Neil (x)\data", "C:\\Users\\x\\", r"D:\a$b\data"]
SPLIT_DIRS = [r"C:\Users\A & B\data", r"C:\Users\100%\data", r"C:\Users\a^b\data", r"C:\a|b", r"C:\a<b>"]


@pytest.mark.parametrize("data_dir", SAFE_DIRS)
def test_vscode_windows_commands_round_trip_the_json(data_dir: str) -> None:
    entry = _vscode_entry(data_dir)
    commands = client_payload._vscode_windows_commands(json.dumps(entry, ensure_ascii=False))
    cmd_text = commands["cli_command_windows"]
    assert cmd_text.startswith("code ")
    flag, value = _through_code_cmd(cmd_text[len("code "):])
    assert flag == "--add-mcp" and json.loads(value) == entry, cmd_text
    flag, value = _through_code_cmd(_powershell_single_quoted(commands["cli_command_powershell"]))
    assert flag == "--add-mcp" and json.loads(value) == entry, commands["cli_command_powershell"]


@pytest.mark.parametrize("data_dir", SPLIT_DIRS)
def test_vscode_windows_commands_are_withheld_when_cmd_would_split_them(data_dir: str) -> None:
    commands = client_payload._vscode_windows_commands(json.dumps(_vscode_entry(data_dir), ensure_ascii=False))
    assert set(commands) == {"cli_command_windows_note"} and "install_link" in commands["cli_command_windows_note"]


def test_vscode_posix_command_survives_an_apostrophe(monkeypatch: pytest.MonkeyPatch) -> None:
    import shlex

    _clean_env(monkeypatch)
    monkeypatch.setattr(client_payload, "resolve_uvx_command", lambda: ["/Users/o'neil/.local/bin/uvx"])
    payload = _payload("--format", "vscode", "--launcher", "uvx-wheel")
    words = shlex.split(payload["cli_command"])
    assert words[:2] == ["code", "--add-mcp"] and json.loads(words[2])["command"] == "/Users/o'neil/.local/bin/uvx"
    assert "cli_command_powershell" in payload and "cli_command_powershell" in payload["note"]


def test_client_config_outside_a_checkout_defaults_to_the_wheel_launcher(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setattr(client_payload, "resolve_uvx_command", lambda: ["/opt/uv/bin/uvx"])
    payload = _payload("--format", "claude-desktop", "--skill-root", str(tmp_path))
    assert payload["launcher"]["kind"] == "uvx-wheel"
    assert payload["mcpServers"]["horosa"]["args"][:1] == ["--from"]


# ---- 真终端：cmd / Windows PowerShell / pwsh 各粘一遍，替身 claude.cmd + claude.ps1（npm 装法）与 code.cmd 记下 argv ----

_DUMP = "import json, os, sys\nwith open(os.environ['DUMP_OUT'], 'a', encoding='utf-8') as f:\n    f.write(json.dumps(sys.argv[1:]) + '\\n')\n"


def _stubs(root: Path) -> Path:
    stub = root / "stubs"
    stub.mkdir()
    (root / "dump.py").write_text(_DUMP, encoding="utf-8")
    line = f'"{sys.executable}" "{root / "dump.py"}"'
    (stub / "claude.cmd").write_text(f"@{line} %*\r\n", encoding="utf-8")
    (stub / "claude.ps1").write_text(f"& {line.replace(chr(34), chr(39))} $args\nexit $LASTEXITCODE\n", encoding="utf-8")
    (stub / "code.cmd").write_text(f"@echo off\r\nsetlocal\r\n{line} %*\r\nendlocal\r\n", encoding="utf-8")
    return stub


def _run_in(shell: str, text: str, root: Path, stub: Path) -> list[str] | None:
    dump = root / "dump.jsonl"
    dump.unlink(missing_ok=True)
    env = {**os.environ, "PATH": f"{stub}{os.pathsep}{os.environ['PATH']}", "DUMP_OUT": str(dump)}
    if shell == "cmd":
        argv: str | list[str] = f'cmd.exe /d /s /c "{text}"'  # 交互粘贴的规则（.bat 文件对 % 另有一套）
    else:
        script = root / "pasted.ps1"
        script.write_text("\ufeff" + text + "\n", encoding="utf-8")  # 无 BOM 时 5.1 按 ANSI 读
        argv = [shell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script)]
    subprocess.run(argv, env=env, capture_output=True, timeout=120, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return json.loads(dump.read_text(encoding="utf-8").splitlines()[0]) if dump.exists() else None


@pytest.mark.skipif(os.name != "nt", reason="[platform] cmd / PowerShell 只在 Windows 上有")
def test_printed_commands_in_real_windows_shells(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setattr(client_payload, "resolve_uvx_command", lambda: [_UVX])
    root = tmp_path / "paste test"  # 替身 .cmd 按 OEM 代码页读，路径不放中文（真 npm 替身用 %~dp0）；中文在被粘的命令里
    root.mkdir()
    stub = _stubs(root)
    claude = _payload("--format", "claude-code", "--launcher", "uvx-wheel", "--output-script", "zh-Hant")
    vscode = _payload("--format", "vscode", "--launcher", "uvx-wheel", "--output-script", "zh-Hant")
    entry = vscode["servers"]["horosa"]
    wanted_json = {"name": "horosa", "command": entry["command"], "args": entry["args"], "env": entry["env"]}
    powershells = [name for name in ("powershell.exe", "pwsh.exe") if shutil.which(name)]
    assert powershells, "Windows 上至少有 Windows PowerShell"
    for shell in ["cmd", *powershells]:
        assert _run_in(shell, claude["command"], root, stub) == _claude_add_argv(claude)[1:], shell
        text = vscode["cli_command_windows" if shell == "cmd" else "cli_command_powershell"]
        got = _run_in(shell, text, root, stub)
        assert got is not None and got[0] == "--add-mcp" and json.loads(got[1]) == wanted_json, (shell, got)
