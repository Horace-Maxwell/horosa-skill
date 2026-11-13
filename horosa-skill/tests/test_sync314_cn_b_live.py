"""上游 v3.14.0（Horosa-Public 10fb75de → e55c3a66）cn_b 批的 live 用例：只在显式点名的 vendored 实例上跑
（test_local_js_tools 的门禁；`:8899` / `:9999` 永不碰）。

这里的每条都是「后端这一版改了口径，skill 原样带出来」的回归：skill 侧没有可注错的代码（负向对照做不了——共享引擎
不许改），所以每条都配一个离线的判别用例（把旧版后端会给的那一行喂给同一个判据，证明判据抓得到），写在各自下面。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from test_local_js_tools import make_service, requires_runtime

from horosa_skill.testing_payloads import build_sample_payloads

_KATHMANDU = {"zone": "+05:45", "lon": "85e19", "lat": "27n42", "gpsLon": 85.316667, "gpsLat": 27.7}


def _text(tmp_path: Path, tool: str, **overrides: object) -> str:
    payload = {**build_sample_payloads()[tool], **overrides, "agent_confirmed_settings": True}
    env = make_service(tmp_path).run_tool(tool, payload, save_result=False)
    assert env.ok is True, env.error
    return env.data["export_snapshot"]["export_text"]


# ── 神数六家的「时区」：UTC±HH:MM（上游 horosa_engine_common.format_timezone_label）────────────────────────────────
# 旧版 webcetiansrv 写 `UTC{tz:+.1f}`（+05:45 → UTC+5.8，丢了精度），另五家 `UTC{tz:+g}`（→ UTC+5.75；地方平时 +00:53
# → UTC+0.883333）。v3.14.0 六家统一 `UTC+05:45`。期望值就是输入的时区本身。

_ZONE_LINE = re.compile(r"^时区：(.*)$", re.MULTILINE)


def _zone_labels(text: str) -> list[str]:
    return _ZONE_LINE.findall(text)


def test_zone_label_check_rejects_the_old_decimal_forms() -> None:
    """判据的离线对照：旧后端的两种写法都不是 UTC±HH:MM。"""
    assert _zone_labels("[起盘]\n时区：UTC+5.8\n经度：85.3") == ["UTC+5.8"]
    assert _zone_labels("时区：UTC+5.75") != ["UTC+05:45"] and _zone_labels("时区：UTC+05:45") == ["UTC+05:45"]


@requires_runtime
@pytest.mark.parametrize("tool", ["cetian", "beiji", "chunzi", "fendjing", "nanji", "qizhengkin"])
def test_shenshu_zone_row_is_utc_hh_mm(tmp_path: Path, tool: str) -> None:
    assert _zone_labels(_text(tmp_path, tool, **_KATHMANDU)) == ["UTC+05:45"]


# ── 后台繁→简不再把卦名「乾」写成「干」（上游 horosa_engine_common.simplify_text）──────────────────────────────────
# 神易数 [神煞] 的驿马 / 血光 / 天财 … 落的是八卦宫位；旧版 display_text 把单字「乾」转成「干」（「驿马：干」）。
_TRIGRAMS = set("乾坎艮震巽离坤兑")
_PALACE_ROWS = ("驿马", "血光", "天财", "魁元", "羊刃", "正禄", "破碎", "劫杀")


def _palace_values(text: str) -> dict[str, str]:
    rows = dict(line.split("：", 1) for line in text.splitlines() if "：" in line and line.split("：", 1)[0] in _PALACE_ROWS)
    return rows


def test_palace_check_rejects_the_old_gan_for_qian() -> None:
    """判据的离线对照：旧后端那一行「驿马：干」落在八卦集合之外。"""
    assert not set(_palace_values("驿马：干\n劫杀：干").values()) <= _TRIGRAMS
    assert set(_palace_values("驿马：乾\n血光：艮").values()) <= _TRIGRAMS


@requires_runtime
def test_shenyishu_palace_names_keep_qian(tmp_path: Path) -> None:
    rows = _palace_values(_text(tmp_path, "shenyishu"))
    assert set(rows) == set(_PALACE_ROWS), rows
    assert set(rows.values()) <= _TRIGRAMS, rows
    assert "乾" in rows.values(), "这张样例盘（1998-02-20 戌时）有两项落乾宫——没有就说明样例换了，用例失去判别力"


@requires_runtime
def test_beiji_palace_label_keeps_qian(tmp_path: Path) -> None:
    text = _text(tmp_path, "beiji")
    assert "乾宫 · 码" in text and "干宫" not in text


# ── 地占问类：真后端只回程序键，快照写中文名（上游 GeomancyMain.questionTypeText）──────────────────────────────────

@requires_runtime
def test_geomancy_backend_returns_only_the_key_and_snapshot_names_it(tmp_path: Path) -> None:
    payload = {**build_sample_payloads()["geomancy"], "questionType": "career", "agent_confirmed_settings": True}
    env = make_service(tmp_path).run_tool("geomancy", payload, save_result=False)
    assert env.ok is True, env.error
    reading = env.data["reading"]
    # 后端哪天开始回 questionTypeZh，这条会红：那时离线桩与 tests/test_sync314_cn_b_ports.py 的说明要跟着改。
    assert reading["questionType"] == "career" and not reading.get("questionTypeZh")
    assert "问类：事业" in env.data["export_snapshot"]["export_text"]


# ── 日子馆：选中日的老黄历卡与黄历同一口径的九星值日（闰期日 2020-06-25：日紫白七赤，lunar 旧口径九紫）────────────────

@requires_runtime
def test_calendar_month_day_card_nine_star_is_the_day_zibai(tmp_path: Path) -> None:
    text = _text(tmp_path, "calendar_month", date="2020-06-25", day="2020-06-25")
    assert "九星值日：七赤金" in text and "九星值日：九紫火" not in text


# ── 紫微：秒进了起盘（00:59:59 与 00:59:00 的真太阳时差 59 秒）──────────────────────────────────────────────────

@requires_runtime
def test_ziwei_true_solar_time_moves_with_the_seconds(tmp_path: Path) -> None:
    def solar(time: str) -> str:
        text = _text(tmp_path, "ziwei_birth", date="1990-05-15", time=time)
        return next(line for line in text.splitlines() if line.startswith("真太阳时："))

    assert solar("00:59:59") == "真太阳时：1990-05-15 01:09:32"
    assert solar("00:59:00") == "真太阳时：1990-05-15 01:08:33"
