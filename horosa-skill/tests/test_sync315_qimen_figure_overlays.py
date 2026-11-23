"""上游 v3.15.0 奇门盘附加层画进报告盘图（app-charts/adapters/qimen.js，DunJiaBoard 的 SVG 重画）。

附加字（暗干 / 寄干 / 天禽 / 推演标记）的落位与字号由上游 qimenCellLayout 算（bundle 里跑原函数），十二建星外环由
dunjiaJianChuRingSlots / dunjiaRingFit 落位。真值按上游写在 qimenCellLayout 注释里的「上挂下注」规则与 DUNJIA_CELL 常量
（格 214、主字 34、留白档内缩 46 / 32、缺省 52 / 40）独立判，不抄 SVG 输出。
"""

from __future__ import annotations

import copy
import gzip
import json
import re
import shutil
from pathlib import Path

import pytest
from node_esm import run_node_esm

from horosa_skill.config import Settings
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.reports import app_charts

PKG_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads(gzip.open(PKG_ROOT / "tests" / "fixtures" / "app_charts_live.json.gz").read())
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="[host] node not on PATH")
CELL, GLYPH = 214, 34
TEXT_RE = re.compile(r'<text x="([\d.]+)" y="([\d.]+)" font-size="([\d.]+)"[^>]*text-anchor="(\w+)"[^>]*>([^<]*)</text>')


def _pan() -> dict:
    return copy.deepcopy(FIXTURE["qimen"]["pan"])


def _overlay_pan() -> dict:
    pan = _pan()
    by = {c["palaceNum"]: c for c in pan["cells"]}
    by[2].update(jiTianGan="戊", tianQin=True, anGan="丙")   # 离
    by[7].update(jiDiGan="己", tuiYanTags=["下1"])           # 艮
    by[4].update(tuiYanTags=["上1", "用"])                    # 震
    by[9].update(tuiYanTags=["空转3"])                        # 乾
    by[5].update(anGan="丁")                                   # 中五宫（暗干排入中宫的起法）
    return pan


def _ring(pan: dict) -> dict:
    out = run_node_esm(
        "const m = await import(process.argv[1]); process.stdout.write(JSON.stringify(m.jianChuRing(JSON.parse(process.argv[2]), process.argv[3])));",
        PKG_ROOT / "horosa-core-js" / "src" / "vendor" / "utils" / "jianChu.js", json.dumps(pan["ganzhi"]), pan["dateStr"],
    )
    return json.loads(out)


def _svg(pan: dict) -> str:
    client = HorosaJsEngineClient(Settings.from_env())
    client._candidate_engine_roots = lambda: [PKG_ROOT / "horosa-core-js"]  # type: ignore[method-assign]
    (res,) = client.render_app_charts([{"kind": "qimen", "data": {"pan": pan}, "options": {}}])
    assert res.get("ok"), res
    return res["svg"]


def _cells(svg: str) -> list[list[tuple[float, float, float, str, str]]]:
    """九宫格（宫序同 pan.cells）各自的字：(x, y, 字号, anchor, 字)，格内坐标。"""
    groups = re.findall(r'<g transform="translate\([\d.]+,[\d.]+\)">((?:(?!<g ).)*?)</g>', svg)
    cells = [g for g in groups if 'rx="14"' in g]
    assert len(cells) == 9, len(cells)
    return [[(float(x), float(y), float(s), a, t) for x, y, s, a, t in TEXT_RE.findall(body)] for body in cells]


def _center_x(item: tuple[float, float, float, str, str]) -> float:
    x, _y, size, anchor, value = item
    width = size * len(value)
    return x if anchor == "middle" else (x + width / 2 if anchor == "start" else x - width / 2)


def _find(cell: list, value: str, size: float | None = None) -> tuple:
    hits = [t for t in cell if t[4] == value and (size is None or abs(t[2] - size) < 1e-6)]
    assert len(hits) == 1, (value, cell)
    return hits[0]


@needs_node
def test_overlays_hang_above_and_below_their_main_glyph() -> None:
    pan = _overlay_pan()
    cells = _cells(_svg(pan))
    li = cells[[c["palaceNum"] for c in pan["cells"]].index(2)]
    door = _find(li, "景", GLYPH)
    # 暗干：门的正上方（以门中线为准、整块在门顶之上）；v3.15 前挂在天盘干右侧（x = 52 + 34 + 6）
    an = _find(li, "丙", 14)
    assert abs(_center_x(an) - _center_x(door)) < 0.01 and an[1] + an[2] / 2 <= door[1] - GLYPH / 2
    # 天盘寄干：天盘干正上方，前缀「寄」小一号（0.68em）；天禽：九星正下方
    tian = _find(li, "壬", GLYPH)
    ji, ji_gan = _find(li, "寄"), _find(li, "戊", 14)
    assert ji[2] < ji_gan[2] and ji_gan[1] + 7 <= tian[1] - GLYPH / 2
    assert abs((ji[0] + _center_x(ji_gan) + 7) / 2 - _center_x(tian)) < 1.5  # 「寄戊」整块以天盘干中线为中
    star = _find(li, "蓬", GLYPH)
    qin = _find(li, "天禽")
    assert abs(_center_x(qin) - _center_x(star)) < 0.01 and qin[1] - qin[2] / 2 >= star[1] + GLYPH / 2
    # 推演标记：门的正下方（震宫两枚，乾宫「空转3」写成「转3」）
    zhen = cells[[c["palaceNum"] for c in pan["cells"]].index(4)]
    shang, yong, door4 = _find(zhen, "上1"), _find(zhen, "用"), _find(zhen, "伤", GLYPH)
    assert min(shang[1], yong[1]) - shang[2] / 2 >= door4[1] + GLYPH / 2
    qian = cells[[c["palaceNum"] for c in pan["cells"]].index(9)]
    assert _find(qian, "转3") and not any(t[4] == "空转3" for t in qian)
    # 中宫暗干：两行大字下方「暗 丁」
    center = cells[[c["palaceNum"] for c in pan["cells"]].index(5)]
    wuhe = [t for t in center if t[4].startswith("五合")][0]
    assert _find(center, "暗")[1] > wuhe[1] and _find(center, "丁")[1] > wuhe[1]


@needs_node
def test_main_glyphs_move_to_the_roomy_insets_only_when_the_board_has_notes() -> None:
    plain = _cells(_svg(_pan()))
    noted = _cells(_svg(_overlay_pan()))
    # DUNJIA_CELL：缺省内缩 52 / 40、留白档 46 / 32（主字 34，天盘干以字框中线落位）
    assert (plain[0][0][0], plain[0][0][1]) == (52.0, 40 + GLYPH / 2)
    assert (noted[0][0][0], noted[0][0][1]) == (46.0, 32 + GLYPH / 2)


@needs_node
def test_jianchu_ring_surrounds_a_shrunk_board() -> None:
    pan = _pan()
    ring = _ring(pan)
    svg = _svg({**pan, "jianChu": ring})
    k = (CELL * 3 + 10 * 2) / (CELL * 3 + 10 * 2 + 2 * 40)   # dunjiaRingFit：边长 662，外环 margin 40
    m = re.search(r'<g transform="translate\(0,([\d.]+)\) scale\(([\d.]+)\)">', svg)
    assert m and abs(float(m.group(2)) - k) < 1e-9
    texts = [t for *_rest, t in TEXT_RE.findall(svg)]
    for zhi, j in ring["byZhi"].items():
        assert zhi in texts and j["name"] in texts, zhi
    # 日值那一支金底并标「日」（日柱辛酉 → 酉）
    assert ring["dayZhi"] == "酉" and texts.count("日") >= 1
    assert len(_cells(svg)) == 9


def test_plan_hands_the_ring_and_cell_notes_to_the_board() -> None:
    pan = {**_overlay_pan(), "jianChu": {"byZhi": {"子": {"name": "成"}}}}
    figures = [{"kind": "grid9", "title": "奇门"}]
    (_, request), = app_charts.plan("qimen", {"pan": pan}, figures)
    sent = request["data"]["pan"]
    assert sent["jianChu"] == pan["jianChu"]
    assert any(c.get("tuiYanTags") == ["上1", "用"] for c in sent["cells"]) and any(c.get("jiTianGan") == "戊" for c in sent["cells"])


@needs_node
def test_sanshi_board_draws_the_same_notes_and_the_branch_side_jianchu() -> None:
    """三式合一盘（SSR 跑上游 SanshiUnitedBoard 再转 SVG）：格内寄干（三式盘只写干、不带「寄」）与天禽「禽」、格旁空格的暗干 /
    推演标记、外圈地支旁的建星（showJianChu）——此前转换器不认这些新元素，整层丢掉。"""
    from horosa_skill.reports.figures import extract_figures

    data = copy.deepcopy(FIXTURE["sanshiunited"])
    by = {c["palaceNum"]: c for c in data["qimen"]["cells"]}
    by[2].update(jiTianGan="戊", tianQin=True, anGan="丙")
    by[4].update(tuiYanTags=["上1", "用"])
    data["qimen"]["options"] = {**(data["qimen"].get("options") or {}), "showJianChu": True}
    client = HorosaJsEngineClient(Settings.from_env())
    client._candidate_engine_roots = lambda: [PKG_ROOT / "horosa-core-js"]  # type: ignore[method-assign]
    figures = app_charts.attach_app_svgs(extract_figures("sanshiunited", data, "sanshiunited"), "sanshiunited", data, client)
    svg = next(f["app_svg"] for f in figures if f.get("app_kind") == "sanshi")
    texts = [t for *_rest, t in TEXT_RE.findall(svg)]
    assert {"禽", "暗", "丙", "上1", "用"} <= set(texts) and "寄" not in texts
    ring = _ring(data["qimen"])
    assert all(j["name"] in texts for j in ring["byZhi"].values())
    plain = copy.deepcopy(FIXTURE["sanshiunited"])
    plain_svg = next(f["app_svg"] for f in app_charts.attach_app_svgs(extract_figures("sanshiunited", plain, "sanshiunited"), "sanshiunited", plain, client)
                     if f.get("app_kind") == "sanshi")
    assert "禽" not in [t for *_r, t in TEXT_RE.findall(plain_svg)], "没开附加层的盘不多字"


@needs_node
@pytest.mark.parametrize("tool", ["jinkou", "suzhan"])
def test_plain_text_boards_drop_the_text_stroke_like_the_page(tool: str) -> None:
    """svg.horosa-plain-text-board（layouts/app/22-tail-fixes.less）：页面上这两张盘的字不描边、极细字重 100 还回 400；svg 根自带的
    stroke（宿占把线色挂在根上、宫格框靠继承）不动。金口诀 v3.15.0 起挂这个类（JinKouChart），宿占早就挂着——报告此前两张都照旧描边。"""
    from horosa_skill.reports.figures import extract_figures

    data = copy.deepcopy(FIXTURE[tool])
    client = HorosaJsEngineClient(Settings.from_env())
    client._candidate_engine_roots = lambda: [PKG_ROOT / "horosa-core-js"]  # type: ignore[method-assign]
    svg = next(f["app_svg"] for f in app_charts.attach_app_svgs(extract_figures(tool, data, tool), tool, data, client) if f.get("app_svg"))
    root = re.match(r"<svg\b[^>]*>", svg).group(0)
    assert "horosa-plain-text-board" in root
    texts = re.findall(r"<text\b[^>]*>", svg)
    assert texts and not [t for t in texts if re.search(r'\sstroke="(?!none")', t)]
    assert not [t for t in texts if 'font-weight="100"' in t]
    if tool == "suzhan":
        assert re.search(r'\sstroke="(?!none")[^"]+"', root), "宿占盘根上的线色要留着（宫格框靠它）"
