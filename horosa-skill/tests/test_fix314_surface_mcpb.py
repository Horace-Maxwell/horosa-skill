"""审计 surface 待决项 1(a)(b)：MCPB 带隐私政策链接；Claude Desktop（MCPB 与 client config）缺省精简面，全量是用户可选项。"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from typer.testing import CliRunner

from horosa_skill.surfaces.cli import app

PKG = Path(__file__).resolve().parents[1]


def _guard():
    spec = importlib.util.spec_from_file_location("verify_mcpb_manifest", PKG / "scripts" / "verify_mcpb_manifest.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_manifest_carries_privacy_policy_and_compact_default() -> None:
    """负向对照（实跑过）：去掉 privacy_policies / compact_tools 缺省改 false / env 不映射 → policy_errors 各报一条。"""
    guard = _guard()
    manifest = json.loads((PKG / "manifest.json").read_text(encoding="utf-8"))
    assert guard.policy_errors(manifest) == []
    broken = json.loads(json.dumps(manifest))
    broken.pop("privacy_policies")
    broken["user_config"]["compact_tools"]["default"] = False
    broken["server"]["mcp_config"]["env"].pop("HOROSA_MCP_COMPACT")
    assert len(guard.policy_errors(broken)) == 3


def test_claude_desktop_config_defaults_to_the_compact_surface() -> None:
    """负向对照：locations._CLIENT_COMPACT_DEFAULT["claude-desktop"] 改回 False → 红。"""
    result = CliRunner().invoke(app, ["client", "config", "--format", "claude-desktop"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["mcpServers"]["horosa"]["env"]["HOROSA_MCP_COMPACT"] == "1"
    full = json.loads(CliRunner().invoke(app, ["client", "config", "--format", "claude-desktop", "--surface", "full"]).output)
    assert (full["mcpServers"]["horosa"].get("env") or {}).get("HOROSA_MCP_COMPACT") in (None, "0")
