"""技法依据卡 + 技法依据报告（v0.27.0）。

它与 `reports/builder.py` 的咨询报告是**两种文档**：那份要 AI 写正文、正文里禁机器元数据；
这份是确定性的方法与出处，零 AI 成分，所以能随每次输出直接给出。测试按这个分界写。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from horosa_skill.schemas.common import TOOL_ENVELOPE_SCHEMA_VERSION
from horosa_skill.reports.technique_card import (
    TECHNIQUE_CARD_SCHEMA,
    build_technique_card,
    build_technique_report,
    render_technique_card_markdown,
    render_technique_report_markdown,
)

PKG_ROOT = Path(__file__).resolve().parents[1]


def _card(**overrides):
    base = dict(
        tool_name="qimen",
        technique_key="qimen",
        input_normalized={
            "date": "2028-04-06",
            "after23NewDay": 1,
            "lateZiHourUseNextDay": 0,
            "tradition": True,
            "agent_confirmed_settings": True,
        },
        response_data={
            "pan": {"source": "kinqimen"},
            "export_snapshot": {
                "section_titles_detected": ["起盘信息", "盘型"],
                "selected_sections": ["起盘信息", "盘型"],
                "missing_selected_sections": [],
                "unknown_detected_sections": [],
                "bundle_version": 13,
                "format_source": "snapshot_parser",
            },
        },
        skill_version="0.27.0",
        envelope_schema=TOOL_ENVELOPE_SCHEMA_VERSION,
        domain="cn",
    )
    base.update(overrides)
    return build_technique_card(**base)


# --- 算源：实测优先于声明 -----------------------------------------------------------------------


def test_card_records_both_the_declaration_and_what_actually_computed_it() -> None:
    card = _card()
    assert card["schema"] == TECHNIQUE_CARD_SCHEMA
    assert card["compute"]["declared_class"] == "ken_backed"
    assert card["compute"]["measured"] == {"pan": "kinqimen"}
    assert card["compute"]["matches_declaration"] is True


def test_silent_ken_fallback_shows_up_as_a_declaration_mismatch() -> None:
    """ken 端点失败也回 HTTP 200（AGENTS §4），静默回退本地脚手架 = 错结果无报错。

    卡片必须把这件事**显示出来**，而不是照着声明印一句「由 kinqimen 计算」——那正好是把最危险的
    失败模式伪装成正常。
    """
    card = _card(response_data={"pan": {"source": "local_calcDunJia"}, "export_snapshot": {}})
    assert card["compute"]["measured"] == {"pan": "local_calcDunJia"}
    assert card["compute"]["matches_declaration"] is False
    assert "⚠️" in render_technique_card_markdown(card)


def test_missing_measurement_is_unknown_not_a_false_pass() -> None:
    card = _card(response_data={"export_snapshot": {}})
    assert card["compute"]["matches_declaration"] is None, "没测到就是不知道，不能算作相符"


# --- 口径：只印真正参与计算的设置 ----------------------------------------------------------------


def test_result_sensitive_settings_are_echoed_for_the_relevant_domain() -> None:
    card = _card()
    settings = card["settings"]
    assert settings["after23NewDay"]["value"] == 1
    assert settings["lateZiHourUseNextDay"]["value"] == 0
    assert "晚子时" in settings["after23NewDay"]["label"]


def test_shared_base_class_defaults_do_not_leak_into_unrelated_techniques() -> None:
    """`BirthInput` 是共享基类：`tradition`/`zodiacal`/`hsys` 会带着默认值出现在**每个**技法的
    `input_normalized` 里。照单全印，会给灵棋经这种纯干支技法印出「黄道制=0」，读者会以为它真按
    那个口径算过——卡片的全部价值是如实说明这盘怎么来的，多印一条没参与计算的口径比不印更糟。
    """
    card = _card(tool_name="lingqi", technique_key="lingqi", domain="cn")
    assert "tradition" not in card["settings"]
    astro = _card(tool_name="chart", technique_key="astrochart", domain="astro")
    assert "tradition" in astro["settings"], "西占技法反过来必须印出古典口径"


def test_ayanamsa_is_read_from_the_right_field_per_tradition() -> None:
    """西占读 `chart.siderealAyanamsa`、印占读 `siderealModeKey`+`ayanamsaValue`——**字段名不同**
    （AGENTS §4），不许硬编码岁差名。"""
    western = _card(
        domain="astro",
        response_data={"chart": {"siderealAyanamsa": "Fagan-Bradley"}, "export_snapshot": {}},
    )
    assert western["settings"]["siderealAyanamsa"]["value"] == "Fagan-Bradley"
    indian = _card(
        domain="astro",
        response_data={"chart": {"siderealModeKey": 3, "ayanamsaValue": 24.1}, "export_snapshot": {}},
    )
    assert indian["settings"]["siderealModeKey"]["value"] == 3
    assert indian["settings"]["ayanamsaValue"]["value"] == 24.1


def test_gate_state_is_recorded_verbatim() -> None:
    card = _card()
    assert card["gate"]["agent_confirmed_settings"]["value"] is True


# --- 段落健康度 ---------------------------------------------------------------------------------


def test_contract_gap_is_reported_not_smoothed_over() -> None:
    card = _card(
        response_data={
            "export_snapshot": {
                "section_titles_detected": ["起盘信息"],
                "selected_sections": ["起盘信息", "盘型"],
                "missing_selected_sections": ["盘型"],
                "unknown_detected_sections": ["某新段"],
            }
        }
    )
    assert card["sections"]["contract_clean"] is False
    rendered = render_technique_card_markdown(card)
    assert "有缺口" in rendered and "盘型" in rendered and "某新段" in rendered


# --- 会话聚合：口径冲突 --------------------------------------------------------------------------


def test_session_report_flags_a_late_zi_switch_conflict_across_techniques() -> None:
    """同一会话里两个技法用了不同的晚子时开关 = 两张盘可能根本不是同一天的日柱，结论不可互证。

    这件事在真实使用里**不会有任何报错**，只会安静地给出两套说法——所以它必须被显式检出。
    """
    first = _card(tool_name="cetian", technique_key="cetian")
    second = _card(
        tool_name="wuzhao",
        technique_key="wuzhao",
        input_normalized={"after23NewDay": 0, "lateZiHourUseNextDay": 0},
    )
    report = build_technique_report(cards=[first, second], scope="group", scope_id="g1")
    conflicts = report["consistency"]["setting_conflicts"]
    assert [c["field"] for c in conflicts] == ["after23NewDay"]
    assert report["consistency"]["all_clear"] is False
    markdown = render_technique_report_markdown(report)
    assert "口径不一致" in markdown and "cetian" in markdown and "wuzhao" in markdown


def test_session_report_is_all_clear_only_when_every_check_passes() -> None:
    report = build_technique_report(cards=[_card(), _card()], scope="group", scope_id="g1")
    assert report["consistency"]["all_clear"] is True
    assert report["technique_count"] == 2
    assert "| 技法 | 工具 | 算源 | 段数 | 导出契约 |" in render_technique_report_markdown(report)


# --- 声明表本身 ---------------------------------------------------------------------------------


def test_every_registered_tool_declares_a_compute_source() -> None:
    """新增技法不声明算源 = 卡片只能按 `execution` 猜，而 `execution` 说明不了算源
    （qimen 是 execution="local" 却整盘由 ken 算）。守卫脚本同款断言，这里让它进 pytest。"""
    from horosa_skill.engine.registry import TOOL_DEFINITIONS

    declared = json.loads(
        (PKG_ROOT / "contracts/technique_provenance.json").read_text(encoding="utf-8")
    )["tools"]
    assert set(declared) == set(TOOL_DEFINITIONS)


@pytest.mark.parametrize("tool_name", ["qimen", "taiyi", "jinkou"])
def test_ken_backed_tools_are_declared_as_such(tool_name: str) -> None:
    declared = json.loads(
        (PKG_ROOT / "contracts/technique_provenance.json").read_text(encoding="utf-8")
    )["tools"]
    assert declared[tool_name]["compute_class"] == "ken_backed"
    assert declared[tool_name]["engines"], "ken 工具必须写明引擎名，卡片要用它比对实测 pan.source"


def test_technique_report_docx_and_pdf_carry_the_report_body(tmp_path, monkeypatch) -> None:
    # 技法依据报告没有 ai_report：此前 DOCX/PDF 只渲染出封面与目录（一致性检查、技法一览、各技法卡全丢），
    # markdown 版却是全的。DOCX/PDF 必须带出同一份正文。
    import zipfile

    from horosa_skill.reports.renderers import render_report

    first = _card()
    second = _card(tool_name="liureng", technique_key="liureng",
                   input_normalized={"date": "2028-04-06", "after23NewDay": 0, "agent_confirmed_settings": True})
    report = build_technique_report(cards=[first, second], scope="group", scope_id="g1")

    docx = tmp_path / "t.docx"
    render_report(report, output_path=docx, format_name="docx")
    with zipfile.ZipFile(docx) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    for expected in ("一致性检查", "技法一览", "口径不一致", "qimen", "liureng", "技法依据报告"):
        assert expected in xml, expected
    assert "结构化解读 · 行动建议 · 风险提示" not in xml  # 不冒充咨询报告封面
    assert "**" not in xml and "`" not in xml

    # PDF 看交给 reportlab 的正文本身，不看文件大小：大小随嵌入的中文字体变（苹方 / Noto / STSong 的子集开销差几倍），
    # 「带正文 > 2 × 不带正文」在 Linux 只有 1.83 倍、macOS 1.94 倍，CI 与矩阵因此红过（v0.41.2）。
    pdf_text = _pdf_story_text(tmp_path / "t.pdf", report, monkeypatch)
    for expected in ("一致性检查", "技法一览", "口径不一致", "qimen", "liureng"):
        assert expected in pdf_text, expected
    # 负向对照：只有标题的文档（= 旧缺陷「只剩封面和目录」的形状）拿不出这些正文。
    bare = _pdf_story_text(tmp_path / "bare.pdf", {"title": report["title"]}, monkeypatch)
    assert not any(expected in bare for expected in ("一致性检查", "技法一览", "口径不一致"))


def _pdf_story_text(path, document, monkeypatch) -> str:
    """渲染 PDF，并收集交给 SimpleDocTemplate.build 的全部段落与表格文字（与字体无关）。"""
    from reportlab.platypus import SimpleDocTemplate

    from horosa_skill.reports.renderers import render_report

    captured: list[str] = []
    original_build = SimpleDocTemplate.build

    def _collect(flowable) -> None:
        if hasattr(flowable, "getPlainText"):
            captured.append(flowable.getPlainText())
        for row in getattr(flowable, "_cellvalues", None) or []:
            for cell in row:
                for item in cell if isinstance(cell, (list, tuple)) else [cell]:
                    captured.append(item.getPlainText() if hasattr(item, "getPlainText") else str(item))

    def spy_build(self, flowables, *args, **kwargs):
        for flowable in flowables:
            _collect(flowable)
        return original_build(self, flowables, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(SimpleDocTemplate, "build", spy_build)
        result = render_report(document, output_path=path, format_name="pdf")
    assert result["format"] == "pdf"
    return "\n".join(captured)
