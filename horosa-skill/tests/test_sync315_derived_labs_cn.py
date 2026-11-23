"""上游 v3.15.0 同步 · 调波盘 / 龙盘 / 重置盘专属段的星、点、星座写中文（utils/derivedAstroLabs.js，vendored 逐字）。

skill 这三段是 Python 移植（service/text/western.py `_derived_*`）。这里把同一份输入交给 vendored 的上游函数与 Python 两边，
逐行比：所有行星 / 虚点 / 星座 id、表外 id 原样、缺星座 / 缺度数的边角。
负向对照：`_derived_cn` 改回原样返回 id → 红；`_derived_sign_pos` 去掉星座后的空格 → 红。
"""
from __future__ import annotations

import json
from pathlib import Path

from node_esm import run_node_esm
from skips import needs_upstream, upstream_source

from horosa_skill.service.text import western as W

CORE_JS = Path(__file__).resolve().parents[1] / "horosa-core-js"
IDS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "North Node", "South Node",
       "Dark Moon", "Purple Clouds", "Chiron", "Pholus", "Ceres", "Pallas", "Juno", "Vesta", "Asc", "MC", "Desc", "IC",
       "Pars Fortuna", "Syzygy", "Vertex", "NotAnId"]
SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]


def _rows() -> dict:
    positions = [{"id": pid, "natalLon": 11.875 + i, "sign": SIGNS[i % 12], "signlon": 16.905 + i / 7} for i, pid in enumerate(IDS)]
    positions += [{"id": "Sun", "natalLon": None, "sign": "", "signlon": 3.0}, {"id": "Moon", "natalLon": 1.0, "sign": "Leo", "signlon": None}]
    conjunctions = [{"a": IDS[i], "b": IDS[i + 1], "orb": 0.0125 * i} for i in range(len(IDS) - 1)] + [{"a": "Sun", "b": "Moon", "orb": None}]
    return {"harmonic": 7, "nodeLon": 123.456, "positions": positions, "conjunctions": conjunctions}


def _chart(angles: dict) -> dict:
    return {"chart": {"objects": [{"id": key, **value} for key, value in angles.items()]}}


def test_python_lines_equal_the_vendored_upstream_functions() -> None:
    res = _rows()
    natal = _chart({"Asc": {"sign": "Virgo", "signlon": 3.21}, "MC": {"sign": "Gemini", "signlon": 1.005}, "IC": {"sign": "", "signlon": None}})
    reloc = _chart({"Asc": {"sign": "Libra", "signlon": 9.5}, "MC": {"sign": "Cancer", "signlon": 2.0}, "Desc": {"sign": "Aries", "signlon": 9.5}})
    script = (
        "const m = await import(process.argv[1]); const [res, natal, reloc] = JSON.parse(process.argv[2]);"
        "process.stdout.write(JSON.stringify({ harmonic: m.harmonicSnapshotLines(res, 7), draconic: m.draconicSnapshotLines(res, 'whole', {}),"
        " reloc: m.relocationSnapshotSpecialty(natal, reloc, 40.7167, -74, {})[0].split('\\n') }));"
    )
    js = json.loads(run_node_esm(script, CORE_JS / "src" / "vendor" / "utils" / "derivedAstroLabs.js", json.dumps([res, natal, reloc])))
    body = W._derived_position_lines(res["positions"], "调波") + W._derived_conjunction_lines(res["conjunctions"])
    assert js["harmonic"][2:] == body
    assert js["draconic"][3:] == W._derived_position_lines(res["positions"], "龙盘") + W._derived_conjunction_lines(res["conjunctions"])
    angles = W._chart_angles(natal), W._chart_angles(reloc)
    py_reloc = [f"{W._derived_cn(a)}：本命 {W._angle_text(angles[0].get(a))} → 重置后 {W._angle_text(angles[1].get(a))}"
                for a in ("Asc", "MC", "Desc", "IC") if angles[0].get(a) or angles[1].get(a)]
    assert js["reloc"][2:] == py_reloc
    assert "日：本命黄经 11.88° → 调波 牡羊 16.91°" in body and "NotAnId：" in "\n".join(body), body[:3]


@needs_upstream("Horosa-Web/astrostudyui/src/constants/AstroConst.js")
def test_curated_astroconst_extracts_hold_the_upstream_values() -> None:
    """curated 子集逐值抽取：manifest `extracts` 里每个字符串常量与上游（门面 + 子模块全集）同值；DESC / IC 在册。"""
    import re

    manifest = json.loads((Path(__file__).resolve().parents[1] / "contracts" / "vendor_manifest.json").read_text(encoding="utf-8"))
    extracts = (manifest.get("files") or manifest)["constants/AstroConst.js"]["extracts"]
    assert {"DESC", "IC"} <= set(extracts)
    pattern = r"^export const {name} = (['\"][^'\"]*['\"])"
    vendored = (CORE_JS / "src" / "vendor" / "constants" / "AstroConst.js").read_text(encoding="utf-8")
    upstream = upstream_source("Horosa-Web/astrostudyui/src/constants/AstroConst.js")
    checked = 0
    for name in extracts:
        mine = re.search(pattern.format(name=name), vendored, re.MULTILINE)
        if mine is None:
            continue   # 数组 / 表达式常量（LIST_URANIAN）不在这条比
        theirs = re.search(pattern.format(name=name), upstream, re.MULTILINE)
        assert theirs and theirs.group(1) == mine.group(1), name
        checked += 1
    assert checked >= 20
