"""客户端可移植性守卫的孪生测试。

核心那条是「旧检查为什么全绿」：修复前 116 个工具里有 70 个空类型属性、116 个数组 type、
108 个 additionalProperties:true、106 个漏出的私有键，而 `test_mcp_contract` / `test_mcp_list_budget`
全绿 —— 因为它们查的是 `$ref` 不在、字节数不超、字段在不在，**没有一条查过「这个 schema 严格
客户端吃不吃得下」**。Gemini/Vertex 与 OpenAI strict 遇到这些是拒**整张工具表**，所以症状不是
「某个参数不好使」，而是「这个 server 在某某客户端里一个工具都没有」。
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

PKG_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PKG_ROOT / "scripts"


def _load():
    spec = importlib.util.spec_from_file_location("verify_mcp_client_compat", SCRIPTS / "verify_mcp_client_compat.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def guard():
    return _load()


@pytest.fixture()
def clean_tool() -> dict:
    """一个通过全部断言的最小工具。"""
    return {
        "name": "horosa_cn_qimen",
        "title": "奇门遁甲",
        "description": "起奇门盘。",
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
        "inputSchema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "公历日期"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
        },
    }


def test_guard_is_green_on_the_real_surfaces(guard) -> None:
    result = guard.measure()
    errors = [e for surface in result["surfaces"].values() for e in surface["errors"]]
    assert errors == [], errors[:10]


def test_clean_tool_passes(guard, clean_tool) -> None:
    assert guard.audit_tool(clean_tool) == []


@pytest.mark.parametrize(
    ("mutate", "needle"),
    [
        # 修复前的真实形状：_widen 把 anyOf pop 掉不补 type → 70 个属性长这样
        (lambda s: s["properties"].__setitem__("gpsLat", {}), "空对象"),
        (lambda s: s["properties"].__setitem__("gpsLat", {"title": "Gpslat"}), "没有 type"),
        # 修复前：116/116 个工具都有数组 type
        (lambda s: s["properties"]["date"].__setitem__("type", ["string", "number"]), "type 是数组"),
        # 修复前：108 个工具写 true
        (lambda s: s.__setitem__("additionalProperties", True), "additionalProperties"),
        # 修复前：106 个工具漏出这个私有键
        (lambda s: s.__setitem__("x-horosa-hidden-knobs", 47), "私有键"),
        # 修复前：门面直接发 pydantic 原样 schema
        (lambda s: s["properties"]["date"].__setitem__("default", None), "`default`"),
        (lambda s: s["properties"].__setitem__("q", {"anyOf": [{"type": "string"}, {"type": "null"}]}), "anyOf"),
        # Gemini 会因为 array 没有 items 直接 400
        (lambda s: s["properties"]["tags"].pop("items"), "items"),
        (lambda s: s.__setitem__("required", ["nope"]), "required 指向不存在"),
    ],
)
def test_negative_controls_on_schema(guard, clean_tool, mutate, needle: str) -> None:
    mutate(clean_tool["inputSchema"])
    errors = guard.audit_tool(clean_tool)
    assert any(needle in e for e in errors), f"期望抓到 {needle!r}，实得 {errors}"


@pytest.mark.parametrize(
    ("mutate", "needle"),
    [
        (lambda t: t.__setitem__("description", "x" * 1100), "1024"),
        (lambda t: t.__setitem__("description", "  "), "描述为空"),
        (lambda t: t.__setitem__("title", ""), "缺 title"),
        (lambda t: t.pop("annotations"), "缺 annotations"),
        (lambda t: t.__setitem__("name", "horosa_" + "x" * 60), "Gemini"),
        (lambda t: t.__setitem__("name", "bad name!"), "工具名不符"),
    ],
)
def test_negative_controls_on_metadata(guard, clean_tool, mutate, needle: str) -> None:
    mutate(clean_tool)
    errors = guard.audit_tool(clean_tool)
    assert any(needle in e for e in errors), f"期望抓到 {needle!r}，实得 {errors}"


def test_why_the_old_checks_could_not_catch_it(guard, clean_tool) -> None:
    """把修复前的真实形状拼出来，证明旧断言全绿而新守卫红。

    旧断言（逐条来自 test_mcp_contract.py / test_mcp_list_budget.py 的修前版本）：
      · `"$ref" not in json.dumps(schema)`     —— 修前确实没有 $ref，绿
      · `not schema.get("required")`           —— 修前确实没有 required，绿
      · `schema["additionalProperties"] is True` —— 修前正是 true，绿（还**要求**它是 true！）
      · 字节数 < 256 KB                         —— 修前 259 KB < 262 KB，绿
    四条全绿，而这个 schema 在 Gemini/Vertex 与 OpenAI strict 下会让整张工具表被拒。
    """
    broken = copy.deepcopy(clean_tool)
    broken["inputSchema"] = {
        "type": "object",
        "properties": {
            "gpsLat": {"title": "Gpslat"},                       # ← _widen pop 掉 anyOf 的残骸
            "lat": {"type": ["string", "number"], "description": "纬度"},
            "request": {"type": ["object", "string"], "description": "整包载荷"},
        },
        "additionalProperties": True,
        "x-horosa-hidden-knobs": 47,
    }
    schema = broken["inputSchema"]
    blob = json.dumps(schema)

    # 旧断言：全部通过
    assert "$ref" not in blob
    assert not schema.get("required")
    assert schema["additionalProperties"] is True
    assert len(blob) < 256 * 1024

    # 新守卫：必须红，且逐条点名
    errors = guard.audit_tool(broken)
    assert any("空对象" in e or "没有 type" in e for e in errors)
    assert any("type 是数组" in e for e in errors)
    assert any("additionalProperties" in e for e in errors)
    assert any("私有键" in e for e in errors)
