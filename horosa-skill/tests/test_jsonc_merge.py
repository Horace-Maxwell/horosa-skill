"""JSONC（带注释 / 尾逗号）客户端配置的读与保注释写入（v0.38.1 C4）。

负向对照：Zed 出厂 settings.json 模板直接喂 `json.loads` 必抛 —— 证明旧 `_merge_client_config` 会以「不是合法 JSON」拒写。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from horosa_skill import jsonc
from horosa_skill.surfaces import cli as cli_module
from horosa_skill.surfaces.cli import app

runner = CliRunner()

ZED_TEMPLATE = """// Zed settings
//
// For information on how to configure Zed, see the Zed
// documentation: https://zed.dev/docs/configuring-zed
{
  "ui_font_size": 16,
  "buffer_font_size": 16,
  /* block comment */
  "theme": {
    "mode": "system",
    "light": "One Light",
    "dark": "One Dark",
  },
  "context_servers": {
    "other": { "command": "x", "args": [] },
  },
}
"""
VSCODE_TEMPLATE = """{
  // Example mcp.json with comments
  "inputs": [],
  "servers": {
    "other": { "type": "stdio", "command": "x" }, // trailing comment
  },
}
"""


def test_the_zed_template_is_not_strict_json() -> None:
    """旧代码用 json.loads → JSONDecodeError → 拒写。这条红了说明 Zed 模板变成了严格 JSON，本模块的理由消失。"""
    with pytest.raises(json.JSONDecodeError):
        json.loads(ZED_TEMPLATE)
    assert jsonc.is_jsonc_only(ZED_TEMPLATE) and jsonc.is_jsonc_only(VSCODE_TEMPLATE)
    assert not jsonc.is_jsonc_only('{"a": 1}') and not jsonc.is_jsonc_only("")


def test_strip_comments_keeps_string_contents_intact() -> None:
    text = '{"url": "http://x/y", "note": "a // not a comment /* nor this */", "list": [1, 2,], }'
    assert jsonc.loads(text) == {"url": "http://x/y", "note": "a // not a comment /* nor this */", "list": [1, 2]}


def test_upsert_into_an_existing_block_keeps_comments_and_other_keys() -> None:
    out = jsonc.upsert_server_entry(ZED_TEMPLATE, "context_servers", "horosa", {"command": "/u/uv", "args": ["run"], "timeout": 600})
    doc = jsonc.loads(out)
    assert set(doc["context_servers"]) == {"other", "horosa"} and doc["context_servers"]["horosa"]["timeout"] == 600
    assert doc["theme"]["dark"] == "One Dark" and doc["ui_font_size"] == 16
    for comment in ("// Zed settings", "/* block comment */", "https://zed.dev/docs/configuring-zed"):
        assert comment in out
    assert out.index('"horosa"') < out.index('"other"'), "插在块开头，用户自己的条目原样跟在后面"


def test_upsert_replaces_an_existing_entry_in_place() -> None:
    once = jsonc.upsert_server_entry(ZED_TEMPLATE, "context_servers", "horosa", {"command": "/old", "args": []})
    twice = jsonc.upsert_server_entry(once, "context_servers", "horosa", {"command": "/new", "args": ["a"]})
    doc = jsonc.loads(twice)
    assert doc["context_servers"]["horosa"] == {"command": "/new", "args": ["a"]}
    assert doc["context_servers"]["other"]["command"] == "x" and twice.count('"horosa"') == 1
    assert "// Zed settings" in twice


def test_upsert_creates_the_root_block_when_missing() -> None:
    out = jsonc.upsert_server_entry(VSCODE_TEMPLATE.replace('"servers"', '"servers_disabled"'), "servers", "horosa", {"type": "stdio", "command": "uv"})
    doc = jsonc.loads(out)
    assert doc["servers"]["horosa"]["type"] == "stdio" and doc["inputs"] == [] and "servers_disabled" in doc
    assert "// Example mcp.json with comments" in out


def test_upsert_survives_braces_inside_strings() -> None:
    text = '{"mcpServers": {"a": {"env": {"X": "{y}"}, "args": ["}", "{"]}}, "z": "}"}'
    doc = jsonc.loads(jsonc.upsert_server_entry(text, "mcpServers", "horosa", {"command": "uv"}))
    assert set(doc["mcpServers"]) == {"a", "horosa"} and doc["z"] == "}" and doc["mcpServers"]["a"]["args"] == ["}", "{"]


def _write(fmt: str, target: Path) -> dict:
    result = runner.invoke(app, ["client", "config", "--format", fmt, "--write", str(target)])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_client_config_write_merges_into_a_commented_zed_settings_file(tmp_path: Path) -> None:
    target = tmp_path / "settings.json"
    target.write_text(ZED_TEMPLATE, encoding="utf-8")
    payload = _write("zed", target)
    text = target.read_text(encoding="utf-8")
    doc = jsonc.loads(text)
    assert set(doc["context_servers"]) == {"other", "horosa"} and doc["context_servers"]["horosa"]["timeout"] == 600
    assert "// Zed settings" in text and "/* block comment */" in text and doc["theme"]["dark"] == "One Dark"
    assert payload["written"]["format"] == "jsonc" and Path(payload["written"]["backup"]).read_text(encoding="utf-8") == ZED_TEMPLATE
    _write("zed", target)  # 幂等：第二次替换同名条目，不重复
    assert target.read_text(encoding="utf-8").count('"horosa"') == 1


def test_client_config_write_merges_into_a_commented_vscode_mcp_json(tmp_path: Path) -> None:
    target = tmp_path / "mcp.json"
    target.write_text(VSCODE_TEMPLATE, encoding="utf-8")
    _write("vscode", target)
    text = target.read_text(encoding="utf-8")
    doc = jsonc.loads(text)
    assert set(doc["servers"]) == {"other", "horosa"} and doc["servers"]["horosa"]["type"] == "stdio"
    assert "// Example mcp.json with comments" in text and "// trailing comment" in text


def test_strict_json_files_still_take_the_structured_merge_path(tmp_path: Path) -> None:
    target = tmp_path / "settings.json"
    target.write_text(json.dumps({"theme": "One Dark", "context_servers": {"other": {"command": "x"}}}), encoding="utf-8")
    payload = _write("zed", target)
    assert payload["written"]["format"] == "json"
    merged = json.loads(target.read_text(encoding="utf-8"))
    assert set(merged["context_servers"]) == {"other", "horosa"} and merged["theme"] == "One Dark"


def test_client_check_reads_commented_configs(tmp_path: Path) -> None:
    target = tmp_path / "settings.json"
    target.write_text(ZED_TEMPLATE, encoding="utf-8")
    _write("zed", target)
    report = cli_module._client_check_report(["zed"], target)
    finding = next(f for f in report["clients"][0]["findings"] if f.get("entry") == "horosa")
    assert finding["ok"] is True, finding
