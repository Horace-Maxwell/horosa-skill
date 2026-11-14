"""查资料类工具缺省不存档，readOnlyHint=True 才是真的；记忆检索缺省不列它们的旧记录（审计 S-14）。

修前：export_registry / export_parse / knowledge_registry / knowledge_read / astrodata / ziwei_rules / gua_desc / gua_meiyi 标了
readOnlyHint:true，却每次调用都落一个 run（manifest + 产物 + 写库；ziwei_rules 一次 106 KB）；`horosa_memory_query {"limit":8}` 的最近 8 条
全是它们与玄史。AGENTS §4.4：写本地 run 的工具必须如实标 readOnly=False。修法取「不存档」而不是改注解：结果太长时阅读视图的续读写成
「同一调用 + response_sections」（没有 run_id 时 result_view 的既有路径），不需要存档。
负向对照（实跑过）：run_tool 的缺省改回恒存档 → 第一、四个用例红；memory 的 hidden 恒 None → 第三个用例红。
"""
from __future__ import annotations

import asyncio
import json

from horosa_skill.config import Settings
from horosa_skill.engine.registry import LOOKUP_TOOLS, TOOL_DEFINITIONS
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces.mcp_server import create_mcp_server


def _service(tmp_path):
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path,
                        runtime_root=tmp_path / "runtime", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs",
                        trace_enabled=False)
    return settings, HorosaSkillService(settings, store=MemoryStore(settings))


def test_a_lookup_writes_no_run_unless_asked(tmp_path) -> None:
    _, service = _service(tmp_path)
    plain = service.run_tool("knowledge_registry", {})
    assert plain.ok and plain.memory_ref is None
    assert service.store.query_runs(limit=5) == []
    kept = service.run_tool("knowledge_registry", {}, save_result=True)   # 显式要存（CLI 开关 / dispatch 组）照存
    assert kept.memory_ref is not None and len(service.store.query_runs(limit=5)) == 1


def test_read_only_annotation_matches_what_the_tool_does(tmp_path) -> None:
    settings, service = _service(tmp_path)
    tools = asyncio.run(create_mcp_server(service, settings).list_tools())
    def flag(tool):  # mcp 1.x readOnlyHint / 2.x read_only_hint
        ann = tool.annotations
        return bool(ann and (getattr(ann, "read_only_hint", None) if hasattr(ann, "read_only_hint") else getattr(ann, "readOnlyHint", None)))

    read_only = {tool.name for tool in tools if flag(tool)}
    by_mcp = {definition.mcp_name: name for name, definition in TOOL_DEFINITIONS.items()}
    technique_read_only = {by_mcp[name] for name in read_only if name in by_mcp}
    assert technique_read_only == set(LOOKUP_TOOLS), technique_read_only ^ set(LOOKUP_TOOLS)


def test_memory_query_does_not_list_lookup_runs_by_default(tmp_path) -> None:
    from test_result_view_catalogue import offline_service

    from horosa_skill.testing_payloads import build_sample_payloads

    service = offline_service(tmp_path)
    service.run_tool("knowledge_registry", {}, save_result=True)
    # 一条起盘成功的 run（假引擎）。审计 O-10 起只有失败调用的 run 缺省也不列，所以不能再拿离线失败信封充数。
    chart = service.run_tool("sixyao", build_sample_payloads()["sixyao"], save_result=True)
    assert chart.ok
    listed = service.query_memory({"limit": 8})
    assert [row["run_id"] for row in listed["results"]] == [chart.memory_ref.run_id]
    assert "hidden_lookups" in listed["applied_filters"]
    named = service.query_memory({"limit": 8, "tool": "knowledge_registry"})
    assert len(named["results"]) == 1 and "hidden_lookups" not in named["applied_filters"]


def test_a_long_unsaved_lookup_still_says_how_to_read_the_rest(tmp_path) -> None:
    settings, service = _service(tmp_path)
    server = create_mcp_server(service, settings)
    result = asyncio.run(server.call_tool("horosa_export_registry", {}))
    result = getattr(result, "content", result)
    blocks = result[0] if isinstance(result, tuple) else result
    body = json.loads(blocks[0].text)
    assert body["ok"] is True and not body.get("memory_ref")
    text = json.dumps(body, ensure_ascii=False)
    assert "超过单次返回的模型预算" in text   # 全表 ~100 KB：一定超预算
    # 续读指向同一调用（response_view / response_sections），而不是一个不存在的 run_id
    assert "the same call" in text or "the same `export_registry` call" in text
    assert "horosa_memory_show" not in text
