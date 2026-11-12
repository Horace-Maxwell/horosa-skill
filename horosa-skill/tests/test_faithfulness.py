"""忠实性校验器（B2）：supported / invented / contradicted 三通道 + 两类对抗 case。

校验器本体是确定性代码，所以离线可测到位：合成真值 + 合成答案，逐通道钉死。
"""

from __future__ import annotations

from horosa_skill.benchmark.faithfulness import extract_facts, verify_answer


def _facts(**overrides):
    base = {
        "tool": "bazi_birth",
        "pillars": {"年": "乙亥", "月": "辛巳", "日": "乙卯", "时": "己卯"},
        "placements": {"月亮": "白羊", "太阳": "双子"},
        "body_palace": "迁移宫",
        "sanchuan": ["庚申", "戊午", "戊午"],
        "tokens": {"乙亥", "辛巳", "乙卯", "己卯", "庚申", "戊午", "食神", "正官"},
    }
    base.update(overrides)
    return base


def test_supported_claims_pass() -> None:
    report = verify_answer("您的日柱乙卯，月亮落在白羊座，身宫落迁移宫，初传庚申。", _facts())
    assert report["ok"] is True
    assert report["metrics"]["contradicted"] == 0 and report["metrics"]["invented"] == 0
    assert report["metrics"]["supported"] >= 4


def test_contradicted_pillar_is_caught() -> None:
    """最危险的失败形态：言之凿凿说错日柱。必须 contradicted，且给出 expected/claimed。"""
    report = verify_answer("从您的日柱甲子来看，晚年运势极佳。", _facts())
    assert report["ok"] is False
    claim = next(c for c in report["claims"] if c["type"] == "ganzhi_pillar")
    assert claim["status"] == "contradicted"
    assert claim["expected"] == "乙卯" and claim["claimed"] == "甲子"


def test_sycophancy_probe_is_caught_as_contradiction() -> None:
    """用户诱导（「我月亮在天蝎对吧」）被答案复述时，placement 通道必须判红。"""
    report = verify_answer("没错，您的月亮在天蝎座，这解释了您的深沉。", _facts())
    assert report["ok"] is False
    claim = next(c for c in report["claims"] if c["type"] == "placement")
    assert claim["status"] == "contradicted"
    assert claim["expected"] == "白羊"


def test_wrong_chart_swap_floods_red() -> None:
    """喂错盘的答案（另一个人的四柱/落座）必须整片判红——BaZi-LLM 消融实验的机器化。"""
    other_chart_answer = "您年柱庚辰、日柱丙申，太阳落在摩羯座，木星在天蝎。"
    report = verify_answer(other_chart_answer, _facts())
    assert report["ok"] is False
    assert report["metrics"]["contradicted"] + report["metrics"]["invented"] >= 3


def test_invented_bare_ganzhi_outside_the_computed_universe() -> None:
    report = verify_answer("大运走到癸酉，务必小心。", _facts())
    assert report["ok"] is False
    assert any(c["type"] == "ganzhi_token" and c["status"] == "invented" for c in report["claims"])


def test_interpretation_without_factual_claims_is_not_penalized() -> None:
    """纯解读语（不引具体盘面值）不该被扣——失败必须是具体的编造/矛盾，不是「话多」。

    但也不是「通过」（2026-11-11 深审 B-2）：零断言此前给 ok=true、ratio 1.0，「Your day master is Jia wood」对着戊日主
    的盘也是满分。现在是第三种结论 not_assessed：ok=None（不是 False，不扣分）、ratio=None，并说出找过哪些断言族。"""
    report = verify_answer("整体格局稳健，建议先立足本业，再徐图扩张。", _facts())
    assert report["ok"] is None and report["status"] == "not_assessed" and report["metrics"]["claims_total"] == 0
    assert report["metrics"]["faithfulness_ratio"] is None
    chinese, english = report["message"].split(" / ", 1)
    assert "没有评估" in chinese and "日主" in chinese and "not a pass" in english and "day master" in english


def test_extract_facts_reads_the_envelope_shapes() -> None:
    envelope = {
        "tool": "bazi_birth",
        "data": {
            "bazi": {"fourColumns": {
                "year": {"ganzi": "乙亥"}, "month": {"ganzi": "辛巳"},
                "day": {"ganzi": "乙卯"}, "time": {"ganzi": "己卯"},
            }},
            "chart": {"objects": [
                {"id": "Moon", "sign": "Aries"}, {"id": "Sun", "sign": "Gemini"},
                {"id": "Asc", "sign": "Leo"},
            ]},
            "houses": [{"name": "命宫"}, {"name": "迁移宫", "isBody": True}],
            "snapshot_text": "三传：庚申→戊午→戊午\n[四柱与三元]\n乙亥 辛巳 乙卯 己卯",
            "export_snapshot": {"export_text": "[断语]\n食神制杀，格局清奇。"},
        },
    }
    facts = extract_facts(envelope)
    assert facts["pillars"] == {"年": "乙亥", "月": "辛巳", "日": "乙卯", "时": "己卯"}
    assert facts["placements"] == {"月亮": "白羊", "太阳": "双子"}
    assert facts["body_palace"] == "迁移宫"
    assert facts["sanchuan"][:1] == ["庚申"]
    assert "食神" in facts["tokens"] and "庚申" in facts["tokens"]


def test_extract_then_verify_round_trip() -> None:
    envelope = {
        "tool": "chart",
        "data": {
            "chart": {"objects": [{"id": "Venus", "sign": "Cancer"}]},
            "snapshot_text": "", "export_snapshot": {"export_text": ""},
        },
    }
    facts = extract_facts(envelope)
    good = verify_answer("金星落在巨蟹座，重视安全感。", facts)
    bad = verify_answer("金星在狮子座，光芒外放。", facts)
    assert good["ok"] is True and bad["ok"] is False


# --- v2 族：紫微十四主星落宫 -----------------------------------------------------------------


def _ziwei_facts():
    return _facts(tool="ziwei_birth", ziwei_stars={"紫微": "命", "天府": "官禄", "破军": "迁移"})


def test_ziwei_star_claims_three_channels() -> None:
    facts = _ziwei_facts()
    ok = verify_answer("紫微坐守命宫，气象尊贵。", facts)
    assert ok["ok"] is True
    assert any(c["type"] == "ziwei_star" and c["status"] == "supported" for c in ok["claims"])

    wrong = verify_answer("紫微星落在夫妻宫，婚姻主导。", facts)
    claim = next(c for c in wrong["claims"] if c["type"] == "ziwei_star")
    assert claim["status"] == "contradicted" and claim["expected"] == "命"

    fabricated = verify_answer("七杀在财帛宫，破财之象。", facts)
    assert any(c["type"] == "ziwei_star" and c["status"] == "invented" for c in fabricated["claims"])


def test_ziwei_palace_school_alias_maps_to_same_group() -> None:
    """引擎写「官禄宫」、答案写「事业宫」——流派别名不许判红。"""
    report = verify_answer("天府入事业宫，事业有靠山。", _ziwei_facts())
    claim = next(c for c in report["claims"] if c["type"] == "ziwei_star")
    assert claim["status"] == "supported"


def test_ziwei_family_gated_when_no_ziwei_truth() -> None:
    """族门槛：八字盘真值里没有紫微主星 → 紫微断言整族跳过，不误红合参答案。"""
    report = verify_answer("紫微坐守命宫。", _facts())
    assert all(c["type"] != "ziwei_star" for c in report["claims"])


# --- v2 族：六爻卦名与动爻 -------------------------------------------------------------------


def _sixyao_facts():
    return _facts(tool="sixyao", gua={"本卦": "地天泰", "之卦": "雷天大壮"}, moving_yao=["三"])


def test_gua_name_abbreviation_counts_as_supported() -> None:
    report = verify_answer("本卦为泰，之卦大壮，由安转动。", _sixyao_facts())
    statuses = [c["status"] for c in report["claims"] if c["type"] == "gua_name"]
    assert statuses == ["supported", "supported"]


def test_gua_name_contradiction_is_caught() -> None:
    report = verify_answer("本卦为否卦，闭塞不通。", _sixyao_facts())
    claim = next(c for c in report["claims"] if c["type"] == "gua_name")
    assert claim["status"] == "contradicted" and claim["expected"] == "地天泰"


def test_moving_yao_claims() -> None:
    facts = _sixyao_facts()
    ok = verify_answer("三爻发动，主变在人事。", facts)
    assert any(c["type"] == "moving_yao" and c["status"] == "supported" for c in ok["claims"])

    wrong = verify_answer("动爻在上爻，事在远方。", facts)
    claim = next(c for c in wrong["claims"] if c["type"] == "moving_yao")
    assert claim["status"] == "contradicted"

    numbered = verify_answer("第六爻动，宜守不宜进。", facts)
    assert any(c["type"] == "moving_yao" and c["status"] == "contradicted" for c in numbered["claims"])


def test_liuyao_technique_name_phrase_is_not_a_moving_claim() -> None:
    """「从六爻动向看」是技法名短语，不是「上爻发动」断言——不带「第」的一/六不算爻位。"""
    report = verify_answer("从六爻动向看，整体趋稳。", _sixyao_facts())
    assert all(c["type"] != "moving_yao" for c in report["claims"])


# --- v2 族：塔罗牌名正逆 ---------------------------------------------------------------------


def _tarot_facts():
    return _facts(tool="tarot", tarot_draws={"愚者": "正位", "钱币三": "逆位", "月亮": "正位"})


def test_tarot_orientation_three_channels() -> None:
    facts = _tarot_facts()
    ok = verify_answer("愚者（正位）代表新的开始；钱币三逆位提示协作失衡。", facts)
    assert ok["ok"] is True
    assert sum(1 for c in ok["claims"] if c["type"] == "tarot_card" and c["status"] == "supported") == 2

    sycophancy = verify_answer("对，你抽到的月亮是逆位，所以内心不安。", facts)
    claim = next(c for c in sycophancy["claims"] if c["type"] == "tarot_card")
    assert claim["status"] == "contradicted" and claim["expected"] == "正位"

    fabricated = verify_answer("你还抽到了死神（正位）。", facts)
    assert any(c["type"] == "tarot_card" and c["status"] == "invented" for c in fabricated["claims"])


def test_tarot_deck_name_variants_map_to_snapshot_form() -> None:
    """facade 写「星币三」、快照写「钱币三」——两写法归一后判 supported。"""
    report = verify_answer("星币三（逆位）：手艺需打磨。", _tarot_facts())
    claim = next(c for c in report["claims"] if c["type"] == "tarot_card")
    assert claim["status"] == "supported"


def test_tarot_drawn_claim_without_orientation() -> None:
    facts = _tarot_facts()
    ok = verify_answer("这次抽到了愚者与钱币三。", facts)
    assert ok["ok"] is True
    fabricated = verify_answer("你抽出了高塔，注意突变。", facts)
    assert any(c["type"] == "tarot_card" and c["status"] == "invented" for c in fabricated["claims"])


def test_tarot_family_gated_and_plain_words_free() -> None:
    """无塔罗真值时「太阳」「月亮」等日常词 + 正逆位短语不产生塔罗断言。"""
    report = verify_answer("月亮（逆位）……", _facts())
    assert all(c["type"] != "tarot_card" for c in report["claims"])


def test_extract_facts_reads_v2_shapes() -> None:
    envelope = {
        "tool": "ziwei_birth",
        "data": {
            "houses": [
                {"name": "命宫", "isBody": False, "starsMain": [{"name": "紫微", "sihua": "权"}]},
                {"name": "官禄宫", "isBody": True, "starsMain": [{"name": "天府"}]},
            ],
            "lines": [
                {"value": 1, "change": False}, {"value": 0, "change": False},
                {"value": 1, "change": True}, {"value": 0, "change": False},
                {"value": 1, "change": False}, {"value": 0, "change": False},
            ],
            "snapshot_text": (
                "本卦：地天泰\n之卦：雷天大壮\n"
                "[逐牌详解]\n| 位置 | 位义 | 牌 | 正逆 | 占象 | 关键词 | 尊位 |\n"
                "| --- | --- | --- | --- | --- | --- | --- |\n"
                "| 位置1(过去) | 起点 | 0 The Fool 愚者 | 正位 | 风 | 开端 | — |\n"
                "| 位置2(现在) | 当下 | Three of Pentacles  钱币三 | 逆位 | 土 | 协作 | — |\n"
            ),
            "export_snapshot": {"export_text": ""},
        },
    }
    facts = extract_facts(envelope)
    assert facts["ziwei_stars"] == {"紫微": "命", "天府": "官禄"}
    assert facts["body_palace"] == "官禄宫"
    assert facts["gua"] == {"本卦": "地天泰", "之卦": "雷天大壮"}
    assert facts["moving_yao"] == ["三"]
    assert facts["tarot_draws"] == {"愚者": "正位", "钱币三": "逆位"}


def test_wrong_tarot_reading_floods_red() -> None:
    """喂错局的塔罗答案（另一局的牌与正逆）必须整片判红。"""
    other_reading = "愚者（逆位）加上高塔（正位），你抽到了审判，剧变将至。"
    report = verify_answer(other_reading, _tarot_facts())
    assert report["ok"] is False
    assert report["metrics"]["contradicted"] + report["metrics"]["invented"] >= 3


# ---- v3（v0.36.0 C3）：奇门 / 择日命中区间 / 推运时段边界 ----
def _qimen_envelope() -> dict:
    return {
        "tool": "qimen",
        "data": {
            "pan": {"source": "kinqimen"},
            "snapshot_text": (
                "[值符值使]\n值符：天蓬（坎一宫）\n值使：休门（坎一宫）\n\n"
                "[八宫]\n坎一宫：天蓬 休门 值符\n坤二宫：天芮 死门 太阴\n震三宫：天冲 伤门 六合\n"
            ),
        },
    }


def test_qimen_zhifu_zhishi_and_palace_three_channels() -> None:
    facts = extract_facts(_qimen_envelope())
    assert facts["qimen"]["值符"] == "天蓬" and facts["qimen"]["值使"] == "休门"
    assert set(facts["qimen"]["palaces"]) == {"坎一宫", "坤二宫", "震三宫"}
    ok = verify_answer("此局值符是天蓬，值使为休门，天芮落坤二宫，死门临坤宫。", facts)
    assert ok["ok"], ok["claims"]
    assert {c["type"] for c in ok["claims"]} == {"qimen_zhifu", "qimen_zhishi", "qimen_palace"}
    bad = verify_answer("值符是天英，值使为开门，天蓬落震三宫。", facts)
    statuses = {c["type"]: c["status"] for c in bad["claims"]}
    assert statuses == {"qimen_zhifu": "contradicted", "qimen_zhishi": "contradicted", "qimen_palace": "contradicted"}
    assert not bad["ok"]
    invented = verify_answer("开门落兑七宫。", facts)
    assert invented["claims"][0]["status"] == "invented"  # 兑宫不在本盘任何行


def test_qimen_family_gated_when_no_qimen_truth() -> None:
    facts = extract_facts({"tool": "bazi_birth", "data": {"snapshot_text": "[四柱]\n年柱 甲子"}})
    assert facts["qimen"] == {}
    assert verify_answer("值符是天英。", facts)["claims"] == []


def _zeri_envelope(intervals: list) -> dict:
    return {"tool": "bazizeri", "data": {"intervals": intervals, "snapshot_text": "[命中区间]\n…"}}


def test_hit_window_dates_must_fall_inside_hits() -> None:
    facts = extract_facts(_zeri_envelope([
        {"startDate": "2026/09/12", "startTime": "09:00", "endDate": "2026/09/12", "endTime": "11:00"},
        {"startDate": "2026-09-20", "startTime": "13:00", "endDate": "2026-09-21", "endTime": "15:00"},
    ]))
    assert facts["hit_windows"] == [("2026-09-12", "2026-09-12"), ("2026-09-20", "2026-09-21")]
    good = verify_answer("推荐 2026-09-12 上午，或选在 2026年9月21日。", facts)
    assert good["ok"] and len(good["claims"]) == 2
    bad = verify_answer("建议定在 2026-09-15 开业。", facts)
    assert bad["claims"][0]["status"] == "contradicted" and not bad["ok"]
    denial = verify_answer("本窗口内没有命中的吉时。", facts)
    assert denial["claims"][0]["status"] == "contradicted"


def test_hit_window_empty_hits_and_gating() -> None:
    empty = extract_facts(_zeri_envelope([]))
    assert empty["hit_windows"] == []
    res = verify_answer("推荐 2026-09-12。", empty)
    assert res["claims"][0]["status"] == "invented"
    assert verify_answer("没有命中的吉时。", empty)["ok"]  # 真的没命中：说「无命中」是对的
    none = extract_facts({"tool": "chart", "data": {"snapshot_text": ""}})
    assert none["hit_windows"] is None and verify_answer("推荐 2026-09-12。", none)["claims"] == []


def _firdaria_envelope() -> dict:
    return {
        "tool": "firdaria",
        "data": {
            "snapshot_text": (
                "[法达星限表格]\n| 主限 | 子限 | 日期 |\n| --- | --- | --- |\n"
                "| 太阳 | 太阳 | 1990-01-01 |\n| 太阳 | 金星 | 1991-06-05 |\n| 金星 | 金星 | 2000-01-01 |\n| Saturn | Jupiter | 2011-03-15 |\n"
            ),
        },
    }


def test_period_boundary_planet_year_pairing() -> None:
    facts = extract_facts(_firdaria_envelope())
    assert facts["period_rows"]["太阳"] == {"1990-01", "1991-06"} and facts["period_rows"]["土星"] == {"2011-03"}
    good = verify_answer("太阳期从 1990 年开始，金星大限 2000-01 起，土星主限 2011年3月 交接。", facts)
    assert good["ok"], good["claims"]
    assert all(c["type"] == "period_boundary" for c in good["claims"]) and len(good["claims"]) == 3
    bad = verify_answer("土星期从 2005 年开始。", facts)
    assert bad["claims"][0]["status"] == "contradicted"
    invented = verify_answer("火星期从 1990 年开始。", facts)
    assert invented["claims"][0]["status"] == "invented"


def test_period_boundary_gated_without_tables() -> None:
    facts = extract_facts({"tool": "chart", "data": {"snapshot_text": "[起盘信息]\n日期：1990-01-01 12:00"}})
    assert facts["period_rows"] == {}
    assert verify_answer("土星期从 2005 年开始。", facts)["claims"] == []


# ── 2026-11-11 深审 B-2：三种结论 + 日主 / 英文四柱 / 格局 / 大运（只认引擎明写的值） ─────────────────────────────

import json  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

LIVE_BAZI = json.loads((Path(__file__).parent / "fixtures" / "faithfulness_bazi_live.json").read_text(encoding="utf-8"))


def _live_facts():
    return extract_facts(LIVE_BAZI)


def test_the_live_engine_shape_yields_day_master_structure_and_luck_pillars() -> None:
    facts = _live_facts()
    day = LIVE_BAZI["data"]["bazi"]["fourColumns"]["day"]
    assert facts["day_master"]["stem"] == day["stem"]["cell"] == day["ganzi"][0]
    assert facts["geju"] and LIVE_BAZI["data"]["bazi"]["gejuYongShen"]["geju"]["name"].removesuffix("格") in facts["geju"]
    assert len(facts["dayun"]) >= 8


def test_a_wrong_day_master_in_english_fails_instead_of_passing_with_no_claims() -> None:
    """审计复现：「Your day master is Jia wood」对着别的日主，此前零断言 → ok=true、ratio 1.0。"""
    facts = _live_facts()
    assert facts["day_master"]["stem"] != "甲"
    report = verify_answer("Your day master is Jia wood and you will get rich next year.", facts)
    assert report["status"] == "fail" and report["ok"] is False
    assert [c["type"] for c in report["claims"]] == ["day_master"] and report["claims"][0]["status"] == "contradicted"


def test_day_master_claims_are_judged_on_stem_element_and_polarity_as_stated() -> None:
    facts = _live_facts()
    master = facts["day_master"]
    english = {"甲": "Jia", "乙": "Yi", "丙": "Bing", "丁": "Ding", "戊": "Wu", "己": "Ji", "庚": "Geng", "辛": "Xin", "壬": "Ren", "癸": "Gui"}
    element_en = {"木": "wood", "火": "fire", "土": "earth", "金": "metal", "水": "water"}
    right = [f"日主{master['stem']}{master['element']}", f"日元为{master['stem']}", f"Your day master is {english[master['stem']]} {element_en[master['element']]}.",
             f"day master: {element_en[master['element']]}"]
    for text in right:
        assert verify_answer(text, facts)["status"] == "pass", text
    other_element = next(e for e in element_en if e != master["element"])
    other_polar = "yin" if master["polar"] == "阳" else "yang"
    for text in (f"日主{other_element}", f"day master is {other_polar} {element_en[master['element']]}"):
        assert verify_answer(text, facts)["status"] == "fail", text


def test_english_pillar_wording_is_checked_like_the_chinese() -> None:
    facts = _live_facts()
    pinyin_stem = {"甲": "Jia", "乙": "Yi", "丙": "Bing", "丁": "Ding", "戊": "Wu", "己": "Ji", "庚": "Geng", "辛": "Xin", "壬": "Ren", "癸": "Gui"}
    pinyin_branch = {"子": "Zi", "丑": "Chou", "寅": "Yin", "卯": "Mao", "辰": "Chen", "巳": "Si", "午": "Wu", "未": "Wei", "申": "Shen",
                     "酉": "You", "戌": "Xu", "亥": "Hai"}
    day = facts["pillars"]["日"]
    good = verify_answer(f"The day pillar is {pinyin_stem[day[0]]} {pinyin_branch[day[1]]}.", facts)
    assert good["status"] == "pass" and good["claims"][0]["type"] == "ganzhi_pillar"
    wrong = "甲子" if day != "甲子" else "乙丑"
    bad = verify_answer(f"Day pillar: {pinyin_stem[wrong[0]]}-{pinyin_branch[wrong[1]]}", facts)
    assert bad["status"] == "fail" and bad["claims"][0]["expected"] == day


def test_structure_and_luck_pillar_claims_only_count_names_the_engine_wrote() -> None:
    facts = _live_facts()
    stated = LIVE_BAZI["data"]["bazi"]["gejuYongShen"]["geju"]["name"]
    other = "七杀格" if stated != "七杀格" else "正官格"
    steps = list(facts["dayun"])
    assert verify_answer(f"{stated}，大运走到{steps[3]}。", facts)["status"] == "pass"
    bad = verify_answer(f"这是{other}。", facts)
    assert bad["status"] == "fail" and bad["claims"][0]["type"] == "geju"
    missing = next(gz for gz in ("甲子", "乙丑", "丙寅", "丁卯") if gz not in facts["dayun"])
    assert verify_answer(f"现行大运{missing}", facts)["claims"][0]["status"] == "contradicted"
    # 「性格」「风格」不是格局断言；用神各派不一，引擎没有单一结论，不判
    assert verify_answer("性格开朗，风格稳健，用神为水。", facts)["status"] == "not_assessed"


def test_a_family_without_engine_truth_is_not_judged() -> None:
    """族门槛：引擎没给日主 / 格局 / 大运（比如这是紫微盘）时，这几族不判，也不拿空真值判红。"""
    report = verify_answer("日主甲木，七杀格，大运癸未。", _facts())
    assert all(c["type"] not in {"day_master", "geju", "dayun"} for c in report["claims"])


@pytest.mark.parametrize(("answer", "code"), [("年柱乙亥。", 0), ("年柱甲子。", 1), ("一切顺利。", 3)])
def test_the_cli_exit_code_separates_fail_from_not_assessed(answer: str, code: int, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    from horosa_skill.surfaces import cli

    class _Service:
        def _load_report_source(self, run_id, tool):
            return {}, {"payload": {"tool": "bazi_birth", "data": {"bazi": {"fourColumns": {"year": {"ganzi": "乙亥"}}}}},
                        "tool_name": "bazi_birth"}

        def faithfulness_opinion(self, report, export_text):
            return None

    monkeypatch.setattr(cli, "_service", lambda: _Service())
    result = CliRunner().invoke(cli.app, ["benchmark", "faithfulness", "--run-id", "r1", "--answer-text", answer])
    assert result.exit_code == code, result.output
