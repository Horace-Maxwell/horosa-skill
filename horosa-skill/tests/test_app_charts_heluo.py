"""河洛理数的 app 信息板（HeLuoMain.renderCenter，HTML）→ 报告盘图。

河洛的正文（[起命] / 爻辞 / [命运篇] / 大限 / 流年 / [断验]）里没有 app 中栏盘上的大半内容：起卦详情（简断、数理、数名、气运、
值月消息卦、元气化工、先后天变化、五命、元堂爻位、命格、十吉、卦气旺衰、命局对体）、先后天卦的卦画 + 纳甲六亲世应 + 元堂、
卦辞吉凶 / 卦旨 / 互覆卦 / 理数标签、易经爻辞与推命、大限每段的吉凶——所以这块板值得进报告（其余神数的板只是正文的卡片排版，
不加，见 AGENTS §9.3.1）。

板上的值只取引擎结果：core-js 的 tools/heluo.js 算正文时那一份 chart / dayun / judge / solarTerm 已在结果里，app 中栏另要的
`nayin`（年柱纳音）与 `extras`（chartExtras）由同一次调用放进 `board_context`，adapter 不另算。
"""
from __future__ import annotations

import copy
import gzip
import json
import shutil

import pytest
from test_app_charts import PKG_ROOT, _Client

from horosa_skill.reports import app_charts
from horosa_skill.reports.figures import extract_figures, is_drawn

BOARDS = json.loads(gzip.decompress((PKG_ROOT / "tests" / "fixtures" / "app_charts_boards_live.json.gz").read_bytes()))
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="[host] node not on PATH")
PARTS = ["河洛起卦详情", "先天卦", "后天卦", "河洛大限"]


def _figures(data: dict) -> list[dict]:
    return app_charts.attach_app_svgs(extract_figures("heluo", data, "heluo"), "heluo", data, _Client())


def test_heluo_has_four_app_only_boards_and_no_builtin_drawing() -> None:
    figures = extract_figures("heluo", BOARDS["heluo"], "heluo")
    assert [f["title"] for f in figures] == PARTS
    assert all(f["kind"] == "app" and f["app_kind"] == "heluo" and not is_drawn(f) for f in figures)
    assert [f["app_options"]["part"] for f in figures] == ["detail", "xian", "hou", "daxian"]


def test_heluo_board_needs_the_engine_board_context() -> None:
    """旧 runtime 的 heluo 结果没有 board_context：不画（adapter 不自己补算纳音 / chartExtras）。"""
    data = copy.deepcopy(BOARDS["heluo"])
    del data["heluo"]["board_context"]
    assert extract_figures("heluo", data, "heluo") == []


@needs_node
def test_heluo_boards_are_drawn_by_the_app_from_the_engine_result() -> None:
    data = BOARDS["heluo"]
    figures = _figures(data)
    assert [f["title"] for f in figures] == PARTS and all(f["renderer"] == "app" for f in figures)
    detail, xian, hou, daxian = (f["app_svg"] for f in figures)
    ctx = data["heluo"]["board_context"]
    chart = data["heluo"]["chart"]
    assert ctx["extras"]["jianDuan"] in detail and ctx["nayin"] in detail, "起卦详情 rows come from board_context"
    assert f'{chart["xian"]["name"]} → {chart["hou"]["name"]}' in detail
    assert chart["xian"]["name"] in xian and "元堂" in xian and chart["hou"]["name"] in hou
    assert all(seg["gua"] in daxian for seg in data["heluo"]["dayun"]["all"])
    for svg in (detail, xian, hou, daxian):
        assert svg.startswith("<svg") and "var(" not in svg
        # 纸面上无意义的交互件：经文展开钮、下钻箭头、「点行看爻辞」提示
        assert "经文（卦义" not in svg and "▾" not in svg and "点行" not in svg


@needs_node
def test_heluo_board_prints_the_results_values_not_recomputed_ones() -> None:
    """负向对照的正面：改结果里的 extras / nayin，板跟着变——证明 adapter 用的是结果里那一份，没有自己再算。"""
    data = copy.deepcopy(BOARDS["heluo"])
    data["heluo"]["board_context"]["extras"]["jianDuan"] = "（测试：简断取自结果）"
    data["heluo"]["board_context"]["nayin"] = "测试纳音"
    detail = _figures(data)[0]["app_svg"]
    assert "（测试：简断取自结果）" in detail and "测试纳音" in detail


def test_core_js_heluo_returns_the_board_context_the_app_board_reads() -> None:
    """app 中栏的 getModel 另算 nayin（年柱纳音）与 chartExtras；core-js 同一次调用把这两样放进 board_context。"""
    from node_esm import run_node_esm

    if not shutil.which("node"):
        pytest.skip("[host] node not on PATH")
    tools = PKG_ROOT / "horosa-core-js" / "src" / "tools"
    script = (
        "const h = await import(process.argv[1]);"
        "const r = h.runHeluo({ date: '1990-01-01', time: '12:00:00', zone: '+08:00', lon: '121e28', gender: 1 });"
        "process.stdout.write(JSON.stringify(r.data));"
    )
    data = json.loads(run_node_esm(script, tools / "heluo.js", cwd=PKG_ROOT / "horosa-core-js"))
    ctx = data["board_context"]
    assert ctx["nayin"] and ctx["nayin"][-1] in "金木水火土"
    assert ctx["extras"]["jianDuan"] and ctx["extras"]["shuLi"]["tian"] and ctx["extras"]["season"] == "冬"
