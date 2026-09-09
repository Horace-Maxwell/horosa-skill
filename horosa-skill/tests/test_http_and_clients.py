"""HTTP 传输面的加固与客户端配置体检（v0.37.0 E5 / E9）。

**为什么旧检查抓不到这些**：整仓此前没有一条测试碰过 `serve` 的网络参数。传输名、绑定地址、
鉴权、Host 白名单全是「跑起来才知道」的东西，而 `test_cli.py` 里唯一一条 serve 用例还把
`run_mcp_server` 整个 monkeypatch 掉了 —— 它测的是「有没有调 run_mcp_server」，不是
「这台机器对外暴露了什么」。
"""
from __future__ import annotations

import json
import os

import pytest
import typer

from horosa_skill.config import Settings
from horosa_skill.surfaces import cli
from horosa_skill.surfaces.mcp_server import (
    StaticTokenVerifier,
    build_auth_settings,
    build_transport_security,
)


# ---------------------------------------------------------------- typer 默认值陷阱

def test_opt_unwraps_typer_option_defaults() -> None:
    """🔴 直接以 Python 函数调用 typer 命令时，未传的形参是 OptionInfo **对象**。

    对象恒真 —— 这让 `test_streamable_http_serve_stops_runtime_after_exit` 长期「因为错误的
    原因通过」：它断言的停机分支其实是被 `bool(OptionInfo)` 打开的，而不是被默认值打开的。
    """
    assert cli._opt(typer.Option(False, "--flag"), False) is False
    assert cli._opt(typer.Option(None, "--x"), "fallback") == "fallback"
    assert cli._opt(True, False) is True
    assert cli._opt("given") == "given"
    assert bool(typer.Option(False, "--flag")) is True, "陷阱本身仍在——所以才需要 _opt"


# ---------------------------------------------------------------- 传输名

@pytest.mark.parametrize("given,expected", [
    ("streamable-http", "streamable-http"),
    ("http", "streamable-http"),          # Claude Code 注册命令里的说法
    ("STDIO", "stdio"),
    ("sse", "sse"),
])
def test_transport_aliases_are_accepted(given, expected) -> None:
    assert cli._normalized_transport(given) == expected


def test_unknown_transport_is_a_clear_parameter_error() -> None:
    with pytest.raises(typer.BadParameter) as excinfo:
        cli._normalized_transport("websocket")
    assert "streamable-http" in str(excinfo.value)


# ---------------------------------------------------------------- Host 白名单

def test_docker_host_alias_is_allowed() -> None:
    """🔴 SDK 的缺省白名单只有回环三种写法。

    Docker Desktop 里的 Open WebUI / n8n / Dify 发的是 `Host: host.docker.internal:8765`
    → 一律 421，症状是「服务明明在跑，容器里就是连不上」。
    """
    security = build_transport_security("127.0.0.1", 8765)
    assert "host.docker.internal:*" in security.allowed_hosts
    assert security.enable_dns_rebinding_protection is True


def test_binding_to_all_interfaces_still_gets_protection() -> None:
    """SDK 在 host 非回环时**完全不开**防护 —— 恰恰是最需要它的那种绑法。"""
    security = build_transport_security("0.0.0.0", 8765)
    assert security.enable_dns_rebinding_protection is True
    assert "0.0.0.0:*" in security.allowed_hosts


def test_extra_allowed_hosts_come_from_env(monkeypatch) -> None:
    monkeypatch.setenv("HOROSA_MCP_ALLOWED_HOSTS", "gateway.internal:8765, mybox.lan:*")
    hosts = build_transport_security("127.0.0.1", 8765).allowed_hosts
    assert "gateway.internal:8765" in hosts and "mybox.lan:*" in hosts


# ---------------------------------------------------------------- 令牌

def test_token_comparison_is_constant_time_and_rejects_wrong_tokens() -> None:
    import anyio

    verifier = StaticTokenVerifier("s3cr3t")
    assert anyio.run(verifier.verify_token, "s3cr3t") is not None
    assert anyio.run(verifier.verify_token, "s3cr3u") is None
    assert anyio.run(verifier.verify_token, "") is None


def test_auth_settings_only_exist_when_a_token_is_configured() -> None:
    assert build_auth_settings("127.0.0.1", 8765, None) is None
    assert build_auth_settings("0.0.0.0", 8765, "tok") is not None


def test_serve_refuses_public_binding_without_a_token(monkeypatch, tmp_path, capsys) -> None:
    """对外绑定 + 无鉴权 = 同网段任何人都能读你的记忆库、驱动本机 runtime。"""
    settings = Settings(db_path=tmp_path / "m.db", output_dir=tmp_path / "runs",
                        runtime_root=tmp_path / "rt")
    monkeypatch.setattr(cli.Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.delenv("HOROSA_MCP_TOKEN", raising=False)
    ran: list[str] = []
    monkeypatch.setattr(cli, "run_mcp_server", lambda *a, **k: ran.append("served"))

    with pytest.raises(typer.Exit) as excinfo:
        cli.serve(transport="streamable-http", host="0.0.0.0", port=8765, skip_runtime_start=True)

    assert excinfo.value.exit_code == 2
    assert ran == []
    payload = json.loads(capsys.readouterr().err)
    assert payload["code"] == "serve.token_required"
    assert "--allow-unauthenticated" in payload["details"]["next_action"]


def test_serve_allows_public_binding_when_explicitly_accepted(monkeypatch, tmp_path) -> None:
    settings = Settings(db_path=tmp_path / "m.db", output_dir=tmp_path / "runs",
                        runtime_root=tmp_path / "rt")
    monkeypatch.setattr(cli.Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.delenv("HOROSA_MCP_TOKEN", raising=False)
    monkeypatch.setattr("horosa_skill.runtime.ports.port_bindable", lambda *a, **k: True)
    ran: list[str] = []
    monkeypatch.setattr(cli, "run_mcp_server", lambda *a, **k: ran.append("served"))

    cli.serve(transport="streamable-http", host="0.0.0.0", port=8765,
              skip_runtime_start=True, allow_unauthenticated=True)
    assert ran == ["served"]


def test_masked_token_never_shows_the_whole_secret() -> None:
    assert cli._mask_token("s3cr3t-probe-value") == "s3cr…ue"
    assert cli._mask_token("short") == "****"
    assert cli._mask_token(None) == ""


# ---------------------------------------------------------------- serverInfo 版本

def test_server_info_reports_our_version_not_the_sdk_version(tmp_path) -> None:
    """🔴 FastMCP 不把 version 透给 lowlevel Server，于是 initialize 回落成 MCP SDK 自己的版本。

    每个客户端的 server 列表因此显示「Horosa Skill 1.29.0」—— 看起来就像我们的版本号，
    而用户报 bug 时会照抄它。
    """
    from horosa_skill import __version__
    from horosa_skill.memory.store import MemoryStore
    from horosa_skill.service import HorosaSkillService
    from horosa_skill.surfaces.mcp_server import create_mcp_server

    settings = Settings(server_root="http://127.0.0.1:9999", db_path=tmp_path / "m.db",
                        output_dir=tmp_path / "runs")
    mcp = create_mcp_server(HorosaSkillService(settings, store=MemoryStore(settings)), settings)
    assert mcp._mcp_server.version == __version__


# ---------------------------------------------------------------- client check

def _audit(entry: dict, client: str = "cursor") -> list[str]:
    return [p["code"] for p in cli._audit_client_entry("horosa", entry, client=client)]


def test_client_check_catches_an_unexpanded_placeholder() -> None:
    codes = _audit({"command": "uv", "args": ["run", "--directory", "${user_config.skillRoot}",
                                              "horosa-skill", "serve", "--transport", "stdio"]})
    assert "unexpanded_placeholder" in codes


def test_client_check_catches_the_retired_mcp_subcommand() -> None:
    codes = _audit({"command": "uv", "args": ["run", "--directory", ".", "horosa-skill", "mcp"]})
    assert "legacy_subcommand" in codes and "missing_transport" in codes


def test_client_check_catches_a_moved_checkout() -> None:
    codes = _audit({"command": "uv", "args": ["run", "--directory", "/definitely/not/here",
                                              "horosa-skill", "serve", "--transport", "stdio"]})
    assert "directory_missing" in codes


def test_client_check_catches_uvx_against_unpublished_pypi() -> None:
    """PyPI 通道尚未开通 —— `uvx horosa-skill` 的症状是客户端里安静地少了这个 server。"""
    codes = _audit({"command": "/usr/local/bin/uvx",
                    "args": ["horosa-skill", "serve", "--transport", "stdio"]})
    assert "pypi_not_published" in codes


def test_client_check_catches_codex_default_timeouts() -> None:
    """Codex 默认 startup 10s / tool 60s —— 首次启动要解压 runtime，择日扫描本就要几分钟。"""
    codes = _audit(
        {"command": "uv", "args": ["run", "--directory", ".", "horosa-skill", "serve", "--transport", "stdio"],
         "startup_timeout_sec": 10, "tool_timeout_sec": 60},
        client="codex",
    )
    assert "codex_startup_timeout_too_short" in codes
    assert "codex_tool_timeout_too_short" in codes


def test_client_check_passes_a_good_entry(tmp_path) -> None:
    package_dir = tmp_path / "horosa-skill"
    package_dir.mkdir()
    (package_dir / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    codes = _audit({"command": "uv", "args": ["run", "--directory", str(package_dir),
                                              "horosa-skill", "serve", "--transport", "stdio"]})
    assert codes == []


def test_client_check_finds_nested_claude_code_project_entries() -> None:
    """Claude Code 把项目级 server 存在 projects.<path>.mcpServers 下，不是顶层。"""
    payload = {"projects": {"/some/repo": {"mcpServers": {"horosa": {"command": "uv", "args": []}}}}}
    found = list(cli._iter_client_entries(payload))
    assert len(found) == 1 and found[0][0].endswith("::horosa")
