"""v0.50.0（IN-08 / IN-12 / IN-04 / 冷启动 F7·N4）：MCP 参数层不再静默丢键，坏字段与非布尔确认位先于闸门问卷被拒。

SDK 按工具签名生成的 arg model 在函数体之前丢掉未声明的顶层键，而 schema 写着 `additionalProperties: true`：
`horosa_cn_bazi_birth {date, time, place:"上海", gender}` 回「缺 lat / lon」且一字不提 place；`timezone` / `sex` /
`latitude` 这类别名键整个消失。现在 `call_tool` 把原始参数交给 `_merge_mcp_arguments`，认得的接住（别名改名进 warnings），
认不得的在 warnings 里点名并给近似名。
"""
from __future__ import annotations

import json
from pathlib import Path

import anyio
import pytest

from horosa_skill.config import Settings
from horosa_skill.errors import ToolValidationError
from horosa_skill.memory.store import MemoryStore
from horosa_skill.schemas.common import ToolEnvelope
from horosa_skill.service import HorosaSkillService
from horosa_skill.service.api.tools import GENDER_DEPENDENT_TOOLS
from horosa_skill.surfaces import mcp_server as M

BIRTH = {"date": "1990-06-15", "time": "10:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gender": 1}
CONFIRM = {"agent_confirmed_settings": True}


def _server(tmp_path: Path, *, compact: bool = False, fake_run: bool = True):
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
                        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs", mcp_compact=compact)
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    seen: list[dict] = []
    if fake_run:
        real = service._validated_tool_input

        def _run_tool(tool_name: str, payload: dict, **_kwargs) -> ToolEnvelope:
            # 只跑入口校验（与真 run_tool 同一段），不碰引擎：看的是参数到了哪里、被读成了什么。
            from horosa_skill.engine.registry import TOOL_DEFINITIONS
            from horosa_skill.input_fields import input_notes_scope

            with input_notes_scope() as notes:
                normalized, *_rest = real(TOOL_DEFINITIONS[tool_name], payload, {"trace_id": "t"})
            seen.append(dict(normalized))
            return ToolEnvelope(ok=True, tool=tool_name, version="test", input_normalized=normalized, warnings=list(notes))

        service.run_tool = _run_tool  # type: ignore[method-assign]
        service.resolve_place_fields = lambda payload, tool_name=None: (  # type: ignore[method-assign]
            {**{k: v for k, v in payload.items() if k != "place"}, "lat": "31n13", "lon": "121e28"} if payload.get("place") == "上海" else payload
        )
    return M.create_mcp_server(service, settings), seen


@pytest.fixture(scope="module")
def flat(tmp_path_factory: pytest.TempPathFactory):
    # 建 server 约 1.7 s：整个模块共用一个（每个用例开头清空 seen）。
    return _server(tmp_path_factory.mktemp("flat"))


@pytest.fixture
def server(flat):
    flat[1].clear()
    return flat


def _call(mcp, name: str, arguments: dict) -> dict:
    async def _go():
        return await mcp.call_tool(name, arguments)

    return json.loads(anyio.run(_go).content[0].text)


def test_top_level_place_reaches_the_resolver(server) -> None:
    mcp, seen = server
    body = _call(mcp, "horosa_cn_bazi_birth", {"date": "1990-06-15", "time": "10:30", "zone": "+08:00", "place": "上海", "gender": 0, **CONFIRM})
    assert body["ok"] is True, body
    assert (seen[0]["lat"], seen[0]["lon"]) == ("31n13", "121e28")


def test_alias_keys_are_read_and_noted(server) -> None:
    mcp, seen = server
    args = {"date": "1990-06-15", "time": "10:30", "timezone": "东八区", "latitude": 31.2167, "lng": "121.4667", "sex": "女", **CONFIRM}
    body = _call(mcp, "horosa_cn_bazi_birth", args)
    assert body["ok"] is True, body
    assert (seen[0]["zone"], seen[0]["lat"], seen[0]["lon"], seen[0]["gender"]) == ("+08:00", "31n13", "121e28", 0)
    warnings = " ".join(body["warnings"])
    for alias in ("timezone", "latitude", "lng", "sex", "东八区"):
        assert alias in warnings, alias


def test_unknown_top_level_key_is_reported_with_a_close_match(server) -> None:
    mcp, _seen = server
    body = _call(mcp, "horosa_astro_chart", {**BIRTH, "hsis": 3, **CONFIRM})
    warnings = " ".join(body["warnings"])
    assert "`hsis`" in warnings and "`hsys`" in warnings


def test_request_payload_wrapper_is_unpacked(server) -> None:
    mcp, seen = server
    body = _call(mcp, "horosa_astro_chart", {"request": {"payload": {**BIRTH, **CONFIRM}}})
    assert body["ok"] is True, body
    assert seen[0]["date"] == "1990-06-15"


def test_nested_birth_on_a_technique_tool_is_lifted(server) -> None:
    mcp, seen = server
    body = _call(mcp, "horosa_cn_bazi_birth", {"birth": BIRTH, **CONFIRM})
    assert body["ok"] is True, body
    assert seen[0]["gender"] == 1


@pytest.mark.parametrize("flag", ["true", 1, "yes"])
def test_non_boolean_confirmation_flag_has_its_own_code(server, flag: object) -> None:
    mcp, seen = server
    body = _call(mcp, "horosa_astro_chart", {**BIRTH, "agent_confirmed_settings": flag})
    assert body["ok"] is False and body["code"] == "tool.confirmation_flag_not_boolean", body
    assert body["details"]["agent_recovery"]["must_ask_user"] is False and seen == []


def test_bad_field_is_refused_before_the_gate_questionnaire(server) -> None:
    mcp, seen = server
    body = _call(mcp, "horosa_cn_bazi_birth", {**BIRTH, "zone": "CST"})  # 没确认、zone 又是一词多义的缩写
    assert body["code"] == "tool.invalid_zone", body["code"]
    fixes = body["details"]["agent_recovery"]["fix_fields"]
    assert [fix["field"] for fix in fixes] == ["zone"] and {"+08:00", "-06:00"} <= {o["value"] for o in fixes[0]["options"]}
    assert seen == []


def test_missing_coordinates_point_at_place_and_pos_is_display_only(server) -> None:
    mcp, _seen = server
    body = _call(mcp, "horosa_cn_bazi_birth", {"date": "1990-06-15", "time": "10:30", "zone": "+08:00", "gender": 1, "pos": "上海", **CONFIRM})
    assert body["ok"] is False and body["code"] == "tool.invalid_payload"
    lat = next(fix for fix in body["details"]["agent_recovery"]["fix_fields"] if fix["field"] == "lat")
    assert "place" in lat["expected"] and "pos" in lat["expected"]


def test_place_and_name_are_declared_on_technique_tools(server) -> None:
    mcp, _seen = server

    async def _list():
        return await mcp.list_tools()

    tools = {tool.name: tool for tool in anyio.run(_list)}
    chart = tools["horosa_astro_chart"].input_schema
    assert chart["properties"]["place"]["type"] == "string"
    # 线上省略 additionalProperties（2020-12 里缺省即 true；OpenAI strict 见到 true 会拒）——行为与之一致：未声明键照收并在 warnings 里点名。
    assert chart.get("additionalProperties", True) is not False
    # name 只进签名（预算），不进广告层；顶层照收（见 test_top_level_name_is_kept）。
    assert "place" in tools["horosa_cn_bazi_birth"].input_schema["properties"]


def test_top_level_name_is_kept(server) -> None:
    mcp, seen = server
    _call(mcp, "horosa_cn_xiaoliuren", {"date": "1990-06-15", "time": "10:30", "name": "张三", **CONFIRM})
    assert seen and seen[0].get("name") == "张三"


def test_tool_run_declares_place(tmp_path: Path) -> None:
    mcp, seen = _server(tmp_path, compact=True)
    body = _call(mcp, "horosa_tool_run", {"tool_name": "bazi_birth", "date": "1990-06-15", "time": "10:30", "zone": "+08:00",
                                          "place": "上海", "gender": 1, **CONFIRM})
    assert body["ok"] is True, body
    assert seen[0]["lat"] == "31n13"


@pytest.mark.parametrize("tool_name", sorted(GENDER_DEPENDENT_TOOLS))
def test_gender_dependent_techniques_refuse_without_gender(tmp_path: Path, tool_name: str) -> None:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
                        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    payload = {key: value for key, value in BIRTH.items() if key != "gender"}
    with pytest.raises(ToolValidationError) as caught:
        service.run_tool(tool_name, {**payload, **CONFIRM}, save_result=False)
    assert caught.value.code == "tool.missing_gender"
    assert caught.value.details["agent_recovery"]["must_ask_user"] is True


def test_gender_requirement_has_one_source_for_gate_and_entry() -> None:
    """技法入口（tool.missing_gender）与澄清闸（事实问题）用同一份名单：合并深审两批时曾分成 12 / 17 两份，
    正传 / 北极 / 南极 / 紫微择日缺性别时直调照样按男排。名单内容由 1 / 0 两种性别逐行实测定（见 LESSONS）。"""
    from horosa_skill.agent_guidance.questions import GENDER_FACT_TOOLS

    assert GENDER_DEPENDENT_TOOLS == GENDER_FACT_TOOLS
    assert {"zhengchuan", "beiji", "nanji", "ziweizeri"} <= GENDER_DEPENDENT_TOOLS
