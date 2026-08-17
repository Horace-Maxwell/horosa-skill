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
