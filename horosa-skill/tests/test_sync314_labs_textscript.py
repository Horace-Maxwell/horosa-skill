"""上游 v3.14.0 辅盘「变换盘」「黄道制」：繁体输出的残差（AGENTS §4.5 第 4 条：新技法用真实输出跑一遍）。

被转的是真引擎排出的正文行（实抓后端结果 → vendored transformSnapshotLines / zodiacSnapshotLines），外加后端 88 星座
中文名全表里会进正文的那几个。期望值：上游 utils/__tests__/transformCharts.test.js「简繁 · 后发座取皇后之发」
（toHant('后发座') === '后髮座'、'然后发送' 不含 后髮）与台湾通行写法（座標 / 摺疊 / 穀神星）。
"""
from __future__ import annotations

import json
from pathlib import Path

from test_sync314_labs_goldens import KEYS, transform_outputs, zodiac_outputs

from horosa_skill import textscript

_RULES = Path(textscript.__file__).parent / "data" / "horosa_char_rules.json"


def _hant(text: str) -> str:
    return textscript.convert(text, "zh-Hant")


def test_section_lines_keep_their_technical_terms_in_traditional() -> None:
    lines = [line for key in KEYS for line in transform_outputs()[key]["lines"]] + zodiac_outputs()["z13a"]["lines"]
    converted = {line: _hant(line) for line in dict.fromkeys(lines)}
    joined = "\n".join(converted.values())
    # 术数 / 天文用字没被转成普通义。
    for wrong in ("黃道製", "幹", "醜", "衝", "佔", "歷", "鬥", "兇", "裏", "迴歸", "週"):
        assert wrong not in joined, wrong
    assert _hant("黄道版本:十三星座 · 甲本(黄经不变,只换分段)") == "黃道版本:十三星座 · 甲本(黃經不變,只換分段)"
    assert converted["基准星:月亮"] == "基準星:月亮"
    assert any(text.startswith("變換:赤緯摺疊。") for text in converted.values())
    assert any(text.startswith("穀神星:本命黃經 ") for text in converted.values())
    assert any(text.startswith("紫氣-木餘:本命黃經 ") for text in converted.values())
    assert _hant("坐标类比") == "座標類比" and _hant("变换盘") == "變換盤" and _hant("黄道制") == "黃道制"
    # 缺省简体：逐字节不变（转换器根本不跑）。
    assert all(textscript.convert(line, "zh-Hans") == line for line in converted)


def test_coma_berenices_keeps_the_queen_and_her_hair() -> None:
    """后发座（Com）：皇后之发 → 后髮座；「然后发送」这类普通话不受影响（上游 transformCharts.test.js「简繁」）。"""
    assert _hant("星座 后发座(黄道外)") == "星座 后髮座(黃道外)"
    assert _hant("金星 下次换星座:1990-06-02 02:06:56 入后发座") == "金星 下次換星座:1990-06-02 02:06:56 入后髮座"
    assert "后髮" not in _hant("然后发送") and _hant("星座 仙后(黄道外)") == "星座 仙后(黃道外)"
    # 实抓：冥王星 1974-07-12 自后发座换入（西雅图盘「上次换星座」行）。这一行的「自后」会被词典先切成「自後」——
    # 要靠逐位定字表里的「后发座」词条把两个字钉回来。上游 v3.14.0 才给 hantRules.js 加这一条，本仓的那张表由 cn_b 批并入；
    # 并入之前这一行转错（已记在备忘「移交」），并入之后必须转对。两种状态各有断言，谁也不是空过。
    line = next(line for line in zodiac_outputs()["z13a"]["lines"] if line.startswith("冥王星 上次换星座:"))
    assert line == "冥王星 上次换星座:1974-07-12 17:03:59 自后发座"
    rules = json.loads(_RULES.read_text(encoding="utf-8"))["rules"]
    merged = "后发座" in rules["后"]["words"] and "后发座" in rules["发"]["words"]
    assert _hant(line) == ("冥王星 上次換星座:1974-07-12 17:03:59 自后髮座" if merged else "冥王星 上次換星座:1974-07-12 17:03:59 自後發座")
