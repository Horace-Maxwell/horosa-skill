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
