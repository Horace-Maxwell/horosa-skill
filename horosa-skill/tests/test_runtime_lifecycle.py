"""端口与生命周期的用户可见行为（v0.37.0 D1-D8）。

**为什么旧检查抓不到这些**：既有测试把 `server_root` 与 `local_backend_port` 当成两个互不相干
的字段分别断言（`test_settings_provenance_reflects_env` 甚至把 server_root 的 "default" 写成契约），
把「HTTP serve 退出时停 runtime」当成契约，把 trace 写入当成单进程操作。三者都是**行为**问题，
形状检查照绿。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from horosa_skill.config import Settings


# ---------------------------------------------------------------- D1 端口与 URL

def test_changing_only_the_port_moves_the_urls_too(monkeypatch) -> None:
    """🔴 只设端口不设 URL 是最自然的「避开端口占用」操作。

    旧实现里启动器听 19999，而探针/客户端/doctor 全都还打 9999 —— 服务起来了却一个技法都用不了。
    """
    monkeypatch.setenv("HOROSA_LOCAL_BACKEND_PORT", "19999")
    monkeypatch.setenv("HOROSA_LOCAL_CHART_PORT", "18898")
    monkeypatch.delenv("HOROSA_SERVER_ROOT", raising=False)
    monkeypatch.delenv("HOROSA_CHART_SERVER_ROOT", raising=False)
    settings = Settings.from_env()
    assert settings.server_root == "http://127.0.0.1:19999"
    assert settings.chart_server_root == "http://127.0.0.1:18898"
    assert settings.settings_provenance["server_root"] == "derived:local_backend_port"


def test_explicit_urls_still_win_over_ports(monkeypatch) -> None:
    monkeypatch.setenv("HOROSA_LOCAL_BACKEND_PORT", "19999")
    monkeypatch.setenv("HOROSA_SERVER_ROOT", "http://198.51.100.7:9999")
    settings = Settings.from_env()
    assert settings.server_root == "http://198.51.100.7:9999"
    assert settings.settings_provenance["server_root"] == "env:HOROSA_SERVER_ROOT"


def test_auto_ports_avoid_a_held_default(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HOROSA_PORTS", "auto")
    monkeypatch.setenv("HOROSA_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.delenv("HOROSA_SERVER_ROOT", raising=False)
    monkeypatch.delenv("HOROSA_CHART_SERVER_ROOT", raising=False)
    monkeypatch.setattr("horosa_skill.runtime.ports.port_bindable", lambda port, host="127.0.0.1": False)
    monkeypatch.setattr("horosa_skill.runtime.ports.find_free_port",
                        lambda preferred, span=100, host="127.0.0.1": preferred + 7)
    settings = Settings.from_env()
    assert settings.local_backend_port == 19999 + 7
    assert settings.server_root.endswith(str(19999 + 7))
    assert settings.settings_provenance["local_backend_port"] == "auto:HOROSA_PORTS"


def test_auto_ports_reuse_what_the_registry_recorded(monkeypatch, tmp_path) -> None:
    """正在跑的实例的端口必须被复用，否则每个新客户端都会另起一套。"""
    (tmp_path / "runtime-state.json").write_text(
        json.dumps({"ports": {"backend": 21001, "chart": 21002}}), encoding="utf-8"
    )
    monkeypatch.setenv("HOROSA_PORTS", "auto")
    monkeypatch.setenv("HOROSA_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.delenv("HOROSA_SERVER_ROOT", raising=False)
    settings = Settings.from_env()
    assert (settings.local_backend_port, settings.local_chart_port) == (21001, 21002)


# ---------------------------------------------------------------- D7 trace 并发

def test_concurrent_processes_never_corrupt_the_trace_file(tmp_path) -> None:
    """N 进程 × M 事件全部可解析。

    诚实说明：旧写法在本机（macOS/APFS）上撕不出来 —— 8 进程 × 520 KB 行并发追加，250 行全绿。
    它安全靠的是 CPython 的实现细节（TextIOWrapper 在 close 时把整行交给一次 raw.write）。
    这条用例锁的是「不依赖那个细节」：O_APPEND + 单次 os.write 让整行原子是**显式**保证，
    换实现、换文件系统（NFS、某些 Windows 共享）或触发短写时仍然成立。
    """
    worker = tmp_path / "w.py"
    worker.write_text(
        "import os, sys\n"
        f"os.environ['HOROSA_TRACE_ENABLED'] = '1'\n"
        f"os.environ['HOROSA_TRACE_DIR'] = {str(tmp_path)!r}\n"
        f"os.environ['HOROSA_SKILL_DATA_DIR'] = {str(tmp_path)!r}\n"
        "from horosa_skill.config import Settings\n"
        "from horosa_skill.tracing import TraceRecorder\n"
        "t = TraceRecorder(Settings.from_env())\n"
        "for i in range(60):\n"
        "    t._write_event({'trace_id': f'{sys.argv[1]}-{i}', 'workflow_name': 'probe', 'blob': 'x' * 400})\n",
        encoding="utf-8",
    )
    procs = [subprocess.Popen([sys.executable, str(worker), f"p{i}"]) for i in range(4)]
    for proc in procs:
        assert proc.wait(timeout=120) == 0

    files = list(tmp_path.glob("*.jsonl"))
    assert files, "没有写出 trace 文件"
    lines = files[0].read_text(encoding="utf-8").splitlines()
    assert len(lines) == 240
    for index, line in enumerate(lines, 1):
        json.loads(line)  # 任何一行坏掉都在这里炸，并指出行号


def test_an_oversized_event_is_truncated_not_dropped(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOROSA_TRACE_ENABLED", "1")
    monkeypatch.setenv("HOROSA_TRACE_DIR", str(tmp_path))
    monkeypatch.setenv("HOROSA_SKILL_DATA_DIR", str(tmp_path))
    from horosa_skill.tracing import TraceRecorder

    TraceRecorder(Settings.from_env())._write_event(
        {"trace_id": "huge", "workflow_name": "probe", "blob": "y" * (400 * 1024)}
    )
    record = json.loads(list(tmp_path.glob("*.jsonl"))[0].read_text(encoding="utf-8").strip())
    assert record["trace_id"] == "huge"
    assert record["truncated"] is True
    assert record["original_bytes"] > 400 * 1024


# ---------------------------------------------------------------- D6 平台死胡同

@pytest.mark.parametrize("platform_name", ["darwin-x64", "linux-x64", "win32-arm64"])
def test_unsupported_platform_error_points_at_gateway_mode(platform_name) -> None:
    """「不支持」不能是终点。网关模式在任何平台上都可用。"""
    from horosa_skill.runtime.manager import _platform_dead_end_advice

    advice = _platform_dead_end_advice(platform_name)
    assert "HOROSA_SERVER_ROOT" in advice["next_action"]
    assert advice["reason"]
    assert advice["agent_recovery"]["must_ask_user"] is False


def test_intel_mac_is_told_rosetta_will_not_work() -> None:
    from horosa_skill.runtime.manager import _platform_dead_end_advice

    assert "Rosetta" in _platform_dead_end_advice("darwin-x64")["reason"]


# ---------------------------------------------------------------- D8 doctor

def test_doctor_names_the_port_holder_and_promises_not_to_kill_it() -> None:
    from horosa_skill.surfaces.cli import _doctor_port_holders, _doctor_summary

    report = {
        "installed": True,
        "issues": [],
        "endpoints": [
            {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": True,
             "identity": {"verdict": "foreign", "port": 8899,
                          "holders": [{"pid": 4242, "command": "python -m http.server 8899"}]}},
        ],
    }
    report["port_conflicts"] = _doctor_port_holders(report)
    summary = _doctor_summary(report)
    assert summary["ready_for_openclaw"] is False
    assert "4242" in summary["user_summary"]
    assert "不会去终止" in summary["user_summary"]
    assert "HOROSA_PORTS=auto" in summary["next_action"]


def test_doctor_flags_unexpanded_placeholders_before_anything_else() -> None:
    """宿主没替换 user_config 时，症状是「装了却全是 not_installed」—— doctor 必须当面点破。"""
    from horosa_skill.surfaces.cli import _doctor_summary

    summary = _doctor_summary({
        "installed": True, "issues": [], "endpoints": [],
        "unexpanded_env_templates": {"HOROSA_RUNTIME_ROOT": "${user_config.runtimeRoot}"},
    })
    assert summary["ready_for_openclaw"] is False
    assert "HOROSA_RUNTIME_ROOT" in summary["user_summary"]
    assert "占位符" in summary["user_summary"]


def test_doctor_ready_next_action_is_client_agnostic() -> None:
    """doctor 是给**任何** MCP 客户端的用户看的，不能把「去开 OpenClaw」当成唯一下一步。"""
    from horosa_skill.surfaces.cli import _doctor_summary

    summary = _doctor_summary({"installed": True, "issues": [], "endpoints": []})
    assert summary["status"] == "ready"
    action = summary["next_action"]
    assert "client config" in action
    for client in ("claude-code", "cursor", "vscode", "codex"):
        assert client in action


def test_config_records_unexpanded_placeholders_for_doctor(monkeypatch) -> None:
    import importlib

    import horosa_skill.config as config

    monkeypatch.setenv("HOROSA_RUNTIME_ROOT", "${user_config.runtimeRoot}")
    importlib.reload(config)
    assert config._env_text("HOROSA_RUNTIME_ROOT", "FALLBACK") == "FALLBACK"
    assert config.unexpanded_env_templates()["HOROSA_RUNTIME_ROOT"] == "${user_config.runtimeRoot}"
    monkeypatch.delenv("HOROSA_RUNTIME_ROOT", raising=False)
    importlib.reload(config)
