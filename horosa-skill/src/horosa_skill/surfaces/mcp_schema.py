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

import copy
import functools
import inspect
import re
from typing import Any

from horosa_skill.agent_guidance import PREDICTIVE_INPUT_CONTRACTS
from horosa_skill.astro_sidereal import INDIA_HOUSE_SYSTEM_LABELS, SIDEREAL_AYANAMSA_LABELS
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.engine.synonyms import synonyms_for
from horosa_skill.profiles import PROFILE_KEY, owns_profile_key
from horosa_skill.schemas.tools import BirthInput
from horosa_skill.schemas.tools.advertised_types import UNTYPED_FIELD_TYPES
from horosa_skill.schemas.tools.base import advertise_hidden_fields
from horosa_skill.surfaces.mcp_requests import COMMON_TECHNIQUE_PARAMS, tool_run_field_docs

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
# v0.48.0 瘦身：这些描述每份要乘 50–100 个工具，所以只写键名说不出的东西（格式 / 取值 / 口径），
# 不再复述键名本身（date→「日期」、zone→「时区」、lat→「纬度」、gender→「性别」、response_view→「响应」）。`tests/test_mcp_list_slim.py` 锁每工具的共享开销。
CORE_DOC: dict[str, str] = {
    "date": "公历 YYYY-MM-DD",
    "time": "HH:mm:ss",
    "zone": "偏移，如 +08:00",
    "lat": "31n13 / 31.22",
    "lon": "121e28 / 121.47",
    "ad": "-1=公元前",
    "hsys": "宫制索引（见 enum；1=Alcabitus，3=Placidus）",
    "zodiacal": "0=回归（默认） 1=恒星",
    "siderealAyanamsa": "恒星黄道岁差制（zodiacal=1 时）",
    "name": "当事人姓名（透传盘头）",
    "pos": "地点显示名",
    "place": "地名",
    "gender": "1/男 0/女",
    "timeAlg": "0=真太阳时 1=钟表时",
    "response_view": "full=原始树",
    "agent_confirmed_settings": "用户已确认设置→true",
    "defaults_accepted": "用户接受默认→true",
    "clarification_notes": "确认摘要",
}
CORE_TYPE: dict[str, Any] = {
    "date": "string", "time": "string", "zone": "string", "lat": ["string", "number"], "lon": ["string", "number"],
    "ad": "integer", "hsys": "integer", "zodiacal": "integer", "siderealAyanamsa": "string", "name": "string",
    "pos": "string", "place": "string", "gender": ["integer", "string"], "timeAlg": "integer", "response_view": "string",
    "agent_confirmed_settings": "boolean", "defaults_accepted": "boolean", "clarification_notes": "string",
}
# 两个截断上限 v0.46.x 收紧（72→64、200→150）：推运图族四法 +4 工具后全量面逼近 256 KB 硬顶，截掉的只是广告层的长尾文字，
# 全文仍在 horosa_agent_guidance / 技法目录资源（verify_mcp_list_budget.py 量）。
OWN_FIELD_DOC_LIMIT = 64  # 字符；工具自有字段描述超长截断（全文见 horosa_agent_guidance）
DESCRIPTION_CHAR_LIMIT = 150  # 字符；技法双语描述超长截断（全文在 guidance / 技法目录资源）


def _enum_for(field: str, tool_name: str) -> dict[str, Any]:
    if field == "hsys":
        # 哪张宫制表跟着校验层走（模型的 HSYS_FAMILY，schemas/tools/base.py）：广告的 enum 与真正收下的值同一张表。
        family = getattr(TOOL_DEFINITIONS[tool_name].input_model, "HSYS_FAMILY", "astro") if tool_name in TOOL_DEFINITIONS else "astro"
        table = INDIA_HOUSE_SYSTEM_LABELS if family == "india" else {int(k): v for k, v in _astro_house_table().items()}
        short = {"整宫制": "整宫", "Vehlow Equal": "Vehlow", "Polich Page": "PolichPage", "天顶为10宫中点等宫制": "MC10宫等宫"}
        legend = " ".join(f"{k}={short.get(table[k], table[k])}" for k in sorted(table))
        return {"enum": sorted(table), "description": legend}
    if field == "zodiacal":
        return {"enum": [0, 1]}
    if field == "ad":
        return {"enum": [1, -1]}
    if field == "response_view":
        return {"enum": ["reading", "sections", "titles", "full"]}
    if field == "siderealAyanamsa":
        # 47 制的 enum 每工具 600 B × 80 工具 = 48 KB，超预算；只给常用键，全表见 guidance。
        # 只举三制：印度标准 lahiri、西方恒星派 fagan_bradley、raman（v0.46.x 预算收紧，其余见 guidance）。
        common = [k for k in ("lahiri", "fagan_bradley", "raman") if k in SIDEREAL_AYANAMSA_LABELS]
        # 「见 guidance」不重复：工具描述末行已指 horosa_agent_guidance（v0.48.0）。
        return {"description": f"zodiacal=1 时：{'/'.join(common)}…共 {len(SIDEREAL_AYANAMSA_LABELS)} 制"}
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


# `Any | None` 字段（anyOf:[{}, {"type":"null"}]）广告成什么 type：逐键登记在 schema 包里
# （`schemas/tools/advertised_types.py`，那里写了为什么不放在这里）。
def _collapse_types(field: str, prop: dict[str, Any]) -> None:
    """anyOf 折叠成广告层的 type：去掉 "null"（可空只是「可不传」，不是一种可传的值）；非空支没有类型就查 UNTYPED_FIELD_TYPES。"""
    members = [a for a in prop.pop("anyOf", None) or [] if isinstance(a, dict)]
    types = sorted({str(a["type"]) for a in members if a.get("type") and a.get("type") != "null"})
    if types:
        prop["type"] = types if len(types) > 1 else types[0]
        return
    prop.update(copy.deepcopy(UNTYPED_FIELD_TYPES.get(field, {"type": "string"})))  # 表是共享的，别让下游改到它


def _own_property(field: str, full_prop: dict[str, Any], required: bool) -> dict[str, Any]:
    prop = {k: v for k, v in full_prop.items() if k in {"type", "enum", "items", "anyOf", "description"}}
    desc = str(prop.get("description") or "").strip()
    if len(desc) > OWN_FIELD_DOC_LIMIT:
        prop["description"] = desc[: OWN_FIELD_DOC_LIMIT - 1] + "…"
    if "type" not in prop:
        _collapse_types(field, prop)
    if "items" in prop and isinstance(prop["items"], dict):
        prop["items"] = {k: v for k, v in prop["items"].items() if k in {"type", "enum"}} or {}
    if required and not str(prop.get("description", "")).startswith("[required]"):
        prop["description"] = f"[required] {prop.get('description', '')}".strip()
    return prop


def _request_property(hidden: list[str], tool_name: str) -> dict[str, Any]:
    text = "整包载荷"
    if hidden:
        # 「见 guidance」不再重复：工具描述末行已指 horosa_agent_guidance（v0.46.x 预算）。
        text += f"；另 {len(hidden)} 个高级旋钮可顶层按名传"
    return {"type": ["object", "string"], "description": text}


def _own_fields(model: type[Any], unadvertised: set[str]) -> list[str]:
    """BirthInput 子类自有的字段（广告层要列的那些），按子类里的声明顺序。

    判据是「不在 BirthInput 里」；唯一例外是 `profile`：基类 FlexibleModel 声明它当命主档案名（隐藏、零字节），天文地占又把它
    声明成传本流派旋钮——后者是地占自有字段，照旧广告。pydantic 把重声明的字段排在继承位置，这里按子类声明的位置放回去，
    地占的广告层逐字节不变（tests/test_profiles.py）。"""
    owned = [f for f in model.model_fields if f not in BirthInput.model_fields]
    if owns_profile_key(model):
        order: list[str] = []
        for cls in reversed(model.__mro__):
            if isinstance(cls, type) and issubclass(cls, BirthInput) and cls is not BirthInput:
                order += [name for name in inspect.get_annotations(cls) if name not in order]
        owned = [name for name in order if name in model.model_fields and (name not in BirthInput.model_fields or name == PROFILE_KEY)]
    return [f for f in owned if f not in unadvertised]


def advertised_technique_schema(tool_name: str, full_schema: dict[str, Any]) -> dict[str, Any]:
    """技法工具的广告层 inputSchema（校验层不动）。"""
    definition = TOOL_DEFINITIONS[tool_name]
    model = definition.input_model
    props = dict(full_schema.get("properties") or {})
    required = {k for k, v in props.items() if isinstance(v, dict) and v.get("x-horosa-required")}
    keep: list[str] = []
    # 「已声明、不广告」两种声明法取并集：模型级 `ADVERTISE_HIDDEN`（西占长尾旋钮）与字段级 `x-horosa-hidden`
    # （v0.40 mingli：紫微 22 传本键 / 八字盘法键等长词表）。校验层照收（MCP 顶层按名可传），只从广告层剔除、
    # 计入隐藏旋钮数；键表与取值进 horosa_agent_guidance。🔴 曾合并成后者覆盖前者 → 西占旋钮全部回到广告层，
    # tools/list 一次 +8 KB 逼近 256 KB 硬顶（verify_mcp_list_budget 抓到）。
    unadvertised = set(advertise_hidden_fields(model)) | {
        k for k, v in props.items() if isinstance(v, dict) and v.get("x-horosa-hidden")
    }
    if issubclass(model, BirthInput):
        core = DOMAIN_CORE.get(definition.domain, ASTRO_CORE)
        targets = list(PREDICTIVE_INPUT_CONTRACTS.get(tool_name, {}).get("required_fields") or [])
        own = _own_fields(model, unadvertised)
        # 域核心也许按工具声明「不广告」（推运图族四法只按回归黄道算 → zodiacal / siderealAyanamsa 只改盘头文字）；
        # 推运目标字段与闸门三键永远广告。
        core = tuple(key for key in core if key not in unadvertised)
        for key in (*core, *targets, *own, *GATE_KEYS):
            if key in props and key not in keep:
                keep.append(key)
    else:
        keep = [f for f in model.model_fields if f in props and f not in unadvertised]
    # `knowledge`（自备知识库）与 `profile`（命主档案名）是全技法通用的附加参数，不是本技法的旋钮：不计数，否则 44 个原本没有
    # 隐藏旋钮的技法平白多一句「另 1 个高级旋钮」（全量面 +2.9 KB）。它们在 SKILL.md、tool_run 的 schema 与 server_profile 里说明。
    # `place` / `name`（v0.50.0，mcp_requests.COMMON_TECHNIQUE_PARAMS）同理不计数；模型自己声明的 name 照旧计入。
    common_added = {key for key in COMMON_TECHNIQUE_PARAMS if key not in model.model_fields}
    if "place" in props and "place" not in model.model_fields and "place" not in keep:
        keep.append("place")  # 地名是给位置的首选写法（SKILL.md），广告给每个收地点的技法
    docs = _field_docs()
    out: dict[str, Any] = {}
    for key in keep:
        if key in CORE_DOC:
            out[key] = _core_property(key, tool_name, key in required)
            continue
        prop = _own_property(key, props[key], key in required)
        bare = str(prop.get("description") or "").removeprefix("[required]").strip()
        if not bare:
            if key in docs:
                prop["description"] = ("[required] " if key in required else "") + docs[key]
            elif key not in required and key not in _SHAPED_DOC:
                continue  # MCP-11：说不清是什么的旋钮不广告（照样按名接受、计入隐藏旋钮数，全表见 guidance）
        out[key] = _shaped(key, prop)
    hidden = sorted(set(props) - set(out) - {"request", "knowledge", PROFILE_KEY} - common_added)
    out["request"] = _request_property(hidden, tool_name)
    return {"type": "object", "properties": out, "additionalProperties": True, "x-horosa-hidden-knobs": len(hidden)}


def _field_docs() -> dict[str, str]:
    global _FIELD_DOCS
    if _FIELD_DOCS is None:
        from horosa_skill.surfaces.mcp_field_docs import field_docs

        _FIELD_DOCS = field_docs()
    return _FIELD_DOCS


_FIELD_DOCS: dict[str, str] | None = None

# 嵌套的一方（合盘 inner / outer）：广告成带 properties 的对象，模型才知道里面放什么（MCP-11：旧广告是一个无形状的值）。
_PARTY_KEYS = ("date", "time", "zone", "lat", "lon", "ad", "name")
_SHAPED_DOC = {"inner": "内圈一方：date/time/zone/lat/lon（同顶层口径）", "outer": "外圈一方：date/time/zone/lat/lon（同顶层口径）"}


def _shaped(key: str, prop: dict[str, Any]) -> dict[str, Any]:
    if key not in _SHAPED_DOC:
        return prop
    required = str(prop.get("description") or "").startswith("[required]")
    return {
        "type": "object",
        "x-horosa-shaped": True,  # 只有登记过形状的对象保留 properties（portable_property）
        "description": ("[required] " if required else "") + _SHAPED_DOC[key],
        "properties": {name: {"type": _scalar(CORE_TYPE.get(name, "string")), "description": CORE_DOC.get(name, name)}
                       for name in _PARTY_KEYS},
    }


def _scalar(kind: Any) -> str:
    return kind[0] if isinstance(kind, list) else str(kind)


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
        "knowledge": {"type": ["array", "string"], "items": {"type": "string"}, "description": "自备知识库：条目名,#标签,auto"},
        "request": {"type": ["object", "string"], "description": "整包载荷（对象或 JSON 串）"},
    }
    if hecan:
        props["tools"] = {"type": "array", "items": {"type": "string"}, "description": "显式指定技法（缺省由路由选盘）"}
        props["max_tools"] = {"type": "integer", "description": "合参技法上限（默认 5）"}
    return {"type": "object", "properties": props, "additionalProperties": True}


AKA_LIMIT = 4
# 描述尾行不带 `(tool_name="…")`（v0.48.0，114 份 × 约 25 B）：模型手里就是本工具的名字，
# guidance 两种写法都收（`engine/registry.resolve_tool_name`）。
GUIDANCE_TAIL = "旋钮/输出段：horosa_agent_guidance"


# 「整词出现」的边界：字母数字与汉字之外的任何字符（空格、标点、括号、/、·）或首尾。
# 只认整词：「星盘」嵌在「西洋星盘」里不算出现——按空格 / 标点切词的工具搜索索引里，那只是「西洋星盘」一个词。
_WORD_CHAR = r"0-9A-Za-z\u3400-\u9fff\uf900-\ufaff"


_WORD_CHAR_RE = re.compile(rf"[{_WORD_CHAR}]", flags=re.IGNORECASE)


@functools.lru_cache(maxsize=None)
def _term_regex(term: str) -> re.Pattern[str]:
    return re.compile(re.escape(term), flags=re.IGNORECASE)


def _appears_as_term(term: str, text: str) -> bool:
    """`(?<![词字符])term(?![词字符])` 的等价写法（忽略大小写）。

    合成一条正则时，每个别名都要重编一遍带整段汉字区间的字符类（IGNORECASE 下尤其慢）：393 次 0.78 s，是
    create_mcp_server 最大的一块（C-20）。字符类只编一次，逐个候选位置检查两侧；候选从每次命中的下一格接着找，
    与 lookaround 的逐位置扫描同一结果（自重叠的词也不漏）。
    """
    pattern = _term_regex(term)
    pos = 0
    while (match := pattern.search(text, pos)) is not None:
        start, end = match.span()
        before_ok = start == 0 or _WORD_CHAR_RE.fullmatch(text[start - 1]) is None
        after_ok = end == len(text) or _WORD_CHAR_RE.fullmatch(text[end]) is None
        if before_ok and after_ok:
            return True
        if start >= len(text):
            break
        pos = start + 1
    return False


def advertised_aka(tool_name: str, head: str) -> list[str]:
    """`aka:` 行的别名：先按 `aka_line` 的口径取前 AKA_LIMIT 个，再去掉描述首段里已作为**整词**出现的。

    去掉的词仍以同一个整词留在这条描述里（工具搜索、模型都看得到），所以描述里可见的词集合不变，只省重复的字节（v0.48.0）。
    不往后补位：补位会让某些工具的描述变长。
    """
    picked = [s for s in synonyms_for(tool_name) if s.lower() != tool_name.lower()][:AKA_LIMIT]
    return [s for s in picked if not _appears_as_term(s, head)]


def advertised_description(tool_name: str) -> str:
    definition = TOOL_DEFINITIONS[tool_name]
    desc = definition.description.strip()
    if len(desc) > DESCRIPTION_CHAR_LIMIT:
        desc = desc[: DESCRIPTION_CHAR_LIMIT - 1] + "…"
    aka = advertised_aka(tool_name, desc)
    return f"{desc}\n{'aka: ' + ', '.join(aka) + '；' if aka else ''}{GUIDANCE_TAIL}"



# ---------------------------------------------------------------------------
# 可移植广告层（v0.37.0）
#
# 广告层与校验层是分开的：校验走 `_signature_for_input_model` 的 `Annotated[Any, …]`（一律宽松），
# 广告层只影响客户端**看到**什么。所以把广告层收窄到「最低公分母客户端也能吃」是**零功能损失**的：
# 服务器照样接受 request 传 JSON 字符串、lat/lon 传数字、顶层塞隐藏旋钮。
#
# 各客户端的硬约束（2026-09 实测/官方文档）：
#   · Gemini CLI / Vertex FunctionDeclaration：每个属性必须有**单个** type；数组必须有 items；
#     拒 $ref/$defs；严格按 JSON Schema 2020-12 校验 —— 违反时拒的是**整张工具表**。
#   · OpenAI strict function calling：不接受 type 数组、不接受 additionalProperties: true。
#   · 私有 x-* 键：部分客户端按未知关键字直接报错。
# ---------------------------------------------------------------------------

# 允许在属性里出现的键；其余（default/title/format/x-*/$…）一律剔除。
_PORTABLE_PROP_KEYS = frozenset({"type", "enum", "items", "description", "properties"})


def _portable_type(prop: dict[str, Any], name: str) -> str:
    """把 anyOf / type 数组收敛成**恰一个**标量 type。"""
    candidates: list[str] = []
    declared = prop.get("type")
    if isinstance(declared, str):
        candidates = [declared]
    elif isinstance(declared, list):
        candidates = [str(x) for x in declared if x and x != "null"]
    if not candidates:
        for entry in prop.get("anyOf") or []:
            if isinstance(entry, dict) and entry.get("type") and entry.get("type") != "null":
                candidates.append(str(entry["type"]))
    if not candidates:
        return "string"
    if len(candidates) == 1:
        return candidates[0]
    # 多类型：字符串永远是安全的收窄口径 —— 服务端的 normalize 层本来就吃字符串
    # （"31.22" → "31n13"、"1" → 1），而 object 联合体（request）另有专门处理。
    return "object" if "object" in candidates else "string"


def portable_property(name: str, prop: dict[str, Any]) -> dict[str, Any]:
    """单个属性的可移植化：恰一个 type、数组有 items、无私有键、绝不返回 {}。"""
    out = {k: v for k, v in prop.items() if k in _PORTABLE_PROP_KEYS}
    out["type"] = _portable_type(prop, name)
    if out["type"] == "array":
        items = out.get("items")
        if not isinstance(items, dict) or not items.get("type"):
            # Gemini 会因为「array 没有 items」直接 400 INVALID_ARGUMENT。
            out["items"] = {"type": "string"}
        else:
            out["items"] = {k: v for k, v in items.items() if k in {"type", "enum"}}
    else:
        out.pop("items", None)
    if out["type"] == "object" and prop.get("x-horosa-shaped") and isinstance(out.get("properties"), dict):
        # 嵌套对象的字段同样可移植化（合盘 inner / outer）；其余对象不带 properties（形状由技法自己校验）。
        out["properties"] = {str(k): portable_property(str(k), v if isinstance(v, dict) else {}) for k, v in out["properties"].items()}
    else:
        out.pop("properties", None)
    if not str(out.get("description") or "").strip():
        out.pop("description", None)
    return out


def portable_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """整张 inputSchema 的可移植化。幂等。"""
    if not isinstance(schema, dict):
        return {"type": "object", "properties": {}}
    out: dict[str, Any] = {"type": "object"}
    props = schema.get("properties")
    out["properties"] = {
        str(name): portable_property(str(name), prop if isinstance(prop, dict) else {})
        for name, prop in (props or {}).items()
    }
    # additionalProperties: true 在 2020-12 里等于「缺省」，但 OpenAI strict 见到 true 会拒；
    # 隐藏旋钮走顶层透传的能力不受影响（服务端不校验广告层）。
    if schema.get("additionalProperties") is False:
        out["additionalProperties"] = False
    if isinstance(schema.get("required"), list) and schema["required"]:
        out["required"] = [str(x) for x in schema["required"]]
    return out


def _with_tool_run_docs(schema: dict[str, Any]) -> dict[str, Any]:
    """`horosa_tool_run` 的公共字段补广告层描述（`mcp_requests.tool_run_field_docs`，只补缺；签名不动）。"""
    docs = tool_run_field_docs()
    props = {
        name: (
            {**prop, "description": docs[name]}
            if isinstance(prop, dict) and name in docs and not str(prop.get("description") or "").strip()
            else prop
        )
        for name, prop in (schema.get("properties") or {}).items()
    }
    return {**schema, "properties": props}


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
        elif tool.name == "horosa_tool_run":
            tool.parameters = _with_tool_run_docs(tool.parameters or {})
    # 🔴 最后对**全部**工具跑一遍可移植化 —— 包括门面工具与 horosa_tool_run。
    # 此前只有技法 + dispatch/hecan 被重写，门面直接把 pydantic 的原始 schema
    # （anyOf:[…,{null}] / default:null / title / $ref）发上线；而在精简面下门面**就是**全部工具。
    # 门面不走技法的广告白名单，基类上的隐藏字段（`knowledge`）也要在这里摘掉，否则每个门面各漏一个无描述属性。
    docs = _field_docs()
    for tool in manager.list_tools():
        params = tool.parameters or {}
        props = params.get("properties")
        if isinstance(props, dict):
            params = {**params, "properties": {
                k: v for k, v in props.items()
                if not (isinstance(v, dict) and v.get("x-horosa-hidden"))
                # MCP-11：不过闸的门面不广告闸门三键（它们在那里什么也不做，只会让模型以为要先确认）
                and not (k in GATE_KEYS and tool.name in UNGATED_FACADES)
            }}
        params = portable_schema(params)
        # 门面字段缺描述的，从共享词典补（一个字段名一句）。
        params["properties"] = {
            k: ({**v, "description": docs[k]} if not str(v.get("description") or "").strip() and k in docs else v)
            for k, v in params["properties"].items()
        }
        _enum_closed_sets(tool.name, params["properties"])
        tool.parameters = params
    return hidden


# 不过澄清闸的门面（report_from_tool 的闸门看的是 payload 里那份技法入参，顶层三键同样不起作用）。
UNGATED_FACADES = frozenset({
    "horosa_agent_guidance", "horosa_knowledge_search", "horosa_place_search", "horosa_profile",
    "horosa_memory_record_answer", "horosa_memory_query", "horosa_memory_show", "horosa_report_template",
    "horosa_report_render", "horosa_technique_report", "horosa_report_from_tool",
})
# 闭集取值进 enum（MCP-11）：模型照着 enum 填，不用从描述里猜。
_REPORT_FORMATS = ["json", "docx", "pdf", "png", "ics"]
_CLOSED_SETS: dict[tuple[str, str], list[Any]] = {
    ("horosa_report_render", "format"): _REPORT_FORMATS,
    ("horosa_report_from_tool", "format"): _REPORT_FORMATS,
    ("horosa_report_render", "style"): ["analysis", "chart"],
    ("horosa_technique_report", "format"): ["markdown", "json", "docx", "pdf"],
}


def _enum_closed_sets(tool_name: str, props: dict[str, Any]) -> None:
    for (owner, field), values in _CLOSED_SETS.items():
        if owner == tool_name and isinstance(props.get(field), dict):
            props[field] = {**props[field], "type": "string", "enum": list(values)}
