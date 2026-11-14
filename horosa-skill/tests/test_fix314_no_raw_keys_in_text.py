"""正文里不漏原始键（审计 O-14）：nongli_time「birth： / yearJieqi：」、qizhengkin「当前大限：palace_index：2；branch：2…」、
xianqin「贵格：name：蛟吞日月；ganzhi：壬午、name：…」、xuanshi「action：search / q：」；nongli_time 的技法名是「其他页面」。

负向对照（实跑过）：_undict_shenshu_rows 直接 return 原文 → 前两条红；nongli 标签表换回键名 → 第三条红；xuanshi 标签表清空 → 第四条红。
"""
from __future__ import annotations

import re
from pathlib import Path

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.service.runners.shenshu import _undict_shenshu_rows
from horosa_skill.service.text.chinese import _build_nongli_snapshot_text
from horosa_skill.service.text.divination import _build_xuanshi_snapshot_text
from test_local_js_tools import requires_runtime

RAW_KEY = re.compile(r"(?<![A-Za-z])[a-z][A-Za-z_]{2,}：")

QIZHENG_TEXT = "[年限]\n当前年龄：28\n当前大限：palace_index：1；branch：7；branch_name：未；palace_name：财帛宫\n流年：午｜福德宫"
XIANQIN_TEXT = "[情性与格局]\n格局：中格\n贵格：name：犬化天徹；ganzhi：庚辰\n福禄上格：name：鼠食牛田；stars：虛日鼠；condition：秋冬夜降\n\n[二十八宿禽]\n角：蛟"


def test_qizhengkin_current_dasha_is_one_reader_line() -> None:
    response = {"qizheng": {"dasha": {"current": {"palace_index": 1, "branch": 7, "branch_name": "未", "palace_name": "财帛宫",
                                                   "lord": "太阴", "years": 25, "start_age": 20, "end_age": 44,
                                                   "start_year": 2018, "end_year": 2042}}}}
    text = _undict_shenshu_rows("qizhengkin", response, QIZHENG_TEXT)
    assert "当前大限：财帛宫｜20-44岁｜太阴｜未（2018–2042 年，共 25 年）" in text and not RAW_KEY.search(text), text
    assert "流年：午｜福德宫" in text


def test_xianqin_literature_rows_list_names_with_their_conditions() -> None:
    response = {"literature": {"gui": [{"name": "犬化天徹", "ganzhi": "庚辰"}, {"name": "犬得佳寛", "ganzhi": ""}],
                               "fulu": [{"name": "鼠食牛田", "stars": "虛日鼠", "condition": "秋冬夜降"}]}}
    text = _undict_shenshu_rows("xianqin", response, XIANQIN_TEXT)
    assert "贵格：犬化天徹（庚辰）、犬得佳寛" in text and "福禄上格：鼠食牛田（虛日鼠；秋冬夜降）" in text
    assert not RAW_KEY.search(text) and "[二十八宿禽]\n角：蛟" in text, text


def test_nongli_time_labels() -> None:
    text = _build_nongli_snapshot_text({"date": "2028-04-06", "time": "09:33:00", "zone": "+08:00"},
                                       {"birth": "2028-04-06 09:36:30", "yearJieqi": "戊申", "jiedelta": "清明后第2天", "chef": "乙木用事"})
    assert "真太阳时：2028-04-06 09:36:30" in text and "年柱（立春界）：戊申" in text and not RAW_KEY.search(text), text


def test_xuanshi_conditions_are_labelled() -> None:
    text = _build_xuanshi_snapshot_text("search", {"q": "武则天", "limit": 5, "has_crosswalk": True}, [])
    assert "检索类型：全文检索（search）" in text and "检索词：武则天" in text and "有交叉对照：是" in text
    assert not RAW_KEY.search(text.replace("（search）", "")), text


@requires_runtime
def test_live_four_texts_carry_no_raw_keys(tmp_path: Path) -> None:
    settings = Settings.from_env().model_copy(update={"db_path": tmp_path / "m.db", "output_dir": tmp_path / "runs", "data_dir": tmp_path / "d"})
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    birth = {"date": "1998-04-06", "time": "09:33", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gender": 1, "defaults_accepted": True}
    for tool, payload in (("nongli_time", birth), ("qizhengkin", birth), ("xianqin", birth), ("xuanshi", {"q": "武则天", "limit": 3})):
        result = service.run_tool(tool, payload, save_result=False)
        assert result.ok, (tool, result.error)
        snapshot = result.data["export_snapshot"]
        text = snapshot["export_text"].replace("（search）", "")
        assert not RAW_KEY.search(text), (tool, RAW_KEY.findall(text)[:5])
        if tool == "nongli_time":
            assert snapshot["technique"]["label"] == "农历时间换算"
