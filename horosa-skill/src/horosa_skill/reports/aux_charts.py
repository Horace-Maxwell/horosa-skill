"""出报告时补算的盘图：星阙 app 画着、结果里却没有那张盘的几个技法。

app 的页面在结果之外另取一张盘来画：
- 推运图族（演进推运 / Bezza 推运图 / 周日小限）：DirectedFigurePage 用同一请求带 `withChart` 时后端另起的外圈整盘，与本命盘
  画成双盘（AstroDoubleChart）。工具调用特意发 `withChart: 0`（~100 KB，正文不读）。
- 推运 / 恒星推运（次限）：ProgMethodPanel 拿所选推运法（缺省 secondary）的推运时刻另起 /chart，画本命 / 推运双盘。
- 天星择日：页面中栏是选中命中时刻的西占单轮；结果只有命中区间。
- 产前朔望：页面左图是朔望那一刻的整盘；结果只留了星体位置。
- 七政择日 / 七政四余：七政页（择日页内嵌的也是它）缺省画 Moira 圆盘（GuoLaoMoiraWheel），要 Moira 规则全集 + 流年盘 +
  择日端点的静盘宫位；结果只留正文用的几键。

做法（一套机制）：报告服务出图前按存档的入参 + 结果里实际用过的时刻，经真引擎补算那张盘（不存档、不改工具返回体，
`ReportsAPI._aux_engine_charts`），这里把它变成盘图规格：西洋轮同时带自绘版（Node / 出图包不可用时照样有图）与 app 请求
（`app_request`，`app_charts.plan` 原样转交）；Moira 盘只有 app 画法（kind="app"）。补算或出图失败时报告照出，原有的图不动，
并把「缺了什么、为什么」写进 `figure_gaps`（正文盘图节下印出）。这里不算任何位置（铁律 1）：盘全是引擎的。
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from horosa_skill.errors import bilingual
from horosa_skill.reports.figures import _ZERI_RETITLE, _wheel

_HEAVY_KEYS = frozenset({"export_snapshot", "technique_card", "snapshot_text"})
_SYZYGY_TYPE = {"new": "朔（日月合）", "full": "望（日月冲）"}  # = app AstroPrenatalSyzygy 的 SYZYGY_TYPE_CN


def _directed(label: str, author: str) -> dict[str, Any]:
    return {"engine": "directed", "title": f"{label}双盘（{author}）", "outer": f"{label}（{author}）"}


# 技法 → engine（ReportsAPI._aux_engine_charts 按它调哪个 runner 补算）、图名、外圈说明、要换掉的原有规格
AUX_TOOLS: dict[str, dict[str, Any]] = {
    "neroman": _directed("演进推运", "Néroman"),
    "bezzafigure": _directed("推运图", "Bezza"),
    "jayprofection": _directed("周日小限", "Jay"),
    "prog": {"engine": "progression", "title": "推运双盘（次限）", "outer": "次限推运盘"},
    # 恒星推运：结果里有一张本命盘（raw.natalChart，回归黄道口径）——app 画的是两圈都按恒星黄道重取的双盘，换掉它
    "vedicprog": {"engine": "progression", "title": "恒星推运双盘（次限）", "outer": "恒星黄道次限推运盘",
                  "replaces": lambda spec: spec.get("kind") == "wheel"},
    "tianxing": {"engine": "tianxing", "title": "选中时刻星盘"},
    "prenatalsyzygy": {"engine": "syzygy", "title": "产前朔望盘"},
    # 七政择日：原有的七政方盘（GLChart）是 app 的另一种盘式；Moira 圆盘画出来才换掉它
    "qizhengzeri": {"engine": "qizheng_moira", "title": "七政择日盘（Moira）",
                    "replaces": lambda spec: spec.get("kind") == "grid12"},
    # 七政页本身：引擎缺省星阙七政、盘式缺省 Moira（getStoredGuolaoChartStyle），方盘（GLChart）只在 Moira 画不出时留着
    "guolao_chart": {"engine": "qizheng_moira", "title": "七政四余盘（Moira）",
                     "replaces": lambda spec: spec.get("kind") == "grid12"},
}


def wanted(tool_name: str, data: Any) -> bool:
    if tool_name not in AUX_TOOLS or not isinstance(data, dict):
        return False
    # 天星择日零命中是结果、不是失败：页面没有可点的命中行，也就没有选中时刻那张盘可缺
    return tool_name != "tianxing" or bool(data.get("intervals"))


def engine(tool_name: str) -> str:
    return str(AUX_TOOLS[tool_name]["engine"])


def title(tool_name: str) -> str:
    return str(AUX_TOOLS[tool_name]["title"])


def _layer(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key not in _HEAVY_KEYS}


def _pick(value: dict[str, Any]) -> dict[str, Any]:
    return {key: value[key] for key in ("params", "chart", "aspects", "lots") if key in value}


def build(tool_name: str, charts: dict[str, Any]) -> dict[str, Any]:
    """补算到的盘 → 一张盘图规格（带 `aux: True`）。盘不完整（缺宫 / 缺星）就抛 ValueError，调用方写说明。"""
    entry = AUX_TOOLS[tool_name]
    kind = entry["engine"]
    if kind in {"directed", "progression"}:
        natal, outer = charts["natal"], charts["outer"]
        inner = _wheel(natal.get("chart") or {}, entry["title"])
        ring = _wheel(outer.get("chart") or {}, "")
        if not inner or not ring:
            raise ValueError(bilingual("引擎回的盘缺宫位或七政", "the engine chart has no full set of 12 houses and 7 planets"))
        moment = str(charts.get("moment") or "")
        when = f"推至 {moment}" if kind == "directed" else f"推运时刻 {moment}（一日行一年）"
        inner.update(
            outer_bodies=ring["bodies"],
            ring_note=f"内圈为本命盘，外圈为{entry['outer']}，{when}。" + ("两圈都按恒星黄道起盘。" if tool_name == "vedicprog" else ""),
            app_request={"kind": "bi_wheel", "data": {"natualChart": _pick(natal), "dirChart": _pick(outer)}, "options": {"size": 760}},
        )
        spec = inner
    elif kind in {"tianxing", "syzygy"}:
        chart = charts["chart"]
        moment = str(charts.get("moment") or "")
        when = [_SYZYGY_TYPE.get(str(charts.get("type") or ""), ""), moment] if kind == "syzygy" else [moment]
        label = " · ".join([entry["title"], " ".join(part for part in when if part)])
        aspects = (chart.get("aspects") or {}).get("normalAsp") if isinstance(chart.get("aspects"), dict) else None
        spec = _wheel(chart.get("chart") or {}, label, aspects)
        if not spec:
            raise ValueError(bilingual("引擎回的盘缺宫位或七政", "the engine chart has no full set of 12 houses and 7 planets"))
        payload = _layer(chart)
        if not isinstance(payload.get("aspects"), dict):
            payload["aspects"] = {"normalAsp": {}}
        spec["app_request"] = {"kind": "natal_wheel", "data": payload, "options": {"size": 760}}
    elif kind == "qizheng_moira":
        root, moira = charts["root"], charts["moira"]
        spec = {
            "kind": "app", "app_kind": "guolao_moira",
            "title": entry["title"] + (_ZERI_RETITLE.format(moment=charts["moment"]) if charts.get("moment") else ""),
            # 喂法 = GuoLaoChartMain.render 的 Moira 分支：本盘 / 流年盘（罗计已换位、挂了四柱）、规则全集、择日端点数据（静盘宫位）、
            # 内嵌页的 fields（adapter 照 QizhengZeriMain.buildFields 由起盘载荷搭）
            "app_request": {"kind": "guolao_moira", "data": {
                "root": _layer(root), "transit": _layer(moira.get("transitChartObj") or {}),
                "transitParams": moira.get("transitParams") or {}, "rules": moira.get("rules") or {},
                "election": charts.get("election") or {}, "params": charts.get("params") or {},
            }, "options": {}},
        }
    else:  # pragma: no cover — AUX_TOOLS 与这里同改
        raise ValueError(bilingual(f"未知的补算种类 {kind!r}", f"unknown aux chart engine {kind!r}"))
    spec["aux"] = True
    return spec


def merge(tool_name: str, figures: list[dict[str, Any]], spec: dict[str, Any]) -> list[dict[str, Any]]:
    """把补算的那张放进规格表：西洋轮（有自绘版）直接换掉要换的那张；app 专属的（Moira）排在它前面，原图留着，
    出图后由 `settle` 定去留。没有可换的就排第一张（它是 app 页面的主图）。"""
    replaces: Callable[[dict[str, Any]], bool] | None = AUX_TOOLS[tool_name].get("replaces")
    out = [dict(item) for item in figures]
    index = next((i for i, item in enumerate(out) if replaces and replaces(item)), None)
    if index is None:
        return [spec, *out]
    if spec.get("kind") == "app":
        out[index]["aux_superseded"] = True
        return [*out[:index], spec, *out[index:]]
    return [*out[:index], spec, *out[index + 1:]]


def settle(figures: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """出图之后：app 专属的补算图画出来了就去掉被它换下的原图；没画出来就去掉它、原图留着，并说明原因。
    `app_request`（引擎整盘，体积大）在这里拿掉，不进文档。"""
    notes: list[str] = []
    drawn = any(item.get("aux") and item.get("kind") == "app" and item.get("app_svg") for item in figures)
    out: list[dict[str, Any]] = []
    for item in figures:
        if item.get("aux") and item.get("kind") == "app" and not item.get("app_svg"):
            notes.append(f"{item.get('title')}没有画出：星阙 app 画法这次不可用（{item.get('renderer_note') or 'not rendered'}）。")
            continue
        if item.get("aux_superseded") and drawn:
            continue
        clean = {key: value for key, value in item.items() if key not in {"app_request", "aux_superseded"}}
        out.append(clean)
    return out, notes


# 说明的后半句只在「报告照出」时成立；PNG 只有这一张图、一个文件都没写成时由 `standing_alone` 拿掉。
_REST_UNAFFECTED = "；其余盘图与正文不受影响。"


def failure_note(tool_name: str, reason: str) -> str:
    return f"{title(tool_name)}没有画出：出报告时补算这张盘没有成功（{reason}）{_REST_UNAFFECTED}"


def app_only_note(spec: dict[str, Any]) -> str:
    """只有星阙 app 画法的盘（没有自绘版）这次没画成：此前整张静默不出，读者和调用方都不知道少了一张。"""
    reason = spec.get("renderer_note") or "星阙 app 画法已关闭（HOROSA_APP_CHARTS=0）"
    return f"{spec.get('title') or '盘图'}没有画出：这张盘只有星阙 app 的画法，这次不可用（{reason}）。"


def standing_alone(note: str) -> str:
    """同一句说明，用在「没有别的图、也没有正文」的场合（PNG 一张都没出）。"""
    return note.replace(_REST_UNAFFECTED, "。")
