"""上游 v3.14.0 同步 · zeri 批：天星择日「得时」(hayyiz) 的半弧法改用当日真黄赤交角（结果会变）。

上游 astropy/astrostudy/election_scan_ext.py `_above_horizon_semiarc`：天顶赤经从 `flatlib.utils.eqCoords(m.mc(), 0)`
（写死 23.44° 的黄→赤换算）改成 `eclipticToEquatorial(m.mc(), 0.0, m.obliquity())`（本刻真黄赤交角，结果即 ARMC，与主盘四轴同一个出口）。
改的是后端，skill 只发请求——这条 live 金标钉的是「skill 拿到的命中区间端点按新口径」，不是 skill 自己的算术。

为什么选公元 1000 年：现代的真黄赤交角（约 23.436°）与 23.44° 只差千分之几度，端点只挪零点几秒，分钟 / 秒级输出看不出来；
公元 1000 年真交角 23.571°，同一个星落时刻两种口径差 5 秒，秒级输出逐字不同。

期望值的独立来源 = 主盘 /chart（perchart，另一条代码路径）在端点前后一秒给的火星赤经赤纬、天顶赤经、巨蟹 0° 的赤纬（= 真黄赤交角），
按半弧法公式手算：|天顶赤经 − 星赤经| ≤ 90° + asin(tan δ · tan φ) + 0.0003°（flatlib.utils.isAboveHorizon 的容差）。

负向对照（实跑过，见批次备忘）：共享引擎不许改，所以用 vendored 解释器把 vendored election_scan 在进程内跑两遍——
原样（真交角）端点 1000-06-02 00:06:29；把 `_above_horizon_semiarc` 换回 v3.13.2 的写法（eqCoords 写死 23.44°）端点 00:06:24。
后者喂给本条第一条断言即红。本文件里再用同一批 /chart 数值把旧公式的端点算出来（落在 00:06:24 与 00:06:25 之间），两头对上。
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from test_local_js_tools import make_service, requires_chart

# 长安（34°16′N 108°56′E），公元 1000 年 6 月（儒略历）。火星在狮子座（阳性座），夜间在地平上 = 得时（Hayyiz）。
PLACE = {"zone": "+08:00", "lat": "34n16", "lon": "108e56", "hsys": 0, "agent_confirmed_settings": True}
SEMI_ARC_TOLERANCE = 0.0003  # flatlib.utils.isAboveHorizon：dist <= dArc/2 + 0.0003（1 角秒）
OLD_FIXED_OBLIQUITY = 23.44  # flatlib.const.ECLI2EQ_OBLIQUITY 的绝对值（v3.13.2 的 eqCoords 用它）


def _ra_of_ecliptic_point(lon: float, obliquity: float) -> float:
    """黄道上一点（黄纬 0）的赤经：tan α = tan λ · cos ε。"""
    lam, eps = math.radians(lon), math.radians(obliquity)
    return math.degrees(math.atan2(math.sin(lam) * math.cos(eps), math.cos(lam))) % 360.0


def _semi_arc_excess(mars: dict[str, Any], mc_ra: float, latitude: float) -> float:
    """|时角| − 昼半弧：≤ 容差 = 在地平上。"""
    half_arc = 90.0 + math.degrees(math.asin(math.tan(math.radians(mars["decl"])) * math.tan(math.radians(latitude))))
    hour_angle = abs((mars["ra"] - mc_ra + 180.0) % 360.0 - 180.0)
    return hour_angle - half_arc


@requires_chart
def test_live_tianxing_hayyiz_boundary_uses_the_true_obliquity(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    env = service.run_tool(
        "tianxing",
        {**PLACE, "date": "1000-06-01", "time": "12:00:00", "pos": "长安", "precision": "second", "zeriSnapshotExplainRows": 0,
         "startDate": "1000-06-01", "startTime": "12:00", "endDate": "1000-06-02", "endTime": "12:00",
         "conditions": {"kind": "group", "joiner": "all", "children": [
             {"type": "sect_joy", "params": {"item": "hayyiz", "planet": "Mars", "hayyizLevels": ["Hayyiz", "DemiHayyiz"]}}]}},
        save_result=False,
    )
    assert env.ok, env.error
    # 一夜一段：日落起（19:47:18，昼夜换边）到火星落（半弧法地平）止。
    assert [(row["start"], row["end"]) for row in env.data["intervals"]] == [("1000-06-01 19:47:18", "1000-06-02 00:06:29")]

    def at(clock: str) -> tuple[dict[str, Any], dict[str, Any], float, float]:
        chart_env = service.run_tool("chart", {**PLACE, "date": "1000-06-02", "time": clock}, save_result=False)
        assert chart_env.ok, chart_env.error
        chart = chart_env.data["chart"]
        objects = {obj["id"]: obj for obj in chart["objects"]}
        obliquity = next(house["decl"] for house in chart["houses"] if abs(house["lon"] - 90.0) < 1e-9)  # 巨蟹 0° 的赤纬 = 真黄赤交角
        return objects["Mars"], objects["MC"], obliquity, float(chart_env.input_normalized["gpsLat"])

    # 新口径：端点落在 00:06:29 与 00:06:30 之间——主盘自己的得时判定在同一秒翻面，半弧公式手算也在这一秒过线。
    mars_in, mc_in, eps, lat = at("00:06:29")
    mars_out, mc_out, _, _ = at("00:06:30")
    assert 23.56 < eps < 23.58, "公元 1000 年的真黄赤交角（Laskar 平交角 23.569° ± 章动）"
    assert (mars_in["hayyiz"], mars_out["hayyiz"]) == ("Hayyiz", "None")
    assert abs(_ra_of_ecliptic_point(mc_in["lon"], eps) - mc_in["ra"]) < 1e-6, "主盘天顶赤经 = 真交角下的 ARMC"
    assert _semi_arc_excess(mars_in, mc_in["ra"], lat) <= SEMI_ARC_TOLERANCE < _semi_arc_excess(mars_out, mc_out["ra"], lat)

    # 旧口径（写死 23.44°）：同一批数值下，00:06:29 那一秒已经判成地平下，端点落在 00:06:24 与 00:06:25 之间——早 5 秒。
    # 这是判别力的证明：引擎若退回旧公式，上面的区间端点断言会读到 00:06:24。
    def old_excess(mars: dict[str, Any], mc: dict[str, Any]) -> float:
        return _semi_arc_excess(mars, _ra_of_ecliptic_point(mc["lon"], OLD_FIXED_OBLIQUITY), lat)

    assert old_excess(mars_in, mc_in) > SEMI_ARC_TOLERANCE
    mars_24, mc_24, _, _ = at("00:06:24")
    mars_25, mc_25, _, _ = at("00:06:25")
    assert old_excess(mars_24, mc_24) <= SEMI_ARC_TOLERANCE < old_excess(mars_25, mc_25)
