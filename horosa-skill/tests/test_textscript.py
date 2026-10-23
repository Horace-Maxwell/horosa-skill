"""输出文字（简 / 繁 / 港繁）：转换器忠实于 OpenCC、术数词表、只转给人读的字段、出口全覆盖、标识能对回原名。

全部离线：不连后端、不起 runtime。真实结果来自 `tests/fixtures/textscript/`（2026-10-22 vendored 实例上 110 技法输出的节选）。
"""
from __future__ import annotations

import ast
import asyncio
import hashlib
import json
import os
from pathlib import Path

import pytest

from horosa_skill.textscript import (
    SIMPLIFIED,
    TRADITIONAL,
    TRADITIONAL_HK,
    canonical_name,
    convert,
    looks_traditional,
    parse_script,
)
from horosa_skill.textscript.converter import _load, _Stage, _variants
from horosa_skill.textscript.localize import localize, localize_document, unclassified_text_paths

PKG = Path(__file__).resolve().parents[1]
FIXTURES = PKG / "tests" / "fixtures" / "textscript"
DATA = PKG / "src" / "horosa_skill" / "textscript" / "data"
ENVELOPES = sorted(FIXTURES.glob("envelope_*.json"))
TRAD = (TRADITIONAL, TRADITIONAL_HK)


def _envelope(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ── 转换器 ───────────────────────────────────────────────────────────────────


def test_bundled_opencc_files_are_the_recorded_upstream_copies() -> None:
    source = json.loads((DATA / "opencc" / "SOURCE.json").read_text(encoding="utf-8"))
    assert source["license"] == "Apache-2.0" and (DATA / "opencc" / "LICENSE").is_file()
    on_disk = {p.name for p in (DATA / "opencc").iterdir() if p.suffix == ".txt"} | {"LICENSE"}
    assert on_disk == set(source["files"])
    for name, digest in source["files"].items():
        assert hashlib.sha256((DATA / "opencc" / name).read_bytes()).hexdigest() == digest, name


def test_converter_without_the_term_table_reproduces_official_opencc() -> None:
    """600 句真实输出：去掉术数词表后，逐字等于官方 opencc 1.4.2 的 s2tw / s2hk。改了算法或字典就会红。"""
    reference = json.loads((FIXTURES / "opencc_reference.json").read_text(encoding="utf-8"))
    stage1 = _Stage(_load("opencc/STPhrases.txt"), _load("opencc/STCharacters.txt"))
    for case in reference["cases"]:
        first = stage1.apply(case["s"])
        assert _variants(TRADITIONAL).apply(first) == case["tw"], case["s"]
        assert _variants(TRADITIONAL_HK).apply(first) == case["hk"], case["s"]


GOLDEN = {
    # 术数义：OpenCC 原本会转错的
    "年干、藏干、干合，日干上神": "年干、藏干、干合，日干上神",
    "子丑合，丑未冲，父母丑土": "子丑合，丑未沖，父母丑土",
    "金克木，受克，生克制化，四课一克下": "金剋木，受剋，生剋制化，四課一剋下",
    "刑冲合害，冲煞，刑冲开库": "刑沖合害，沖煞，刑沖開庫",
    "北斗、斗宿、斗君，斗牛女虚危": "北斗、斗宿、斗君，斗牛女虛危",
    "吉凶，凶星，凶恶": "吉凶，凶星，凶惡",
    "占卜，夜占，西占，天文地占": "占卜，夜占，西占，天文地占",
    "泽山咸，咸池": "澤山咸，咸池",
    "农历、黄历、出生历日": "農曆、黃曆、出生曆日",
    "天干五合中，合中带": "天干五合中，合中帶",
    "太阳回归，塔罗圣杯": "太陽回歸，塔羅聖杯",
    "经云、书云、又云": "經云、書云、又云",
    "紫微斗数，三台八座，卷舌，神后": "紫微斗數，三台八座，卷舌，神后",
    # 普通义：必须仍交给 OpenCC 的词组
    "冲击、冲动、冲突": "衝擊、衝動、衝突",
    "克服、克己、千克": "克服、克己、千克",
    "历史、经历": "歷史、經歷",
    "争斗、战斗": "爭鬥、戰鬥",
    "丑闻、丑陋": "醜聞、醜陋",
    "占有、占优、占比": "佔有、佔優、佔比",
    "头发、发财、发用": "頭髮、發財、發用",
    # 跨词错切（词组表管不住，逐位定字才对；前四条是上游星阙 hantRules.js 注释里点名的）
    "真实干支": "真實干支",
    "午丑相害": "午丑相害",
    "的历法": "的曆法",
    "淳风云：一事，故曰云云": "淳風云：一事，故曰云云",
    # 上游白名单会转错、本仓已纠正的（deviations）
    "农历年月日": "農曆年月日",
    "查密码表": "查密碼表",
    "占有点": "佔有點",
    # 钟 / 表（与上游一致）
    "城钟，手表，钟情，星历表": "城鐘，手錶，鍾情，星曆表",
}


@pytest.mark.parametrize("simplified,traditional", GOLDEN.items())
def test_shushu_golden_terms(simplified: str, traditional: str) -> None:
    assert convert(simplified, TRADITIONAL) == traditional
    # 香港字形在这些词上与台湾相同（只差异体字表）
    assert convert(simplified, TRADITIONAL_HK) == _variants(TRADITIONAL_HK).apply(
        _variants(TRADITIONAL).apply(traditional)
    ) or convert(simplified, TRADITIONAL_HK) == traditional


def test_every_term_table_entry_is_well_formed_and_takes_effect() -> None:
    seen: dict[str, str] = {}
    for line in (DATA / "horosa_s2t.txt").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        key, tab, rest = line.partition("\t")
        value = rest.split("#", 1)[0].strip()
        assert tab and key and value and " " not in value, line
        assert key not in seen, f"duplicate term-table key {key}"
        seen[key] = value
    for key, value in seen.items():
        for script in TRAD:
            assert convert(key, script) == _variants(script).apply(value), key


def test_dictionary_entries_keep_length_so_character_rules_can_align() -> None:
    """逐位定字按位对齐原文与译文：任何字典条目一旦不等长，对齐就失效（上游同一前提）。"""
    for name in ("STPhrases", "STCharacters", "TWVariants", "TWVariantsPhrases", "HKVariants", "HKVariantsPhrases"):
        assert all(len(k) == len(v) for k, v in _load(f"opencc/{name}.txt").items()), name
    assert all(len(k) == len(v) for k, v in _load("horosa_s2t.txt").items())


def _char_rules_doc() -> dict:
    return json.loads((DATA / "horosa_char_rules.json").read_text(encoding="utf-8"))


def test_every_character_rule_is_well_formed_and_takes_effect() -> None:
    rules = _char_rules_doc()["rules"]
    assert {"干", "丑", "斗", "占", "冲", "历", "凶", "钟", "云", "表", "克", "咸"} <= set(rules)
    for char, rule in rules.items():
        for word, traditional in rule["words"].items():
            assert char in word and len(word) == len(traditional), (char, word)
            converted = convert(word, TRADITIONAL)
            for index, letter in enumerate(word):
                if letter == char:
                    assert converted[index] == traditional[index], (char, word, converted)
        if rule.get("default"):
            # 孤立的字取缺省（「冲」→「沖」、「克」→「剋」）
            assert convert(f"，{char}，", TRADITIONAL)[1] == rule["default"], char


UPSTREAM_ROOT = Path(os.environ.get("HOROSA_SOURCE_ROOT") or PKG.parent.parent / "Horosa-Public")
UPSTREAM_RULES = UPSTREAM_ROOT / "Horosa-Web" / "astrostudyui" / "src" / "utils" / "scriptConvert" / "hantRules.js"


@pytest.mark.skipif(not UPSTREAM_RULES.is_file(), reason="needs the upstream Horosa-Public checkout next to this repo")
def test_character_rules_cover_upstream_except_documented_deviations() -> None:
    """与上游星阙界面简繁同一套字：上游每条规则本仓都有、取值相同，除非写进了 deviations（并给出理由）。"""
    import re

    text = UPSTREAM_RULES.read_text(encoding="utf-8")
    body = text[text.index("const RULES = {"):text.index("};", text.index("const RULES = {")) + 1]
    upstream = {}
    for match in re.finditer(r"'(.)': \{ def: (null|'(.)'),( quote: true,)? words: \{(.*?)\} \}", body, re.S):
        upstream[match.group(1)] = (match.group(3), bool(match.group(4)), dict(re.findall(r"'([^']+)': '([^']+)'", match.group(5))))
    assert upstream, "could not parse upstream hantRules.js"
    doc = _char_rules_doc()
    ours, deviations = doc["rules"], set(doc["deviations"])
    for char, (default, quote, words) in upstream.items():
        assert char in ours, f"上游新增了「{char}」的规则，本仓还没有"
        assert ours[char].get("default") == default and bool(ours[char].get("quote")) == quote, char
        for word, traditional in words.items():
            if word in deviations:
                continue
            assert ours[char]["words"].get(word) == traditional, f"{char}: 上游 {word}→{traditional}，本仓 {ours[char]['words'].get(word)}"


def test_conversion_is_idempotent_and_leaves_non_chinese_alone() -> None:
    text = _envelope(ENVELOPES[0])["data"]["export_snapshot"]["export_text"]
    for script in TRAD:
        once = convert(text, script)
        assert convert(once, script) == once
    for plain in ("", "abc 123 {\"k\": [1, 2]}", "https://example.com/a?b=c"):
        assert convert(plain, TRADITIONAL) == plain


# ── 设置 ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("raw,expected", [
    (None, SIMPLIFIED), ("", SIMPLIFIED), ("false", SIMPLIFIED), ("0", SIMPLIFIED), ("zh-Hans", SIMPLIFIED),
    ("true", TRADITIONAL), ("True", TRADITIONAL), ("1", TRADITIONAL), ("zh-TW", TRADITIONAL), ("traditional", TRADITIONAL),
    ("zh-Hant-HK", TRADITIONAL_HK), ("HK", TRADITIONAL_HK), ("tradtional", None),
])
def test_parse_script(raw, expected) -> None:
    assert parse_script(raw) == expected


def test_settings_default_is_simplified_and_a_typo_falls_back(monkeypatch) -> None:
    from horosa_skill.config import ENV_FLAG_REGISTRY, FIELD_ENV_MAP, Settings

    assert ENV_FLAG_REGISTRY["HOROSA_OUTPUT_SCRIPT"] == "stable" and FIELD_ENV_MAP["output_script"] == "HOROSA_OUTPUT_SCRIPT"
    monkeypatch.delenv("HOROSA_OUTPUT_SCRIPT", raising=False)
    assert Settings.from_env().output_script == SIMPLIFIED
    for raw, expected in (("true", TRADITIONAL), ("zh-Hant-HK", TRADITIONAL_HK), ("tradtional", SIMPLIFIED),
                          ("${user_config.traditional_chinese}", SIMPLIFIED)):
        monkeypatch.setenv("HOROSA_OUTPUT_SCRIPT", raw)
        assert Settings.from_env().output_script == expected, raw


def test_settings_screens_expose_one_checkbox_wired_to_the_same_variable() -> None:
    root = PKG.parent
    mcpb = json.loads((PKG / "manifest.json").read_text(encoding="utf-8"))
    assert mcpb["server"]["mcp_config"]["env"]["HOROSA_OUTPUT_SCRIPT"] == "${user_config.traditional_chinese}"
    assert mcpb["user_config"]["traditional_chinese"]["type"] == "boolean"
    assert mcpb["user_config"]["traditional_chinese"]["default"] is False
    plugin = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    plugin_mcp = json.loads((root / ".claude-plugin" / "mcp.json").read_text(encoding="utf-8"))
    assert plugin["userConfig"]["traditionalChinese"]["type"] == "boolean"
    assert plugin["userConfig"]["traditionalChinese"]["default"] is False
    assert plugin_mcp["mcpServers"]["horosa"]["env"]["HOROSA_OUTPUT_SCRIPT"] == "${user_config.traditionalChinese}"


# ── 只转给人读的字段 ──────────────────────────────────────────────────────────


def _keys(value, path="$"):
    if isinstance(value, dict):
        out = {path}
        for k, v in value.items():
            out |= _keys(v, f"{path}.{k}")
        return out
    if isinstance(value, list):
        out = set()
        for v in value:
            out |= _keys(v, f"{path}[]")
        return out
    return {path}


def test_simplified_returns_the_same_object() -> None:
    envelope = _envelope(ENVELOPES[0])
    assert localize(envelope, SIMPLIFIED) is envelope
    assert localize_document(envelope, SIMPLIFIED) is envelope
    assert convert("年干", SIMPLIFIED) == "年干"


@pytest.mark.parametrize("path", ENVELOPES, ids=lambda p: p.stem)
@pytest.mark.parametrize("script", TRAD)
def test_display_fields_convert_and_machine_fields_do_not(path: Path, script: str) -> None:
    original = _envelope(path)
    converted = localize(original, script)
    assert original == _envelope(path), "localize must not mutate its input"
    snapshot, out = original["data"]["export_snapshot"], converted["data"]["export_snapshot"]
    assert out["export_text"] == convert(snapshot["export_text"], script) != snapshot["export_text"]
    assert [s["title"] for s in out["sections"]] == [convert(s["title"], script) for s in snapshot["sections"]]
    assert [s["body"] for s in out["sections"]] == [convert(s["body"], script) for s in snapshot["sections"]]
    assert converted["summary"] == [convert(s, script) for s in original["summary"]]
    assert out["output_script"] == script and "output_script" not in snapshot
    # 机器字段一字不动
    for key in ("ok", "tool", "version", "input_normalized", "memory_ref", "code", "error"):
        assert converted.get(key) == original.get(key), key
    assert out["technique"] == snapshot["technique"] and out["settings_used"] == snapshot["settings_used"]
    raw_keys = [k for k in original["data"] if k not in ("export_snapshot", "technique_card", "snapshot_text")]
    assert raw_keys and all(converted["data"][k] == original["data"][k] for k in raw_keys)
    card, card_out = original["data"]["technique_card"], converted["data"]["technique_card"]
    assert {k: v["value"] for k, v in card["settings"].items()} == {k: v["value"] for k, v in card_out["settings"].items()}
    assert card_out["technique"]["key"] == card["technique"]["key"]
    assert card_out["technique"]["label"] == convert(card["technique"]["label"], script)
    # 结构不变：只多一个 export_snapshot.output_script
    assert _keys(converted) - _keys(original) == {"$.data.export_snapshot.output_script"}
    assert _keys(original) <= _keys(converted)


def test_protected_subtrees_stay_put_even_when_they_hold_display_like_keys() -> None:
    """回显的入参 / 引擎原始数据 / details 里就算出现 title、summary 这类键也不转（AI 会原样送回）。"""
    envelope = _envelope(ENVELOPES[0])
    envelope["input_normalized"] = {"title": "问事业", "summary": ["发财"], "question": "干支"}
    envelope["data"]["bazi"] = {"title": "日干", "label": "丑"}
    envelope["details"] = {"message": "历日", "agent_recovery": {"prompt_to_user": "请确认", "options": ["冲"]}}
    out = localize(envelope, TRADITIONAL)
    assert out["input_normalized"] == envelope["input_normalized"]
    assert out["data"]["bazi"] == envelope["data"]["bazi"]
    assert out["details"] == {"message": "历日", "agent_recovery": {"prompt_to_user": "請確認", "options": ["冲"]}}


def test_protocol_tools_come_back_unconverted_even_through_tool_run() -> None:
    """精简面 horosa_tool_run(tool_name="export_parse") 走同一个出口：按信封的 tool 字段整份放行。"""
    for tool in ("export_parse", "export_registry", "knowledge_registry"):
        envelope = {"ok": True, "tool": tool, "input_normalized": {}, "summary": ["已解析导出"],
                    "data": {"export_text": "[起盘信息]\n日干", "technique_card": {"technique": {"key": "x", "label": "紫微斗数"}}}}
        assert localize(envelope, TRADITIONAL) == envelope, tool
    reader = {"ok": True, "tool": "knowledge_read", "input_normalized": {}, "summary": [],
              "data": {"key": "流派分歧", "title": "紫微斗数", "blocks": [{"type": "text", "text": "斗君"}]}}
    out = localize(reader, TRADITIONAL)["data"]
    assert out == {"key": "流派分歧", "title": "紫微斗數", "blocks": [{"type": "text", "text": "斗君"}]}


def test_pydantic_envelopes_keep_their_type() -> None:
    from horosa_skill.schemas.common import DispatchEnvelope, ToolEnvelope

    envelope = ToolEnvelope.model_validate(_envelope(ENVELOPES[0]))
    out = localize(envelope, TRADITIONAL)
    assert isinstance(out, ToolEnvelope) and out.summary == [convert(s, TRADITIONAL) for s in envelope.summary]
    dispatch = DispatchEnvelope(ok=True, version="x", summary=["已选技法"], results={"bazi_birth": envelope})
    out = localize(dispatch, TRADITIONAL)
    assert isinstance(out, DispatchEnvelope) and out.summary == ["已選技法"]
    assert out.results["bazi_birth"].data["export_snapshot"]["output_script"] == TRADITIONAL


def _facade_shapes(envelope: dict) -> list:
    """各门面的真实形状（2026-10-22 实测 memory_show / hecan / report_from_tool / knowledge_read / 错误信封）。"""
    return [
        envelope,
        {"ok": True, "results": {"bazi_birth": envelope}, "summary": ["已选技法"], "normalized_inputs": {"x": {"q": "问事业"}}},
        {"ok": False, "tool": "bazi_birth", "code": "agent_guidance.required", "message": "调用前需要先确认设置",
         "details": {"agent_recovery": {"prompt_to_user": "请确认出生时间", "options": ["真太阳时"]}, "missing": ["时间"]}},
        {"ok": True, "result": {"run_id": "x", "subject": {"name": "张三"}, "tool_calls": [
            {"tool_name": "bazi_birth", "input": {"question": "事业"}, "summary": ["已排八字"], "warnings": [], "error": None}]},
         "summary": ["已读取对应 run 的本地完整记录。"]},
        {"ok": True, "question": "看看事业", "techniques": [{"tool": "bazi_birth", "technique": {"key": "bazi", "label": "八字"},
         "summary": ["日主偏弱"], "section_titles": ["起盘信息"]}], "synthesis_contract": {"instructions": ["分歧必须披露"]}},
        {"ok": True, "mode": "analysis_required", "report_template": {"role": "你是解盘助手"}, "ai_process": {"process": ["先读盘"]},
         "tool_result": {"ok": True, "tool": "bazi_birth", "input_normalized": {}, "summary": ["已排八字"]}},
        {"domain": "astro", "category": "planet", "key": "Sun", "title": "太阳", "tips": ["阳性"], "lines": ["阳性"],
         "rendered_text": "[太阳]\n- 阳性", "citation": "Xingque hover knowledge · astro/planet/Sun"},
        {"mode": "search", "query": "太阳", "matches": [{"domain": "germany", "category": "手册", "key": "太阳弧",
         "title": "太阳弧", "snippet": "太阳弧叠层", "citation": "星阙操作手册"}]},
    ]


@pytest.mark.parametrize("path", ENVELOPES, ids=lambda p: p.stem)
def test_every_chinese_string_in_real_outputs_is_classified(path: Path) -> None:
    """新加的输出字段必须先归类（TEXT_KEYS 转 / KEEP_KEYS 保持 / SKIP_KEYS 协议）——否则这里红。"""
    for shape in _facade_shapes(_envelope(path)):
        assert unclassified_text_paths(shape) == [], shape


def test_classification_guard_catches_a_new_unclassified_field() -> None:
    """负向对照：哪天有人在结果里加了「advice」这种新正文字段却没归类，守卫必须报出来。"""
    envelope = _envelope(ENVELOPES[0])
    envelope["advice"] = "宜守不宜攻"
    envelope["data"]["technique_card"]["new_note"] = "新备注"
    assert sorted(unclassified_text_paths(envelope)) == ["$.advice", "$.data.technique_card.new_note"]


def test_documents_convert_text_but_keep_machine_keys() -> None:
    document = {"schema": "horosa.skill.report.v1", "title": "八字报告", "language": "zh-TW", "run_id": "abc",
                "sections": [{"id": "basis", "title": "盘面依据", "body": "日干克时干"}], "input_normalized": {"q": "问事业"}}
    out = localize_document(document, TRADITIONAL)
    assert out["title"] == "八字報告" and out["sections"][0]["body"] == "日干剋時干"
    assert out["sections"][0]["id"] == "basis" and out["schema"] == document["schema"]
    assert out["input_normalized"] == {"q": "问事业"} and out["run_id"] == "abc"


# ── 送回来的标识对得回原名 ────────────────────────────────────────────────────


def test_every_section_title_survives_a_round_trip() -> None:
    from horosa_skill.exports.registry import build_export_registry, get_technique_info

    registry = build_export_registry()
    keys = [t["key"] for t in registry["techniques"]] if isinstance(registry.get("techniques"), list) else list(registry["techniques"])
    checked = 0
    for technique in keys:
        info = get_technique_info(technique)
        vocabulary = set(info["preset_sections"]) | set(info.get("optional_sections") or [])
        for title in vocabulary:
            for script in (SIMPLIFIED, *TRAD):
                assert canonical_name(convert(title, script), vocabulary) == title, (technique, title, script)
                checked += 1
    assert checked > 3000  # 783 个段名 × 3 种写法（2026-10-22）；变少说明词表没读全
    assert canonical_name("不存在的段", {"起盘信息"}) == "不存在的段"


def test_export_parse_accepts_section_names_copied_from_traditional_output() -> None:
    from horosa_skill.exports.parser import parse_export_content

    content = (PKG / "tests" / "fixtures" / "export_snapshots" / "bazi_live_snapshot.txt").read_text(encoding="utf-8")
    plain = parse_export_content(technique="bazi", content=content, selected_sections=["起盘信息", "五行力量"])
    copied = parse_export_content(technique="bazi", content=content, selected_sections=["起盤信息", "五行力量"])
    assert copied["selected_sections"] == plain["selected_sections"]
    assert [s["title"] for s in copied["sections"]] == [s["title"] for s in plain["sections"]]


def test_knowledge_search_and_read_accept_traditional_input() -> None:
    from horosa_skill.knowledge.store import read_knowledge_entry, search_knowledge

    plain = search_knowledge({"query": "紫微斗数", "limit": 3})
    folded = search_knowledge({"query": "紫微斗數", "limit": 3})
    assert folded["total_matched"] == plain["total_matched"] > 0
    assert folded["query"] == "紫微斗數" and folded["query_folded"] == "紫微斗数"
    assert search_knowledge({"query": "紫微斗数", "limit": 3}) == plain  # 简体输入行为逐字不变
    assert looks_traditional("紫微斗數") and not looks_traditional("紫微斗数")
    entry = read_knowledge_entry({"domain": "astro", "category": "planet", "key": "Sun"})
    assert entry["key"] == "Sun"


# ── 出口全覆盖 ───────────────────────────────────────────────────────────────


def _server(tmp_path: Path, script: str):
    from horosa_skill.config import Settings
    from horosa_skill.memory.store import MemoryStore
    from horosa_skill.service import HorosaSkillService
    from horosa_skill.surfaces.mcp_server import create_mcp_server

    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
                        db_path=tmp_path / "m.db", output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt",
                        output_script=script)
    return create_mcp_server(HorosaSkillService(settings, store=MemoryStore(settings)), settings)


async def _calls(mcp) -> dict:
    from mcp.shared.memory import create_connected_server_and_client_session

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        out = {}
        for name, args in (
            ("horosa_knowledge_read", {"query": "紫微斗数", "limit": 2}),
            ("horosa_cn_bazi_birth", {"date": "1990-01-01"}),  # 缺设置 → 门禁错误信封（不碰后端）
            ("horosa_agent_guidance", {"tool_name": "bazi_birth"}),
        ):
            result = await client.call_tool(name, args)
            out[name] = json.loads(result.content[0].text)
        tools = {tool.name for tool in (await client.list_tools()).tools}
    return {"results": out, "tools": tools}


def test_mcp_results_convert_at_the_exit_and_protocol_tools_do_not(tmp_path: Path) -> None:
    from horosa_skill.surfaces.mcp_runner import UNLOCALIZED_TOOLS

    simplified = asyncio.run(_calls(_server(tmp_path / "s", SIMPLIFIED)))
    traditional = asyncio.run(_calls(_server(tmp_path / "t", TRADITIONAL)))
    assert UNLOCALIZED_TOOLS <= simplified["tools"], "UNLOCALIZED_TOOLS 里有已经不存在的工具名"
    s, t = simplified["results"], traditional["results"]
    # 知识：正文转、键不转
    s_match, t_match = s["horosa_knowledge_read"]["data"]["matches"][0], t["horosa_knowledge_read"]["data"]["matches"][0]
    assert t_match["snippet"] == convert(s_match["snippet"], TRADITIONAL) and t_match["key"] == s_match["key"]
    # 门禁错误：提示转、错误码与选项不转
    s_err, t_err = s["horosa_cn_bazi_birth"], t["horosa_cn_bazi_birth"]
    assert t_err["code"] == s_err["code"] == "agent_guidance.required"
    s_prompt = s_err["details"]["agent_recovery"]["prompt_to_user"]
    assert t_err["details"]["agent_recovery"]["prompt_to_user"] == convert(s_prompt, TRADITIONAL) != s_prompt
    assert {k: v for k, v in t_err["details"].items() if k != "agent_recovery"} == {
        k: v for k, v in s_err["details"].items() if k != "agent_recovery"}
    # 协议工具逐字不变（只有 server_profile 报出当前设置）
    s_guide, t_guide = s["horosa_agent_guidance"], t["horosa_agent_guidance"]
    assert s_guide["server_profile"]["output_script"] == SIMPLIFIED and t_guide["server_profile"]["output_script"] == TRADITIONAL
    assert {k: v for k, v in s_guide.items() if k != "server_profile"} == {k: v for k, v in t_guide.items() if k != "server_profile"}


def test_simplified_server_never_calls_the_converter(tmp_path: Path, monkeypatch) -> None:
    import horosa_skill.surfaces.mcp_runner as runner

    monkeypatch.setattr(runner, "localize", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("converter ran")))
    result = asyncio.run(_calls(_server(tmp_path, SIMPLIFIED)))
    assert result["results"]["horosa_cn_bazi_birth"]["code"] == "agent_guidance.required"


def test_every_cli_command_that_prints_results_goes_through_the_converter() -> None:
    """CLI 打印 JSON 的命令：要么经 `_localized`，要么在 UNLOCALIZED_COMMANDS 里声明——新命令不归类就红。"""
    from horosa_skill.surfaces import cli

    tree = ast.parse((PKG / "src" / "horosa_skill" / "surfaces" / "cli.py").read_text(encoding="utf-8"))
    printing, localized = set(), set()
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or not any(
            isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "command"
            for d in node.decorator_list
        ):
            continue
        names = {n.func.id for n in ast.walk(node) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        if names & {"_emit_json", "_print_json"}:
            printing.add(node.name)
            if "_localized" in names:
                localized.add(node.name)
    unclassified = printing - localized - cli.UNLOCALIZED_COMMANDS
    assert not unclassified, f"这些命令打印结果却没经 _localized、也没在 UNLOCALIZED_COMMANDS 声明：{sorted(unclassified)}"
    assert cli.UNLOCALIZED_COMMANDS <= printing, f"UNLOCALIZED_COMMANDS 里有不存在的命令：{sorted(cli.UNLOCALIZED_COMMANDS - printing)}"
    assert {"tool_run", "dispatch", "hecan", "memory_show", "report_render", "knowledge_read"} <= localized


# ── 报告 ─────────────────────────────────────────────────────────────────────


def test_traditional_reports_pick_a_font_that_has_traditional_glyphs() -> None:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont

    from horosa_skill.reports.renderers import _docx_font_name, _register_pdf_fonts

    sample = convert("生克制化，刑冲合害，农历历日，紫微斗数，与为发", TRADITIONAL)
    for script in TRAD:
        name, _ = _register_pdf_fonts(pdfmetrics, UnicodeCIDFont, TTFont, script)
        font = pdfmetrics.getFont(name)
        face = getattr(font, "face", None)
        if hasattr(face, "charToGlyph"):
            missing = [ch for ch in sample if "一" <= ch <= "鿿" and ord(ch) not in face.charToGlyph]
            assert not missing, (name, missing)
        else:
            assert name == "MSung-Light"  # 繁体 CID 回退，不是简体的 STSong-Light
        assert _docx_font_name(script) in {
            "Microsoft JhengHei", "PingFang TC", "PingFang HK", "Songti TC", "Arial Unicode MS",
            "Noto Sans CJK TC", "Noto Sans CJK HK", "Arial"}


def test_report_language_follows_the_setting_unless_the_caller_set_it() -> None:
    from types import SimpleNamespace

    from horosa_skill.schemas.tools import ReportRenderInput
    from horosa_skill.service.api.reports import ReportsAPI

    host = SimpleNamespace(settings=SimpleNamespace(output_script=TRADITIONAL))
    implicit = ReportRenderInput.model_validate({"run_id": "x"})
    explicit = ReportRenderInput.model_validate({"run_id": "x", "language": "zh-CN"})
    assert ReportsAPI._report_language(host, implicit) == "zh-TW"
    assert ReportsAPI._report_language(host, explicit) == "zh-CN"
    host.settings.output_script = SIMPLIFIED
    assert ReportsAPI._report_language(host, implicit) == "zh-CN"
    assert ReportsAPI._report_script(host, "zh-HK") == TRADITIONAL_HK
    assert ReportsAPI._report_script(host, "en") == SIMPLIFIED
