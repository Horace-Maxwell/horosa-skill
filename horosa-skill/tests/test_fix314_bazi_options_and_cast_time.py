"""八字口径认不出就拒、运限逐键校验（审计 F17）；起课技法缺时刻的话术是「此刻」不是出生日期（审计 F10）。

F17 修前：southMonth=「南半球」+ 确认位 → ok，「无法识别，已按缺省 none 起盘」——用户要南半球口径，拿到不对冲的月柱；
period={liunian:["明年"], liuyue:[13]} → ok、无告警，正文「流年：明年年（超出大运范围）」「流月：明年年 第13月（）」。
F10 修前：qimen / 六爻 / 小六壬 / 卜卦缺 date / time →「公历日期 YYYY-MM-DD」、example 1990-05-03、ask_user:true，让模型去问用户今天几号。
负向对照（实跑过）：_bazi_option 的拒绝改回按缺省 → 第二个用例红；_bazi_period 改回原样透传 → 第三个红；_is_cast_tool 恒 False → 最后一个红。
"""
from __future__ import annotations

import pytest

from horosa_skill.config import Settings
from horosa_skill.errors import ToolValidationError
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

BIRTH = {"date": "1990-05-03", "time": "08:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gender": 0,
         "agent_confirmed_settings": True}


def _service(tmp_path) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path,
                        runtime_root=tmp_path / "runtime", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs",
                        trace_enabled=False)
    return HorosaSkillService(settings, store=MemoryStore(settings))


def test_south_month_synonyms_mean_chong(tmp_path) -> None:
    service = _service(tmp_path)
    assert service._bazi_option({"southMonth": "南半球"}, "southMonth") == "chong"
    assert service._bazi_option({"southMonth": "不对冲"}, "southMonth") == "none"


@pytest.mark.parametrize(("key", "value"), [("southMonth", "xyz"), ("school", "随便"), ("ageStyle", "old")])
def test_an_unrecognised_bazi_option_is_refused_not_defaulted(tmp_path, key, value) -> None:
    result = _service(tmp_path).run_tool("bazi_birth", {**BIRTH, key: value}, save_result=False)
    assert result.ok is False and result.error.code == "tool.invalid_option", result.error
    assert result.error.details["field"] == key and result.error.details["options"]


@pytest.mark.parametrize("period", [{"liunian": ["明年"]}, {"liuyue": [13]}, {"liushi": [12]}, {"liuri": ["下周"]}, {"liuday": [1]}])
def test_bad_period_entries_are_refused(tmp_path, period) -> None:
    result = _service(tmp_path).run_tool("bazi_birth", {**BIRTH, "period": period}, save_result=False)
    assert result.ok is False and result.error.code == "tool.invalid_option", result.error
    assert result.error.details["field"].startswith("period.")


def test_a_good_period_still_renders(tmp_path) -> None:
    result = _service(tmp_path).run_tool("bazi_birth", {**BIRTH, "period": {"liunian": 2027, "liuyue": [3]}}, save_result=False)
    assert result.ok, result.error
    text = result.data["export_snapshot"]["export_text"]
    assert "流年：2027年" in text and "流月：2027年 第3月" in text


@pytest.mark.parametrize("tool", ["qimen", "sixyao", "xiaoliuren", "horary"])
def test_cast_tools_missing_the_moment_say_pass_now_not_ask_the_birth_date(tmp_path, tool) -> None:
    with pytest.raises(ToolValidationError) as excinfo:
        _service(tmp_path).run_tool(tool, {"question": "出行顺利吗", "defaults_accepted": True}, save_result=False)
    fields = {entry["field"]: entry for entry in excinfo.value.details["fields"]}
    for leaf in ("date", "time"):
        assert fields[leaf]["ask_user"] is False and "1990" not in str(fields[leaf]["example"])
        assert "不要问用户" in fields[leaf]["expected"]
    assert fields["zone"]["ask_user"] is True   # 用户此刻在哪：不知道才问
