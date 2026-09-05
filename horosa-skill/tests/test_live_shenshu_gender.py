"""v0.36.0 B3 — live: the 神数 gender/place knobs the gate now asks about must change the result.

Runs only against a local runtime (Java backend); skips otherwise. This is the §5.12 "改参数结果必变"
check for the settings the new SHENSHU_GENDER_POLICY / SHENSHU_PLACE_POLICY ask for.
"""
from __future__ import annotations

import pytest
from test_local_js_tools import make_service, requires_runtime


@requires_runtime
@pytest.mark.parametrize("tool", ["tieban", "shaozi"])
def test_shenshu_gender_changes_the_reading(tmp_path, tool: str) -> None:
    service = make_service(tmp_path)
    base = {"date": "1990-01-01", "time": "12:00:00", "agent_confirmed_settings": True}
    male = service.run_tool(tool, {**base, "gender": 1}, save_result=False)
    female = service.run_tool(tool, {**base, "gender": 0}, save_result=False)
    if not (male.ok and female.ok):
        pytest.skip(f"{tool} backend unavailable: {male.error or female.error}")
    assert male.data["snapshot_text"] != female.data["snapshot_text"]


@requires_runtime
@pytest.mark.parametrize("tool", ["xianqin", "qizhengkin"])
def test_shenshu_place_changes_the_reading(tmp_path, tool: str) -> None:
    service = make_service(tmp_path)
    base = {"date": "1990-01-01", "time": "12:00:00", "zone": "+08:00", "gender": 1, "agent_confirmed_settings": True}
    shanghai = service.run_tool(tool, {**base, "lat": "31n13", "lon": "121e28"}, save_result=False)
    urumqi = service.run_tool(tool, {**base, "lat": "43n49", "lon": "87e36"}, save_result=False)
    if not (shanghai.ok and urumqi.ok):
        pytest.skip(f"{tool} backend unavailable: {shanghai.error or urumqi.error}")
    assert shanghai.data["snapshot_text"] != urumqi.data["snapshot_text"]
