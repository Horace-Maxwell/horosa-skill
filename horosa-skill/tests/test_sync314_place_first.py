"""广告层：收地名的技法，zone / lat / lon 不标 [required]，place 写明「可代 zone/lat/lon，首选」（审计 S-06 / F20）。

为什么：标成必填会把照 schema 填字段的模型引去自填「+08:00 + 凭记忆的坐标」——1986–1991 中国夏令时（以及任何地方的历史
夏令时）就此静默丢掉；而 `place` 一个键会按出生当日取时区。校验层不变：三者与 place 都没给，照旧逐字段报缺。

负向对照（实跑过）：把 mcp_schema 里 `not (place_covers and key in _PLACE_COVERED)` 去掉 → 第一条红（zone 又带 [required]）。
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from fakes import FakeClient

from horosa_skill.config import Settings
from horosa_skill.errors import ToolValidationError
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces.mcp_server import create_mcp_server


def _tools(tmp_path: Path) -> dict[str, dict]:
    settings = Settings(server_root="http://127.0.0.1:9", db_path=tmp_path / "m.db", output_dir=tmp_path / "runs")
    mcp = create_mcp_server(HorosaSkillService(settings, store=MemoryStore(settings)), settings)
    return {t.name: t.model_dump(mode="json", by_alias=True, exclude_none=True) for t in asyncio.run(mcp.list_tools())}


def test_tools_that_take_a_place_do_not_mark_zone_lat_lon_required(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    with_place = [t for t in tools.values() if "place" in (t["inputSchema"].get("properties") or {})]
    assert len(with_place) > 90
    for tool in with_place:
        props = tool["inputSchema"]["properties"]
        assert props["place"]["description"].startswith("地名（可代 zone/lat/lon"), tool["name"]
        for key in ("zone", "lat", "lon"):
            if key in props:
                assert not props[key]["description"].startswith("[required]"), (tool["name"], key)
    # 日期 / 时刻仍是必填事实
    assert tools["horosa_cn_qimen"]["inputSchema"]["properties"]["date"]["description"].startswith("[required]")


def test_validation_still_refuses_when_neither_place_nor_coordinates_are_given(tmp_path: Path) -> None:
    import pydantic
    import pytest

    settings = Settings(server_root="http://127.0.0.1:9", db_path=tmp_path / "m.db", output_dir=tmp_path / "runs")
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings))
    with pytest.raises((pydantic.ValidationError, ToolValidationError)) as excinfo:
        service.run_tool("chart", {"date": "1990-05-03", "time": "08:00", "defaults_accepted": True}, save_result=False)
    assert {"zone", "lat", "lon"} <= {str(err["loc"][0]) for err in excinfo.value.errors()} if isinstance(excinfo.value, pydantic.ValidationError) else True
