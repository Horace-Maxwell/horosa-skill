"""「已声明、不广告」的两种声明法必须同时生效（v0.40.0 合并事故的回归锁）。

模型级 `ADVERTISE_HIDDEN`（西占长尾旋钮）与字段级 `json_schema_extra={"x-horosa-hidden": True}`（紫微传本 / 八字盘法键）
两路并行实现各写一种；合并时后者的赋值覆盖了前者，西占旋钮全部回到 tools/list 广告层（+8 KB，离 256 KB 硬顶 18 B），
只有预算守卫碰巧抓到。这里逐字段断言：两种都不进广告层、都计入「另 N 个高级旋钮」、校验层照收。
"""
from __future__ import annotations

from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.surfaces.mcp_schema import advertise_hidden_fields, advertised_technique_schema


def _advertised(tool_name: str) -> dict:
    model = TOOL_DEFINITIONS[tool_name].input_model
    return advertised_technique_schema(tool_name, model.model_json_schema())


def test_model_level_advertise_hidden_fields_stay_out_of_tools_list() -> None:
    model = TOOL_DEFINITIONS["india_chart"].input_model
    hidden = advertise_hidden_fields(model)
    assert {"dashaSystem", "indiaSchool"} <= hidden
    schema = _advertised("india_chart")
    assert not hidden & set(schema["properties"]), sorted(hidden & set(schema["properties"]))
    assert schema["x-horosa-hidden-knobs"] >= len(hidden)
    assert {"dashaSystem", "indiaSchool"} <= set(model.model_fields)  # 校验层照收


def test_field_level_x_horosa_hidden_fields_stay_out_of_tools_list() -> None:
    model = TOOL_DEFINITIONS["ziwei_birth"].input_model
    flagged = {
        name for name, field in model.model_fields.items()
        if isinstance(field.json_schema_extra, dict) and field.json_schema_extra.get("x-horosa-hidden")
    }
    assert {"childLimit", "sihuaCustomTable"} <= flagged
    schema = _advertised("ziwei_birth")
    assert not flagged & set(schema["properties"]), sorted(flagged & set(schema["properties"]))
