"""CLI 的 stdout / stderr 在任何代码页下都是 UTF-8（v0.47.2-dev，Windows 原生复验）。

默认 Windows 上管道 / 重定向的文本流是 ANSI 代码页：实测 cp1252 下 60 个命令 55 个 `--help` 抛 UnicodeEncodeError；stderr 的 JSON 错误信封
不是合法 UTF-8，只有 shell 的 agent 按 SKILL.md 契约读 `code` 时 UnicodeDecodeError。`PYTHONIOENCODING=cp1252` 让任何平台都复现同一形状
（CliRunner 换掉了真流，抓不到——必须起真子进程）。
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from horosa_skill.surfaces.cli import _utf8_stdio

PKG_ROOT = Path(__file__).resolve().parents[1]


def _cli(tmp_path: Path, *args: str, module: str = "horosa_skill") -> subprocess.CompletedProcess[bytes]:
    # Typer 见到 GITHUB_ACTIONS / FORCE_COLOR / PY_COLORS 就强制终端模式，rich 把 `--input` 拆成 `\x1b[1;36m-\x1b[0m\x1b[1;36m-input`，
    # 字面子串查不到（只在 Linux runner 红：Windows 上 rich 的旧控制台判定不出 ANSI，本机复现不了）。这里只测编码，关掉终端模式。
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("HOROSA_") and k not in {"PYTHONUTF8", "GITHUB_ACTIONS", "FORCE_COLOR", "PY_COLORS"}}
    env.update({
        "_TYPER_FORCE_DISABLE_TERMINAL": "1",
        "PYTHONIOENCODING": "cp1252",
        "HOROSA_SKILL_DATA_DIR": str(tmp_path / "data"),
        "HOROSA_RUNTIME_ROOT": str(tmp_path / "rt"),
        "HOROSA_SERVER_ROOT": "http://127.0.0.1:9",
        "HOROSA_CHART_SERVER_ROOT": "http://127.0.0.1:9",
    })
    return subprocess.run([sys.executable, "-m", module, *args], capture_output=True, env=env, cwd=PKG_ROOT, timeout=120, check=False)


@pytest.mark.parametrize(
    ("args", "needle"),
    [
        (["--help"], "本地术数"),
        (["doctor", "--help"], "doctor"),
        (["setup", "--help"], "一条命令接入"),
        (["tool", "run", "--help"], "--input"),
    ],
)
def test_help_is_utf8_under_a_legacy_code_page(tmp_path: Path, args: list[str], needle: str) -> None:
    result = _cli(tmp_path, *args)
    assert result.returncode == 0, result.stderr[-600:]
    assert needle in result.stdout.decode("utf-8")


def test_every_module_entry_point_gets_the_fix(tmp_path: Path) -> None:
    result = _cli(tmp_path, "--help", module="horosa_skill.surfaces.cli")
    assert result.returncode == 0, result.stderr[-600:]
    assert "本地术数" in result.stdout.decode("utf-8")


def test_gate_error_on_stderr_is_parseable_utf8_json(tmp_path: Path) -> None:
    """SKILL.md 的 shell 契约：退出码 2 + stderr JSON 的 code / details.agent_recovery。"""
    payload = tmp_path / "birth.json"
    payload.write_text(json.dumps({"date": "1995-06-03", "time": "05:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"}), encoding="utf-8")
    result = _cli(tmp_path, "tool", "run", "chart", "--input", str(payload))
    assert result.returncode == 2 and result.stdout == b""
    text = result.stderr.decode("utf-8")  # 修复前：UnicodeDecodeError（裸 cp1252 字节）
    envelope = json.loads(text[text.index("{"):])
    assert envelope["code"] == "agent_guidance.required"
    prompt = envelope["details"]["agent_recovery"]["prompt_to_user"]
    assert any("一" <= ch <= "鿿" for ch in prompt), "问用户的话必须是真中文，不是 \\uXXXX 转义"
    assert "\\u" not in prompt


def _text_stream(encoding: str) -> io.TextIOWrapper:
    return io.TextIOWrapper(io.BytesIO(), encoding=encoding)


def test_legacy_stream_becomes_utf8_and_utf8_is_left_alone() -> None:
    legacy, utf8 = _text_stream("cp1252"), _text_stream("utf-8")
    utf8.reconfigure(errors="strict")
    _utf8_stdio(legacy, utf8)
    assert legacy.encoding == "utf-8" and legacy.errors == "backslashreplace"
    assert utf8.errors == "strict", "已是 UTF-8 的流不动（控制台就是这种）"
    legacy.write("本地")
    legacy.flush()
    assert legacy.buffer.getvalue().decode("utf-8") == "本地"


def test_streams_without_reconfigure_are_skipped() -> None:
    class Plain:
        encoding = "cp1252"

    _utf8_stdio(None, Plain())  # pythonw 的 sys.stdout 是 None；被替换的流可能没有 reconfigure
