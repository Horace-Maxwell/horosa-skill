"""审计 PF-03 / PF-10 / PF-13：交给用户的命令按安装上下文写；serve 横幅按传输与令牌写。"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

import pytest

from horosa_skill.runtime import hints


def _origin(url: str) -> tuple[str, str | None]:
    """(scheme, host) of a URL: compare parsed origins, not substrings (CodeQL py/incomplete-url-substring-sanitization)."""
    parts = urlsplit(url)
    return parts.scheme, parts.hostname

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


def test_plain_http_mirrors_are_refused_unless_allowed(monkeypatch) -> None:
    """审计 PF-01 第 2 层：明文 http 镜像（回环除外）以前照收。负向对照（实跑过）：mirror_prefixes 不过滤 → 红。"""
    from horosa_skill.runtime.mirrors import mirror_candidates, mirror_prefixes

    url = "https://github.com/Horace-Maxwell/horosa-skill/releases/download/v1/x.tar.gz"
    monkeypatch.delenv("HOROSA_RUNTIME_MIRROR_ALLOW_HTTP", raising=False)
    monkeypatch.setenv("HOROSA_RUNTIME_MIRROR", "http://mirror.example, http://127.0.0.1:18794, https://safe.example")
    usable, rejected = mirror_prefixes()
    assert rejected == ["http://mirror.example"] and usable == ["http://127.0.0.1:18794", "https://safe.example"]
    assert not any(_origin(c) == ("http", "mirror.example") for c in mirror_candidates(url))
    monkeypatch.setenv("HOROSA_RUNTIME_MIRROR_ALLOW_HTTP", "1")
    assert _origin(mirror_candidates(url)[0]) == ("http", "mirror.example")


def test_manifest_comes_from_the_origin_first_and_a_mirror_only_asserts_integrity(tmp_path, monkeypatch) -> None:
    """审计 PF-01 第 1 层：以前镜像的清单优先，结果写 sha256_verified: true。负向对照（实跑过）：候选不重排 → 先取镜像 → 红。"""
    import httpx

    from horosa_skill.config import Settings
    from horosa_skill.runtime.manager import HorosaRuntimeManager

    monkeypatch.setenv("HOROSA_RUNTIME_MIRROR", "https://mirror.example/gh")
    asked: list[str] = []
    manifest = '{"version": "9.9.9", "platforms": {}}'

    class _Client:
        def __init__(self, *a, **k):  # noqa: ANN002, ANN003
            pass

        def __enter__(self):  # noqa: ANN204
            return self

        def __exit__(self, *a):  # noqa: ANN002, ANN204
            return False

        def get(self, url):  # noqa: ANN001, ANN201
            asked.append(url)
            if _origin(url) == ("https", "github.com") and origin_down:
                raise httpx.ConnectError("down")
            return httpx.Response(200, text=manifest, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "Client", _Client)
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path,
                        db_path=tmp_path / "m.db", output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt")
    manager = HorosaRuntimeManager(settings)
    location = "https://github.com/Horace-Maxwell/horosa-skill/releases/latest/download/runtime-manifest.json"
    origin_down = False
    manager._read_json_location(location)
    assert asked[0] == location and manager._manifest_via_mirror is None
    origin_down = True
    asked.clear()
    manager._read_json_location(location)
    assert asked[0] == location and manager._manifest_via_mirror == "mirror.example"
    assert [w["code"] for w in manager._mirror_trust_warnings()] == ["runtime.install_mirror_trusted"]


def test_install_refuses_a_silent_downgrade_and_pins_the_manifest_to_the_package(tmp_path) -> None:
    """审计 PF-04：清单 0.38.0 对已装 0.50.1 以前照装、当场删旧副本。负向对照（实跑过）：去掉降级判定 → 继续下载 → 红。"""
    import json

    from horosa_skill import __version__
    from horosa_skill.config import Settings
    from horosa_skill.errors import RuntimeInstallError
    from horosa_skill.runtime.manager import HorosaRuntimeManager, _platform_key

    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path / "d",
                        db_path=tmp_path / "m.db", output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt")
    assert settings.default_runtime_manifest_url.endswith(f"/releases/download/v{__version__}/runtime-manifest.json")
    manager = HorosaRuntimeManager(settings)
    manager.current_dir.mkdir(parents=True)
    (manager.current_dir / "runtime-manifest.json").write_text(json.dumps({"version": "0.50.1", "platform": _platform_key()}), encoding="utf-8")
    old = tmp_path / "old-manifest.json"
    old.write_text(json.dumps({"version": "0.38.0", "platforms": {_platform_key(): {
        "url": "https://example.invalid/never.tar.gz", "sha256": "0" * 64}}}), encoding="utf-8")
    with pytest.raises(RuntimeInstallError) as caught:
        manager.install(manifest_url=str(old))
    assert caught.value.code == "runtime.install_downgrade_refused"
    assert caught.value.details["previous_version"] == "0.50.1" and caught.value.details["version"] == "0.38.0"


def test_trace_export_is_a_whitelisted_otlp_span_off_the_calling_thread(monkeypatch) -> None:
    """审计 PF-06：以前整条本地事件（出生时刻、地名、家目录路径）同步 POST 出去。负向对照（实跑过）：otlp_payload 改回整条事件 → 红。"""
    import json
    import time

    from horosa_skill import tracing

    event = {"trace_id": "3f2c1d8e-0000-4000-8000-000000000001", "workflow_name": "tool.run", "tool": "bazi_birth", "ok": False,
             "error_code": "place.not_found", "error_message": "没有找到地名「张三家王府井大街99号」", "duration_ms": 12.5,
             "summary": ["日期：1990-05-17 08:30:00"], "artifact_path": "/Users/someone/.horosa-skill/runs/x.json",
             "started_at": "2026-11-14T10:00:00+00:00", "finished_at": "2026-11-14T10:00:01+00:00"}
    payload = tracing.otlp_payload(event)
    text = json.dumps(payload, ensure_ascii=False)
    for secret in ("张三", "1990-05-17", "/Users/someone", "王府井"):
        assert secret not in text, secret
    span = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert span["traceId"] == "3f2c1d8e000040008000000000000001" and span["status"]["code"] == 2
    queue = tracing._OutboundQueue()
    slow: list[float] = []

    class _Client:
        def __init__(self, *a, **k):  # noqa: ANN002, ANN003
            pass

        def __enter__(self):  # noqa: ANN204
            return self

        def __exit__(self, *a):  # noqa: ANN002, ANN204
            return False

        def post(self, url, json):  # noqa: ANN001, A002, ANN201
            time.sleep(0.3)
            slow.append(time.monotonic())

    monkeypatch.setattr(tracing.httpx, "Client", _Client)
    started = time.monotonic()
    queue.submit("http://127.0.0.1:9/v1/traces", payload)
    assert time.monotonic() - started < 0.1, "提交不能等网络"
    queue.join()
    assert queue.sent == 1


def test_client_remove_takes_only_our_entry_out_with_a_backup(tmp_path) -> None:
    """审计 PF-07：卸载后客户端配置条目还在，CLI 没有「拿掉条目」的命令。负向对照：remove_client_entries 不删 → 红。"""
    import json

    from horosa_skill.client_config.audit import remove_client_entries

    config = tmp_path / "mcp.json"
    config.write_text(json.dumps({"mcpServers": {"horosa": {"command": "uvx"}, "other": {"command": "x"}}}), encoding="utf-8")
    planned = remove_client_entries("cursor", config_path=config, dry_run=True)
    assert planned["results"][0]["action"] == "would_remove" and "horosa" in json.loads(config.read_text())["mcpServers"]
    done = remove_client_entries("cursor", config_path=config)
    assert done["results"][0]["action"] == "removed" and done["results"][0]["backup"]
    assert json.loads(config.read_text(encoding="utf-8"))["mcpServers"] == {"other": {"command": "x"}}
    jsonc = tmp_path / "settings.json"
    jsonc.write_text('{\n  // 注释\n  "mcpServers": {"horosa": {}}\n}\n', encoding="utf-8")
    assert remove_client_entries("vscode", config_path=jsonc)["results"][0]["action"] == "manual"


def test_uninstall_lists_what_it_leaves_elsewhere(tmp_path, monkeypatch) -> None:
    import json

    from horosa_skill.client_config import audit, locations

    cursor = tmp_path / ".cursor" / "mcp.json"
    cursor.parent.mkdir(parents=True)
    cursor.write_text(json.dumps({"mcpServers": {"horosa": {"command": "uvx"}}}), encoding="utf-8")
    monkeypatch.setattr(locations, "_client_config_locations", lambda name: [cursor] if name == "cursor" else [])
    monkeypatch.setattr(audit, "_client_skill_report", lambda name: [])
    report = audit.elsewhere_report()
    assert report["client_configs"] == [{"client": "cursor", "path": str(cursor), "remove": audit._cli("client remove --client cursor")}]


def test_container_runs_as_non_root_with_a_healthcheck_and_loopback_ports() -> None:
    """审计 PF-15：root 运行、无 HEALTHCHECK、compose 端口对所有网卡、无加固。负向对照：去掉 USER / HEALTHCHECK → 红。"""
    import asyncio
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
    assert "USER 10001:10001" in dockerfile and "HEALTHCHECK" in dockerfile and "pip install --no-cache-dir uv" not in dockerfile
    assert '"127.0.0.1:8765:8765"' in compose and "read_only: true" in compose and "- ALL" in compose and "no-new-privileges:true" in compose

    from horosa_skill.surfaces.mcp_hosts import HostGuidanceMiddleware

    sent: list[dict] = []

    async def inner(scope, receive, send):  # noqa: ANN001, ANN202
        raise AssertionError("healthz must not reach the MCP app (no auth, no data)")

    async def send(message):  # noqa: ANN001, ANN202
        sent.append(message)

    scope = {"type": "http", "path": "/healthz", "method": "GET", "headers": [(b"host", b"127.0.0.1:8765")]}
    asyncio.run(HostGuidanceMiddleware(inner, ["127.0.0.1:*"])(scope, None, send))
    assert sent[0]["status"] == 200 and sent[1]["body"] == b"ok\n"
