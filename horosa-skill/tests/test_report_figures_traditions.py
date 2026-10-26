"""完整排盘报告的盘图（第二批）：太乙十六宫 / 七政四余十二宫 / 七政择日动盘 / 南印方盘 / 量化盘 90° 度盘 / 合盘双圈 / 择时盘。

两条规矩贯穿：位置只从引擎结果里取（铁律 1）；引擎正文里有同一份位置表时逐项对照，对不上整张不画（图文不打架）。
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from horosa_skill.reports import figures, renderers

SIGNS = ("Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces")


def _sections(**bodies: str) -> dict:
    return {"export_snapshot": {"sections": [{"title": title, "body": body} for title, body in bodies.items()]}}


# ── 太乙 ────────────────────────────────────────────────────────────────

def _taiyi_pan() -> dict:
    items = {name: [] for name in figures.TAIYI_RING}
    items.update({"坤": ["太乙", "天乙", "主大"], "午": ["四神", "客大", "定参", "太尊"], "亥": ["文昌"]})
    return {"palace16": [{"palace": name, "items": items[name]} for name in ("子", *[n for n in figures.TAIYI_RING if n != "子"])],
            "kook": {"text": "陽遁四十二局", "year": "理人"}, "methodLabel": "太乙統宗", "taiyiNum": 7,
            "homeCal": 27, "awayCal": 12, "setCal": 34}


def _taiyi_text(pan: dict) -> str:
    return "\n".join(f"{row['palace']}：{'、'.join(row['items']) or '—'}" for row in pan["palace16"]) + "\n中：—"


def test_taiyi_ring_follows_the_upstream_board_and_the_engine_palace_marks() -> None:
    pan = _taiyi_pan()
    taiyi, = figures.extract_figures("taiyi", {"pan": pan, **_sections(十六宫标记=_taiyi_text(pan))})
    assert taiyi["kind"] == "taiyi" and [p["branch"] for p in taiyi["palaces"]] == list(figures.TAIYI_RING)  # 午起顺时针
    kun = next(p for p in taiyi["palaces"] if p["branch"] == "坤")
    assert kun["lines"] == ["太乙", "天乙", "主大"] and kun["emphasis"] == "main"
    assert len(next(p for p in taiyi["palaces"] if p["branch"] == "午")["lines"]) == 4  # 上游截到 3 个；正文全列，图也全画
    assert "主算 27　客算 12　定算 34" in taiyi["lines"] and "陽遁四十二局（理人）" in taiyi["text"]
    # 三式合一把太乙放在 data.taiyi，正文段名是「太乙十六宫」。
    assert figures.extract_figures("sanshiunited", {"taiyi": pan, **_sections(太乙十六宫=_taiyi_text(pan))})[-1]["kind"] == "taiyi"


def test_taiyi_is_not_drawn_when_it_disagrees_with_the_text_or_misses_a_palace() -> None:
    pan = _taiyi_pan()
    wrong = _taiyi_text(pan).replace("亥：文昌", "亥：—")
    assert figures.extract_figures("taiyi", {"pan": pan, **_sections(十六宫标记=wrong)}) == []
    pan["palace16"] = pan["palace16"][:15]
    assert figures.extract_figures("taiyi", {"pan": pan}) == []


# ── 七政四余 ────────────────────────────────────────────────────────────

def _guolao_chart(node_swap: bool = False) -> dict:
    houses = [{"id": f"House{(i - 2) % 12 + 1}", "lon": i * 30.0, "sign": sign} for i, sign in enumerate(SIGNS)]  # 双子 = 第 1 宫
    stars = {"Sun": ("Aries", "壁", 1), "Moon": ("Leo", "星", 1), "Mercury": ("Aries", "壁", 1), "Venus": ("Gemini", "昴", 1),
             "Mars": ("Aries", "壁", 1), "Jupiter": ("Virgo", "张", -1), "Saturn": ("Aries", "奎", 1),
             "North Node": ("Capricorn", "斗", -1), "South Node": ("Cancer", "井", -1), "Asc": ("Gemini", "参", 0)}
    if node_swap:
        stars["North Node"], stars["South Node"] = stars["South Node"], stars["North Node"]
    objects = [{"id": k, "sign": s, "su28": su, "lonspeed": sp, "lon": 0} for k, (s, su, sp) in stars.items()]
    return {"houses": houses, "objects": objects, "zodiacal": "Tropical"}


_MIAOWANG = "| 曜 | 地支 | 所属 | 速度态 |\n| --- | --- | --- | --- |\n| 日 | 戌 | 旺 | 顺 |\n| 计 | 未 | - | 逆 |\n| 罗 | 丑 | - | 逆 |"


def test_guolao_square_places_stars_by_engine_sign_with_mansion_and_house() -> None:
    data = {"chart": _guolao_chart(), **_sections(**{"星曜庙旺与星点动态（殿垣庙旺乐喜怒 · 顺逆留伏迟速）": _MIAOWANG})}
    square, = figures.extract_figures("guolao_chart", data, "七政四余")
    cells = {c["branch"]: c for c in square["cells"]}
    assert cells["戌"]["lines"] == ["日·壁　水·壁　火·壁　土·奎"] and cells["戌"]["label"] == "白羊 · 第11宫"
    assert cells["未"]["lines"] == ["计·井(逆)"] and cells["丑"]["lines"] == ["罗·斗(逆)"]
    assert cells["申"]["emphasis"] == "main" and "升·参" in cells["申"]["lines"][0]
    assert figures.extract_figures("guolao_chart", {"chart": _guolao_chart()})  # 没有庙旺表时照画（无从对照）


def test_guolao_square_is_dropped_when_the_luoji_naming_disagrees_with_the_text() -> None:
    # 盘上罗计落宫与正文庙旺表相反（例如罗计命名没换位）：图会把罗画到计的宫，宁可不画。
    data = {"chart": _guolao_chart(node_swap=True), **_sections(星曜庙旺=_MIAOWANG)}
    assert figures.extract_figures("guolao_chart", data) == []


def test_qizheng_election_grid_matches_the_dynamic_pan_lines() -> None:
    planets = [{"label": "日", "lonTropical": 16.78, "retrograde": False}, {"label": "罗", "lonTropical": 298.4, "retrograde": True}]
    pan = {"planets": planets, "housesBySystem": {}, "lifeDeg": 15.1}
    text = _sections(择日动盘="山位口径：二十四山\n日：16戌47 | 06辰山12+\n罗：28丑25 | 03坤山36+", 天象要素="命度：15戌07（日出起）")
    grid, = figures.extract_figures("qizhengelection", {"pan": pan, **text})
    cells = {c["branch"]: c for c in grid["cells"]}
    assert cells["戌"]["lines"] == ["日 16°"] and cells["丑"]["lines"] == ["罗 28°(逆)"]
    assert cells["戌"]["emphasis"] == "main" and grid["center"]["lines"] == ["命度：15戌07（日出起）"]
    moved = _sections(择日动盘="日：16酉47 | x\n罗：28丑25 | x")  # 正文说日在酉：对不上
    assert figures.extract_figures("qizhengelection", {"pan": pan, **moved}) == []


# ── 印度 ────────────────────────────────────────────────────────────────

def _india_chart() -> dict:
    houses = [{"id": f"House{(i - 2) % 12 + 1}", "sign": sign} for i, sign in enumerate(SIGNS)]
    bodies = ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "North Node", "South Node")
    objects = [{"id": b, "sign": SIGNS[(i * 5) % 12], "signlon": 3.7 + i, "lonspeed": -0.05 if "Node" in b else 1}
               for i, b in enumerate(bodies)]
    objects.append({"id": "Asc", "sign": "Gemini", "signlon": 0.9})
    return {"houses": houses, "objects": objects}


def test_india_south_chart_has_fixed_sign_cells_and_marks_the_lagna() -> None:
    data = {"chart": _india_chart(), "params": {"varga": {"label": "D1 Rashi"}, "ayanamsaLabel": "Lahiri"}}
    square, = figures.extract_figures("india_chart", data, "印度律盘")
    assert square["layout"] == "india_south" and square["title"] == "南印方盘 · D1 Rashi"
    cells = {c["branch"]: c for c in square["cells"]}
    assert figures.grid_position(square, cells["Pisces"]) == (0, 0) and figures.grid_position(square, cells["Virgo"]) == (3, 3)
    assert cells["Gemini"]["emphasis"] == "main" and cells["Gemini"]["label"] == "第一宫"
    assert cells["Aries"]["lines"] == ["日 3°"] and cells["Pisces"]["lines"] == ["北交 10°R"]
    chart = _india_chart()
    chart["objects"] = [o for o in chart["objects"] if o["id"] != "Saturn"]
    assert figures.extract_figures("india_chart", {"chart": chart}) == []  # 九曜缺一不画


# ── 量化盘 90° ──────────────────────────────────────────────────────────

def _germany() -> dict:
    ids = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "North Node", "Asc", "MC")
    objects = [{"id": b, "lon": 16.78 + i * 37} for i, b in enumerate(ids)] + [{"id": "Chiron", "lon": 3.0}]
    houses = [{"id": f"House{i}", "lon": i * 30.0} for i in range(1, 13)]
    return {"chart": {"houses": houses, "objects": objects}, "raw": {"tnp": [{"id": "Cupido", "lon": 283.91}]}}


def test_germany_adds_a_90_degree_dial_whose_factors_equal_the_text() -> None:
    data = _germany()
    folds = sorted(round(o["lon"] % 90, 2) for o in data["chart"]["objects"] if o["id"] != "Chiron") + [round(283.91 % 90, 2)]
    text = "\n".join(f"P{i} = {v:.2f}°" for i, v in enumerate(sorted(folds)))
    kinds = [f["kind"] for f in figures.extract_figures("germany", {**data, **_sections(**{"90°中点盘": text})}, "量化盘")]
    assert kinds == ["wheel", "dial90"]
    dial = figures.extract_figures("germany", data, "量化盘")[-1]
    assert "Chiron" not in {p["id"] for p in dial["points"]} and {"Cupido", "Asc"} <= {p["id"] for p in dial["points"]}
    off = text.replace(f"{min(folds):.2f}", f"{min(folds) + 1:.2f}")
    assert [f["kind"] for f in figures.extract_figures("germany", {**data, **_sections(**{"90°中点盘": off})})] == ["wheel"]


# ── 择时盘 ──────────────────────────────────────────────────────────────

def test_election_results_draw_the_chosen_moment_from_data_base() -> None:
    pan = _taiyi_pan()
    taiyi, = figures.extract_figures("taiyizeri", {"pan_moment": "2028-04-01 00:03:00", "pan": pan, "base": {"pan": pan}})
    assert taiyi["title"] == "太乙十六宫盘（择时盘 2028-04-01 00:03:00）"
    data = {"pan_moment": "2028-04-01 05:48", "base": {"chart": _guolao_chart()}}
    assert figures.extract_figures("qizhengzeri", data)[0]["title"].startswith("七政四余十二宫（择时盘")
    assert figures.extract_figures("indiazeri", {"pan_moment": "2028-04-06 05:38", "base": None}) == []  # 结果里没有盘


# ── 渲染：PDF 与 DOCX 都画得出来 ─────────────────────────────────────────

def _all_new_figures() -> list[dict]:
    pan = _taiyi_pan()
    out = figures.extract_figures("taiyi", {"pan": pan})
    out += figures.extract_figures("guolao_chart", {"chart": _guolao_chart()})
    out += figures.extract_figures("india_chart", {"chart": _india_chart()})
    out += figures.extract_figures("germany", _germany())
    out += figures.extract_figures("relative", {"inner": {"chart": _germany()["chart"]}, "outer": {"chart": _germany()["chart"]}})
    return out


def test_new_figures_render_in_pdf_and_docx(tmp_path: Path) -> None:
    from reportlab.graphics.shapes import Circle, Line, Rect, String, Wedge
    from reportlab.lib import colors

    found = _all_new_figures()
    assert [f["kind"] for f in found] == ["taiyi", "grid12", "grid12", "wheel", "dial90", "wheel"]
    for figure in (f for f in found if f["kind"] in figures.DRAWN_KINDS):
        drawing = figures.figure_drawing(figure, 380, "Helvetica", "Helvetica", colors)
        # DOCX 位图后端只认这五种图元：画了别的就会在 Word 里静默缺块。
        assert drawing.contents and all(isinstance(s, (Wedge, Circle, Line, Rect, String)) for s in drawing.contents)
    sections = [{"id": "a", "title": "起盘信息", "body": "日期：2028-04-06", "human_visible": True, "group": "chart"}]
    for fmt in ("pdf", "docx"):
        renderers.render_report({"title": "盘图", "style": "chart", "figures": found, "sections": sections},
                                output_path=tmp_path / f"r.{fmt}", format_name=fmt)
    with zipfile.ZipFile(tmp_path / "r.docx") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
        media = [n for n in archive.namelist() if n.startswith("word/media/")]
    assert "南印方盘" in xml and "白羊 · 第11宫" in xml  # 方盘画成 Word 表格
    if renderers._drawing_font_files(renderers.SIMPLIFIED) is None:
        pytest.skip("本机没有可供 Pillow 使用的 TTF 中文字体（CID 回退）")
    assert len(media) == 4  # 太乙 / 量化盘星盘 / 90° 度盘 / 合盘双圈


def test_bi_wheel_axis_lines_stay_out_of_the_partner_ring() -> None:
    from reportlab.graphics.shapes import Line
    from reportlab.lib import colors

    wheel = _all_new_figures()[-1]
    size = 400
    drawing = figures.wheel_drawing(wheel, size, "Helvetica", "Helvetica", colors)
    r_frame = size / 2 - 16
    teal = colors.HexColor("#0f766e")
    for line in (s for s in drawing.contents if isinstance(s, Line) and s.strokeColor == teal):
        radii = [((x - size / 2) ** 2 + (y - size / 2) ** 2) ** 0.5 for x, y in ((line.x1, line.y1), (line.x2, line.y2))]
        inside, outside = min(radii), max(radii)
        assert outside <= r_frame * 0.8 + 0.01 or inside >= r_frame - 0.01  # 不跨过乙方行星圈
