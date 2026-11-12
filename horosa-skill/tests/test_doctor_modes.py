"""doctor 先定模式，再说话（docs/LESSONS.md v0.50.0-dev「doctor 不分模式」）。

审计证据（audit-1111/env/doc0 / docE / docN）：新机器、网关可达、网关不可达三种现场，doctor 给的是**同一份**报告 ——
12 条 `missing:*`、「The offline runtime is not installed yet」、下一步「去跑 OpenClaw setup」，`uv run` 前缀写死，中英混杂。
网关模式因此永远到不了 ready。

本文件的设置一律把本机端口放在 18806 / 18807（不碰 8899 / 9999），runtime 根与数据目录都在 tmp_path。
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from horosa_skill.config import Settings
from horosa_skill.errors import ToolTransportError
from horosa_skill.runtime import hints
from horosa_skill.runtime.manager import HorosaRuntimeManager
from horosa_skill.surfaces import doctor
from test_runtime_manager import _managed_mode, create_runtime_archive  # noqa: F401 - _managed_mode 是 autouse fixture

GATEWAY = ("http://192.0.2.10:9999", "http://192.0.2.10:8899")


def _settings(tmp_path: Path) -> Settings:
    return Settings(runtime_root=tmp_path / "rt", data_dir=tmp_path / "data", db_path=tmp_path / "data" / "m.db",
                    output_dir=tmp_path / "data" / "runs", local_backend_port=18806, local_chart_port=18807,
                    server_root="http://127.0.0.1:18806", chart_server_root="http://127.0.0.1:18807")


def _endpoints(urls: tuple[str, str], reachable: bool) -> list[dict[str, object]]:
    return [{"label": "java_backend", "url": urls[0], "reachable": reachable},
            {"label": "python_chart", "url": urls[1], "reachable": reachable}]


def _gateway(monkeypatch: pytest.MonkeyPatch, manager: HorosaRuntimeManager, *, reachable: bool) -> None:
    monkeypatch.setenv("HOROSA_SERVER_ROOT", GATEWAY[0])
    monkeypatch.setenv("HOROSA_CHART_SERVER_ROOT", GATEWAY[1])
    monkeypatch.setattr(manager, "_service_status", lambda: _endpoints(GATEWAY, reachable))


def _ready_js(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("horosa_skill.engine.js_client.HorosaJsEngineClient.diagnose",
                        lambda self: {"state": "ready", "ok": True, "fix": None, "affects": "x / y"})


def _report(settings: Settings, manager: HorosaRuntimeManager) -> dict:
    return doctor._doctor_report(settings, manager)


# ── 三种模式 ──────────────────────────────────────────────────────────────────


def test_a_fresh_machine_gets_one_issue_and_the_install_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _ready_js(monkeypatch)
    settings = _settings(tmp_path)
    manager = HorosaRuntimeManager(settings)
    monkeypatch.setattr(manager, "_service_status", lambda: _endpoints(("http://127.0.0.1:18806", "http://127.0.0.1:18807"), False))

    report = _report(settings, manager)

    assert report["deployment"] == "not_installed"
    assert report["issues"] == ["runtime:not_installed"], "不是 12 条 missing:*"
    assert report["status"] == "needs_attention"
    install = hints.install_command()["install"]
    assert f"`{install}`" in report["next_action"] and "openclaw" not in report["next_action"].lower()
    assert " / " in report["user_summary"] and " / " in report["next_action"], "中英成对，不混"
    assert [a["code"] for a in report["advice"]][:1] == ["runtime:not_installed"]


def test_a_reachable_gateway_is_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _ready_js(monkeypatch)
    settings = _settings(tmp_path)
    manager = HorosaRuntimeManager(settings)
    _gateway(monkeypatch, manager, reachable=True)

    report = _report(settings, manager)

    assert report["deployment"] == "external" and report["mode"] == "external"
    assert report["issues"] == [] and report["status"] == "ready" and report["ready_for_openclaw"] is True
    assert "gateway" in report["user_summary"] and "openclaw" not in report["next_action"].lower()
    assert "setup --client" in report["next_action"]


def test_an_unreachable_gateway_says_which_address(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _ready_js(monkeypatch)
    settings = _settings(tmp_path)
    manager = HorosaRuntimeManager(settings)
    _gateway(monkeypatch, manager, reachable=False)

    report = _report(settings, manager)

    assert report["issues"] == ["external:unreachable"] and report["status"] == "needs_attention"
    assert GATEWAY[0] in report["user_summary"]
    assert not any(issue.startswith(("missing:", "runtime:not_installed", "services:")) for issue in report["issues"])


def test_an_installed_runtime_that_is_not_running_says_start_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _ready_js(monkeypatch)
    settings = _settings(tmp_path)
    manager = HorosaRuntimeManager(settings)
    manager.install(archive=str(create_runtime_archive(tmp_path)))
    monkeypatch.setattr(manager, "_service_status", lambda: _endpoints(("http://127.0.0.1:18806", "http://127.0.0.1:18807"), False))
    summary = doctor._doctor_summary({**manager.doctor(), "issues": ["services:not_running"]})
    assert summary["deployment"] == "managed" and hints.cli_command("runtime start") in summary["next_action"]


# ── 命令按安装方式写；OpenClaw 只给确知是 OpenClaw 的人 ─────────────────────────


def test_commands_follow_the_install_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _ready_js(monkeypatch)
    bundle = tmp_path / "Claude Extensions" / "local.dxt.horosa"
    monkeypatch.setenv("HOROSA_INSTALL_CONTEXT", "mcpb")
    monkeypatch.setenv("HOROSA_PLUGIN_ROOT", str(bundle))
    settings = _settings(tmp_path)
    manager = HorosaRuntimeManager(settings)
    monkeypatch.setattr(manager, "_service_status", lambda: _endpoints(("http://127.0.0.1:18806", "http://127.0.0.1:18807"), False))

    report = _report(settings, manager)

    prefix = f'uv run --directory "{bundle}" horosa-skill'
    assert f"`{prefix} install`" in report["next_action"]
    advice = {a["code"]: a for a in report["advice"]}
    assert f"`{prefix} install`" in advice["runtime:not_installed"]["next_action"]
    assert "`uv run horosa-skill" not in json.dumps(report, ensure_ascii=False)


def test_openclaw_is_named_only_when_the_client_is_known(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPENCLAW_WORKSPACE", raising=False)
    ready = {"installed": True, "deployment": "managed", "issues": [], "endpoints": []}
    assert "openclaw" not in doctor._doctor_summary(ready)["next_action"].lower()
    monkeypatch.setenv("OPENCLAW_WORKSPACE", str(tmp_path / "ws"))
    assert "openclaw-setup" in doctor._doctor_summary(ready)["next_action"]


# ── E-08：runtime 根写不了 ─────────────────────────────────────────────────────


@pytest.mark.skipif(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0), reason="[platform] POSIX permissions, non-root")
def test_an_unwritable_runtime_root_is_an_issue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _ready_js(monkeypatch)
    parent = tmp_path / "locked"
    parent.mkdir()
    settings = _settings(tmp_path).model_copy(update={"runtime_root": parent / "rt"})
    manager = HorosaRuntimeManager(settings)
    monkeypatch.setattr(manager, "_service_status", lambda: _endpoints(("http://127.0.0.1:18806", "http://127.0.0.1:18807"), False))
    parent.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        report = manager.doctor()
    finally:
        parent.chmod(stat.S_IRWXU)
    assert "runtime:root_not_writable" in report["issues"] and report["runtime_root_writable"]["ok"] is False
    summary = doctor._doctor_summary({**report, "runtime_root": str(settings.runtime_root)})
    assert "HOROSA_RUNTIME_ROOT" in summary["next_action"]


# ── E-02：JS 引擎一节 ──────────────────────────────────────────────────────────


def test_the_js_engine_block_says_absent_why_and_how(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from horosa_skill.engine.js_client import HorosaJsEngineClient

    monkeypatch.delenv("HOROSA_CORE_JS_ROOT", raising=False)
    client = HorosaJsEngineClient(_settings(tmp_path))
    monkeypatch.setattr(client, "_candidate_engine_roots", lambda: [tmp_path / "nowhere"])
    block = client.diagnose()
    assert block["state"] == "absent" and block["ok"] is False and block["engine_root"] is None
    assert "HOROSA_CORE_JS_ROOT" in block["fix"] and {r["source"] for r in block["searched"]} >= {"runtime", "source_checkout"}
    assert block["node"]["required"] == ">=20.10.0"


def test_a_ready_gateway_without_the_js_engine_says_what_will_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("horosa_skill.engine.js_client.HorosaJsEngineClient.diagnose",
                        lambda self: {"state": "absent", "ok": False, "fix": "装 runtime / install the runtime",
                                      "affects": "八字等 / BaZi and others"})
    settings = _settings(tmp_path)
    manager = HorosaRuntimeManager(settings)
    _gateway(monkeypatch, manager, reachable=True)

    report = _report(settings, manager)

    assert report["status"] == "ready", "网关能用的部分照常可用：不能因为 JS 引擎把网关永远判成没就绪"
    assert "JS engine is unavailable" in report["user_summary"] and "install the runtime" in report["next_action"]
    assert "js_engine:unavailable" in [w["code"] for w in report["warnings"]]


def test_the_real_js_engine_block_in_this_checkout_is_ready(tmp_path: Path) -> None:
    """本仓（conftest 钉了 HOROSA_CORE_JS_ROOT）有引擎、PATH 上有够新的 node：ready，来源与版本都报出来。"""
    from horosa_skill.engine.js_client import HorosaJsEngineClient

    block = HorosaJsEngineClient(_settings(tmp_path)).diagnose()
    assert block["state"] == "ready" and block["engine_root"] and block["node"]["version"]


# ── selfcheck 不能在没有 JS 引擎时说「全部通过」────────────────────────────────


def test_selfcheck_runs_a_js_technique_and_fails_without_the_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from horosa_skill.surfaces import cli as cli_module

    monkeypatch.setenv("HOROSA_RUNTIME_ROOT", str(tmp_path / "rt"))
    monkeypatch.setenv("HOROSA_SKILL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(HorosaRuntimeManager, "doctor", lambda self: {"installed": True, "issues": [], "endpoints": [
        {"label": "java_backend", "reachable": True}, {"label": "python_chart", "reachable": True}]})
    monkeypatch.setattr(HorosaRuntimeManager, "runtime_mode", lambda self: "external")
    memory = SimpleNamespace(run_id="r1")
    monkeypatch.setattr(cli_module.HorosaSkillService, "run_tool",
                        lambda self, name, payload, **kw: SimpleNamespace(ok=True, error=None, memory_ref=memory))
    monkeypatch.setattr(cli_module.HorosaSkillService, "show_memory", lambda self, payload: {"ok": True})

    def no_engine(self, payload):  # noqa: ANN001
        raise ToolTransportError("missing", code="js_engine.cli_missing", details={})

    monkeypatch.setattr(cli_module.HorosaSkillService, "place_search", no_engine)
    result = CliRunner().invoke(cli_module.app, ["selfcheck"])
    report = json.loads(result.stdout)
    assert result.exit_code == 1 and report["ok"] is False
    assert report["steps"]["js_engine"] == {"ok": False, "tool": "place_search", "error": {"code": "js_engine.cli_missing", "message": "missing"}}
    assert "全部通过" not in report["next_action"] and "js_engine" in report["next_action"]

    monkeypatch.setattr(cli_module.HorosaSkillService, "place_search", lambda self, payload: {"match": {"name": "上海"}})
    passed = json.loads(CliRunner().invoke(cli_module.app, ["selfcheck"]).stdout)
    assert passed["ok"] is True and passed["steps"]["js_engine"]["ok"] is True and "全部通过" in passed["next_action"]
