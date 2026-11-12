"""错误码测试债的偿还（C-18 尾巴，v0.50.0-dev）：每个码由真实调用路径产出，断言码本身。

`scripts/verify_error_recovery.py` 规则 4 只认测试里**字符串字面量**中出现的码（注释、docstring 不算——此前算，
于是八个只在说明文字里被提到的码也记作「测过」）。这里每一行都从公开入口（门面 / run_tool）或该码所在的那一层调起：
入口校验已先拦住的「第二道闸」（如 runner 里的日期 / 性别检查）直接调 runner，证明那道闸自己也还在。
离线可达的都在这里；剩下的（要真 runtime / 真下载 / 真 Jev 的）留在 contracts/error_code_test_debt.json。
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from fakes import FakeClient, FakeJsClient

from horosa_skill.config import Settings
from horosa_skill.engine.client import HorosaApiClient
from horosa_skill.errors import HorosaSkillError, ToolTransportError, engine_tool_code
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.service.options_cn import _split_birth_ymdhm
from horosa_skill.testing_payloads import build_sample_payloads

SAMPLES = build_sample_payloads()


@pytest.fixture(scope="module")
def service(tmp_path_factory: pytest.TempPathFactory) -> HorosaSkillService:
    tmp = tmp_path_factory.mktemp("paydown")
    settings = Settings(db_path=tmp / "m.db", output_dir=tmp / "runs", runtime_root=tmp / "rt", data_dir=tmp / "data")
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())


def _tool(tool: str, **extra: Any) -> Callable[[HorosaSkillService], Any]:
    return lambda svc: svc.run_tool(tool, {**SAMPLES[tool], **extra, "agent_confirmed_settings": True}, save_result=False)


def _code(call: Callable[[], Any]) -> str | None:
    try:
        result = call()
    except HorosaSkillError as exc:
        return exc.code
    if getattr(result, "ok", True) is False:
        return result.error.code
    return None


CASES: dict[str, Callable[[HorosaSkillService], Any]] = {
    # 门面的载荷校验
    "hecan.invalid_payload": lambda svc: svc.hecan({"query": "x", "max_tools": "lots"}),
    "memory.answer.invalid_payload": lambda svc: svc.record_ai_answer({"run_id": 5}),
    "report.from_tool.invalid_payload": lambda svc: svc.report_from_tool({"tool_name": 3}),
    "report.render.invalid_payload": lambda svc: svc.report_render({"run_id": {"x": 1}}),
    "report.technique.invalid_payload": lambda svc: svc.technique_report({"include_sections": {"x": 1}}),
    "report.template.invalid_payload": lambda svc: svc.report_template({"run_id": ["x"]}),
    "knowledge.search.empty_query": lambda svc: svc.knowledge_search({"query": "  "}),
    "knowledge.search.invalid_payload": lambda svc: svc.knowledge_search({"query": "x", "limit": "many"}),
    # 知识精读：每个域 / 类目的「查无此键」
    "knowledge.astro.unknown_key": _tool("knowledge_read", domain="astro", category="planet", key="Nope"),
    "knowledge.helpdoc.unknown_key": _tool("knowledge_read", domain="yanqin", category="手册", key="绝不存在的键"),
    "knowledge.unknown_category": _tool("knowledge_read", domain="yanqin", category="nope", key="x"),
    "knowledge.liureng.unknown_key": _tool("knowledge_read", domain="liureng", category="shen", key="nope"),
    "knowledge.liureng.unknown_category": _tool("knowledge_read", domain="liureng", category="nope", key="x"),
    "knowledge.liureng.unknown_jiang": _tool("knowledge_read", domain="liureng", category="house", key="不存在的将"),
    "knowledge.liureng.invalid_branch": _tool("knowledge_read", domain="liureng", category="house", key="贵人",
                                              tian_branch="子", di_branch="zz"),
    "knowledge.qimen.unknown_key": _tool("knowledge_read", domain="qimen", category="door", key="nope"),
    # 技法 runner 自己的参数闸
    "tool.invalid_argument": _tool("xuanshi", action="zzz"),
    "tool.invalid_export_technique": lambda svc: svc.run_tool(
        "export_parse", {"technique": "nope", "content": "[x]\n1", "agent_confirmed_settings": True}, save_result=False),
    "tool.qimenzeri_missing_conditions": _tool("qimenzeri", conditions=None, tree=None),
    "tool.qizhengelection_unknown_action": _tool("qizhengelection", action="zzz"),
    "tool.wangji_invalid_xinyi_method": _tool("wangji", xinyiMethod="zzz"),
    "tool.suzhan_nongli_timealg_invalid": _tool("suzhan", nongliTimeAlg=7),
    # 第二道闸：入口的逐字段校验先拦（tool.invalid_date / tool.invalid_gender）；runner 层的闸直接调，证明它还在
    "tool.qimen_invalid_date": lambda svc: svc._run_qimen_tool({**SAMPLES["qimen"], "date": "abcd"}),
    "tool.sixyao_invalid_gender": lambda svc: svc._run_sixyao_tool({**SAMPLES["sixyao"], "gender": "女"}),
    "tool.shenshu_bad_date": lambda _svc: _split_birth_ymdhm({"date": "not a date", "time": "12:00:00"}),
}


@pytest.mark.parametrize("code", sorted(CASES))
def test_each_code_comes_out_of_its_real_path(service: HorosaSkillService, code: str) -> None:
    assert _code(lambda: CASES[code](service)) == code


@pytest.mark.parametrize("endpoint", ["/nongli/time", "/chart"])
def test_a_non_json_answer_is_transport_invalid_json(endpoint: str) -> None:
    """Java 聚合层与星盘服务两条路各自的「回了非 JSON」分支（client.py 两处）。"""
    client = HorosaApiClient("http://127.0.0.1:9999",
                             transport=httpx.MockTransport(lambda _request: httpx.Response(200, text="<html>proxy login</html>")))
    with pytest.raises(ToolTransportError) as caught:
        client.call(endpoint, {"date": "2028-04-06"})
    assert caught.value.code == "transport.invalid_json"
    assert caught.value.details["endpoint"] == endpoint


def test_scan_engines_fall_back_to_the_scan_failed_family() -> None:
    """择日 runner 把引擎错误码按族收口：认得的族原样（invalid_conditions），认不出的落到调用点给的缺省族 scan_failed。"""
    assert engine_tool_code("qimenzeri", None, "scan_failed") == "tool.qimenzeri_scan_failed"
    assert engine_tool_code("qimenzeri", "invalid_conditions", "scan_failed") == "tool.qimenzeri_invalid_conditions"


def test_the_paid_codes_left_the_debt_file() -> None:
    import json

    debt = set(json.loads((Path(__file__).resolve().parents[1] / "contracts" / "error_code_test_debt.json")
                          .read_text(encoding="utf-8"))["untested"])
    assert not debt & set(CASES)
