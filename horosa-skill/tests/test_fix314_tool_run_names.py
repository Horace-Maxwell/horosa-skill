"""精简面 horosa_tool_run / CLI tool run / run_tool 认中文名；点错名字给带中文名的候选（审计 S-10）。

修前：`horosa_tool_run {"tool_name":"八字"}` / `"小六壬"` → tool.unknown，details.catalog 是一张没有标签的 114 键清单
（七政四余 = guolao_chart、邵子参评数 = canping 旁边就是 shaozi，照拼音猜会选错）；而合参与记忆检索都认中文名。
负向对照（实跑过）：run_tool 改回只认注册键 / MCP 名 → 前三个用例红。
"""
from __future__ import annotations

import asyncio
import json

from typer.testing import CliRunner

from horosa_skill.agent_guidance import resolve_technique, unknown_tool_details
from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces import cli
from horosa_skill.surfaces.mcp_server import create_mcp_server


def _service(tmp_path):
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path,
                        runtime_root=tmp_path / "runtime", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs",
                        trace_enabled=False)
    return settings, HorosaSkillService(settings, store=MemoryStore(settings))


def test_run_tool_takes_an_unambiguous_chinese_name_and_says_so(tmp_path) -> None:
    _, service = _service(tmp_path)
    result = service.run_tool("知识库目录", {}, save_result=False)
    assert result.ok and result.tool == "knowledge_registry"
    assert any("「知识库目录」按 knowledge_registry" in line for line in result.warnings), result.warnings


def test_compact_tool_run_takes_chinese_names(tmp_path) -> None:
    settings, service = _service(tmp_path)
    settings.mcp_compact = True
    server = create_mcp_server(service, settings)

    def call(name: str) -> dict:
        result = asyncio.run(server.call_tool("horosa_tool_run", {"tool_name": name, "request": {}}))
        result = getattr(result, "content", result)
        blocks = result[0] if isinstance(result, tuple) else result
        return json.loads(blocks[0].text)

    ok = call("知识库目录")
    assert ok["ok"] is True and ok["tool"] == "knowledge_registry"
    # 八字要闸门 / 出生数据：认得出名字，就停在闸门（agent_guidance.required）而不是 tool.unknown
    gated = call("八字")
    assert gated["ok"] is False and gated["error"]["code"] != "tool.unknown" and gated["tool"] == "bazi_birth", gated["error"]


def test_cli_tool_run_takes_a_chinese_name(monkeypatch, tmp_path) -> None:
    _, service = _service(tmp_path)
    monkeypatch.setattr(cli, "_service", lambda: service)
    (tmp_path / "empty.json").write_text("{}", encoding="utf-8")
    out = CliRunner().invoke(cli.app, ["tool", "run", "知识库目录", "--input", str(tmp_path / "empty.json")])
    assert out.exit_code == 0, out.output
    assert json.loads(out.stdout)["tool"] == "knowledge_registry"


def test_resolution_is_exact_and_never_picks_between_two_techniques() -> None:
    assert resolve_technique("八字")[0] == "bazi_birth"
    assert resolve_technique("小六壬")[0] == "xiaoliuren"
    assert resolve_technique("七政四余")[0] == "guolao_chart"
    assert resolve_technique("太陽返照")[0] == "solarreturn"   # 繁体照认
    assert resolve_technique("horosa_cn_bazi_birth") == ("bazi_birth", None)   # 原有写法不写说明
    assert resolve_technique("邵子") == (None, None)   # 邵子参评数 / 邵子神数 两个：不替用户挑
    assert resolve_technique("梅花") == (None, None)   # 不是整词同名：不猜


def test_unknown_name_lists_labelled_candidates_then_the_labelled_catalog() -> None:
    details = unknown_tool_details("邵子")
    picked = {row["tool_name"]: row["name"] for row in details["candidates"]}
    assert picked == {"canping": "邵子参评数", "shaozi": "邵子神数"}
    assert all(row["summary"] for row in details["candidates"])
    catalog = details["catalog"]
    assert sum(len(names) for names in catalog.values()) == len(TOOL_DEFINITIONS)
    flat = {key: name for names in catalog.values() for key, name in names.items()}
    assert flat["guolao_chart"] == "七政四余" and flat["canping"] == "邵子参评数"
    assert "candidates" not in unknown_tool_details("zzzz_nothing_like_it")
