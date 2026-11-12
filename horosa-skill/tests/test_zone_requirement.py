"""缺时区：每个技法都有归属，缺了就是逐字段错误或说明过的上游缺省（v0.50.0 深审余项）。

症状（复现于共享引擎）：小六壬占时起课缺 zone → tool.internal_error（KeyError 'zone'）；飞宫时支起 / 小成图占时 / 轨策占时 /
神数正传缺 zone → transport.http_error（/nongli/time 收到 null，HTTP 500）。全目录探查（每个技法 × 去掉 zone 的样例载荷）另查出：
参评 / 河洛 / 一掌经（本地八字链 parseZoneHours → 8）与八个读时区的神数（后端 timezone_to_float(zone, 8.0)）悄悄按 +08:00 算，
世运盘悄悄按上游缺省地点起盘、不说。

现在：
- 入参模型要求 zone 的技法 → pydantic 缺字段（tool.invalid_payload，details.fields 里有 zone，提示「或传 place」）。
- 模型里 zone 可选、结果却随它变的（agent_guidance.questions：ZONE_FACT_TOOLS + 占时起课的 place_fields_required）→
  tool.missing_field，每个缺的字段一条恢复条目，用户才知道的标 ask_user。
- 上游有成文缺省的（ZONE_DOCUMENTED_DEFAULTS：世运盘）→ 照用并在 warnings 里说明。
- 与时区无关的（ZONE_FREE_TOOLS）→ 不问；live 用例换两个时区逐字节比对，证明真的无关。

负向对照（实跑过）：`_require_result_facts` 里删掉时地检查 → 占时五技法 / 读时区的十一个技法用例全红（offline 走到假后端成功，
不再报缺 zone）；把某个技法从 ZONE_FACT_TOOLS 拿掉 → 归属完整性用例红；世运盘删掉说明 → 缺省说明用例红。
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from fakes import FakeClient, FakeJsClient
from test_local_js_tools import make_service, requires_runtime

from horosa_skill.agent_guidance.questions import (
    CAST_PLACE_FIELDS,
    ZONE_DOCUMENTED_DEFAULTS,
    ZONE_FACT_TOOLS,
    ZONE_FREE_TOOLS,
    place_fields_required,
)
from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.errors import ToolValidationError
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.testing_payloads import build_sample_payloads

SAMPLES = build_sample_payloads()
TIME = {"agent_confirmed_settings": True, "date": "2031-05-20", "time": "12:30:00", "lat": "31n13", "lon": "121e28"}
# 占时起课：按时刻起课的那条路（样例载荷走的是免起课路径）。
CAST_VARIANTS: dict[str, dict[str, Any]] = {
    "xiaoliuren": {**TIME, "school": "dao"},
    "feigong": {**TIME, "qiMode": "hour"},
    "xiaochengtu": {**TIME, "qiguaFa": "time"},
    "guice": {**TIME, "qiguaFa": "time"},
    "zhengchuan": {**SAMPLES["zhengchuan"]},
}
PARTY_KEYS = ("inner", "outer", "natal", "birth", "subject")


def _service(tmp_path) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())


def _fields(tool: str) -> dict[str, Any]:
    return getattr(TOOL_DEFINITIONS[tool].input_model, "model_fields", {})


def _zone_required_by_model(tool: str) -> bool:
    fields = _fields(tool)
    if "zone" in fields:
        return fields["zone"].is_required()
    return any(name in fields and fields[name].is_required() for name in ("inner", "outer"))


def _strip_zone(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _strip_zone(v) for k, v in value.items() if k != "zone"}
    if isinstance(value, list):
        return [_strip_zone(item) for item in value]
    return value


def test_every_tool_that_takes_a_zone_has_a_rule() -> None:
    """模型里 zone 可选的技法必须明确归属：随它变（缺了报错）/ 与它无关（附理由）/ 上游成文缺省（附说明）。新技法漏登记即红。"""
    optional = sorted(name for name in TOOL_DEFINITIONS if "zone" in _fields(name) and not _fields(name)["zone"].is_required())
    classified = ZONE_FACT_TOOLS | set(CAST_VARIANTS) | set(ZONE_FREE_TOOLS) | set(ZONE_DOCUMENTED_DEFAULTS)
    assert sorted(set(optional) - classified) == [], "zone 可选却没有归属的技法"
    assert sorted(classified - set(optional)) == [], "归属表里有 zone 必填 / 不收 zone 的技法（表过期）"
    for groups in (ZONE_FACT_TOOLS & set(ZONE_FREE_TOOLS), set(ZONE_FREE_TOOLS) & set(ZONE_DOCUMENTED_DEFAULTS)):
        assert not groups, groups
    assert all(reason.strip() for reason in ZONE_FREE_TOOLS.values())


@pytest.mark.parametrize("tool", sorted(name for name in TOOL_DEFINITIONS if _zone_required_by_model(name) or name in ZONE_FACT_TOOLS))
def test_missing_zone_is_a_field_error(tmp_path, tool: str) -> None:
    payload = _strip_zone(SAMPLES[tool])
    with pytest.raises(ToolValidationError) as caught:
        _service(tmp_path).run_tool(tool, payload, save_result=False)
    error = caught.value
    assert error.code in ("tool.invalid_payload", "tool.missing_field"), (tool, error.code)
    zone_fields = [item for item in error.details["fields"] if item["field"].split(".")[-1] == "zone"]
    assert zone_fields and all(item["code"] == "tool.missing_field" for item in zone_fields), error.details["fields"]
    assert all(item["ask_user"] for item in zone_fields)
    assert "place" in json.dumps(zone_fields, ensure_ascii=False)
    assert error.details["agent_recovery"]["kind"] == "input"


@pytest.mark.parametrize("tool", sorted(CAST_VARIANTS))
@pytest.mark.parametrize("drop", CAST_PLACE_FIELDS[1:])
def test_time_cast_names_each_missing_place_field(tmp_path, tool: str, drop: str) -> None:
    """占时起课：缺哪个报哪个（以前缺 zone → 内部错误 / HTTP 500；缺 lat → 另一个专用码，缺 time 直接发 null）。"""
    gone = {drop, {"lat": "gpsLat", "lon": "gpsLon"}.get(drop, drop)}  # gps 十进制是同一个点的另一种写法，一起去掉
    payload = {k: v for k, v in CAST_VARIANTS[tool].items() if k not in gone}
    with pytest.raises(ToolValidationError) as caught:
        _service(tmp_path).run_tool(tool, payload, save_result=False)
    error = caught.value
    assert error.code in ("tool.missing_field", "tool.invalid_payload"), (tool, error.code)
    assert drop in [item["field"] for item in error.details["fields"]], error.details["fields"]
    assert error.details["agent_recovery"]["next_action"] == "ask_user_then_retry"


@pytest.mark.parametrize("tool, payload", [
    ("xiaoliuren", SAMPLES["xiaoliuren"]),                     # nums 免起课
    ("feigong", SAMPLES["feigong"]),                           # 选支 + 干支
    ("xiaochengtu", SAMPLES["xiaochengtu"]),                   # 股价起卦
    ("guice", SAMPLES["guice"]),                               # 四柱 / 农历月日给全
    ("zhengchuan", {"agent_confirmed_settings": True, "school": "xinyi", "item": "父母"}),  # 查询层
])
def test_cast_free_paths_do_not_ask_for_place(tool: str, payload: dict[str, Any]) -> None:
    assert place_fields_required(tool, {**TOOL_DEFINITIONS[tool].input_model.model_validate(payload).model_dump(exclude_none=True)}) == ()


def test_time_cast_is_not_retried_as_a_transport_error(tmp_path) -> None:
    """旧码 tool.<技法>_cast_geo_required（只管 lat / lon）已并入同一个逐字段错误。"""
    from horosa_skill.errors import TOOL_CODE_FAMILIES

    assert "cast_geo_required" not in TOOL_CODE_FAMILIES


@requires_runtime
@pytest.mark.parametrize("tool", sorted(ZONE_FREE_TOOLS))
def test_zone_free_tools_really_ignore_the_zone(tmp_path, tool: str) -> None:
    service = make_service(tmp_path)
    texts = []
    for zone in ("+08:00", "-05:00"):
        env = service.run_tool(tool, {**SAMPLES[tool], "zone": zone}, save_result=False)
        assert env.ok, env.error
        texts.append(env.data["export_snapshot"]["export_text"])
    assert texts[0] == texts[1], f"{tool} 的结果随时区变：不该在 ZONE_FREE_TOOLS 里"


@requires_runtime
def test_mundane_states_the_upstream_default_place(tmp_path) -> None:
    env = make_service(tmp_path).run_tool("mundane", {"agent_confirmed_settings": True, "year": 2025, "ingressTerm": "春分"}, save_result=False)
    assert env.ok, env.error
    assert any("MundaneMain" in w and "`zone`" in w for w in env.warnings), env.warnings
    given = make_service(tmp_path).run_tool("mundane", SAMPLES["mundane"], save_result=False)
    assert not any("MundaneMain" in w for w in given.warnings)


def test_shenshu_zone_written_in_options_counts(tmp_path) -> None:
    """神数旧写法把 zone 写在 options 里（runner 提升到顶层）：算给了，不报缺。"""
    payload = {k: v for k, v in SAMPLES["xianqin"].items() if k != "zone"}
    env = _service(tmp_path).run_tool("xianqin", {**payload, "options": {"zone": "+08:00"}}, save_result=False)
    assert env.error is None or env.error.code != "tool.missing_field", env.error
