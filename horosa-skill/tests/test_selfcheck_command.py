"""`selfcheck` 先用全预算把 runtime 拉起来，再做活体探针（v0.38.1 R11）。

事故形状：`setup` 之后紧跟 `selfcheck`。工具路径只为「等 runtime 起来」阻塞 5 s（HOROSA_RUNTIME_CALL_WAIT_SECONDS），
不够一次冷启动 → selfcheck 在每个平台上都以 runtime.starting 退出 1，用户看到的是「刚装完就坏了」。
旧顺序 ["run_tool"]；新顺序 ["start", "run_tool"]。
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from horosa_skill.runtime.manager import HorosaRuntimeManager
from horosa_skill.surfaces import cli as cli_module
from horosa_skill.surfaces.cli import app

runner = CliRunner()


def _doctor(*, installed: bool = True, reachable: bool = False) -> dict[str, object]:
    return {
        "installed": installed,
        "issues": [] if reachable else ["services:not_running"],
        "endpoints": [{"label": "java_backend", "reachable": reachable}, {"label": "python_chart", "reachable": reachable}],
    }


@pytest.fixture()
def wired(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("HOROSA_RUNTIME_ROOT", str(tmp_path / "rt"))
    monkeypatch.setenv("HOROSA_SKILL_DATA_DIR", str(tmp_path / "data"))
    for key in ("HOROSA_SERVER_ROOT", "HOROSA_CHART_SERVER_ROOT", "HOROSA_PORTS"):
        monkeypatch.delenv(key, raising=False)
    order: list[tuple[str, object]] = []

    def wire(*, doctor: dict[str, object], mode: str = "managed") -> list[tuple[str, object]]:
        monkeypatch.setattr(HorosaRuntimeManager, "doctor", lambda self: doctor)
        monkeypatch.setattr(HorosaRuntimeManager, "runtime_mode", lambda self: mode)

        def start(self, *, wait_seconds=None):  # noqa: ANN001
            order.append(("start", wait_seconds))
            return {"ok": True, "already_running": False}

        def run_tool(self, name, payload, **kwargs):  # noqa: ANN001
            order.append(("run_tool", name))
            return SimpleNamespace(ok=True, error=None, memory_ref=None)

        monkeypatch.setattr(HorosaRuntimeManager, "start_local_services", start)
        monkeypatch.setattr(cli_module.HorosaSkillService, "run_tool", run_tool)
        monkeypatch.setattr(cli_module.HorosaSkillService, "show_memory", lambda self, payload: {"ok": False})
        return order

    return wire


def test_selfcheck_starts_the_runtime_with_the_full_budget_before_probing(wired) -> None:
    order = wired(doctor=_doctor())
    result = runner.invoke(app, ["selfcheck"])
    report = json.loads(result.stdout)
    assert [step[0] for step in order] == ["start", "run_tool"], order
    assert order[0] == ("start", None), "全预算（wait_seconds=None），不是工具路径的 5 s"
    assert report["steps"]["start"]["ok"] is True and report["steps"]["start"]["budget_seconds"] > 0
    assert report["steps"]["compute"]["ok"] is True


def test_selfcheck_skips_the_start_when_services_are_already_reachable(wired) -> None:
    order = wired(doctor=_doctor(reachable=True))
    result = runner.invoke(app, ["selfcheck"])
    assert [step[0] for step in order] == ["run_tool"], order
    assert "start" not in json.loads(result.stdout)["steps"]


def test_selfcheck_never_starts_anything_in_external_mode(wired) -> None:
    order = wired(doctor=_doctor(), mode="external")
    runner.invoke(app, ["selfcheck"])
    assert [step[0] for step in order] == ["run_tool"], order


def test_selfcheck_does_not_try_to_start_an_uninstalled_runtime(wired) -> None:
    order = wired(doctor=_doctor(installed=False))
    runner.invoke(app, ["selfcheck"])
    assert [step[0] for step in order] == ["run_tool"], "未安装时交给工具路径报 not_installed（带上下文修复命令）"
