"""别名改写在地名解析之前（审计 S-07 / F05）。

- `city` / `location` / `出生地` 以前是「没人读的参数」，接着报缺 zone / lat / lon、让模型去问用户时区和经纬度。
- `timezone` + `place`：以前地名推出的时区顶掉别名给的时区（warning 还说「两个都给了」），规范名 `zone` 却照用——同一个意思差一小时。
负向对照（实跑过）：tools.py 里去掉 `apply_field_aliases(...)` → 两条用例都红。
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fakes import FakeClient

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="[host] node not installed")
BIRTH = {"date": "1990-05-03", "time": "08:00", "defaults_accepted": True}


def _service(tmp_path: Path) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", db_path=tmp_path / "m.db",
                        output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt", data_dir=tmp_path / "d")
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings))


@requires_node
@pytest.mark.parametrize("key", ["city", "location", "birthplace", "出生地"])
def test_place_aliases_resolve_like_place(tmp_path: Path, key: str) -> None:
    result = _service(tmp_path).run_tool("chart", {**BIRTH, key: "上海"}, save_result=False)
    assert result.ok, result.error
    assert (result.input_normalized["lat"], result.input_normalized["zone"]) == ("31n13", "+09:00")
    assert any(f"`{key}` 按地名 `place` 读" in w for w in result.warnings)


@requires_node
@pytest.mark.parametrize("alias", ["timezone", "tz", "zone"])
def test_an_explicit_zone_beats_the_place_zone_whatever_it_is_called(tmp_path: Path, alias: str) -> None:
    # 1990-05-03 上海在行夏令时（+09:00）：显式 +08:00 正好差一个夏令时，先问一次（待决项 3，tool.zone_conflict）；确认后照用显式值。
    result = _service(tmp_path).run_tool("chart", {**BIRTH, "place": "上海", alias: "+08:00", "zone_confirmed": True}, save_result=False)
    assert result.ok, result.error
    assert result.input_normalized["zone"] == "+08:00"
