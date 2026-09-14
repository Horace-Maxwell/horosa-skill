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
from typer.testing import CliRunner
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

def _audit(entry: dict, client: str = "cursor", config_dir=None) -> list[str]:
    return [p["code"] for p in cli._audit_client_entry("horosa", entry, client=client, config_dir=config_dir)]


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


def test_client_check_flags_missing_codex_timeouts() -> None:
    """缺省 = Codex 默认 10 s / 60 s：此前只在写了且太短时才报（v0.38.0 B2）。"""
    codes = _audit({"command": "uv", "args": ["run", "--directory", ".", "horosa-skill", "serve", "--transport", "stdio"]},
                   client="codex")
    assert "codex_startup_timeout_missing" in codes and "codex_tool_timeout_missing" in codes
    # v0.38.1 C6：没有 env 根的 Codex 条目也是一条真发现（Codex 不转发 shell 环境 → server 用另一套目录），
    # 所以「完好」的条目必须带两个绝对根；旧断言里的 good 条目没有 env，如今会正确地报 codex_env_roots_missing。
    without_roots = _audit({"command": "uv", "args": ["run", "--directory", ".", "horosa-skill", "serve", "--transport", "stdio"],
                            "startup_timeout_sec": 120, "tool_timeout_sec": 600}, client="codex")
    assert [c for c in without_roots if c.startswith("codex_")] == ["codex_env_roots_missing"]
    good = _audit({"command": "uv", "args": ["run", "--directory", ".", "horosa-skill", "serve", "--transport", "stdio"],
                   "startup_timeout_sec": 120, "tool_timeout_sec": 600,
                   "env": {"HOROSA_RUNTIME_ROOT": "/r", "HOROSA_SKILL_DATA_DIR": "/d"}}, client="codex")
    assert not [c for c in good if c.startswith("codex_")]


def test_client_check_flags_codex_cwd_missing(tmp_path) -> None:
    entry = {"command": "uv", "args": ["run", "horosa-skill", "serve", "--transport", "stdio"],
             "startup_timeout_sec": 120, "tool_timeout_sec": 600, "cwd": str(tmp_path / "gone")}
    assert "codex_cwd_missing" in _audit(entry, client="codex")
    entry["cwd"] = str(tmp_path)
    assert "codex_cwd_missing" not in _audit(entry, client="codex")


def test_client_check_catches_a_command_not_on_path(monkeypatch) -> None:
    """裸命令名靠 PATH，而 GUI 客户端在 Windows 上不继承 shell PATH（v0.38.0 B2）。"""
    monkeypatch.setattr(cli.shutil, "which", lambda name: None)
    codes = _audit({"command": "uvx", "args": ["--from", "git+https://x", "horosa-skill", "serve", "--transport", "stdio"]})
    assert "command_not_on_path" in codes
    # 绝对路径不查 PATH（负向对照）
    codes = _audit({"command": "/opt/uv/bin/uvx", "args": ["--from", "git+https://x", "horosa-skill", "serve", "--transport", "stdio"]})
    assert "command_not_on_path" not in codes


def test_client_check_searches_the_located_windows_paths(monkeypatch, tmp_path) -> None:
    located = tmp_path / "Roaming" / "Code" / "User" / "mcp.json"
    located.parent.mkdir(parents=True)
    located.write_text(json.dumps({"servers": {"horosa": {"type": "stdio", "command": "/opt/uv/bin/uv",
                                                          "args": ["run", "horosa-skill", "serve", "--transport", "stdio"]}}}),
                       encoding="utf-8")
    monkeypatch.setattr(cli, "_client_config_locations", lambda name, **kw: [located] if name == "vscode" else [tmp_path / "none.json"])
    result = CliRunner().invoke(cli.app, ["client", "check", "--client", "vscode"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["configured_clients"] == ["vscode"]
    assert report["clients"][0]["searched"] == [str(located)]


def test_client_check_accepts_wheel_from_and_notes_version_drift() -> None:
    """wheel 资产 URL 是免 git / 免 PyPI 的零安装源（v0.38.0 B3）：不得被当成「PyPI 未开通」；钉错版本要报。"""
    from horosa_skill import __version__

    good = f"https://github.com/o/r/releases/download/v{__version__}/horosa_skill-{__version__}-py3-none-any.whl"
    codes = _audit({"command": "/opt/uv/bin/uvx", "args": ["--from", good, "horosa-skill", "serve", "--transport", "stdio"]})
    assert "pypi_not_published" not in codes and "launcher_version_drift" not in codes
    stale = "https://github.com/o/r/releases/download/v0.0.1/horosa_skill-0.0.1-py3-none-any.whl"
    codes = _audit({"command": "/opt/uv/bin/uvx", "args": ["--from", stale, "horosa-skill", "serve", "--transport", "stdio"]})
    assert "launcher_version_drift" in codes
    git_stale = "git+https://github.com/o/horosa-skill@v0.0.1#subdirectory=horosa-skill"
    codes = _audit({"command": "/opt/uv/bin/uvx", "args": ["--from", git_stale, "horosa-skill", "serve", "--transport", "stdio"]})
    assert "launcher_version_drift" in codes


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


def test_relative_directory_resolves_against_the_config_file_not_the_cwd(tmp_path) -> None:
    """🔴 客户端启动 server 时的 CWD 是项目根，而 `client check` 可能在任何地方被调用。

    仓里提交的 `.cursor/mcp.json` 曾用 `./horosa-skill`，从 horosa-skill/ 里跑 check 就被误报
    `directory_missing`。相对路径必须按**配置文件所在目录**解析；仓内两份配置现在都用
    `${workspaceFolder}`，这条锁的是审计器本身不会再误报。
    """
    package_dir = tmp_path / "horosa-skill"
    package_dir.mkdir()
    (package_dir / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    entry = {"command": "uv", "args": ["run", "--directory", "./horosa-skill",
                                       "horosa-skill", "serve", "--transport", "stdio"]}
    assert _audit(entry, config_dir=tmp_path) == []
    assert "directory_missing" in _audit(entry, config_dir=tmp_path / "elsewhere")


def test_committed_client_configs_are_clean() -> None:
    """仓里提交的 `.vscode/mcp.json` / `.cursor/mcp.json` 必须自己过体检。"""
    import json
    from pathlib import Path as _Path

    repo_root = _Path(__file__).resolve().parents[2]
    for rel, client in ((".vscode/mcp.json", "vscode"), (".cursor/mcp.json", "cursor")):
        path = repo_root / rel
        assert path.is_file(), f"{rel} 应随仓提交（打开仓即用）"
        payload = json.loads(path.read_text(encoding="utf-8"))
        entries = list(cli._iter_client_entries(payload))
        assert entries, f"{rel} 里没有 horosa 条目"
        for entry_name, entry in entries:
            problems = cli._audit_client_entry(entry_name, entry, client=client, config_dir=path.parent)
            assert problems == [], f"{rel}: {[p['code'] for p in problems]}"


# ---------------------------------------------------------------- v0.38.1 R7：streamable-http 真握手


def test_streamable_http_handshake_end_to_end(tmp_path) -> None:
    """真起一次 `serve --transport streamable-http`：无令牌 401、错 Host 421、带 Bearer 的 initialize + tools/list = 全量面。"""
    import os
    import socket
    import subprocess
    import sys
    import time

    import anyio
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    from horosa_skill.engine.registry import TOOL_DEFINITIONS
    from horosa_skill.surfaces.mcp_server import FACADE_TOOL_COUNT

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    token = "lane-token-0123456789"
    env = {**os.environ, "HOROSA_RUNTIME_ROOT": str(tmp_path / "rt"), "HOROSA_SKILL_DATA_DIR": str(tmp_path / "data"), "PYTHONIOENCODING": "utf-8"}
    env.pop("HOROSA_MCP_COMPACT", None)
    env.pop("HOROSA_TOOLSETS", None)
    url = f"http://127.0.0.1:{port}/mcp"
    proc = subprocess.Popen(
        [sys.executable, "-m", "horosa_skill.surfaces.cli", "serve", "--transport", "streamable-http", "--host", "127.0.0.1",
         "--port", str(port), "--token", token, "--skip-runtime-start"],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
    )
    try:
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    break
            except OSError:
                assert proc.poll() is None, f"serve exited early: {proc.stderr.read()[-800:] if proc.stderr else ''}"
                time.sleep(0.5)
        body = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}
        headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
        with httpx.Client(timeout=30) as http:
            assert http.post(url, json=body, headers=headers).status_code == 401
            assert http.post(url, json=body, headers={**headers, "Authorization": f"Bearer {token}", "Host": "evil.example"}).status_code == 421

        async def handshake() -> int:
            with anyio.fail_after(60):
                async with streamablehttp_client(url, headers={"Authorization": f"Bearer {token}"}) as (read, write, _sid):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        return len((await session.list_tools()).tools)

        assert anyio.run(handshake) == FACADE_TOOL_COUNT + len(TOOL_DEFINITIONS)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
