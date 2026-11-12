"""任何响应视图都不许改变一盘算出了什么（v0.50.0-dev，冷客户端审计 F4）。

`response_view` 是「返回体长什么样」的开关，不是算法输入。v0.49.0 及以前它跟着载荷进了 runner 的子调用：
择日类先算一张展示盘再读它的 `snapshot_text`，子调用把视图也用上了，快照被清空，外层读到空串 →
黄历择日 14 段里 7 段成了「本次本地计算结果未返回…细项」，还多出一条假的「结果不完整」告警。

这里对整张技法表逐个对照：每种视图下的段落（序号、标题、正文）与告警，跟不带视图的那一次完全一致。
离线用 fakes（整张表三遍约 2 秒）；live 变体打共享引擎，覆盖十个择日技法。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fakes import FakeClient, FakeJsClient
from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.testing_payloads import build_sample_payloads

SERVICE_VIEWS = ("sections", "titles")
ZERI_TOOLS = (
    "tianxing", "qimenzeri", "huanglizeri", "bazizeri", "taiyizeri", "ziweizeri", "liurengzeri", "sanshizeri",
    "qizhengzeri", "indiazeri",
)
# 视图自己加的那一句不算「多出来的告警」。
_VIEW_NOTE = "response_view="


def offline_service(tmp_path: Path) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
                        db_path=tmp_path / "m.db", output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt",
                        data_dir=tmp_path / "data")
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())


def section_rows(envelope: dict[str, Any]) -> list[tuple[Any, Any]]:
    snapshot = (envelope.get("data") or {}).get("export_snapshot") or {}
    return [(row.get("index"), row.get("title")) for row in snapshot.get("sections") or []]


def section_bodies(envelope: dict[str, Any]) -> list[Any]:
    snapshot = (envelope.get("data") or {}).get("export_snapshot") or {}
    return [row.get("body") for row in snapshot.get("sections") or []]


def view_drift(raw: dict[str, Any], viewed: dict[str, Any], *, bodies: bool) -> list[str]:
    """一个视图相对原始结果变了什么（空 = 没变）。"""
    problems: list[str] = []
    if section_rows(raw) != section_rows(viewed):
        problems.append(f"sections {len(section_rows(raw))} -> {len(section_rows(viewed))}")
    elif bodies and section_bodies(raw) != section_bodies(viewed):
        changed = [row[1] for row, a, b in zip(section_rows(raw), section_bodies(raw), section_bodies(viewed)) if a != b]
        problems.append(f"bodies changed: {changed[:3]}")
    extra = [w for w in viewed.get("warnings") or [] if w not in (raw.get("warnings") or []) and _VIEW_NOTE not in w]
    if extra:
        problems.append(f"new warning: {extra[0][:60]}")
    return problems


def test_service_views_never_change_what_was_computed(tmp_path: Path) -> None:
    """负向对照：run_tool 里去掉「嵌套调用先摘掉展示键」→ 7 个择日技法（黄历 / 八字 / 太乙 / 紫微 / 六壬 / 三式 / 七政）红（实跑过）。"""
    service = offline_service(tmp_path)
    payloads = build_sample_payloads()
    checked = 0
    drift: dict[str, list[str]] = {}
    for name in TOOL_DEFINITIONS:
        raw = service.run_tool(name, payloads[name], save_result=False).model_dump(mode="json")
        assert raw["ok"], (name, raw.get("code"))
        if not isinstance((raw.get("data") or {}).get("export_snapshot"), dict):
            continue
        checked += 1
        for view in SERVICE_VIEWS:
            viewed = service.run_tool(name, {**payloads[name], "response_view": view}, save_result=False).model_dump(mode="json")
            problems = view_drift(raw, viewed, bodies=view == "sections")
            if problems:
                drift[f"{name}[{view}]"] = problems
    assert checked >= 100, checked   # 整张表都在比，不是只比了几个
    assert not drift, drift


def test_nested_calls_drop_presentation_keys_and_stay_unviewed(tmp_path: Path) -> None:
    """子调用拿到的载荷里没有展示键，子信封也不裁；最外层那一次照旧按视图裁。"""
    service = offline_service(tmp_path)
    seen: list[tuple[str, bool, int]] = []
    original = service._compute_tool_result

    def spy(call):  # noqa: ANN001, ANN202
        from horosa_skill.service._context import run_tool_depth

        seen.append((call.tool_name, "response_view" in call.input_normalized, run_tool_depth()))
        return original(call)

    service._compute_tool_result = spy  # type: ignore[method-assign]
    payload = {**build_sample_payloads()["huanglizeri"], "response_view": "titles"}
    envelope = service.run_tool("huanglizeri", payload, save_result=False)
    outer = [row for row in seen if row[2] == 1]
    inner = [row for row in seen if row[2] > 1]
    assert [row[0] for row in outer] == ["huanglizeri"] and outer[0][1] is True
    assert inner and not any(row[1] for row in inner), seen
    # 最外层仍然是 titles 视图：段只剩序号与标题。
    assert all(set(row) == {"index", "title"} for row in envelope.data["export_snapshot"]["sections"])


# ---------------------------------------------------------------------------------------------------------------------
# MCP 面：阅读视图（缺省）与各显式视图 —— 正文与原始结果一致，体积在预算内。

import asyncio  # noqa: E402
import json  # noqa: E402

from horosa_skill.result_view import FULL, READING, SECTIONS, TITLES, Budget, ViewRequest, estimate_tokens, shape_result  # noqa: E402
from horosa_skill.surfaces import mcp_runner  # noqa: E402

CLAUDE_CODE_SPILL_CHARS = 50_000   # 超过即落盘（contracts/third_party_facts.json · claude-code.tool-search）
SSE_EVENT_LIMIT = 1_048_576        # mcp/client/streamable_http.py
CONFIRM = {"agent_confirmed_settings": True, "clarification_notes": "result view catalogue test"}
UNLIMITED = Budget(max_tokens=10**9, max_chars=10**9)


def test_every_view_keeps_the_text_of_the_raw_run(tmp_path: Path) -> None:
    """视图只挑、不改：段的序号 / 标题与原始结果一致；阅读视图的正文与原始 export_text 逐字相同；分段正文逐段相同。

    负向对照：_plan_envelope 里把段标题换成 raw_title / 丢掉最后一段 → 红（实跑过）。"""
    service = offline_service(tmp_path)
    payloads = build_sample_payloads()
    drift: dict[str, str] = {}
    for name in TOOL_DEFINITIONS:
        raw = service.run_tool(name, payloads[name], save_result=False).model_dump(mode="json")
        snapshot = (raw.get("data") or {}).get("export_snapshot")
        if not isinstance(snapshot, dict):
            continue
        for view in (READING, SECTIONS, TITLES):
            shaped = shape_result(raw, ViewRequest(view=view), UNLIMITED)
            problems = view_drift(raw, shaped, bodies=False)
            out = shaped["data"]["export_snapshot"]
            if view == READING and out.get("export_text") != snapshot.get("export_text"):
                problems.append("export_text differs")
            if view == SECTIONS and [row.get("body") for row in out["sections"]] != section_bodies(raw):
                problems.append("section bodies differ")
            if "snapshot_text" in shaped["data"]:
                problems.append("text twice")
            if problems:
                drift[f"{name}[{view}]"] = "; ".join(problems)
    assert not drift, drift


def mcp_server(service: HorosaSkillService, **settings_overrides: Any):
    from horosa_skill.surfaces.mcp_server import create_mcp_server

    return create_mcp_server(service, service.settings.model_copy(update=settings_overrides))


def call_all(mcp, calls: list[tuple[str, dict[str, Any]]]) -> list[tuple[str, int, str]]:
    """[(标签, 线上字节, 正文)]：一个会话里依次调用。"""
    from mcp.client import Client

    async def run() -> list[tuple[str, int, str]]:
        out = []
        async with Client(mcp) as client:
            for label, (name, args) in zip([c[0] for c in calls], [c[1] for c in calls]):
                result = await client.call_tool(name, args)
                wire = len(result.model_dump_json(by_alias=True, exclude_none=True).encode("utf-8"))
                out.append((label, wire, result.content[0].text))
        return out

    return asyncio.run(run())


def catalogue_calls(birth: dict[str, Any]) -> list[tuple[str, tuple[str, dict[str, Any]]]]:
    payloads = build_sample_payloads()
    calls = [(name, (definition.mcp_name, {**payloads[name], **CONFIRM})) for name, definition in TOOL_DEFINITIONS.items()]
    calls.append(("dispatch", ("horosa_dispatch", {"query": "用八字和紫微看看我今年的事业", "birth": birth, **CONFIRM})))
    calls.append(("hecan", ("horosa_hecan", {"query": "今年事业如何", "tools": ["bazi_birth", "ziwei_birth", "qimen"],
                                             "birth": birth, "context": {**birth, "date": "2026-11-12", "time": "10:00:00"},
                                             **CONFIRM})))  # 奇门是起课技法：v0.50.0 起合参按 context 的此刻起，不拿出生时刻
    return calls


BIRTH = {"date": "1990-05-03", "time": "08:00:00", "zone": "+08:00", "lat": "31n14", "lon": "121e28", "gender": 1}


def budget_breaches(results: list[tuple[str, int, str]], budget: Budget) -> dict[str, str]:
    breaches: dict[str, str] = {}
    for label, wire, text in results:
        body = json.loads(text)
        problems = []
        if len(text) > CLAUDE_CODE_SPILL_CHARS or len(text) > budget.max_chars:
            problems.append(f"{len(text)} chars")
        if estimate_tokens(text) > budget.max_tokens:
            problems.append(f"~{estimate_tokens(text)} tokens")
        if wire > mcp_runner.MCP_RESULT_WIRE_BUDGET:
            problems.append(f"{wire} wire bytes")
        if body.get("ok") is not True and label not in ("dispatch", "hecan"):
            problems.append(f"not ok: {body.get('code')}")
        if problems:
            breaches[label] = ", ".join(problems)
    return breaches


def inflate(service: HorosaSkillService, tool: str, factor: int) -> None:
    """让一个技法的正文变成原来的 factor 倍（模拟节气盘 / 流年明细那种 9 万字的正文）。"""
    original = service.run_tool

    def run_tool(name, payload, **kwargs):  # noqa: ANN001, ANN202
        envelope = original(name, payload, **kwargs)
        snapshot = envelope.data.get("export_snapshot") if envelope.ok else None
        if name == tool and isinstance(snapshot, dict):
            for row in snapshot["sections"]:
                row["body"] = "\n".join([row["body"]] * factor)
            snapshot["export_text"] = "\n\n".join(f"[{row['title']}]\n{row['body']}" for row in snapshot["sections"])
            envelope.data["snapshot_text"] = snapshot["export_text"]
        return envelope

    service.run_tool = run_tool  # type: ignore[method-assign]


@pytest.mark.parametrize("script", ["zh-Hans", "zh-Hant"])
def test_default_result_of_every_technique_fits_the_model_budget(tmp_path: Path, script: str) -> None:
    """整张技法表 + 调度 + 合参：缺省结果不超过 Claude Code 的落盘线、模型预算与线上预算（< 1 MiB SSE）。

    负向对照：mcp_runner 里不调 shape_result（回到 v0.49.0 的缺省）→ 被放大的八字与 agepoint 等红（实跑过）。"""
    service = offline_service(tmp_path)
    inflate(service, "bazi_birth", 40)
    mcp = mcp_server(service, output_script=script)
    budget = mcp.result_budget
    results = call_all(mcp, catalogue_calls(BIRTH))
    assert not budget_breaches(results, budget), budget_breaches(results, budget)
    bodies = {label: json.loads(text) for label, _, text in results}
    # 被放大的正文是按段裁的：告警写明续读调用，照抄过去就是下一段。
    bazi = bodies["bazi_birth"]
    note = next(w for w in bazi["warnings"] if "horosa_memory_show(" in w)
    assert f'run_id="{bazi["memory_ref"]["run_id"]}"' in note and "response_sections=" in note
    assert bodies["dispatch"]["ok"] is True and set(bodies["dispatch"]["results"]) >= {"bazi_birth"}
    assert set(bodies["hecan"]["results"]) == {"bazi_birth", "ziwei_birth", "qimen"}
    assert all(row["data"]["export_snapshot"]["sections"] for row in bodies["hecan"]["results"].values() if row["ok"])
    assert SSE_EVENT_LIMIT > mcp_runner.MCP_RESULT_WIRE_BUDGET


def test_full_view_is_still_reachable_and_wire_bounded(tmp_path: Path) -> None:
    """`response_view="full"` 拿回原始树（v0.49.0 的缺省），只受线上预算管。"""
    service = offline_service(tmp_path)
    mcp = mcp_server(service)
    payloads = build_sample_payloads()
    calls = [(name, (TOOL_DEFINITIONS[name].mcp_name, {**payloads[name], **CONFIRM, "response_view": "full"}))
             for name in ("bazi_birth", "chart", "qimen", "agepoint")]
    for label, wire, text in call_all(mcp, calls):
        body = json.loads(text)
        raw = service.run_tool(label, {**payloads[label], **CONFIRM}, save_result=False).model_dump(mode="json")
        assert wire <= mcp_runner.MCP_RESULT_WIRE_BUDGET
        assert set(body["data"]) == set(raw["data"]), label          # 原始字段都在
        assert body["data"]["export_snapshot"]["export_text"] == raw["data"]["export_snapshot"]["export_text"]


def test_the_default_switch_lives_in_the_config_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from horosa_skill.config import ENV_FLAG_REGISTRY, Settings as _Settings

    for name in ("HOROSA_MCP_RESULT_VIEW", "HOROSA_MCP_RESULT_MAX_TOKENS", "HOROSA_MCP_RESULT_MAX_CHARS"):
        assert ENV_FLAG_REGISTRY[name] == "stable"
    monkeypatch.setenv("HOROSA_MCP_RESULT_VIEW", "raw")
    monkeypatch.setenv("HOROSA_MCP_RESULT_MAX_TOKENS", "12000")
    settings = _Settings.from_env()
    assert settings.mcp_result_view == FULL and settings.mcp_result_max_tokens == 12_000
    monkeypatch.setenv("HOROSA_MCP_RESULT_VIEW", "everything")
    assert _Settings.from_env().mcp_result_view == READING
    service = offline_service(tmp_path)
    mcp = mcp_server(service, mcp_result_view=FULL)
    payloads = build_sample_payloads()
    [(_, _, text)] = call_all(mcp, [("bazi", ("horosa_cn_bazi_birth", {**payloads["bazi_birth"], **CONFIRM}))])
    assert "snapshot_text" in json.loads(text)["data"]


def test_compact_wire_text_keeps_structured_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """正文 JSON 不缩进；HOROSA_OUTPUT_SCHEMA=1 时 structuredContent 照旧，且与正文同一份数据。"""
    from mcp.client import Client

    monkeypatch.setenv("HOROSA_OUTPUT_SCHEMA", "1")
    service = offline_service(tmp_path)
    mcp = mcp_server(service)
    payloads = build_sample_payloads()

    async def run():
        async with Client(mcp) as client:
            return await client.call_tool("horosa_cn_bazi_birth", {**payloads["bazi_birth"], **CONFIRM})

    result = asyncio.run(run())
    text = result.content[0].text
    assert "\n  " not in text[:2_000] and text.startswith('{"ok":true')
    assert result.structured_content is not None
    assert result.structured_content["data"]["export_snapshot"]["export_text"] == json.loads(text)["data"]["export_snapshot"]["export_text"]


def test_guidance_index_and_free_text_cap_over_mcp(tmp_path: Path) -> None:
    """include_all 回索引（v0.49.0 是 126 万字符的全量指引）；过长的澄清备注截断、告警，存档里也是截断后的。

    负向对照：门面里不调 guidance_index → 第一条红；call_tool 里不调 cap_free_text → 存档断言红（实跑过）。"""
    service = offline_service(tmp_path)
    mcp = mcp_server(service)
    payload = {**build_sample_payloads()["bazi_birth"], **CONFIRM, "clarification_notes": "备" * 30_000}
    (_, _, guidance), (_, _, bazi) = call_all(mcp, [
        ("guidance", ("horosa_agent_guidance", {"include_all": True})),
        ("bazi", ("horosa_cn_bazi_birth", payload)),
    ])
    index = json.loads(guidance)
    assert len(guidance) < CLAUDE_CODE_SPILL_CHARS and index["view"] == "index" and len(index["tools"]) == len(TOOL_DEFINITIONS)
    body = json.loads(bazi)
    assert len(bazi) < CLAUDE_CODE_SPILL_CHARS
    assert any("clarification_notes" in w and "30000" in w for w in body["warnings"])
    stored = service.show_memory({"run_id": body["memory_ref"]["run_id"]})["result"]
    assert len(json.dumps(stored, ensure_ascii=False)) < 200_000


def test_stored_runs_are_readable_as_a_resource(tmp_path: Path) -> None:
    """`horosa://runs/{run_id}` = memory_show 的阅读视图（资源读不经 call_tool，视图在资源里自己做）。"""
    import anyio

    service = offline_service(tmp_path)
    mcp = mcp_server(service, mcp_result_max_tokens=4_000)   # 小预算：存档里的八字正文放不下，要按段裁
    envelope = service.run_tool("bazi_birth", {**build_sample_payloads()["bazi_birth"], **CONFIRM})

    async def read():
        templates = await mcp.list_resource_templates()
        contents = await mcp.read_resource(f"horosa://runs/{envelope.memory_ref.run_id}")
        return [str(t.uri_template) for t in templates], list(contents)

    templates, contents = anyio.run(read)
    assert "horosa://runs/{run_id}" in templates
    text = contents[0].content if hasattr(contents[0], "content") else contents[0].text
    assert len(text) < CLAUDE_CODE_SPILL_CHARS
    body = json.loads(text)
    stored = next(a for a in body["result"]["artifacts"] if a["kind"] == "tool_result")["payload"]
    assert stored["data"]["export_snapshot"]["export_text"] and "snapshot_text" not in stored["data"]
    assert any("horosa_memory_show(" in w for w in body["warnings"])


# ---------------------------------------------------------------------------------------------------------------------
# live：共享引擎（8877 / 9977）。门禁里两个后端都钉在 :9，这几条跳过。

from test_local_js_tools import requires_runtime  # noqa: E402


def live_service(tmp_path: Path) -> HorosaSkillService:
    settings = Settings.from_env().model_copy(update={
        "db_path": tmp_path / "m.db", "output_dir": tmp_path / "runs", "data_dir": tmp_path / "data",
    })
    return HorosaSkillService(settings, store=MemoryStore(settings))


@requires_runtime
@pytest.mark.parametrize("tool", ZERI_TOOLS)
def test_live_zeri_views_never_change_what_was_computed(tmp_path: Path, tool: str) -> None:
    service = live_service(tmp_path)
    payload = {**build_sample_payloads()[tool], **CONFIRM}
    raw = service.run_tool(tool, payload, save_result=False).model_dump(mode="json")
    assert raw["ok"], raw.get("code")
    for view in SERVICE_VIEWS:
        viewed = service.run_tool(tool, {**payload, "response_view": view}, save_result=False).model_dump(mode="json")
        assert not view_drift(raw, viewed, bodies=view == "sections"), (view, view_drift(raw, viewed, bodies=view == "sections"))
    for view in (READING, SECTIONS, TITLES):
        shaped = shape_result(raw, ViewRequest(view=view), UNLIMITED)
        assert not view_drift(raw, shaped, bodies=False), view


@requires_runtime
def test_live_default_result_of_every_technique_fits_the_model_budget(tmp_path: Path) -> None:
    service = live_service(tmp_path)
    mcp = mcp_server(service)
    results = call_all(mcp, catalogue_calls(BIRTH))
    assert not budget_breaches(results, mcp.result_budget), budget_breaches(results, mcp.result_budget)
