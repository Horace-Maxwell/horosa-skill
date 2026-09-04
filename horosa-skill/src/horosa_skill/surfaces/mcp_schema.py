"""tools/list 广告层瘦身（v0.36.0 B1）：两层 schema —— 广告的是「域核心 + 工具自有字段」，校验的仍是全模型。

为什么不能直接瘦 `__signature__`：FastMCP 按签名生成的 arg model 是 `extra="ignore"`，签名里没有的顶层键
会被静默丢掉（A6 那一类病）。所以签名保持全字段（校验层），注册后只重写 `Tool.parameters`（广告层）。
效果：默认全量 tools/list 1186 KB → ≤256 KB；精简面 93 KB → ≤30 KB（`scripts/verify_mcp_list_budget.py` 棘轮）。

广告层规则：
- BirthInput 族：域核心（西占/推运/chart：date/time/zone/lat/lon/ad/hsys/zodiacal/siderealAyanamsa；中式/神数：
  去掉宫制/黄道/岁差，加 gender/timeAlg）+ 推运目标字段（PREDICTIVE_INPUT_CONTRACTS）+ 工具自有字段（模型上
  非 BirthInput 继承的字段）+ 闸门三键 + `request` 逃生舱（注明还有 N 个高级旋钮按名接受，全表见
  horosa_agent_guidance）；`additionalProperties: true`。
- 非 BirthInput 的小模型：全部字段照广告（本来就小）。
- 枚举只进广告层：hsys（西占用 ASTRO_HOUSE_SYSTEM_TEXT，印占用 INDIA_HOUSE_SYSTEM_LABELS）、zodiacal、ad、
  response_view、siderealAyanamsa（47 制）。
- dispatch/hecan：5 路 union 内联两次（各 24 KB）→ 单一宽松对象。
- 描述：去掉每工具重复的澄清闸段（server instructions 已讲），只留技法双语一句 + 指引一行。
"""
from __future__ import annotations

from typing import Any

from horosa_skill.agent_guidance import PREDICTIVE_INPUT_CONTRACTS
from horosa_skill.astro_sidereal import INDIA_HOUSE_SYSTEM_LABELS, SIDEREAL_AYANAMSA_LABELS
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.schemas.tools import BirthInput

GATE_KEYS: tuple[str, ...] = ("agent_confirmed_settings", "defaults_accepted", "clarification_notes")
# name/pos（显示名）已声明、顶层照收，但不进广告层：两字段 × 80 工具 ≈ 10 KB，只是盘头文字。
ASTRO_CORE: tuple[str, ...] = (
    "date", "time", "zone", "lat", "lon", "ad", "hsys", "zodiacal", "siderealAyanamsa", "response_view",
)
CN_CORE: tuple[str, ...] = ("date", "time", "zone", "lat", "lon", "ad", "gender", "timeAlg", "response_view")
DOMAIN_CORE: dict[str, tuple[str, ...]] = {
    "astro": ASTRO_CORE,
    "predict": ASTRO_CORE,
    "chart": ASTRO_CORE,
    "cn": CN_CORE,
    "shenshu": CN_CORE,
}
# 域核心字段的短描述（广告层专用；校验层的长描述仍在模型上，guidance 可查）。
CORE_DOC: dict[str, str] = {
    "date": "公历日期 YYYY-MM-DD",
    "time": "HH:mm:ss",
    "zone": "时区偏移，如 +08:00",
    "lat": "纬度 31n13 / 31.22",
    "lon": "经度 121e28 / 121.47",
    "ad": "纪元 1=公元后（默认） -1=公元前",
    "hsys": "宫制索引（见 enum；1=Alcabitus，3=Placidus）",
    "zodiacal": "0=回归（默认） 1=恒星（配 siderealAyanamsa）",
    "siderealAyanamsa": "恒星黄道岁差制（zodiacal=1 时）",
    "name": "当事人姓名（透传盘头）",
    "pos": "地点显示名",
    "gender": "性别 1/男 0/女",
    "timeAlg": "0=真太阳时 1=钟表时",
    "response_view": "响应裁剪：full|sections|titles（完整结果已存档）",
    "agent_confirmed_settings": "用户已确认设置→true",
    "defaults_accepted": "用户接受默认→true",
    "clarification_notes": "确认摘要",
}
CORE_TYPE: dict[str, Any] = {
    "date": "string", "time": "string", "zone": "string", "lat": ["string", "number"], "lon": ["string", "number"],
    "ad": "integer", "hsys": "integer", "zodiacal": "integer", "siderealAyanamsa": "string", "name": "string",
    "pos": "string", "gender": ["integer", "string"], "timeAlg": "integer", "response_view": "string",
    "agent_confirmed_settings": "boolean", "defaults_accepted": "boolean", "clarification_notes": "string",
}
OWN_FIELD_DOC_LIMIT = 72  # 字符；工具自有字段描述超长截断（全文见 horosa_agent_guidance）


def _enum_for(field: str, tool_name: str) -> dict[str, Any]:
    if field == "hsys":
        table = INDIA_HOUSE_SYSTEM_LABELS if tool_name.startswith("india") else {int(k): v for k, v in _astro_house_table().items()}
        short = {"整宫制": "整宫", "Vehlow Equal": "Vehlow", "Polich Page": "PolichPage", "天顶为10宫中点等宫制": "MC10宫等宫"}
        legend = " ".join(f"{k}={short.get(table[k], table[k])}" for k in sorted(table))
        return {"enum": sorted(table), "description": legend}
    if field == "zodiacal":
        return {"enum": [0, 1]}
    if field == "ad":
        return {"enum": [1, -1]}
    if field == "response_view":
        return {"enum": ["full", "sections", "titles"]}
    if field == "siderealAyanamsa":
        # 47 制的 enum 每工具 600 B × 80 工具 = 48 KB，超预算；只给常用键，全表见 guidance。
        common = [k for k in ("lahiri", "raman", "krishnamurti", "fagan_bradley", "yukteshwar") if k in SIDEREAL_AYANAMSA_LABELS]
        return {"description": f"恒星黄道岁差制（zodiacal=1 时）；共 {len(SIDEREAL_AYANAMSA_LABELS)} 制，常用 {'/'.join(common)}，全表见 guidance"}
    return {}


def _astro_house_table() -> dict[str, str]:
    # 延迟导入：service 模块很重，且 mcp_schema 不能反向让 service 依赖它。
    from horosa_skill.service import ASTRO_HOUSE_SYSTEM_TEXT

    return ASTRO_HOUSE_SYSTEM_TEXT


def _core_property(field: str, tool_name: str, required: bool) -> dict[str, Any]:
    prop: dict[str, Any] = {"type": CORE_TYPE.get(field, "string"), "description": CORE_DOC.get(field, field)}
    prop.update(_enum_for(field, tool_name))  # enum 源自带 description 时覆盖短描述（hsys 全表 / 岁差制）
    if required:
        prop["description"] = f"[required] {prop['description']}"
    return prop


def _own_property(field: str, full_prop: dict[str, Any], required: bool) -> dict[str, Any]:
    prop = {k: v for k, v in full_prop.items() if k in {"type", "enum", "items", "anyOf", "description"}}
    desc = str(prop.get("description") or "").strip()
    if len(desc) > OWN_FIELD_DOC_LIMIT:
        prop["description"] = desc[: OWN_FIELD_DOC_LIMIT - 1] + "…"
    if "anyOf" in prop and "type" not in prop:
        types = sorted({str(a.get("type")) for a in prop["anyOf"] if isinstance(a, dict) and a.get("type")})
        prop.pop("anyOf", None)
        prop["type"] = types if len(types) > 1 else (types[0] if types else "string")
    if "items" in prop and isinstance(prop["items"], dict):
        prop["items"] = {k: v for k, v in prop["items"].items() if k in {"type", "enum"}} or {}
    if required and not str(prop.get("description", "")).startswith("[required]"):
        prop["description"] = f"[required] {prop.get('description', '')}".strip()
    return prop


def _request_property(hidden: list[str], tool_name: str) -> dict[str, Any]:
    text = "整包载荷"
    if hidden:
        text += f"；另 {len(hidden)} 个高级旋钮顶层按名可传（全表见 guidance）"
    return {"type": ["object", "string"], "description": text}


def advertised_technique_schema(tool_name: str, full_schema: dict[str, Any]) -> dict[str, Any]:
    """技法工具的广告层 inputSchema（校验层不动）。"""
    definition = TOOL_DEFINITIONS[tool_name]
    model = definition.input_model
    props = dict(full_schema.get("properties") or {})
    required = {k for k, v in props.items() if isinstance(v, dict) and v.get("x-horosa-required")}
    keep: list[str] = []
    if issubclass(model, BirthInput):
        core = DOMAIN_CORE.get(definition.domain, ASTRO_CORE)
        targets = list(PREDICTIVE_INPUT_CONTRACTS.get(tool_name, {}).get("required_fields") or [])
        own = [f for f in model.model_fields if f not in BirthInput.model_fields]
        for key in (*core, *targets, *own, *GATE_KEYS):
            if key in props and key not in keep:
                keep.append(key)
    else:
        keep = [f for f in model.model_fields if f in props]
    hidden = sorted(set(props) - set(keep) - {"request"})
    out: dict[str, Any] = {}
    for key in keep:
        if key in CORE_DOC:
            out[key] = _core_property(key, tool_name, key in required)
        else:
            out[key] = _own_property(key, props[key], key in required)
    out["request"] = _request_property(hidden, tool_name)
    return {"type": "object", "properties": out, "additionalProperties": True, "x-horosa-hidden-knobs": len(hidden)}


def advertised_dispatch_schema(*, hecan: bool) -> dict[str, Any]:
    props: dict[str, Any] = {
        "query": {"type": "string", "description": "[required] 用户原话（选盘依据）", "x-horosa-required": True},
        "birth": {
            "type": "object",
            "description": "出生/起课信息：date/time/zone/lat/lon（+ gender 等技法字段），按所选技法校验",
            "additionalProperties": True,
        },
        "subject": {"type": "object", "description": "当事人：name/year 等（可选）", "additionalProperties": True},
        "context": {"type": "object", "description": "补充上下文：time/zone/lat/lon 等", "additionalProperties": True},
        "preferences": {"type": "object", "description": "偏好/流派设置", "additionalProperties": True},
        "save_result": {"type": "boolean", "description": "默认 true：写入记忆"},
        "agent_confirmed_settings": {"type": "boolean", "description": CORE_DOC["agent_confirmed_settings"]},
        "defaults_accepted": {"type": "boolean", "description": CORE_DOC["defaults_accepted"]},
        "clarification_notes": {"type": "string", "description": CORE_DOC["clarification_notes"]},
        "request": {"type": ["object", "string"], "description": "整包载荷（对象或 JSON 串）"},
    }
    if hecan:
        props["tools"] = {"type": "array", "items": {"type": "string"}, "description": "显式指定技法（缺省由路由选盘）"}
        props["max_tools"] = {"type": "integer", "description": "合参技法上限（默认 5）"}
    return {"type": "object", "properties": props, "additionalProperties": True}


def advertised_description(tool_name: str) -> str:
    definition = TOOL_DEFINITIONS[tool_name]
    return f"{definition.description.strip()}\n口径/输出段/全部旋钮：horosa_agent_guidance(tool_name=\"{tool_name}\")"


def apply_advertised_schemas(mcp: Any) -> dict[str, int]:
    """注册完成后重写各工具的广告层 schema/描述；返回 {mcp_name: 隐藏旋钮数}（测试/棘轮用）。"""
    manager = getattr(mcp, "_tool_manager", None)
    if manager is None:
        return {}
    by_mcp_name = {definition.mcp_name: name for name, definition in TOOL_DEFINITIONS.items()}
    hidden: dict[str, int] = {}
    for tool in manager.list_tools():
        tool_name = by_mcp_name.get(tool.name)
        if tool_name is not None:
            slim = advertised_technique_schema(tool_name, tool.parameters or {})
            tool.parameters = slim
            tool.description = advertised_description(tool_name)
            hidden[tool.name] = int(slim.get("x-horosa-hidden-knobs", 0))
        elif tool.name in {"horosa_dispatch", "horosa_hecan"}:
            tool.parameters = advertised_dispatch_schema(hecan=tool.name == "horosa_hecan")
    return hidden
