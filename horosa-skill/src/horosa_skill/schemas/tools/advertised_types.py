"""广告层（tools/list）专用的类型登记：`Any | None` 字段在 tools/list 上广告成什么 type（v0.48.0）。

为什么放在 schema 包里而不是 surfaces/mcp_schema.py：这是 schema 的**元数据**（和模型上的 `ADVERTISE_HIDDEN` 同类），
不是消费者。`scripts/verify_schema_knob_wiring.py` 的草堆排除整个 schema 包——「schema 自己提到自己不算接线」；
放进 surfaces 会让只靠后端消费的旋钮（如印占大运年长 / 星曜战判据）在那把守卫眼里「突然有了消费者」，债务虚降。

pydantic 把 `Any | None` 写成 anyOf:[{}, {"type":"null"}]——非空那支没有类型。v0.48.0 之前广告层的折叠把 "null" 当成唯一类型
发出去（42 个属性 / 18 个工具），严格客户端据此只许传 null。可移植层要求恰一个标量 type（verify_mcp_client_compat 禁 anyOf、
缺 type 即红），所以这里逐键按 runner **实际收的形状**登记；多形态的键取 runner 收的其中一种写法。只改广告层，校验层照旧 Any。
键是字段名：同名字段在各工具上语义相同；不登记的无类型字段回落 "string"，`tests/test_mcp_advertised_types.py` 会点名要求登记，
表里的死条目同样会红。
"""
from __future__ import annotations

from typing import Any

UNTYPED_FIELD_TYPES: dict[str, dict[str, Any]] = {
    # 择日 / 天星条件树：vendored compile* 只收 `typeof tree === 'object'`（组节点），JSON 串会被当成缺条件。
    "conditions": {"type": "object"},
    # 后端把它们当 lat/lon 原样起盘（build_relocation / _compute_tajaka），样例与上游页面都发 "51n30" 形的串。
    "relocLat": {"type": "string"}, "relocLon": {"type": "string"},
    "varshaLat": {"type": "string"}, "varshaLon": {"type": "string"},
    # 值域闸 `_require_option(value in 字符串键表)`：只收字符串键。
    "pdMethod": {"type": "string"}, "pdTimeKey": {"type": "string"},
    # 档位键：择日流派 / 卜卦考量硬度 / 阿拉伯点集 / 四化流派，引擎都按字符串比对。
    "school": {"type": "string"}, "considerationsMode": {"type": "string"},
    "lotsSet": {"type": "string"}, "sihuaSchool": {"type": "string"},
    # 印占（webindiasrv）：indiaHsys → hsys 整数 0–24；indiaAyanamsa → siderealMode 键（lahiri…）。
    "indiaHsys": {"type": "integer"}, "indiaAyanamsa": {"type": "string"},
    # resolve_variants / normalize_varga_variants 收 dict 或 JSON 串：广告 dict。
    "dashaVariants": {"type": "object"}, "vargaVariant": {"type": "object"},
    # float() + 五档白名单（365.25 / 365.2425 / 360 / 365.2422 / 365.2563）。
    "dashaYearLength": {"type": "number"},
    # 引擎按 str(x) == '7' 判，上游页面发 '7' / '8'；战判据 'latitude' / 'longitude'。
    "karakaScheme": {"type": "string"}, "yuddhaCriterion": {"type": "string"},
    # _normalize_india_extra_vargas 收列表或 "9,7" 串：广告整数列表。
    "indiaExtraVargas": {"type": "array", "items": {"type": "integer"}},
    # 后端 `if data.get('tripataki')` 真值判。
    "tripataki": {"type": "boolean"},
    # 问事族：prashnaTime 走 str()；prashnaSchools 是 str(…).split(',')——**列表会被 str() 成 "['kp']" 而失效**，只能广告逗号串。
    "prashnaTime": {"type": "string"}, "prashnaSchools": {"type": "string"},
    "prashnaMatter": {"type": "string"}, "prashnaCuspMode": {"type": "string"},
    "prashnaNumber": {"type": "integer"}, "prashnaPrimaryHouse": {"type": "integer"},
    # Tājika 年盘：int(tajakaYear)；annualChartType 'varsha' / 'tithi'。
    "tajakaYear": {"type": "integer"}, "annualChartType": {"type": "string"},
}
