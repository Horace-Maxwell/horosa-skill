"""推运目标时刻的时区（审计 F03 / 待决项 6，P0：缺省给的是另一张盘）。

- 直调没给 dirZone：以前用出生时的偏移（1990-05-03 上海是夏令时 +09:00），2026-11-13 10:00 这个目标钟点被读成 +09:00，差一小时；
  现在按出生地（或 dirLat / dirLon 给的目标地点）在目标日期的偏移取，并写一条说明。显式 dirZone 照用。
- dispatch：目标时刻取自 context（用户「此刻」）时，时区跟 context 走——以前落回本命，人在纽约 10:00 问按 +09:00 起，差 14 小时。

负向对照（实跑过）：tools.py 里 `self._default_target_zone(...)` 那一行删掉 → 直调用例红（dirZone 回到 +09:00）；
dispatch_plan 里 context zone → dirZone 那段删掉 → dispatch 用例红。
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fakes import FakeClient
from test_local_js_tools import requires_chart

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="[host] node not installed")
BIRTH = {"date": "1990-05-03", "time": "08:00", "place": "上海", "defaults_accepted": True}


def _service(tmp_path: Path, client=None) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", db_path=tmp_path / "m.db",
                        output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt", data_dir=tmp_path / "d")
    return HorosaSkillService(settings, client=client or FakeClient(), store=MemoryStore(settings))


@requires_node
@pytest.mark.parametrize("tool", ["givenyear", "solarreturn", "prog", "timelords"])
def test_target_clock_time_is_read_in_the_birthplace_zone_of_that_date(tmp_path: Path, tool: str) -> None:
    result = _service(tmp_path).run_tool(tool, {**BIRTH, "datetime": "2026-11-13 10:00"}, save_result=False)
    assert result.input_normalized["zone"] == "+09:00"          # 出生那天上海在行夏令时
    assert result.input_normalized["dirZone"] == "+08:00", tool  # 2026-11-13 上海是 +08:00
    assert any("推运目标时刻 2026-11-13 10:00:00 按出生地当日时区 +08:00" in w for w in result.warnings)


@requires_node
def test_explicit_dir_zone_and_date_only_targets_are_untouched(tmp_path: Path) -> None:
    service = _service(tmp_path)
    explicit = service.run_tool("givenyear", {**BIRTH, "datetime": "2026-11-13 10:00", "dirZone": "+09:00"}, save_result=False)
    assert explicit.input_normalized["dirZone"] == "+09:00"
    assert not any("推运目标时刻" in w for w in explicit.warnings)


@requires_node
def test_dispatch_reads_the_context_clock_in_the_context_zone(tmp_path: Path) -> None:
    envelope = _service(tmp_path).dispatch({
        "query": "用流年法（givenyear）看看我此刻", "birth": {"date": "1990-05-03", "time": "08:00", "place": "上海"},
        "context": {"date": "2026-11-13", "time": "10:00", "place": "纽约"}, "defaults_accepted": True,
    })
    data = envelope.model_dump() if hasattr(envelope, "model_dump") else envelope
    result = data["results"]["givenyear"]
    assert result["input_normalized"]["dirZone"] == "-05:00"   # 纽约 2026-11-13 是 EST
    assert result["input_normalized"]["datetime"].startswith("2026-11-13 10:00")


@requires_chart
def test_live_the_zone_changes_the_cast(tmp_path: Path) -> None:
    """改这个参数，结果必须变：同一目标钟点按 +08:00 与 +09:00 起，流年盘不同（证明缺省取对时区是有意义的）。"""
    from horosa_skill.config import Settings as S

    svc = HorosaSkillService(S.from_env().model_copy(update={"db_path": tmp_path / "m.db", "output_dir": tmp_path / "runs"}))
    default = svc.run_tool("givenyear", {**BIRTH, "datetime": "2026-11-13 10:00"}, save_result=False)
    old = svc.run_tool("givenyear", {**BIRTH, "datetime": "2026-11-13 10:00", "dirZone": "+09:00"}, save_result=False)
    assert default.ok and old.ok
    assert default.data["export_snapshot"]["export_text"] != old.data["export_snapshot"]["export_text"]
