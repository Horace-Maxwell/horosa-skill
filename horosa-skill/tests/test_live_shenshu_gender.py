"""v0.36.0 B3 — live: the 神数 gender/place knobs the gate now asks about must change the result.

Runs only against a local runtime (Java backend); skips otherwise. This is the §5.12 "改参数结果必变"
check for the settings the new SHENSHU_GENDER_POLICY / SHENSHU_PLACE_POLICY ask for.

v0.36.0 收尾实测（首次带 Mongo 的全量 live）：演禽（xianqin）对地点/时区/timeAlg **完全不敏感**——输出里
没有时区/经纬度行，上海↔乌鲁木齐逐字节相同。所以它归 gender 组，并且用一条**反向**断言把这个事实钉住：
若上游哪天让演禽读地点，这条会红，届时把它挪回 place 组即可（而不是让闸门凭想象问地点）。
"""
from __future__ import annotations

import pytest
from test_local_js_tools import make_service, requires_runtime

_BASE = {"date": "1990-01-01", "time": "12:00:00", "zone": "+08:00", "agent_confirmed_settings": True}
_SHANGHAI = {"lat": "31n13", "lon": "121e28"}
_URUMQI = {"lat": "43n49", "lon": "87e36"}


def _pair(tmp_path, tool: str, a: dict, b: dict):
    service = make_service(tmp_path)
    first = service.run_tool(tool, a, save_result=False)
    second = service.run_tool(tool, b, save_result=False)
    if not (first.ok and second.ok):
        pytest.skip(f"{tool} backend unavailable: {first.error or second.error}")
    return first.data["snapshot_text"], second.data["snapshot_text"]


@requires_runtime
@pytest.mark.parametrize("tool", ["tieban", "shaozi", "xianqin", "cetian", "qizhengkin"])
def test_shenshu_gender_changes_the_reading(tmp_path, tool: str) -> None:
    male, female = _pair(tmp_path, tool, {**_BASE, **_SHANGHAI, "gender": 1}, {**_BASE, **_SHANGHAI, "gender": 0})
    assert male != female


@requires_runtime
@pytest.mark.parametrize("tool", ["cetian", "qizhengkin"])
def test_shenshu_place_changes_the_reading(tmp_path, tool: str) -> None:
    shanghai, urumqi = _pair(tmp_path, tool, {**_BASE, **_SHANGHAI, "gender": 1}, {**_BASE, **_URUMQI, "gender": 1})
    assert shanghai != urumqi


@requires_runtime
def test_xianqin_ignores_place_so_its_gate_must_not_ask_for_it(tmp_path) -> None:
    """Negative control: 演禽 reads clock time + gender only. If this ever flips, move xianqin to the place policy."""
    shanghai, urumqi = _pair(tmp_path, "xianqin", {**_BASE, **_SHANGHAI, "gender": 1}, {**_BASE, **_URUMQI, "gender": 1})
    assert shanghai == urumqi
    assert "经度" not in shanghai and "时区" not in shanghai
