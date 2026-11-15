"""审计 PF-03 / PF-10 / PF-13：交给用户的命令按安装上下文写；serve 横幅按传输与令牌写。"""
from __future__ import annotations

import re

import pytest

from horosa_skill.runtime import hints

WHEEL = ("wheel", None, 'uvx --from "https://example.invalid/horosa_skill-9.9.9-py3-none-any.whl" horosa-skill')
BARE = re.compile(r"`(?:uv run )?horosa-skill ")


@pytest.fixture
def wheel_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hints, "cli_prefix", lambda env=None: WHEEL)


def test_recovery_table_commands_follow_the_install_context(wheel_context: None) -> None:
    """负向对照（实跑过）：recovery_for 里去掉 contextualize → runtime.* 等 25 条照写 `uv run horosa-skill` → 红。"""
    from horosa_skill.errors import RECOVERY_TABLE, recovery_for

    leaks = []
    for code in RECOVERY_TABLE:
        details = recovery_for(code, {})
        recovery = details.get("agent_recovery") or {}
        for text in (recovery.get("prompt_to_user"), recovery.get("next_action"), details.get("hint")):
            if isinstance(text, str) and BARE.search(text):
                leaks.append((code, text[:80]))
    assert not leaks, leaks[:5]


def test_other_user_facing_commands_follow_the_install_context(wheel_context: None, tmp_path) -> None:
    from horosa_skill.client_config import audit
    from horosa_skill.surfaces.serve_flow import _serve_banner

    assert audit._cli("client config --format cursor").startswith("uvx --from")
    banner = _serve_banner(host="127.0.0.1", port=8765, transport="http", token=None, skip_runtime_start=True)
    assert "uv run horosa-skill" not in banner and "uvx --from" in banner


def test_serve_banner_matches_transport_and_token() -> None:
    from horosa_skill.surfaces.serve_flow import _serve_banner

    sse = _serve_banner(host="127.0.0.1", port=8765, transport="sse", token=None, skip_runtime_start=True)
    assert "--transport sse" in sse
    tokened = _serve_banner(host="127.0.0.1", port=8765, transport="http", token="secret-token-123456", skip_runtime_start=True)
    assert '--header "Authorization: Bearer $HOROSA_MCP_TOKEN"' in tokened and "secret-token-123456" not in tokened


def test_client_check_flags_misspelled_env_bad_values_and_an_over_cap_surface() -> None:
    """审计 PF-08 / PF-12：以前三种都是「未发现问题」。负向对照（实跑过）：check 里不调 _env_problems → 红。"""
    from horosa_skill.client_config.audit import _env_problems

    entry = {"command": "uvx", "args": ["serve", "--transport", "stdio"],
             "env": {"HOROSA_MCP_COMPAT": "1", "HOROSA_TOOLSET": "cn", "HOROSA_MCP_RESULT_VIEW": "bogus"}}
    codes = [(p["code"], p["detail"]) for p in _env_problems(entry, client="cursor")]
    assert [c for c, _ in codes].count("unknown_env_name") == 2
    assert any("HOROSA_MCP_COMPACT" in d for c, d in codes if c == "unknown_env_name")
    assert any(c == "rejected_env_value" and "HOROSA_MCP_RESULT_VIEW" in d for c, d in codes)
    assert any(c == "tool_surface_exceeds_client_cap" for c, _ in codes)
    # 精简面、或显式全量（setup --surface full 写的 0）不报超上限；Claude Code 没有上限
    assert not _env_problems({"env": {"HOROSA_MCP_COMPACT": "1"}}, client="cursor")
    assert not _env_problems({"env": {"HOROSA_MCP_COMPACT": "0"}}, client="cursor")
    assert not _env_problems({"env": {}}, client="claude-code")


def test_client_check_report_counts_the_env_problems(tmp_path) -> None:
    """经 client check 的整条报告：以前 problems=0、「未发现问题」。负向对照（实跑过）：_client_check_report 不调 _env_problems → 红。"""
    import json

    from horosa_skill.client_config.audit import _client_check_report

    config = tmp_path / "mcp.json"
    config.write_text(json.dumps({"mcpServers": {"horosa": {"command": "/usr/bin/env", "args": ["horosa-skill", "serve", "--transport", "stdio"],
                                                            "env": {"HOROSA_MCP_COMPAT": "1"}}}}), encoding="utf-8")
    report = _client_check_report(["cursor"], config_path=config)
    codes = [p["code"] for p in report["clients"][0]["findings"][0]["problems"]]
    assert "unknown_env_name" in codes and "tool_surface_exceeds_client_cap" in codes and report["ok"] is False


def test_misspelled_server_env_reaches_doctor_warnings(monkeypatch) -> None:
    """审计 PF-12：拼错的变量以前只在 stderr 说「已忽略，不影响运行」。负向对照（实跑过）：doctor 不并 _unknown_env_warnings → 红。"""
    from horosa_skill import config
    from horosa_skill.surfaces import doctor

    monkeypatch.setenv("HOROSA_MCP_COMPAT", "1")
    rows = config.unknown_env_names()
    assert {"name": "HOROSA_MCP_COMPAT", "did_you_mean": "HOROSA_MCP_COMPACT"} in rows
    warnings = doctor._unknown_env_warnings()
    assert any(w["variable"] == "HOROSA_MCP_COMPAT" and "HOROSA_MCP_COMPACT" in w["detail"] for w in warnings)
    assert "不起作用" in " ".join(config.audit_env_flags(force=True, log=False))


def test_technique_report_refuses_unknown_arguments_and_an_unnamed_run(tmp_path) -> None:
    """审计 PF-09：{"bogus_key":"x","tool":"chart"} 以前 ok:true、对之前八字那条出报告。负向对照（实跑过）：两道检查都去掉 → 红。"""
    from horosa_skill.config import Settings
    from horosa_skill.errors import ToolValidationError
    from horosa_skill.memory.store import MemoryStore
    from horosa_skill.service import HorosaSkillService

    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path,
                        db_path=tmp_path / "m.db", output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt")
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    run_id = service.store.create_run(entrypoint="tool", query_text="八字", subject={})
    with pytest.raises(ToolValidationError) as caught:
        service.technique_report({"bogus_key": "x", "tool": "chart"})
    assert caught.value.code == "report.technique.unknown_argument" and "bogus_key" in caught.value.details["unknown"]
    with pytest.raises(ToolValidationError) as caught:
        service.technique_report({"format": "markdown"})
    assert caught.value.code == "report.technique.scope_required"
    assert caught.value.details["recent"][0]["run_id"] == run_id


def test_loopback_http_gets_an_owner_only_token_that_is_reused(tmp_path) -> None:
    """审计 PF-05 / 平台待决项 6：回环 HTTP 以前不要令牌（本机任何进程都能读记忆库）。负向对照（实跑过）：_run_serve 不调 _auto_token → 红（见下一条）。"""
    import os
    import stat

    from horosa_skill.config import Settings
    from horosa_skill.surfaces.serve_flow import _auto_token

    settings = Settings(data_dir=tmp_path / "data", db_path=tmp_path / "m.db", output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt")
    first, path = _auto_token(settings)
    again, _ = _auto_token(settings)
    assert first == again and len(first) >= 32
    if os.name == "posix":
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_serve_wires_the_auto_token_and_refuses_a_world_readable_token_file(tmp_path, monkeypatch) -> None:
    import os

    from horosa_skill.surfaces import serve_flow

    seen: dict = {}
    monkeypatch.setattr(serve_flow, "_auto_token", lambda settings: ("auto-token-value-0123456789abcdef", "/x/mcp-token"))

    class _Stop(Exception):
        pass

    def fake_banner(**kwargs):  # noqa: ANN003, ANN202
        seen.update(kwargs)
        raise _Stop

    monkeypatch.setattr(serve_flow, "_serve_banner", fake_banner)
    monkeypatch.setattr(serve_flow, "HorosaSkillService", lambda *a, **k: None)
    # _run_serve 直接写 os.environ：先经 monkeypatch 登记，测试结束时还原（否则令牌漏进后面的用例）
    monkeypatch.setenv("HOROSA_MCP_TOKEN", "placeholder")
    monkeypatch.delenv("HOROSA_MCP_TOKEN", raising=False)
    monkeypatch.setenv("HOROSA_SKILL_DATA_DIR", str(tmp_path / "data"))
    with pytest.raises(_Stop):
        serve_flow._run_serve(transport="streamable-http", host="127.0.0.1", port=18765, token=None, allow_unauthenticated=False,
                              skip_runtime_start=True, stop_runtime_on_exit=False)
    assert seen["token"] == "auto-token-value-0123456789abcdef" and seen["token_source"] == "file:/x/mcp-token"
    monkeypatch.delenv("HOROSA_MCP_TOKEN", raising=False)
    with pytest.raises(_Stop):
        serve_flow._run_serve(transport="streamable-http", host="127.0.0.1", port=18765, token=None, allow_unauthenticated=True,
                              skip_runtime_start=True, stop_runtime_on_exit=False)
    assert seen["token"] is None
    if os.name == "posix":
        loose = tmp_path / "tok"
        loose.write_text("abc", encoding="utf-8")
        loose.chmod(0o644)
        import typer

        with pytest.raises((SystemExit, typer.Exit)):
            serve_flow._read_token_file(loose)


def test_origin_allowlist_is_empty_unless_configured(monkeypatch) -> None:
    """审计 PF-23：以前任意本机端口的网页（Origin: http://localhost:3000）都放行。负向对照（实跑过）：origins 改回跟 Host 走 → 红。"""
    from horosa_skill.surfaces.mcp_auth import build_transport_security

    monkeypatch.delenv("HOROSA_MCP_ALLOWED_ORIGINS", raising=False)
    assert build_transport_security("127.0.0.1", 8765).allowed_origins == []
    monkeypatch.setenv("HOROSA_MCP_ALLOWED_ORIGINS", "http://localhost:6274/, https://app.example")
    assert build_transport_security("127.0.0.1", 8765).allowed_origins == ["http://localhost:6274", "https://app.example"]


def test_doctor_has_no_side_effects_and_can_signal_failure(tmp_path, monkeypatch) -> None:
    """审计 PF-17：干净机器上跑 doctor 曾建出 memory.db / traces；ok:false 也退 0。负向对照（实跑过）：去掉 db 不存在的短路 → memory.db 被建 → 红。"""
    import json

    from typer.testing import CliRunner

    from horosa_skill.surfaces.cli import app

    data = tmp_path / "data"
    monkeypatch.setenv("HOROSA_SKILL_DATA_DIR", str(data))
    monkeypatch.setenv("HOROSA_RUNTIME_ROOT", str(tmp_path / "rt"))
    result = CliRunner().invoke(app, ["doctor"])
    report = json.loads(result.stdout)
    assert report["memory_db"]["state"] == "absent"
    assert not (data / "memory.db").exists() and not (data / "traces").exists()
    flagged = CliRunner().invoke(app, ["doctor", "--exit-code"])
    assert flagged.exit_code == (1 if report.get("ok") is False else 0)
