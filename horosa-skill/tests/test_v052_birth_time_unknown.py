"""审计输入一路待决项 1（第二档）：出生时刻未知模式——八字三柱、西洋无宫位盘、其余按族拒绝并说清楚还能用什么。"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.engine.time_roles import NATAL, NATAL_MOMENT, NATAL_TARGET, time_role
from horosa_skill.errors import ToolValidationError
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService, birth_time

BIRTH = {"date": "1990-05-03", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gender": "女", "defaults_accepted": True}
requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="[host] node not installed")


def _service(tmp_path: Path) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path,
                        db_path=tmp_path / "m.db", output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt")
    return HorosaSkillService(settings, store=MemoryStore(settings))


def test_every_natal_technique_declares_what_it_does_with_an_unknown_time() -> None:
    covered = birth_time.SUPPORTED_TOOLS | birth_time._MINGLI_REFUSE | birth_time._CHART_REFUSE | birth_time._PREDICTIVE_REFUSE
    natal = {name for name in TOOL_DEFINITIONS if time_role(name) in (NATAL, NATAL_TARGET, NATAL_MOMENT)}
    assert natal <= covered, sorted(natal - covered)


@requires_node
def test_bazi_with_an_unknown_time_gives_three_pillars_and_says_so(tmp_path: Path) -> None:
    """负向对照（实跑过）：_compute_tool_result 不调 birth_time.apply → 正文里有时柱行与命宫 → 红。"""
    env = _service(tmp_path).run_tool("bazi_birth", {**BIRTH, "time": "不详"}, save_result=False, gate="checked")
    assert env.ok, env.error
    text = env.data["export_snapshot"]["export_text"]
    assert "| 时柱 |" not in text and "命宫：" not in text and "身宫：" not in text and "小运" not in text
    # v3.15.0 新段 [卦释]：逐柱一行，时柱那行要去掉、其余柱留着（负向对照：过滤式不认「时柱 干支:」→ 红）
    assert "[卦释]" in text and "日柱 " in text.split("[卦释]")[1] and not any(line.startswith("时柱 ") for line in text.split("\n"))
    assert "| 日柱 |" in text and "只给年 / 月 / 日三柱" in text and "起运岁数是约数" in text
    assert env.data["birth_time"]["precision"] == "unknown" and "格局·用神" in env.data["birth_time"]["omitted_sections"]
    assert env.data["technique_card"]["birth_time"]["computed_at"] == "12:00:00"
    assert any("出生时刻未知" in warning for warning in env.warnings)
    for title in env.data["birth_time"]["omitted_sections"]:   # 有意略去 ≠ 引擎没给
        assert f"本次本地计算结果未返回「{title}」" not in text, title


def test_techniques_that_need_the_time_refuse_with_a_family_specific_way_out(tmp_path: Path) -> None:
    service = _service(tmp_path)
    for tool, needle in (("ziwei_birth", "按时辰起盘"), ("solarreturn", "planet_cycles"), ("india_chart", "无宫位盘")):
        with pytest.raises(ToolValidationError) as caught:
            service.run_tool(tool, {**BIRTH, "time": "unknown", "datetime": "2026"}, save_result=False, gate="checked")
        assert caught.value.code == "tool.time_unknown" and needle in str(caught.value), tool
        assert caught.value.details["agent_recovery"]["must_ask_user"] is True


def test_a_missing_time_is_still_asked_not_treated_as_unknown(tmp_path: Path) -> None:
    with pytest.raises(ToolValidationError) as caught:
        _service(tmp_path).run_tool("bazi_birth", dict(BIRTH), save_result=False, gate="checked")
    assert caught.value.code in ("tool.time_unknown", "tool.invalid_payload", "tool.missing_field")


def test_western_filter_keeps_planets_and_aspects_and_drops_angles_and_houses() -> None:
    snapshot = "\n".join([
        "[起盘信息]", "日期：1990-05-03 12:00:00", "直接时间：1990-05-03 12:00:00",
        "[宫位宫头]", "第1宫 巨蟹 3°",
        "[星与虚点]", "太阳 金牛 12°", "上升 巨蟹 3°", "天顶 双鱼 10°",
        "[相位]", "太阳 三分 木星", "月亮 合 上升",
        "[希腊点]", "福点 天秤 2°",
        "[古典]", "日间盘",
    ])
    text, omitted, dropped = birth_time.filter_snapshot("chart", snapshot)
    assert "太阳 金牛 12°" in text and "太阳 三分 木星" in text
    assert "上升 巨蟹" not in text and "月亮 合 上升" not in text and "第1宫" not in text and "福点" not in text
    assert set(omitted) == {"宫位宫头", "希腊点", "古典"} and dropped == 4   # 三条四轴行 + 起盘信息的直接时间
    assert "无宫位盘" in text and "直接时间" not in text


def test_western_filter_drops_house_info_that_rides_inside_kept_sections() -> None:
    """2026-11-20 对 vendored 实例实跑才看到的漏网：行星名后的宫位标记、落宫列、阿拉伯点行、整宫制宫主表、
    「◆ 上升旬详情」整块、德国派「主体：Asc」块（只删标题会把相位行挂到上一个主体下）、起盘信息里的日夜盘与宫制。
    负向对照（实跑过）：_filter_body 换回逐行删四轴词 → 本测试红在宫位标记 / 孤儿相位行。"""
    snapshot = "\n".join([
        "[起盘信息]", "1990-05-03 12:00:00 周四", "时区：+08:00 ，日生盘", "回归黄道，Alcabitus",
        "说明：行星名后括号中的 nR 为宫主宫位标记；逆行会明确写为“逆行”。", "日主星：木", "时主星：土", "命主星：日 落第十宫（金牛）",
        "[行星]", "◆ 位置与速度", "| 星曜 | 落座 | 落宫 | 当前速度 |", "| --- | --- | --- | --- |",
        "| 日 (10th; 1R) | 12˚金牛28分 | 第十宫 | 0.97度 |", "| 灵点 (9th; -) | 3˚金牛26分 | 第九宫 | — |",
        "◆ 尊贵与主宰", "| 星曜 | 禀赋 | 分值 | 入垣宫 |", "| --- | --- | --- | --- |", "| 金 (8th; 3R10R) | 擢升，日三分 | 7 | 第三宫 |",
        "◆ 汇合恒星", "水 (10th; 2R11R)", "天大將軍一：14˚金牛5分", "福点 (4th; -)", "某星：5˚射手", "火 (7th; 4R9R)", "羽林军二六：8˚双鱼44分",
        "[主宰星链]", "木：木 → 月", "◆ 整宫制宫主表(wholeSignRulers)", "| 宫 | 宫主 |", "| 1宫 | 日 |",
        "[埃及历]", "◆ 各行星落旬", "上升：第14旬", "日：第5旬", "◆ 上升旬详情", "第14旬 狮子2", "护符：秘名 Ipi", "◆ 埃及民用历", "1853 年",
    ])
    text, _omitted, _dropped = birth_time.filter_snapshot("chart", snapshot)
    assert "(10th" not in text and "第十宫" not in text and "第三宫" not in text and "| 1宫 |" not in text
    assert "灵点" not in text and "福点" not in text and "某星" not in text and "第14旬" not in text and "护符" not in text
    assert "日生盘" not in text and "Alcabitus" not in text and "时主星" not in text and "命主星" not in text and "宫主宫位标记" not in text
    assert "| 日 | 12˚金牛28分 | — | 0.97度 |" in text and "日三分（须白天出生）" in text and "| 7 |" not in text
    assert "天大將軍一" in text and "羽林军二六" in text and "日：第5旬" in text and "1853 年" in text and "木：木 → 月" in text
    assert "回归黄道（无宫位）" in text and "12:00（出生时刻未知，按正午起）" in text and "日主星：木" in text

    germany = "\n".join(["[中点相位]", "主体：Asc", "与中点(Hades | Poseidon) 成 0 相位", "", "主体：Sun", "与中点(Sun | Mercury) 成 0 相位"])
    gtext, _o, _d = birth_time.filter_snapshot("germany", germany)
    assert "Hades | Poseidon" not in gtext and "主体：Sun" in gtext and "Sun | Mercury" in gtext
