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
    """纯解读语（不引具体盘面值）不该被扣——失败必须是具体的编造/矛盾，不是「话多」。"""
    report = verify_answer("整体格局稳健，建议先立足本业，再徐图扩张。", _facts())
    assert report["ok"] is True and report["metrics"]["claims_total"] == 0
    assert report["metrics"]["faithfulness_ratio"] == 1.0


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
