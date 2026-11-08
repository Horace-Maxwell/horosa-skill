"""广告层的 type 必须是 runner 收的形状，绝不能只剩 "null"（v0.48.0）。

`Any | None` 字段在 pydantic 里是 anyOf:[{}, {"type":"null"}]。旧折叠把 "null" 当唯一类型广告出去：42 个属性 / 18 个工具
（择日 conditions ×10、relocLat/relocLon、pdMethod/pdTimeKey、印占 indiaHsys/indiaAyanamsa…）在 tools/list 里写着
`"type": "null"`，严格客户端据此只许传 null。可移植守卫（verify_mcp_client_compat）只查「恰一个 type」，"null" 也算一个，所以一直绿。

这里锁三件事：① 两个面上没有任何属性只广告 "null"；② 每个无类型的技法字段都在 `UNTYPED_FIELD_TYPES` 登记了
runner 实收的类型，且广告的就是登记的那个（不靠回落 "string" 蒙混）；③ `horosa_tool_run` 的公共字段带上描述（此前那列描述从没广告过）。
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fakes import FakeClient, FakeJsClient

from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces.mcp_requests import tool_run_field_docs
from horosa_skill.surfaces.mcp_schema import CORE_DOC, UNTYPED_FIELD_TYPES
from horosa_skill.surfaces.mcp_server import create_mcp_server


def _surface(tmp, *, compact: bool) -> dict[str, dict]:
    settings = Settings(db_path=tmp / "memory.db", output_dir=tmp / "runs", mcp_compact=compact)
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    mcp = create_mcp_server(service, settings)
    return {tool.name: tool.model_dump(mode="json", by_alias=True) for tool in asyncio.run(mcp.list_tools())}


@pytest.fixture(scope="module")
def surfaces(tmp_path_factory) -> dict[str, dict[str, dict]]:
    return {
        "full": _surface(tmp_path_factory.mktemp("full"), compact=False),
        "compact": _surface(tmp_path_factory.mktemp("compact"), compact=True),
    }


def _is_untyped(source: dict[str, Any]) -> bool:
    """模型 JSON schema 里「非空那支没有类型」：Any / Any | None。独立于实现里的折叠逻辑。"""
    if any(key in source for key in ("type", "$ref", "enum", "const")):
        return False
    branches = [b for b in source.get("anyOf") or [] if isinstance(b, dict)]
    return all(b.get("type") == "null" or not any(k in b for k in ("type", "$ref", "enum", "const")) for b in branches)


def test_no_property_is_advertised_as_null_only(surfaces) -> None:
    offenders = [
        (label, tool_name, prop_name)
        for label, tools in surfaces.items()
        for tool_name, tool in tools.items()
        for prop_name, prop in (tool["inputSchema"].get("properties") or {}).items()
        if prop.get("type") in ("null", ["null"])
    ]
    assert not offenders, f"属性只广告了 \"null\"（严格客户端只许传 null）：{offenders[:6]}（共 {len(offenders)} 个）"


def test_untyped_fields_advertise_the_type_registered_from_the_runner(surfaces) -> None:
    full = surfaces["full"]
    unregistered: list[tuple[str, str]] = []
    mismatched: list[tuple[str, str, Any, Any]] = []
    seen: set[str] = set()
    for tool_name, definition in TOOL_DEFINITIONS.items():
        advertised = (full.get(definition.mcp_name) or {}).get("inputSchema", {}).get("properties") or {}
        source = definition.input_model.model_json_schema().get("properties") or {}
        for field, prop in advertised.items():
            # 域核心字段走 CORE_TYPE 那条路（siderealAyanamsa 等），不经折叠；这里只管工具自有字段。
            if field in CORE_DOC or field not in source or not _is_untyped(source[field]):
                continue
            seen.add(field)
            want = UNTYPED_FIELD_TYPES.get(field)
            if want is None:
                unregistered.append((tool_name, field))
                continue
            got = {k: prop[k] for k in ("type", "items") if k in prop}
            if got != want:
                mismatched.append((tool_name, field, got, want))
    assert not unregistered, f"无类型字段没登记 runner 实收类型（会静默回落 string）：{unregistered}"
    assert not mismatched, f"广告的 type 与登记表不一致：{mismatched[:5]}"
    # 反向：登记表里没有死条目（字段改了类型 / 删了，表也要跟着删，免得下次有人照着死条目「修」）。
    assert set(UNTYPED_FIELD_TYPES) == seen, f"登记表多出未广告的无类型字段：{sorted(set(UNTYPED_FIELD_TYPES) - seen)}"


def test_tool_run_common_fields_carry_their_descriptions(surfaces) -> None:
    props = surfaces["compact"]["horosa_tool_run"]["inputSchema"]["properties"]
    docs = tool_run_field_docs()
    missing = [name for name in docs if not str((props.get(name) or {}).get("description") or "").strip()]
    assert not missing, f"horosa_tool_run 公共字段没带描述：{missing}"
    # 闸门三键与技法广告层同一句（精简面下模型只看得到 tool_run 这一份）。
    for name in ("agent_confirmed_settings", "defaults_accepted", "clarification_notes"):
        assert props[name]["description"] == docs[name]
