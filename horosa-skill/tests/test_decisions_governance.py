"""治理面：旗标登记、hermetic 剥离、instructions 两态预算、doctor 视图、清单四处、族表锁、问题构造点 lint。"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from horosa_skill.benchmark.runner import _HERMETIC_KEEP_ENV
from horosa_skill.config import ENV_FLAG_REGISTRY
from horosa_skill.decisions.questions import MAX_CJK_RATIO_IN_INSTRUCTIONS, Choice, QuestionSpecError, cjk_ratio
from horosa_skill.decisions.surfaces.extract import build_gender_question
from horosa_skill.decisions.surfaces.routing import FAMILIES, build_routing_questions, family_of
from horosa_skill.decisions.surfaces.zhancat import ZHANDUAN_CATEGORIES, build_zhan_question
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.surfaces.mcp_server import _SERVER_INSTRUCTIONS, _server_instructions

REPO_ROOT = Path(__file__).resolve().parents[2]
PKG_ROOT = REPO_ROOT / "horosa-skill"
JEV_FLAGS = ("HOROSA_JEV", "HOROSA_JEV_API_KEY", "HOROSA_JEV_SCOPE", "HOROSA_JEV_SURFACES", "HOROSA_JEV_MODEL", "HOROSA_JEV_BASE_URL", "HOROSA_JEV_TIMEOUT_MS", "HOROSA_JEV_LEDGER")


def test_every_jev_flag_is_registered_as_experimental() -> None:
    for flag in JEV_FLAGS:
        assert ENV_FLAG_REGISTRY.get(flag) == "experimental", flag


def test_hermetic_bench_strips_the_decision_layer() -> None:
    """评测报告不许被本机的 HOROSA_JEV 改写结论：白名单里不能有任何 JEV 旗标。"""
    assert not any(key.startswith("HOROSA_JEV") for key in _HERMETIC_KEEP_ENV)


def test_instructions_fit_the_budget_in_both_states_and_off_is_byte_identical() -> None:
    off = _server_instructions(decision_layer_on=False)
    on = _server_instructions(decision_layer_on=True)
    assert off == _SERVER_INSTRUCTIONS
    assert len(off.encode("utf-8")) <= 2048 and len(on.encode("utf-8")) <= 2048
    assert "nothing is sent to a remote service" in off
    assert "nothing is sent to a remote service" not in on and "HOROSA_JEV is ON" in on and "TypeSafe Jev" in on


def test_doctor_report_has_a_keyless_decision_layer_section(monkeypatch, tmp_path: Path) -> None:
    from horosa_skill.decisions.policy import load_policy, load_thresholds

    key = "sk-doctor-1234567890abcdef1234567890"
    monkeypatch.setenv("HOROSA_JEV", "shadow")
    monkeypatch.setenv("HOROSA_JEV_API_KEY", key)
    view = load_policy().doctor_view(load_thresholds())
    assert view["mode"] == "shadow" and view["key_present"] is True
    assert key not in json.dumps(view, ensure_ascii=False)


def test_manifests_declare_the_two_user_config_entries_consistently() -> None:
    mcpb = json.loads((PKG_ROOT / "manifest.json").read_text(encoding="utf-8"))
    env = mcpb["server"]["mcp_config"]["env"]
    assert env["HOROSA_JEV"] == "${user_config.jev_mode}" and env["HOROSA_JEV_API_KEY"] == "${user_config.jev_api_key}"
    assert mcpb["user_config"]["jev_api_key"]["sensitive"] is True and mcpb["user_config"]["jev_mode"]["default"] == "off"

    plugin = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert plugin["userConfig"]["jevApiKey"]["sensitive"] is True and plugin["userConfig"]["jevMode"]["default"] == "off"
    mcp = json.loads((REPO_ROOT / ".claude-plugin" / "mcp.json").read_text(encoding="utf-8"))
    plugin_env = mcp["mcpServers"]["horosa"]["env"]
    assert plugin_env["HOROSA_JEV"] == "${user_config.jevMode}" and plugin_env["HOROSA_JEV_API_KEY"] == "${user_config.jevApiKey}"

    server = json.loads((REPO_ROOT / "server.json").read_text(encoding="utf-8"))
    blob = json.dumps(server)
    assert '"HOROSA_JEV_API_KEY"' in blob and '"isSecret": true' in blob and '"HOROSA_JEV"' in blob


def test_generated_client_configs_never_carry_the_key() -> None:
    """沿 HOROSA_MCP_TOKEN 先例：key 只在操作者环境里，永不写进任何生成的客户端配置。"""
    cli = (PKG_ROOT / "src" / "horosa_skill" / "surfaces" / "cli.py").read_text(encoding="utf-8")
    config_builder = cli[cli.index("def _build_client_config") if "def _build_client_config" in cli else 0 :]
    assert "HOROSA_JEV_API_KEY" not in config_builder.split("def jev_status")[0]


def test_routing_families_partition_the_registry_exactly() -> None:
    seen: list[str] = [tool for _desc, tools in FAMILIES.values() for tool in tools]
    assert len(seen) == len(set(seen)), "a tool appears in two families"
    assert set(seen) == set(TOOL_DEFINITIONS), f"registry − families: {sorted(set(TOOL_DEFINITIONS) - set(seen))}; families − registry: {sorted(set(seen) - set(TOOL_DEFINITIONS))}"
    assert family_of("liureng_gods") == "liureng" and family_of("nope") is None


def test_question_construction_points_follow_the_house_rules() -> None:
    """英文 instructions、ASCII 选项键、必带弃权项、Choice ≤255——每个面的问题都过同一把尺。"""
    questions = {**build_routing_questions(), "gender": build_gender_question(), "zhan": build_zhan_question()}
    assert len(build_routing_questions()) == len(FAMILIES) + 1
    for qid, question in questions.items():
        assert isinstance(question, Choice), qid
        assert cjk_ratio(question.instructions) <= MAX_CJK_RATIO_IN_INSTRUCTIONS, f"{qid}: instructions must be English-led"
        assert question.instructions[0].isascii(), f"{qid}: instructions must open in English"
        assert question.abstain in question.criteria, qid
        assert all(re.match(r"^[A-Za-z][A-Za-z0-9_]*$", key) for key in question.criteria), qid
    assert set(ZHANDUAN_CATEGORIES) >= {"hunyin", "taichan", "jibing", "caiyun", "guansong", "qiuming", "shiwu", "xingren", "chuxing", "zhaiyun", "tianshi", "general"}


def test_question_spec_rejects_missing_abstain_and_chinese_instructions() -> None:
    with pytest.raises(QuestionSpecError):
        Choice(instructions="Pick.", criteria={"a": "A", "b": "B"}, abstain="unknown")
    with pytest.raises(QuestionSpecError):
        Choice(instructions="请选择一个", criteria={"a": "A", "unknown": "none"}, abstain="unknown")
    with pytest.raises(QuestionSpecError):
        Choice(instructions="Pick.", criteria={f"o{i}": None for i in range(256)} | {"unknown": None}, abstain="unknown")


# ---------------------------------------------------------------- 错误信息是接口（v0.39.0 发布前 CI 红过一次）
# `verify_error_recovery.py` 的双语棘轮按文件计数、只挡**总量**上升（别处还了 5 处债、这里新欠 3 处也过）。decisions/ 是新包，
# 这里零容忍：每个带字面 message 的 raise 都必须「中文 / English」。
_CJK_RE = re.compile(r"[一-鿿]")
_LATIN_RE = re.compile(r"[A-Za-z]{3,}")


def single_language_raises(sources: dict[str, str]) -> list[str]:
    import ast

    offenders: list[str] = []
    for name, text in sorted(sources.items()):
        for node in ast.walk(ast.parse(text)):
            if not (isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call) and node.exc.args):
                continue
            first = node.exc.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                message = first.value
            elif isinstance(first, ast.JoinedStr):
                message = "".join(v.value for v in first.values if isinstance(v, ast.Constant) and isinstance(v.value, str))
            else:
                continue
            if not (_CJK_RE.search(message) and _LATIN_RE.search(message)):
                offenders.append(f"{name}:{node.lineno}")
    return offenders


def test_every_raise_in_the_decisions_package_is_bilingual() -> None:
    pkg = REPO_ROOT / "horosa-skill" / "src" / "horosa_skill" / "decisions"
    sources = {py.relative_to(pkg).as_posix(): py.read_text(encoding="utf-8") for py in pkg.rglob("*.py")}
    assert sources, "decisions package not found"
    assert single_language_raises(sources) == []


def test_bilingual_raise_guard_catches_a_single_language_message() -> None:
    bad = 'def f():\n    raise ValueError("response.model missing")\n'
    good = 'def f():\n    raise ValueError(f"response.model 缺失 / response.model missing")\n'
    dynamic = 'def f(msg):\n    raise ValueError(msg)\n'
    assert single_language_raises({"bad.py": bad, "good.py": good, "dynamic.py": dynamic}) == ["bad.py:2"]
