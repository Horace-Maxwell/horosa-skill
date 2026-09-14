"""client config 生成器测试（v0.33.0 批 III-6）——此前五格式零测试。

重点盯 codex：TOML 产物必须可解析、字段 ⊆ Codex RawMcpServerConfig 白名单
（deny_unknown_fields：写错一个字段=整段拒收），`--write` 三态（新文件整写 /
已有 TOML 只动 [mcp_servers.<name>] 表并备份 / 非法 TOML 拒绝合并绝不覆盖）。
`--write` 曾把用户 config.toml 整个覆盖成 JSON（毁文件雷，III-1 拆除）。
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from horosa_skill.surfaces.cli import app

runner = CliRunner()


def _payload(*args: str) -> dict:
    result = runner.invoke(app, ["client", "config", *args])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


@pytest.mark.parametrize("fmt", ["claude-code", "claude-desktop", "cursor", "vscode", "codex"])
def test_all_formats_emit_payload(fmt: str) -> None:
    payload = _payload("--format", fmt)
    assert isinstance(payload, dict) and payload, fmt
    assert payload.get("note") or payload.get("command") or payload.get("mcpServers"), fmt


def test_codex_toml_parses_and_fields_stay_in_whitelist() -> None:
    payload = _payload("--format", "codex", "--server-name", "horosa")
    doc = tomllib.loads(payload["toml_stdio"])
    server = doc["mcp_servers"]["horosa"]
    # Codex RawMcpServerConfig 有效字段集（deny_unknown_fields）；env 是嵌套表。
    allowed = {
        "command", "args", "env", "cwd", "url", "bearer_token_env_var",
        "startup_timeout_sec", "tool_timeout_sec", "enabled", "required",
        "enabled_tools", "disabled_tools",
    }
    unknown = sorted(set(server) - allowed)
    assert unknown == [], f"生成了 Codex 会整段拒收的未知字段：{unknown}"
    assert server["startup_timeout_sec"] == 120, "必须盖过 45s 冷启动（Codex 默认 30s 不够）"
    assert server["tool_timeout_sec"] == 600
    assert Path(server["cwd"]).is_absolute()
    assert isinstance(server["args"], list) and "stdio" in server["args"]
    assert isinstance(server.get("env"), dict), "env 表必须在场（Codex 只透传 11 个系统变量白名单）"
    http_doc = tomllib.loads(payload["toml_http"])
    assert http_doc["mcp_servers"]["horosa"]["url"].startswith("http://")


def test_codex_write_creates_new_file_as_toml(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    _payload("--format", "codex", "--write", str(target))
    text = target.read_text(encoding="utf-8")
    doc = tomllib.loads(text)
    assert "horosa" in doc["mcp_servers"]
    assert not text.lstrip().startswith("{"), "绝不能把 TOML 目标写成 JSON"


def test_codex_write_merges_preserving_existing_content(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    target.write_text(
        "# 用户自己的注释\n"
        "model = \"o4\"\n"
        "\n"
        "[mcp_servers.other]\n"
        "command = \"other-server\"\n",
        encoding="utf-8",
    )
    _payload("--format", "codex", "--write", str(target))
    text = target.read_text(encoding="utf-8")
    doc = tomllib.loads(text)
    assert doc["model"] == "o4", "用户顶层配置必须保留"
    assert doc["mcp_servers"]["other"]["command"] == "other-server", "既有 server 必须保留"
    assert "horosa" in doc["mcp_servers"]
    assert "# 用户自己的注释" in text, "注释逐字保留（tomlkit）"
    backup = tmp_path / "config.toml.horosa-bak"
    assert backup.exists() and "other-server" in backup.read_text(encoding="utf-8")


def test_codex_write_refuses_to_clobber_invalid_toml(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    target.write_text("{ this is not toml at all ]", encoding="utf-8")
    result = runner.invoke(app, ["client", "config", "--format", "codex", "--write", str(target)])
    assert result.exit_code != 0
    assert target.read_text(encoding="utf-8") == "{ this is not toml at all ]", "拒绝合并时用户文件必须原封不动"


def test_json_write_still_merges_mcp_servers(tmp_path: Path) -> None:
    """既有 JSON 合并路径零回归（claude-desktop 家族）。"""
    target = tmp_path / "claude_desktop_config.json"
    target.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}, "theme": "dark"}), encoding="utf-8")
    _payload("--format", "claude-desktop", "--write", str(target))
    merged = json.loads(target.read_text(encoding="utf-8"))
    assert merged["theme"] == "dark"
    assert set(merged["mcpServers"]) == {"other", "horosa"}


# ---- v0.36.0 C4：PyPI 分发 → `--launcher uvx`；v0.38.0 B2：写绝对路径，找不到才退回裸名并警告 ----
def test_client_config_launcher_uvx_emits_absolute_command_when_found(monkeypatch: pytest.MonkeyPatch) -> None:
    from horosa_skill.surfaces import cli

    monkeypatch.setattr(cli, "resolve_uvx_command", lambda: ["/opt/uv/bin/uvx"])
    payload = _payload("--format", "claude-desktop", "--launcher", "uvx")
    server = payload["mcpServers"]["horosa"]
    assert server["command"] == "/opt/uv/bin/uvx"
    assert server["args"] == ["horosa-skill", "serve", "--transport", "stdio"]
    assert "warnings" not in payload
    claude_code = _payload("--format", "claude-code", "--launcher", "uvx-git")
    assert claude_code["command"].startswith("claude mcp add horosa -- /opt/uv/bin/uvx --from git+https://github.com/")
    assert claude_code["mcpServers"]["horosa"]["command"] == "/opt/uv/bin/uvx"


def test_client_config_launcher_uvx_warns_when_uvx_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from horosa_skill.surfaces import cli

    def missing() -> list[str]:
        raise FileNotFoundError("uvx not found")

    monkeypatch.setattr(cli, "resolve_uvx_command", missing)
    payload = _payload("--format", "claude-desktop", "--launcher", "uvx")
    assert payload["mcpServers"]["horosa"]["command"] == "uvx"
    assert any("uvx" in w for w in payload["warnings"])
    bad = runner.invoke(app, ["client", "config", "--format", "claude-desktop", "--launcher", "pipx"])
    assert bad.exit_code != 0


# ---- v0.38.0 B2：根键感知的安全合并（vscode/zed/claude-code 曾被整文件覆盖）----
def _write(fmt: str, target: Path, *extra: str) -> dict:
    return _payload("--format", fmt, "--write", str(target), *extra)


def test_vscode_write_merges_under_servers_and_keeps_user_keys(tmp_path: Path) -> None:
    target = tmp_path / "mcp.json"
    target.write_text(json.dumps({"servers": {"other": {"type": "stdio", "command": "x"}}, "inputs": [1]}), encoding="utf-8")
    payload = _write("vscode", target)
    merged = json.loads(target.read_text(encoding="utf-8"))
    assert set(merged["servers"]) == {"other", "horosa"} and merged["inputs"] == [1]
    assert merged["servers"]["horosa"]["type"] == "stdio"
    assert payload["written"]["root_key"] == "servers"


def test_zed_write_merges_context_servers_and_keeps_theme(tmp_path: Path) -> None:
    """现状（v0.37）必红 = 负向对照：zed 产物没有 mcpServers → 整文件覆盖，theme 丢失。"""
    target = tmp_path / "settings.json"
    target.write_text(json.dumps({"theme": "One Dark", "context_servers": {"other": {"command": "x"}}}), encoding="utf-8")
    _write("zed", target)
    merged = json.loads(target.read_text(encoding="utf-8"))
    assert merged["theme"] == "One Dark"
    assert set(merged["context_servers"]) == {"other", "horosa"}
    assert "note" not in merged and "tool_surface" not in merged


def test_claude_code_write_merges_project_mcp_json(tmp_path: Path) -> None:
    # 文件名故意不用项目级那个点开头的名字：test_verify_client_configs 把「谁读过它」钉成了前提。
    target = tmp_path / "project" / "mcp.json"
    _write("claude-code", target)
    merged = json.loads(target.read_text(encoding="utf-8"))
    assert list(merged) == ["mcpServers"] and "horosa" in merged["mcpServers"]
    assert "--transport" in merged["mcpServers"]["horosa"]["args"]


def test_json_write_creates_backup_and_never_writes_meta_keys(tmp_path: Path) -> None:
    target = tmp_path / "claude_desktop_config.json"
    target.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}), encoding="utf-8")
    payload = _write("claude-desktop", target)
    backup = tmp_path / "claude_desktop_config.json.horosa-bak"
    assert backup.exists() and "other" in backup.read_text(encoding="utf-8")
    assert payload["written"]["backup"] == str(backup)
    merged = json.loads(target.read_text(encoding="utf-8"))
    assert set(merged) == {"mcpServers"}
    for meta in ("note", "tool_surface", "config_path", "deep_link", "install_link", "cli_command", "warnings", "written"):
        assert meta not in merged


def test_json_write_refuses_non_object_or_invalid_json_untouched(tmp_path: Path) -> None:
    for raw in ("[1, 2, 3]", "{ not json"):
        target = tmp_path / "settings.json"
        target.write_text(raw, encoding="utf-8")
        result = runner.invoke(app, ["client", "config", "--format", "cursor", "--write", str(target)])
        assert result.exit_code != 0, raw
        assert target.read_text(encoding="utf-8") == raw, "拒绝合并时用户文件必须原封不动"


def test_json_write_is_atomic_when_replace_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from horosa_skill.surfaces import cli

    target = tmp_path / "mcp.json"
    original = json.dumps({"mcpServers": {"other": {"command": "x"}}})
    target.write_text(original, encoding="utf-8")

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(cli.os, "replace", boom)
    result = runner.invoke(app, ["client", "config", "--format", "cursor", "--write", str(target)])
    assert result.exit_code != 0
    assert target.read_text(encoding="utf-8") == original
    assert not (tmp_path / "mcp.json.horosa-tmp").exists(), "半成品临时文件不许留下"


def test_openclaw_note_only_formats_refuse_to_write_prose_as_config(tmp_path: Path) -> None:
    from horosa_skill.surfaces import cli

    with pytest.raises(Exception):
        cli._merge_client_config(tmp_path / "x.json", {"note": "只有说明，没有 server 块"})
    assert not (tmp_path / "x.json").exists()


# ---- v0.38.0 B2：各 OS 的真实配置路径 ----
def test_client_config_locations_windows_shapes() -> None:
    from horosa_skill.surfaces import cli

    env = {"APPDATA": r"C:\Users\张 三\AppData\Roaming"}
    for client in cli._CLIENT_NAMES:
        paths = [str(p) for p in cli._client_config_locations(client, os_name="nt", env=env, home=r"C:\Users\张 三", cwd=r"D:\proj")]
        assert paths, client
        assert all("张 三" in p or p.startswith("D:") for p in paths), (client, paths)
    zed = str(cli._client_config_locations("zed", os_name="nt", env=env, home=r"C:\Users\张 三")[0])
    assert zed.endswith("settings.json") and "Zed" in zed and "Roaming" in zed
    vscode = str(cli._client_config_locations("vscode", os_name="nt", env=env, home=r"C:\Users\张 三")[0])
    assert "Code" in vscode and vscode.endswith("mcp.json") and "Roaming" in vscode
    cline = str(cli._client_config_locations("cline", os_name="nt", env=env, home=r"C:\Users\张 三")[0])
    assert "saoudrizwan.claude-dev" in cline and "Roaming" in cline


def test_client_config_locations_darwin_and_linux_shapes(tmp_path: Path) -> None:
    from horosa_skill.surfaces import cli

    # env={}：Linux runner 设了 XDG_CONFIG_HOME=/home/runner/.config（v0.38.1 C19 起会覆盖合成 home）；本机没设所以曾只在 CI 红
    mac = str(cli._client_config_locations("claude-desktop", os_name="darwin", home=tmp_path, env={})[0])
    assert mac == str(tmp_path / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json")
    linux = str(cli._client_config_locations("claude-desktop", os_name="linux", home=tmp_path, env={})[0])
    assert linux == str(tmp_path / ".config" / "Claude" / "claude_desktop_config.json")
    # as_posix(): on a Windows host str(Path) uses backslashes and this assertion went red on every Windows run
    assert cli._client_config_locations("zed", os_name="darwin", home=tmp_path, env={})[0].as_posix().endswith(".config/zed/settings.json")
    with pytest.raises(Exception):
        cli._client_config_locations("roo", os_name="darwin", home=tmp_path)


def test_client_config_reports_a_real_config_path_for_every_json_client(monkeypatch: pytest.MonkeyPatch) -> None:
    for fmt in ("claude-code", "claude-desktop", "cursor", "vscode", "codex", "gemini", "windsurf", "cline", "zed"):
        payload = _payload("--format", fmt)
        assert Path(payload["config_path"]).is_absolute(), (fmt, payload["config_path"])


def test_codex_toml_round_trips_spaced_cjk_windows_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from horosa_skill.surfaces import cli

    root = tmp_path / "张 三" / "horosa-skill"
    root.mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    monkeypatch.setattr(cli, "resolve_uv_command", lambda: [r"C:\Users\张 三\AppData\Local\Programs\uv\uv.exe"])
    payload = _payload("--format", "codex", "--skill-root", str(root))
    server = tomllib.loads(payload["toml_stdio"])["mcp_servers"]["horosa"]
    assert server["command"] == r"C:\Users\张 三\AppData\Local\Programs\uv\uv.exe"
    assert server["args"][2] == str(root.resolve())


# ---- v0.38.0 B3：免 git / 免 PyPI 的零安装 → `--launcher uvx-wheel`（镜像感知、钉版本）----
def test_launcher_uvx_wheel_emits_pinned_release_url(monkeypatch: pytest.MonkeyPatch) -> None:
    from horosa_skill import __version__
    from horosa_skill.surfaces import cli

    monkeypatch.delenv("HOROSA_RUNTIME_MIRROR", raising=False)
    monkeypatch.setattr(cli, "resolve_uvx_command", lambda: ["/opt/uv/bin/uvx"])
    payload = _payload("--format", "claude-desktop", "--launcher", "uvx-wheel")
    server = payload["mcpServers"]["horosa"]
    expected = f"https://github.com/Horace-Maxwell/horosa-skill/releases/download/v{__version__}/horosa_skill-{__version__}-py3-none-any.whl"
    assert server["command"] == "/opt/uv/bin/uvx"
    assert server["args"] == ["--from", expected, "horosa-skill", "serve", "--transport", "stdio"]
    assert payload["launcher"]["kind"] == "uvx-wheel" and payload["launcher"]["pinned_version"] == __version__
    assert payload["launcher"]["alternatives"] == [expected]
    assert "uvx --from" in payload["launcher"]["install_hint"]


def test_launcher_uvx_wheel_uses_the_first_mirror_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    from horosa_skill import __version__
    from horosa_skill.surfaces import cli

    monkeypatch.setenv("HOROSA_RUNTIME_MIRROR", "https://mirror.example/gh, https://m2.example.org/")
    monkeypatch.setattr(cli, "resolve_uvx_command", lambda: ["/opt/uv/bin/uvx"])
    payload = _payload("--format", "cursor", "--launcher", "uvx-wheel")
    url = payload["mcpServers"]["horosa"]["args"][1]
    assert url.startswith("https://mirror.example/gh/Horace-Maxwell/horosa-skill/releases/download/v")
    alternatives = payload["launcher"]["alternatives"]
    assert len(alternatives) == 3 and alternatives[-1].startswith("https://github.com/")
    assert alternatives[1].startswith("https://m2.example.org/Horace-Maxwell/")
    # 负向对照：没有镜像时 URL 就是原始 GitHub 地址
    monkeypatch.delenv("HOROSA_RUNTIME_MIRROR")
    payload = _payload("--format", "cursor", "--launcher", "uvx-wheel")
    assert payload["mcpServers"]["horosa"]["args"][1].startswith("https://github.com/")


# ---- v0.38.1 A4 / A7 ----
def test_claude_code_command_keeps_a_spaced_checkout_path_as_one_argument(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """README 教的是复制粘贴这条命令：`/Users/x/My Projects/horosa-skill` 不带引号会被 shell 拆成两个参数。"""
    import shlex

    from horosa_skill.surfaces import cli

    root = tmp_path / "My Projects" / "horosa-skill"
    root.mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname = 'horosa-skill'\n", encoding="utf-8")
    monkeypatch.setattr(cli, "resolve_uv_command", lambda: ["/opt/u v/bin/uv"])
    payload = _payload("--format", "claude-code", "--skill-root", str(root), "--surface", "compact")
    argv = shlex.split(payload["command"])
    assert argv[:4] == ["claude", "mcp", "add", "horosa"]
    assert "-e" in argv and "HOROSA_MCP_COMPACT=1" in argv
    assert "/opt/u v/bin/uv" in argv and str(root.resolve()) in argv, argv
    assert argv[argv.index("--") + 1] == "/opt/u v/bin/uv"


def test_codex_merge_accepts_a_utf16_config(tmp_path: Path) -> None:
    from horosa_skill.surfaces.cli import _write_codex_toml_merge

    target = tmp_path / "config.toml"
    target.write_bytes("[other]\nx = 1\n".encode("utf-16"))  # Notepad / Out-File 形状：BOM ff fe
    assert target.read_bytes()[:2] in {b"\xff\xfe", b"\xfe\xff"}
    _write_codex_toml_merge(target, '[mcp_servers.horosa]\ncommand = "uv"\n')
    merged = tomllib.loads(target.read_text(encoding="utf-8"))
    assert merged["other"]["x"] == 1 and merged["mcp_servers"]["horosa"]["command"] == "uv"


def test_codex_merge_refuses_undecodable_bytes_without_a_traceback(tmp_path: Path) -> None:
    import typer

    from horosa_skill.surfaces.cli import _write_codex_toml_merge

    target = tmp_path / "config.toml"
    garbage = b"\xff\xfe" + b"\x00\xd8" * 4  # UTF-16 BOM + 孤立代理项 → UnicodeDecodeError
    target.write_bytes(garbage)
    with pytest.raises(typer.BadParameter):
        _write_codex_toml_merge(target, '[mcp_servers.horosa]\ncommand = "uv"\n')
    assert target.read_bytes() == garbage, "拒绝合并时用户文件必须原封不动"


# ---- v0.38.1 B2：C1 compose / C3 占位符白名单 / C5 超时 / C6 Codex env 根 / C10 项目根 / C19 路径表 / C15 本地 wheel ----
def test_docker_compose_gateway_declares_both_roots_and_requires_a_token() -> None:
    compose = (Path(__file__).resolve().parents[1] / "docker-compose.yml").read_text(encoding="utf-8")
    env_block = compose.split("environment:", 1)[1].split("volumes:", 1)[0]
    assert "HOROSA_SERVER_ROOT:" in env_block and "HOROSA_CHART_SERVER_ROOT:" in env_block, "少一个 ROOT，chart 族在容器里全部失败"
    assert "host.docker.internal:8899" in env_block and "host.docker.internal:9999" in env_block
    assert "HOROSA_MCP_TOKEN: ${HOROSA_MCP_TOKEN:?" in env_block, "绑 0.0.0.0 必须给令牌"


def test_cline_and_zed_entries_carry_a_600_second_timeout() -> None:
    cline = _payload("--format", "cline")["mcpServers"]["horosa"]
    zed = _payload("--format", "zed")["context_servers"]["horosa"]
    assert cline["timeout"] == 600 and cline["type"] == "stdio"
    assert zed["timeout"] == 600 and "source" not in zed, "Zed 的 context_servers 条目没有 source 字段"


@pytest.mark.parametrize("client", ["cline", "zed"])
def test_client_check_flags_missing_or_short_timeouts_for_cline_and_zed(client: str) -> None:
    from horosa_skill.surfaces.cli import _audit_client_entry

    base = {"command": "/opt/uv/bin/uv", "args": ["run", "horosa-skill", "serve", "--transport", "stdio"]}
    codes = [p["code"] for p in _audit_client_entry("horosa", base, client=client)]
    assert f"{client}_tool_timeout_missing" in codes
    codes = [p["code"] for p in _audit_client_entry("horosa", {**base, "timeout": 60}, client=client)]
    assert f"{client}_tool_timeout_too_short" in codes
    codes = [p["code"] for p in _audit_client_entry("horosa", {**base, "timeout": 600}, client=client)]
    assert not any("timeout" in code for code in codes)


def test_codex_toml_declares_absolute_runtime_and_data_roots(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOROSA_RUNTIME_ROOT", str(tmp_path / "rt"))
    monkeypatch.setenv("HOROSA_SKILL_DATA_DIR", str(tmp_path / "data"))
    doc = tomllib.loads(_payload("--format", "codex")["toml_stdio"])
    env = doc["mcp_servers"]["horosa"]["env"]
    assert Path(env["HOROSA_RUNTIME_ROOT"]) == (tmp_path / "rt").resolve()
    assert Path(env["HOROSA_SKILL_DATA_DIR"]) == (tmp_path / "data").resolve()
    assert "env_vars" not in doc["mcp_servers"]["horosa"], "老版本 Codex 对未知键 deny_unknown_fields"


def test_client_check_flags_a_codex_entry_without_the_env_roots() -> None:
    from horosa_skill.surfaces.cli import _audit_client_entry

    entry = {"command": "/opt/uv/bin/uv", "args": ["run", "horosa-skill", "serve", "--transport", "stdio"],
             "startup_timeout_sec": 120, "tool_timeout_sec": 600, "env": {"HOROSA_MCP_COMPACT": "1"}}
    assert "codex_env_roots_missing" in [p["code"] for p in _audit_client_entry("horosa", entry, client="codex")]
    entry["env"].update({"HOROSA_RUNTIME_ROOT": "/r", "HOROSA_SKILL_DATA_DIR": "/d"})
    assert "codex_env_roots_missing" not in [p["code"] for p in _audit_client_entry("horosa", entry, client="codex")]


def test_placeholders_are_judged_per_client(tmp_path: Path) -> None:
    from horosa_skill.surfaces import cli

    args = ["run", "--directory", "${workspaceFolder}/horosa-skill", "horosa-skill", "serve", "--transport", "stdio"]
    project = tmp_path / "proj"
    (project / "horosa-skill").mkdir(parents=True)
    (project / "horosa-skill" / "pyproject.toml").write_text("[project]\nname='horosa-skill'\n", encoding="utf-8")
    (project / ".vscode").mkdir()
    ok = cli._audit_client_entry("horosa", {"command": "/opt/uv/bin/uv", "args": args}, client="vscode", config_dir=project / ".vscode")
    assert [p["code"] for p in ok] == [], ok
    # 负向对照：VS Code 不展开 Claude Code 的变量 —— 旧判定放行它（只要 blob 里有 ${CLAUDE_PROJECT_DIR）。
    bad_args = ["run", "--directory", "${CLAUDE_PROJECT_DIR:-.}/horosa-skill", "horosa-skill", "serve", "--transport", "stdio"]
    bad = cli._audit_client_entry("horosa", {"command": "/opt/uv/bin/uv", "args": bad_args}, client="vscode", config_dir=project / ".vscode")
    assert "unexpanded_placeholder" in [p["code"] for p in bad]
    # Cursor 认 ${env:…}；Claude Code 认 ${CLAUDE_PROJECT_DIR:-.}
    env_args = ["run", "--directory", "${env:HOROSA_CHECKOUT:-" + str(project) + "}/horosa-skill", "horosa-skill", "serve", "--transport", "stdio"]
    assert "unexpanded_placeholder" not in [p["code"] for p in cli._audit_client_entry("horosa", {"command": "/opt/uv/bin/uv", "args": env_args}, client="cursor", config_dir=project / ".cursor")]
    assert "unexpanded_placeholder" not in [p["code"] for p in cli._audit_client_entry("horosa", {"command": "/opt/uv/bin/uv", "args": bad_args}, client="claude-code", config_dir=project)]
    # 展开后目录不存在 → directory_missing（此前含占位符就跳过检查）
    missing = cli._audit_client_entry("horosa", {"command": "/opt/uv/bin/uv", "args": ["run", "--directory", "${workspaceFolder}/elsewhere", "horosa-skill", "serve", "--transport", "stdio"]}, client="cursor", config_dir=project / ".cursor")
    assert "directory_missing" in [p["code"] for p in missing]


def test_project_root_walks_up_to_git_or_mcp_json(tmp_path: Path) -> None:
    from horosa_skill.surfaces.cli import _project_root

    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    deep = repo / "horosa-skill" / "src"
    deep.mkdir(parents=True)
    assert _project_root(deep) == repo.resolve()
    loose = tmp_path / "loose" / "dir"
    loose.mkdir(parents=True)
    assert _project_root(loose) == loose.resolve()
    (tmp_path / "loose" / ".mcp.json").write_text("{}", encoding="utf-8")
    assert _project_root(loose) == (tmp_path / "loose").resolve()


def test_project_level_config_locations_follow_the_project_root(tmp_path: Path) -> None:
    from horosa_skill.surfaces import cli

    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    sub = repo / "horosa-skill"
    sub.mkdir()
    paths = cli._client_config_locations("cursor", os_name="darwin", home=tmp_path / "home", cwd=cli._project_root(sub))
    assert paths[-1] == repo / ".cursor" / "mcp.json"


def test_config_locations_honour_codex_home_xdg_and_secondary_cline_hosts(tmp_path: Path) -> None:
    from horosa_skill.surfaces import cli

    env = {"CODEX_HOME": str(tmp_path / "codex-home"), "XDG_CONFIG_HOME": str(tmp_path / "xdg")}
    assert cli._client_config_locations("codex", os_name="linux", env=env, home=tmp_path)[0] == tmp_path / "codex-home" / "config.toml"
    assert cli._client_config_locations("zed", os_name="linux", env=env, home=tmp_path)[0] == tmp_path / "xdg" / "zed" / "settings.json"
    assert cli._client_config_locations("claude-desktop", os_name="linux", env={}, home=tmp_path)[0] == tmp_path / ".config" / "Claude" / "claude_desktop_config.json"
    gemini = cli._client_config_locations("gemini", os_name="darwin", home=tmp_path, cwd=tmp_path / "proj")
    assert gemini[-1] == tmp_path / "proj" / ".gemini" / "settings.json"
    cline = [p.as_posix() for p in cli._client_config_locations("cline", os_name="darwin", home=tmp_path)]
    assert any("/Code/User/" in p for p in cline) and any("/Cursor/User/" in p for p in cline) and any("/Windsurf/User/" in p for p in cline)
    assert all(p.endswith("saoudrizwan.claude-dev/settings/cline_mcp_settings.json") for p in cline)


def test_client_check_understands_a_local_wheel_source(tmp_path: Path) -> None:
    from horosa_skill import __version__
    from horosa_skill.surfaces.cli import _audit_client_entry

    wheel = tmp_path / f"horosa_skill-{__version__}-py3-none-any.whl"
    entry = {"command": "/opt/uv/bin/uvx", "args": ["--from", str(wheel), "horosa-skill", "serve", "--transport", "stdio"]}
    assert "wheel_cache_missing" in [p["code"] for p in _audit_client_entry("horosa", entry, client="cursor")]
    wheel.write_bytes(b"PK")
    codes = [p["code"] for p in _audit_client_entry("horosa", entry, client="cursor")]
    assert "wheel_cache_missing" not in codes and "launcher_version_drift" not in codes
    stale = tmp_path / "horosa_skill-0.1.0-py3-none-any.whl"
    stale.write_bytes(b"PK")
    entry["args"][1] = str(stale)
    assert "launcher_version_drift" in [p["code"] for p in _audit_client_entry("horosa", entry, client="cursor")]
