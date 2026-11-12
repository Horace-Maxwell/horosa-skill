"""SKILL.md 与 references 里的示例调用 ↔ 真实工具面（v0.50.0 文档批）。

弱模型照抄示例：一个写错的参数名、一个读不懂的时区、一个字符串 "true"，抄过去就是一次拒绝或一张算错的盘。
示例写在 ```call 代码块里，一行一个 `<MCP 工具名> <JSON 参数>`（`//` 开头是注释）；`<run_id>` 这类尖括号占位换成假 id。
每一条离线逐项核对（不碰引擎）：

1. 工具名在全量面的 tools/list 里（`horosa_tool_run` 在精简面），`tool_name` 认得出；
2. 参数过得了该工具广告出去的 JSON Schema；
3. 每个顶层参数名都是这个工具真读的字段（广告属性、输入模型字段、通用入口 place / name / profile、视图参数、登记的别名）——
   多出来的名字在线上只会进 warnings、什么都不改；
4. 技法载荷过逐字段校验（precheck_arguments：确认位是 JSON 布尔、日期 / 时刻 / 时区 / 经纬度 / 性别读得懂），且归一化不留
   「这些参数不是本技法的参数」的说明；门面载荷过它的输入模型；
5. 澄清闸放行（地名按已解析处理；带命主档案的跳过：闸门那时要读档案库）。

线上真跑由文档批对共享引擎逐条执行（见 CHANGELOG）；这里守的是「示例不会随代码改动悄悄烂掉」。负向对照在文件末尾。
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from fakes import FakeClient, FakeJsClient

from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS, resolve_tool_name
from horosa_skill.input_fields import input_notes_scope
from horosa_skill.input_normalization import FIELD_ALIASES, NON_TECHNIQUE_KEYS, normalize_request_payload
from horosa_skill.memory.store import MemoryStore
from horosa_skill.profiles import carries_profile
from horosa_skill.result_view import VIEW_KNOBS
from horosa_skill.schemas.tools import (
    AgentGuidanceInput,
    DispatchInput,
    HecanInput,
    KnowledgeSearchInput,
    MemoryAnswerInput,
    MemoryQueryInput,
    MemoryShowInput,
    PlaceSearchInput,
    ProfileInput,
    ReportFromToolInput,
    ReportRenderInput,
    ReportTemplateInput,
    TechniqueReportInput,
)
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces.mcp_errors import _agent_preflight_error
from horosa_skill.surfaces.mcp_requests import COMMON_TECHNIQUE_PARAMS, gate_view_arguments, precheck_arguments
from horosa_skill.surfaces.mcp_server import create_mcp_server

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "horosa-agent"
FENCE = re.compile(r"```call\n(.*?)```", re.S)
LINE = re.compile(r"^(?P<tool>horosa_\w+)\s+(?P<args>\{.*\})\s*$")
PLACEHOLDER = re.compile(r'"<[^"<>]+>"')
FAKE_RUN_ID = "0123456789abcdef0123456789abcdef"

FACADE_MODELS: dict[str, Any] = {
    "horosa_agent_guidance": AgentGuidanceInput,
    "horosa_dispatch": DispatchInput,
    "horosa_hecan": HecanInput,
    "horosa_knowledge_search": KnowledgeSearchInput,
    "horosa_memory_record_answer": MemoryAnswerInput,
    "horosa_memory_query": MemoryQueryInput,
    "horosa_memory_show": MemoryShowInput,
    "horosa_place_search": PlaceSearchInput,
    "horosa_profile": ProfileInput,
    "horosa_report_from_tool": ReportFromToolInput,
    "horosa_report_render": ReportRenderInput,
    "horosa_report_template": ReportTemplateInput,
    "horosa_technique_report": TechniqueReportInput,
}
GATED_FACADES = {"horosa_dispatch": "dispatch", "horosa_hecan": "hecan"}
# 地名在线上先解析成坐标与时区再过闸（mcp_server._gate_view_with_places）；离线用一组固定值代替解析结果。
RESOLVED_PLACE = {"lat": "31n13", "lon": "121e28", "zone": "+08:00"}
PARTY_SLOTS = ("birth", "context", "inner", "outer")


def examples(root: Path = SKILL_ROOT) -> list[tuple[str, str, dict[str, Any]]]:
    """(文件名, 工具名, 参数) —— 全部 ```call 块，按出现顺序。"""
    found: list[tuple[str, str, dict[str, Any]]] = []
    for path in [root / "SKILL.md", *sorted((root / "references").glob("*.md"))]:
        for block in FENCE.findall(path.read_text(encoding="utf-8")):
            for raw in block.splitlines():
                line = raw.strip()
                if not line or line.startswith("//"):
                    continue
                match = LINE.match(line)
                assert match, f"{path.name}: a ```call line must be `<tool> <json>`: {line[:80]}"
                found.append((path.name, match["tool"], json.loads(match["args"])))
    return found


def _substitute(args: dict[str, Any]) -> dict[str, Any]:
    return json.loads(PLACEHOLDER.sub(json.dumps(FAKE_RUN_ID), json.dumps(args, ensure_ascii=False)))


def _placed(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    out = {key: (_placed(value) if key in PARTY_SLOTS or key == "subject" else value) for key, value in payload.items()}
    if out.get("place"):
        out = {**RESOLVED_PLACE, **{k: v for k, v in out.items() if k != "place"}}
    return out


def _server(tmp_path: Path, *, compact: bool):
    settings = Settings(db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs", mcp_compact=compact)
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    return create_mcp_server(service, settings)


@pytest.fixture(scope="module")
def surfaces(tmp_path_factory) -> dict[str, dict[str, Any]]:
    listed: dict[str, dict[str, Any]] = {}
    for compact in (False, True):
        mcp = _server(tmp_path_factory.mktemp("compact" if compact else "full"), compact=compact)
        for tool in asyncio.run(mcp.list_tools()):
            listed.setdefault(tool.name, tool.model_dump(mode="json", by_alias=True, exclude_unset=True)["inputSchema"])
    return listed


def _technique_problems(key: str, payload: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    model = TOOL_DEFINITIONS[key].input_model
    allowed = set(model.model_fields) | NON_TECHNIQUE_KEYS | set(COMMON_TECHNIQUE_PARAMS) | set(VIEW_KNOBS) | set(FIELD_ALIASES)
    problems += [f"`{name}` is not a field of {key}" for name in payload if name not in allowed]
    error = precheck_arguments(key, payload)
    if error is not None:
        problems.append(f"{key}: precheck refused ({error.code}): {str(error)[:200]}")
        return problems
    if not carries_profile(payload, model):
        body = {k: v for k, v in payload.items() if k not in VIEW_KNOBS}
        with input_notes_scope() as notes:
            normalize_request_payload(_placed(body), model=model, tool_name=key)
        # 只认示例自己写的键：归一化从 lon 派生的 gpsLon 之类不算示例的错（那是工具自己的告警）。
        problems += [f"{key}: {note}" for note in notes
                     if "不是本技法的参数" in note and any(f"`{name}`" in note for name in body)]
        refusal = _agent_preflight_error(key, gate_view_arguments(key, _placed(body)))
        if refusal is not None:
            problems.append(f"{key}: the gate refuses this example ({refusal.get('code')})")
    return problems


def example_problems(tool: str, args: dict[str, Any], surfaces: dict[str, dict[str, Any]]) -> list[str]:
    """一条示例的全部问题（空 = 照抄可用）。"""
    args = _substitute(args)
    schema = surfaces.get(tool)
    if schema is None:
        return [f"`{tool}` is not on the MCP surface"]
    problems = [f"schema: {error.message}" for error in jsonschema.Draft202012Validator(schema).iter_errors(args)]
    advertised = set(schema.get("properties", {}))
    if tool == "horosa_tool_run":
        key = resolve_tool_name(str(args.get("tool_name") or ""))
        if key not in TOOL_DEFINITIONS:
            return [*problems, f"tool_name `{args.get('tool_name')}` is not a technique"]
        request = args.get("request") or {}
        payload = {**{k: v for k, v in args.items() if k not in ("tool_name", "request")}, **request}
        return problems + _technique_problems(key, payload)
    key = resolve_tool_name(tool)
    if key in TOOL_DEFINITIONS:
        return problems + _technique_problems(key, args)
    model = FACADE_MODELS.get(tool)
    if model is None:
        return [*problems, f"no example check for `{tool}` (add its input model to FACADE_MODELS)"]
    problems += [f"`{name}` is not a parameter of {tool}" for name in args
                 if name not in advertised and name not in model.model_fields and name not in VIEW_KNOBS]
    try:
        model.model_validate(_placed({k: v for k, v in args.items() if k not in VIEW_KNOBS or k in model.model_fields}))
    except Exception as exc:  # noqa: BLE001 - 报出来即可
        problems.append(f"{tool}: input model refused: {str(exc)[:200]}")
    gate = GATED_FACADES.get(tool)
    if gate and not carries_profile(args, model):
        error = precheck_arguments(gate, args)
        if error is not None:
            problems.append(f"{tool}: precheck refused ({error.code})")
        elif (refusal := _agent_preflight_error(gate, gate_view_arguments(gate, _placed(args)))) is not None:
            problems.append(f"{tool}: the gate refuses this example ({refusal.get('code')})")
    return problems


def test_the_skill_carries_examples_and_every_one_is_a_call() -> None:
    found = examples()
    assert len(found) >= 15, "the extractor found too few ```call examples — did the fence format change?"
    assert any(name == "SKILL.md" for name, _tool, _args in found)


@pytest.mark.parametrize(("source", "tool", "args"), examples(), ids=lambda value: value if isinstance(value, str) else None)
def test_every_example_matches_the_tool_surface(source: str, tool: str, args: dict[str, Any], surfaces) -> None:
    assert example_problems(tool, args, surfaces) == [], f"{source}: {tool}"


@pytest.mark.parametrize(
    ("tool", "args", "needle"),
    [
        ("horosa_cn_bazi_brith", {"date": "1990-05-03"}, "not on the MCP surface"),
        ("horosa_astro_chart", {"date": "1990-05-03", "time": "08:00", "place": "上海", "hosue_system": 3,
                                "defaults_accepted": True}, "hosue_system"),
        ("horosa_cn_bazi_birth", {"date": "1990-05-03", "time": "08:00", "zone": "CST", "lat": "31n13", "lon": "121e28",
                                  "gender": "女", "defaults_accepted": True}, "tool.invalid_zone"),
        ("horosa_cn_bazi_birth", {"date": "1990-05-03", "time": "08:00", "place": "上海", "gender": "女",
                                  "defaults_accepted": "true"}, "tool.confirmation_flag_not_boolean"),
        ("horosa_cn_bazi_birth", {"date": "1990-05-03", "time": "08:00", "place": "上海", "defaults_accepted": True},
         "the gate refuses"),
        ("horosa_astro_chart", {"date": "1990-05-03", "time": "08:00", "place": "上海"}, "the gate refuses"),
        ("horosa_tool_run", {"tool_name": "palmistry"}, "not a technique"),
        ("horosa_memory_query", {"person": "妈妈"}, "`person` is not a parameter"),
        ("horosa_dispatch", {"query": "起一卦", "defaults_accepted": True}, "the gate refuses"),
        ("horosa_memory_show", {"run_id": 5}, "schema"),
    ],
)
def test_the_checker_catches_broken_examples(tool: str, args: dict[str, Any], needle: str, surfaces) -> None:
    """负向对照：错的工具名、拼错的参数、读不懂的时区、字符串确认位、缺性别、未答设置、缺起课时刻、未知门面参数、类型错，各自必红。"""
    problems = example_problems(tool, args, surfaces)
    assert any(needle in problem for problem in problems), problems


def test_the_extractor_rejects_a_malformed_call_line(tmp_path: Path) -> None:
    (tmp_path / "references").mkdir()
    (tmp_path / "SKILL.md").write_text("```call\nhorosa_cn_qimen date=2026\n```\n", encoding="utf-8")
    with pytest.raises(AssertionError):
        examples(tmp_path)
