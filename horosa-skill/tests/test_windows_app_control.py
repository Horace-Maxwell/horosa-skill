"""Windows 应用控制（Smart App Control）拦 uv trampoline 的出路：`python -m horosa_skill` 入口（v0.43.1，Windows 原生复验）。

症状：开着 Smart App Control 的 Windows 11 上，uv / uvx 给新环境现生成的 `Scripts\\horosa-skill.exe`、`pytest.exe` 可能被拒绝执行——
`error: Failed to spawn: … (os error 4551)`。这些 trampoline 内容随安装路径变，永远没有云端信誉，同一台机器上时拦时放；
环境里的 `python.exe` 是解释器自带的那份，不受影响。四处落点各有断言：入口模块、配置生成（--entry）、setup 探针诊断、本机门禁镜像。
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
import typer

from horosa_skill.client_config import payload as client_payload
from horosa_skill.runtime import manager
from horosa_skill.surfaces import setup_flow

PKG_ROOT = Path(__file__).resolve().parents[1]

# 2026-10-23 本机原文（uv 0.12.x）；中文 Windows 上中间那句会本地化，`(os error 4551)` 不会。
_BLOCKED_STDERR = (
    "error: Failed to spawn: `horosa-skill`\n"
    "  Caused by: An Application Control policy has blocked this file. (os error 4551)\n"
)
_BLOCKED_STDERR_ZH = "error: Failed to spawn: horosa-skill\n  Caused by: 应用程序控制策略已阻止此文件。 (os error 4551)\n"


def test_python_dash_m_runs_the_same_cli() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "horosa_skill", "--version"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, check=False,
        env={**os.environ, "PYTHONUTF8": "1"},
    )
    assert result.returncode == 0, result.stderr[-800:]
    assert result.stdout.strip().startswith("horosa-skill "), result.stdout


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        (["uv", "run", "--directory", r"C:\x\horosa-skill", "horosa-skill", "serve", "--transport", "stdio"],
         ["uv", "run", "--directory", r"C:\x\horosa-skill", "python", "-m", "horosa_skill", "serve", "--transport", "stdio"]),
        (["uvx", "--from", "https://e.org/horosa_skill-0.43.0-py3-none-any.whl", "horosa-skill", "serve", "--transport", "stdio"],
         ["uvx", "--from", "https://e.org/horosa_skill-0.43.0-py3-none-any.whl", "python", "-m", "horosa_skill", "serve",
          "--transport", "stdio"]),
        # uvx-git 的 URL 里也有 horosa-skill 字样：只换 serve 前一位
        (["uvx", "--from", "git+https://github.com/o/horosa-skill@v1#subdirectory=horosa-skill", "horosa-skill", "serve"],
         ["uvx", "--from", "git+https://github.com/o/horosa-skill@v1#subdirectory=horosa-skill", "python", "-m", "horosa_skill",
          "serve"]),
    ],
)
def test_module_entry_rewrites_only_the_program(command: list[str], expected: list[str]) -> None:
    assert client_payload.module_entry_command(command) == expected


def test_module_entry_leaves_unrecognised_commands_alone() -> None:
    for command in (["npx", "mcporter", "serve"], ["uv", "run", "horosa-skill", "doctor"], []):
        assert client_payload.module_entry_command(command) == command


def test_entry_auto_follows_smart_app_control(monkeypatch: pytest.MonkeyPatch) -> None:
    for state, expected in (("on", "module"), ("evaluation", "script"), ("off", "script"), (None, "script")):
        monkeypatch.setattr(manager, "smart_app_control_state", lambda state=state: state)
        assert client_payload.resolve_entry("auto")[0] == expected, state
    assert client_payload.resolve_entry("module")[0] == "module"
    assert client_payload.resolve_entry("SCRIPT")[0] == "script"
    with pytest.raises(typer.BadParameter):
        client_payload.resolve_entry("exe")


def _desktop_args(monkeypatch: pytest.MonkeyPatch, entry: str, state: str | None) -> list[str]:
    monkeypatch.setattr(manager, "smart_app_control_state", lambda: state)
    payload, command, _env = client_payload._build_client_config_payload(
        format_name="claude-desktop", skill_root=PKG_ROOT, server_name="horosa", launcher="uv", surface="auto", entry=entry,
    )
    assert payload["mcpServers"]["horosa"]["args"] == command[1:]
    assert payload["launcher"]["entry"]["mode"] in {"script", "module"}
    return command


def test_config_entry_changes_only_when_asked_or_app_control_is_on(monkeypatch: pytest.MonkeyPatch) -> None:
    default = _desktop_args(monkeypatch, "auto", None)
    assert default == _desktop_args(monkeypatch, "script", "on"), "--entry script 必须压过 auto"
    assert default[-4:] == ["horosa-skill", "serve", "--transport", "stdio"], "Smart App Control 不开时生成物与以前逐字节相同"
    for entry, state in (("auto", "on"), ("module", None)):
        command = _desktop_args(monkeypatch, entry, state)
        assert command[-6:] == ["python", "-m", "horosa_skill", "serve", "--transport", "stdio"], (entry, state)


@pytest.mark.parametrize("stderr", [_BLOCKED_STDERR, _BLOCKED_STDERR_ZH])
def test_setup_probe_names_the_app_control_block(stderr: str) -> None:
    command = ["uv", "run", "--directory", r"C:\x\horosa-skill", "horosa-skill", "serve", "--transport", "stdio"]
    diagnosis = setup_flow._diagnose_probe_stderr("…build noise…\n" + stderr, command=command)
    assert diagnosis is not None and diagnosis["cause"] == "windows_app_control_blocked"
    assert diagnosis["blocked_program"] == "horosa-skill"
    assert "python -m horosa_skill serve" in diagnosis["module_command"]
    assert "--entry module" in diagnosis["next_action"]


def test_setup_probe_other_shapes_are_unchanged() -> None:
    lock = "error: failed to remove file `C:\\v\\.venv\\Scripts\\horosa-skill.exe`: Access is denied. (os error 32)"
    assert setup_flow._diagnose_probe_stderr(lock)["cause"] == "windows_file_in_use"
    assert setup_flow._diagnose_probe_stderr("Traceback (most recent call last): boom") is None
    # 已经是 module 入口还被拦（极少见：解释器本身也被拦）——仍报因，但不再给一条一模一样的「改写后」命令
    module = ["uv", "run", "python", "-m", "horosa_skill", "serve"]
    diagnosis = setup_flow._diagnose_probe_stderr(_BLOCKED_STDERR, command=module)
    assert diagnosis["cause"] == "windows_app_control_blocked" and "module_command" not in diagnosis


def test_smart_app_control_registry_values() -> None:
    assert [manager.smart_app_control_label(v) for v in (0, 1, 2, "1", 7, None, "x")] == [
        "off", "on", "evaluation", "on", None, None, None,
    ]


@pytest.mark.skipif(os.name != "nt", reason="registry + doctor.windows only exist on Windows")
def test_doctor_windows_block_reports_smart_app_control(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert manager.read_smart_app_control_state() in {"on", "off", "evaluation", None}  # 真读本机注册表不抛
    for state in ("on", "off", None):
        monkeypatch.setattr(manager, "smart_app_control_state", lambda state=state: state)
        report = manager.windows_path_report(tmp_path)
        assert report["smart_app_control"] == state
        assert (report["app_control_note"] is None) == (state != "on")


def _gates_module():
    spec = importlib.util.spec_from_file_location("run_ci_gates", PKG_ROOT / "scripts" / "run_ci_gates.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_local_gate_mirror_uses_the_module_entry_on_windows_only() -> None:
    gates = _gates_module()
    assert gates.local_command("uv run pytest -q", windows=True) == "uv run python -m pytest -q"
    assert gates.local_command("uv run pytest", windows=True) == "uv run python -m pytest"
    assert gates.local_command("uv run pytest -q", windows=False) == "uv run pytest -q"
    for untouched in ("uv run pytestx", "uv run python scripts/verify_docs_sync.py", "uv run python -m pytest -q"):
        assert gates.local_command(untouched, windows=True) == untouched
