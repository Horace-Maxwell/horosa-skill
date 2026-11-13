"""上游 v3.14.0（Horosa-Public 10fb75de → e55c3a66）九星值日口径：黄历 / 日子馆 / 黄历择日的「九星值日」统一到本软件日紫白。

上游改了什么（components/calendar/huangliDay.js，vendored verbatim）：`readNineStar` 不再取 lunar-javascript 的
`getDayNineStar()`，改走 `dayNineStarOf(y, m, d)` = `fengshui/zibai.js` 的 `dayCenter`。日紫白的规则（zibai.js 文件头）：
离冬至 / 夏至**最近**的甲子换遁，阳遁一白 · 七赤 · 四绿顺行、阴遁九紫 · 三碧 · 六白逆行；相邻两个起遁甲子隔 240 日
（约十一二年一次）时置闰——前遁延 30 日、后遁提前 30 日，在中间的甲午换遁（阳转阴甲午起三碧、阴转阳甲午起七赤）。
lunar 的排法在闰期那 30 日与此不同（2008-12-20 ~ 2009-01-18、2020-06-20 ~ 07-19、2031-12-20 ~ 2032-01-18）。

期望值的来源（不是把当前输出抄成期望）：本文件 `_hand_day_star` 按上面那段规则**另算一遍**——日干支用儒略日数直接取
（2000-01-01 = 戊午），二至日期写死为天文年历的北京时间日期，不经 lunar-javascript、也不经 zibai.js；另有三条取自上游
自己的夹具 `components/fengshui/__tests__/zibaiAugment.test.js`（2026-04-20 四绿、2026-06-21 七赤、2026-12-15 一白）。
「旧值」一栏是 lunar `getDayNineStar()` 在同一天给的星（2026-11-13 用 node 实取），只用来证明这些日子新旧确实不同。

负向对照（2026-11-13 实跑）：把 vendored `huangliDay.js` 的 `readNineStar` 改回
`normalizeNineStar(safe(()=> lunarForDetail().getDayNineStar(), null))` → 本文件 8 条红（闰期五日 + 两个闰期换遁日 +
择日条件），非闰期用例与平常换遁日照绿；恢复后 15 条全绿。日子馆（calendar_month 要后端）的同口径用例在
tests/test_sync314_cn_b_live.py。
"""

from __future__ import annotations

import datetime as dt
import itertools
import shutil
from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.engine.client import HorosaApiClient
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="[host] node not installed")

STAR_NAME = {1: "一白水", 2: "二黑土", 3: "三碧木", 4: "四绿木", 5: "五黄土", 6: "六白金", 7: "七赤金", 8: "八白土", 9: "九紫火"}

# 二至的北京时间日期（天文年历；夏至在前、冬至在后）。只列用例要用到的年份。
_SUMMER = {2007: (6, 22), 2008: (6, 21), 2009: (6, 21), 2019: (6, 21), 2020: (6, 21), 2021: (6, 21), 2023: (6, 21),
           2024: (6, 21), 2025: (6, 21), 2026: (6, 21), 2027: (6, 21), 2030: (6, 21), 2031: (6, 21), 2032: (6, 21)}
_WINTER = {2007: (12, 22), 2008: (12, 21), 2009: (12, 22), 2019: (12, 22), 2020: (12, 21), 2021: (12, 21), 2023: (12, 22),
           2024: (12, 21), 2025: (12, 21), 2026: (12, 22), 2027: (12, 22), 2030: (12, 22), 2031: (12, 22), 2032: (12, 21)}
_EPOCH = dt.date(2000, 1, 1)   # 戊午日，六十甲子序 54（甲子 = 0）


def _gz(day: dt.date) -> int:
    return (54 + (day - _EPOCH).days) % 60


def _nearest_jiazi(solstice: dt.date) -> dt.date:
    before = solstice - dt.timedelta(days=_gz(solstice))
    after = before + dt.timedelta(days=60)
    return before if (solstice - before) <= (after - solstice) else after   # 等距取前一个


def _hand_day_star(day: dt.date) -> int:
    """按 zibai.js 文件头那段文字规则手算日紫白入中星（独立实现，见模块说明）。"""
    starts: list[tuple[dt.date, bool]] = []   # (起遁甲子, 阳遁?)
    for year in sorted(_SUMMER):
        starts.append((_nearest_jiazi(dt.date(year, *_SUMMER[year])), False))
        starts.append((_nearest_jiazi(dt.date(year, *_WINTER[year])), True))
    starts.sort()
    duns: list[tuple[dt.date, bool, int]] = []   # (换遁日, 阳遁?, 换遁日的星)
    for (prev, _), (cur, yang) in itertools.pairwise(starts):
        gap = (cur - prev).days
        if gap > 240:   # 年表不连续处（只列了用例要用的年份）：这一遁的起点无从判断，不收
            continue
        assert gap in (180, 240), (prev, cur, gap)
        if gap == 240:   # 置闰：提前 30 日在甲午换遁
            duns.append((cur - dt.timedelta(days=30), yang, 7 if yang else 3))
        else:
            duns.append((cur, yang, 1 if yang else 9))
    start, yang, star = [d for d in duns if d[0] <= day][-1]
    n = (day - start).days
    assert n < 240, f"{day} 落在年表没覆盖的年份"
    return (star - 1 + (n if yang else -n)) % 9 + 1


class _NoBackend(HorosaApiClient):
    """黄历族全是本地 JS 引擎：任何远端调用都是接线错误。"""

    def __init__(self) -> None:
        super().__init__("http://fake")

    def probe(self, endpoint: str = "/common/time", payload: dict | None = None) -> bool:
        return True

    def call(self, endpoint: str, payload: dict) -> dict:
        raise AssertionError(f"unexpected backend call {endpoint}")


def _service(tmp_path: Path) -> HorosaSkillService:
    settings = Settings(
        server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs", runtime_root=tmp_path / "runtime",
    )
    return HorosaSkillService(settings, client=_NoBackend(), store=MemoryStore(settings))


def _text(service: HorosaSkillService, tool: str, payload: dict) -> str:
    env = service.run_tool(tool, {**payload, "agent_confirmed_settings": True}, save_result=False)
    assert env.ok is True, env.error
    return env.data["export_snapshot"]["export_text"]


def _nine_star_line(text: str) -> str:
    lines = [line for line in text.splitlines() if line.startswith("九星值日：")]
    assert len(lines) == 1, lines
    return lines[0].split("：", 1)[1]


# (日期, 手算星, lunar 旧值)。闰期五日新旧不同；其余新旧相同（非闰期结果不变）。
LEAP_DAYS = [
    ("2008-12-25", 3, "一白水"),   # 阴转阳闰头：2008-12-20 甲午起七赤顺行，第 6 日
    ("2009-01-10", 1, "九紫火"),
    ("2020-06-25", 7, "九紫火"),   # 阳转阴闰头：2020-06-20 甲午起三碧逆行，第 6 日
    ("2020-07-01", 1, "六白金"),
    ("2031-12-25", 3, "一白水"),
]
PLAIN_DAYS = [
    ("2026-04-20", 4),   # 上游夹具 zibaiAugment.test.js：下元甲子四绿
    ("2026-06-21", 7),   # 同上：夏至当日接着逆行
    ("2026-12-15", 1),   # 同上：阴遁末日一白
    ("2028-04-06", 1),
    ("2024-06-21", 2),
]


def test_hand_calculation_reproduces_the_upstream_fixture_values() -> None:
    """手算器自己先过上游夹具（独立来源互证）：它不对，下面的期望值就没有意义。"""
    assert _hand_day_star(dt.date(2026, 4, 20)) == 4
    assert _hand_day_star(dt.date(2026, 6, 21)) == 7
    assert _hand_day_star(dt.date(2026, 12, 15)) == 1
    assert _hand_day_star(dt.date(2020, 6, 19)) == 3   # zibaiAugment.test.js:63 前遁延出的闰尾
    for iso, star, _old in LEAP_DAYS:
        assert _hand_day_star(dt.date.fromisoformat(iso)) == star, iso
    for iso, star in PLAIN_DAYS:
        assert _hand_day_star(dt.date.fromisoformat(iso)) == star, iso


@requires_node
@pytest.mark.parametrize(("iso", "star", "old"), LEAP_DAYS)
def test_huangli_nine_star_in_a_leap_window_is_the_day_zibai(tmp_path: Path, iso: str, star: int, old: str) -> None:
    got = _nine_star_line(_text(_service(tmp_path), "huangli", {"date": iso, "hour": 12}))
    assert got == STAR_NAME[star], f"{iso}: {got}（lunar 旧口径是 {old}）"
    assert got != old   # 这些日子新旧口径确实不同——用例有判别力


@requires_node
@pytest.mark.parametrize(("iso", "star"), PLAIN_DAYS)
def test_huangli_nine_star_outside_leap_windows_is_unchanged(tmp_path: Path, iso: str, star: int) -> None:
    assert _nine_star_line(_text(_service(tmp_path), "huangli", {"date": iso, "hour": 12})) == STAR_NAME[star]


@requires_node
@pytest.mark.parametrize(("before", "after", "star"), [
    ("2020-06-19", "2020-06-20", 3),   # 阳遁闰尾末日三碧 → 甲午换阴遁，当日仍三碧
    ("2008-12-19", "2008-12-20", 7),   # 阴遁闰尾末日七赤 → 甲午换阳遁，当日仍七赤
    ("2026-06-18", "2026-06-19", 9),   # 平常换遁：阳遁末日九紫 → 阴遁甲子九紫（zibaiAugment.test.js:38-44）
])
def test_the_day_a_dun_turns_keeps_the_previous_days_star(tmp_path: Path, before: str, after: str, star: int) -> None:
    """跨换遁日：换遁那天与前一日同星，前后各再走一天方向相反。"""
    service = _service(tmp_path)
    for iso in (before, after):
        assert _hand_day_star(dt.date.fromisoformat(iso)) == star
        assert _nine_star_line(_text(service, "huangli", {"date": iso, "hour": 12})) == STAR_NAME[star], iso
    day_before = (dt.date.fromisoformat(before) - dt.timedelta(days=1)).isoformat()
    day_after = (dt.date.fromisoformat(after) + dt.timedelta(days=1)).isoformat()
    got = [_nine_star_line(_text(service, "huangli", {"date": iso, "hour": 12})) for iso in (day_before, day_after)]
    assert got[0] == got[1] != STAR_NAME[star]   # 一个往上走到这颗星、一个从这颗星往回走：两侧同星


@requires_node
def test_huanglizeri_nine_star_condition_judges_by_the_day_zibai(tmp_path: Path) -> None:
    """黄历择日「九星值日」条件（huangliZeriConditionTypes.nine_star）按新口径判：2020-07-01 是一白，不是 lunar 的六白。"""
    service = _service(tmp_path)

    def hits(value: str) -> str:
        text = _text(service, "huanglizeri", {
            "date": "2020-07-01", "time": "09:00:00", "zone": "+08:00", "lat": "26n05", "lon": "119e19", "pos": "福州",
            "startDate": "2020-06-29", "startTime": "00:00", "endDate": "2020-07-03", "endTime": "23:59",
            "conditions": {"kind": "group", "joiner": "all", "children": [
                {"kind": "leaf", "type": "nine_star", "params": {"values": [value]}},
            ]},
        })
        return text.split("[命中日段]\n", 1)[1]

    # 手算：06-29 三碧 → 06-30 二黑 → 07-01 一白 → 07-02 九紫 → 07-03 八白（阴遁逆行）；lunar 旧口径 07-01 是六白。
    assert [_hand_day_star(dt.date(2020, 6, 29) + dt.timedelta(days=i)) for i in range(5)] == [3, 2, 1, 9, 8]
    new, old = hits("一"), hits("六")
    assert new.startswith("1. 2020-07-01(1天)") and "实际 九星:一白水 ✓" in new and "\n2. " not in new, new
    assert old.strip() == "(尚未择吉或无命中)", old   # 旧口径那天的星，五天里零命中
