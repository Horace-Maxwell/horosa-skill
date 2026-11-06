"""导出契约里不属于服务层的两样：工具 → 导出键的表、缺段时填的那句护栏。

knowledge / reports 都要用它们，放在 service 里就成了下层 import 上层（tests/test_layering.py）。
"""
from __future__ import annotations

from typing import Any

from horosa_skill.engine.registry import TOOL_DEFINITIONS

# 不起盘的门面，没有导出契约。
_NO_EXPORT_TECHNIQUE = frozenset({"export_parse", "export_registry", "knowledge_read", "knowledge_registry"})
# 导出键与工具名不同的工具；其余工具的导出键就是工具名，加技法不用动这里。
# 上游把出盘页面一族按页拆键（aiExport.js 的 ASTRO_LIKE_EXPORT_KEYS）：希腊盘与调波盘各有自己的导出键，
# 不再共用 astrochart_like，否则两者的导出勾选会互相串。
_EXPORT_TECHNIQUE_OVERRIDES: dict[str, str] = {
    "chart": "astrochart",
    "chart13": "astrochart_like",
    "chart12": "dwadasamsa",
    "hellen_chart": "hellenastro",
    "guolao_chart": "guolao",
    "pd": "primarydirect",
    "pdchart": "primarydirchart",
    "zr": "zodialrelease",
    "india_chart": "indiachart",
    "ziwei_birth": "ziwei",
    "ziwei_rules": "ziwei",
    "bazi_birth": "bazi",
    "bazi_direct": "bazi",
    "liureng_gods": "liureng",
    "liureng_runyear": "liureng",
    "jieqi_year": "jieqi",
    "nongli_time": "generic",
    "calendar_month": "calendar",
    "gua_desc": "sixyao",
    "gua_meiyi": "sixyao",
}


def _derive_export_technique_map(tool_names: Any, *, overrides: dict[str, str]) -> dict[str, str]:
    return {name: overrides.get(name, name) for name in tool_names if name not in _NO_EXPORT_TECHNIQUE}


# bench 生成 case 与导出契约挂接都吃这张表（tests/test_benchmark.py 核对每个键都在导出注册表里）。
TOOL_EXPORT_TECHNIQUE_MAP: dict[str, str] = _derive_export_technique_map(TOOL_DEFINITIONS, overrides=_EXPORT_TECHNIQUE_OVERRIDES)


def missing_detail_text(title: str) -> str:
    """引擎这次没给内容的段填这句：写给 AI 的护栏，不是给人看的正文。"""
    return (
        f"本次本地计算结果未返回「{title}」细项；"
        "报告只能基于已返回盘面判断，不能臆造外部依赖、桌面端服务或不存在的数据。"
    )
