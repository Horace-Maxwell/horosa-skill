"""黄道星释的停层跟着输出层级走；停层比要的层浅就拒；basePoint 收常见写法（审计待决项 4 / S-24 / S-21）。

修前：缺省四层全算，信封 1,062,910 B，正文只读 L1（stopLevelIdx 0 与缺省正文逐字相同，130 KB）；aiMode l2_in_l1 + stopLevelIdx 0 → 正文
「无L2数据」、ok:true 无告警；basePoint:"Spirit" 先撞一次错。偏离上游缺省（AGENTS §10 登记）。
负向对照（实跑过）：stopLevelIdx 缺省分支去掉 → 第一个用例红；拒绝分支去掉 → 第二个用例红。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.errors import ToolValidationError
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.testing_payloads import build_sample_payloads
from test_local_js_tools import requires_runtime


class _Stop(Exception):
    pass


def _offline(tmp_path: Path, sent: list) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path,
                        runtime_root=tmp_path / "runtime", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs",
                        trace_enabled=False)
    service = HorosaSkillService(settings, store=MemoryStore(settings))

    def remote(endpoint, body):
        sent.append((endpoint, dict(body)))
        raise _Stop

    service._call_remote = remote  # type: ignore[attr-defined]
    return service


def _run(service, payload):
    try:
        return service.run_tool("zr", payload, save_result=False), None
    except ToolValidationError as exc:
        return None, exc


@pytest.mark.parametrize(("mode", "level"), [(None, 1), ("l2_in_l1", 1), ("l3_in_l2", 2), ("l4_in_l3", 3)])
def test_the_stop_level_follows_the_output_level(tmp_path: Path, mode, level) -> None:
    sent: list = []
    payload = {**build_sample_payloads()["zr"], **({"aiMode": mode} if mode else {})}
    payload.pop("stopLevelIdx", None)
    _run(_offline(tmp_path, sent), payload)
    assert sent and sent[-1][1].get("stopLevelIdx") == level, sent


def test_a_stop_level_shallower_than_the_output_level_is_refused(tmp_path: Path) -> None:
    sent: list = []
    result, refused = _run(_offline(tmp_path, sent), {**build_sample_payloads()["zr"], "aiMode": "l3_in_l2", "stopLevelIdx": 1})
    code = refused.code if refused else result.error.code
    assert code == "tool.predictive_invalid_option" and sent == []


def test_base_point_aliases(tmp_path: Path) -> None:
    sent: list = []
    result, refused = _run(_offline(tmp_path, sent), {**build_sample_payloads()["zr"], "basePoint": "Spirit"})
    assert refused is None and (result.error is None or result.error.code != "tool.predictive_invalid_option")
    assert any(endpoint == "/chart" for endpoint, _ in sent)   # 精神点要先取本命盘上它所在的星座


@requires_runtime
def test_live_default_is_small_and_reads_the_same(tmp_path: Path) -> None:
    import json

    settings = Settings.from_env().model_copy(update={"db_path": tmp_path / "m.db", "output_dir": tmp_path / "runs", "data_dir": tmp_path / "d"})
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    # 带当前目标时刻：[当前时点]「当前所处：L1 … / L2 …」读 L2——停层 0 时那半句会掉（审计复核时 live 实测）
    payload = {"date": "1992-08-15", "time": "08:20", "zone": "+08:00", "lat": "30n15", "lon": "120e10", "defaults_accepted": True,
               "datetime": "2026-11-14 12:00:00"}
    default = service.run_tool("zr", payload, save_result=False)
    deep = service.run_tool("zr", {**payload, "stopLevelIdx": 3}, save_result=False)
    assert default.ok and deep.ok
    assert default.data["export_snapshot"]["export_text"] == deep.data["export_snapshot"]["export_text"]
    assert "/ L2 " in default.data["export_snapshot"]["export_text"]
    assert len(json.dumps(default.data, ensure_ascii=False)) * 3 < len(json.dumps(deep.data, ensure_ascii=False))
