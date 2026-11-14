"""「这些参数不是本技法的参数」只对调用方自己写的键报（审计 S-11）。

修前：
- dispatch 八字成功，子结果 warnings 却是「不是本技法的参数：hsys、tradition、predictive、southchart、zodiacal、asporb」——
  没人传，是 `birth` 联合里被选中的出生模型的缺省值，dispatch 一并下发（合参每个子技法都有）；
- 万年历 / 小六壬传 place → 「gpsLat、gpsLon 不是本技法的参数」，那是地名解析自己补的。
SKILL 要求 warnings 每行都读：每次都叫，真告警就没人看了。
负向对照（实跑过）：dispatch_plan 改回 exclude_none 不带 exclude_unset → 第一个用例红；_place_filled 恒返回空 → 第二个用例红。
"""
from __future__ import annotations

from horosa_skill.config import Settings
from horosa_skill.engine import dispatch_plan
from horosa_skill.memory.store import MemoryStore
from horosa_skill.schemas.tools import DispatchInput
from horosa_skill.service import HorosaSkillService

BIRTH = {"date": "1990-05-03", "time": "08:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"}


def test_dispatch_hands_children_only_the_fields_the_caller_gave() -> None:
    for birth in (BIRTH, {**BIRTH, "gender": 0}):   # 不同字段集落在联合的不同分支（BirthInput / BaZiBirthInput）
        request = DispatchInput.model_validate({"query": "帮我排个八字", "birth": birth})
        inputs = dispatch_plan.inputs_from_request(request)
        assert inputs.birth_fields == birth, inputs.birth_fields
        assert inputs.birth == birth


def test_place_filled_coordinates_are_not_reported_as_unknown(tmp_path) -> None:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path,
                        runtime_root=tmp_path / "runtime", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs",
                        trace_enabled=False)
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    # 万年历：模型不声明 gpsLat / gpsLon。离线时引擎不可达、信封 ok:false，但入参说明（含「不是本技法的参数」）在起算前就定了，
    # 失败信封照样回显（tools.run_tool：成功 / 失败信封的 warnings 都带 input notes）。
    result = service.run_tool("calendar_month", {"date": "2026-11-13", "place": "上海", "foo": 1}, save_result=False)
    unknown = [line for line in result.warnings if "不是本技法的参数" in line]
    # 调用方自己写错的 foo 照报；地名补的 gpsLat / gpsLon 不报
    assert len(unknown) == 1 and "`foo`" in unknown[0] and "gpsLat" not in unknown[0], unknown


def test_the_mcp_layer_does_not_bake_union_defaults_into_dispatch_payloads() -> None:
    """MCP 面先校验再 model_dump：以前把联合分支的缺省值写成显式值交给 service（CLI 与 MCP 的 normalized_inputs 因此不同，
    test_cli_refusals 的 CLI / MCP 对照抓到）。"""
    from horosa_skill.schemas.tools import HecanInput
    from horosa_skill.surfaces.mcp_requests import _normalize_mcp_request

    for model in (DispatchInput, HecanInput):
        payload = _normalize_mcp_request({"query": "看看八字", "birth": {**BIRTH, "gender": 1}}, model)
        leaked = {"ad", "byLon", "timeAlg", "phaseType", "hsys", "tradition", "predictive", "southchart", "zodiacal"} & set(payload["birth"])
        assert not leaked, payload["birth"]   # 归一化补的 gpsLat / gpsLon 是给了的坐标换算来的，不算缺省值
        assert payload["birth"]["date"] == BIRTH["date"] and payload["birth"]["gender"] == 1
