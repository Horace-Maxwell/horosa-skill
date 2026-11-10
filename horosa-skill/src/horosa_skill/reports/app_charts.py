"""盘图用星阙 app 自己的样式：跑 app 原版绘图代码出 SVG，转成 reportlab 矢量图。

- 出图：`horosa-core-js/dist/app-charts.cjs`（`app-charts/build.mjs` 从 Horosa-Public 打包）在 Node 里用 app 的组件画——
  西洋盘是 `AstroChartCircle`、紫微是 `ZWChart`，喂的就是 app 喂给它们的那份引擎结果。这里不算任何位置（铁律 1）。
- 接入：`attach_app_svgs` 在报告渲染前对 `extract_figures` 的规格逐张配 app 图（一次 Node 调用），成功的规格多一个
  `app_svg`；`figures.figure_drawing` 有 `app_svg` 就画它，没有（旧 runtime 没带 bundle、Node 起不来、这张没对上）就画原来的图，
  规格里 `renderer` 写明用的是哪一种（`app` / `builtin`）及原因——退回不是静默的。
- 转换：svglib 读 SVG。先做几处无损规整：`transparent` → none、`var(--x, 回退)` → 回退值（app 的浅色主题值就写在回退里）、
  rgba → 颜色 + 透明度、数字字重 → 常规 / 粗体；字族只留 app 的符号字体（ywastro / morinus，随包 `data/fonts/`），其余文字一律用报告
  本身嵌入的 TrueType 字体（PDF/UA 要求字体全嵌；也保证中文不出方块）。
- 关掉：`HOROSA_APP_CHARTS=0` 只画原来的图（排查用）。
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

FONT_DIR = Path(__file__).resolve().parents[1] / "data" / "fonts"
# SVG font-family → (随包字体文件, reportlab 注册名)。ywastro 与 ywastrochart 在 app 里是同一个文件。
GLYPH_FONTS = {
    "ywastrochart": ("ywastro.ttf", "HorosaAppYwastro"),
    "ywastro": ("ywastro.ttf", "HorosaAppYwastro"),
    "morinus": ("morinus-webfont.ttf", "HorosaAppMorinus"),
}
TEXT_FAMILY = "HorosaReportText"
TEXT_BOLD_FAMILY = "HorosaReportTextBold"
# 装饰性符号（塔罗没有牌面图时的符号牌面 ✦ / 🐎 …）：报告字体与补字链都印不出来时整个去掉，不印方块
OPTIONAL_GLYPH_SVG_FAMILY = "horosa-optional-glyph"
OPTIONAL_FAMILY = "HorosaOptionalGlyph"

# 塔罗牌面图：从 pin 住的上游逐字节拷进包里（scripts/sync_tarot_art.py），manifest 记尺寸与 sha。app 的 cardImageUrl 给出的
# 相对路径（tarot-art/<牌组>/<文件>.jpg）就是这里的键；只认这个形状，别的 href 一律不读文件。
TAROT_ART_DIR = Path(__file__).resolve().parents[1] / "data" / "tarot-art"
_TAROT_HREF = re.compile(r"^tarot-art/(rws|tdm|wirth|egyptian)/([a-z0-9_]+\.jpg)$")
_IMAGE_TAG = re.compile(r"<image\b[^>]*?>(?:\s*</image>)?")
_HREF_ATTR = re.compile(r'\s(?:xlink:)?href="([^"]*)"')


@lru_cache(maxsize=1)
def _tarot_manifest() -> dict[str, Any]:
    try:
        return json.loads((TAROT_ART_DIR / "manifest.json").read_text(encoding="utf-8")).get("files") or {}
    except (OSError, ValueError):
        return {}


def tarot_art_sizes() -> dict[str, list[int]]:
    """这次安装真有的牌面图：{app 的相对路径: [宽, 高]}。缺了的不列（app 侧就画符号牌面，与 app 的 <img onError> 同一回退）。"""
    return {f"tarot-art/{rel}": [int(meta["width"]), int(meta["height"])] for rel, meta in sorted(_tarot_manifest().items())
            if (TAROT_ART_DIR / rel).is_file()}


@lru_cache(maxsize=256)
def _tarot_data_uri(href: str) -> str | None:
    match = _TAROT_HREF.match(href)
    if not match or f"{match.group(1)}/{match.group(2)}" not in _tarot_manifest():
        return None
    try:
        data = (TAROT_ART_DIR / match.group(1) / match.group(2)).read_bytes()
    except OSError:
        return None
    return "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")


def embed_images(svg: str) -> str:
    """把 app 图里的牌面图（href 以 tarot-art/ 开头）换成内嵌 data URI（svglib 从内存读 SVG，读不了相对路径）；别的 <image>
    原样不动。读不到的牌面图整个去掉（app 侧只给它确认有的图，见 tarot_art_sizes；这里只兜底），绝不读包外文件。"""
    def swap(match: re.Match[str]) -> str:
        tag = match.group(0)
        href = _HREF_ATTR.search(tag)
        if not href or not href.group(1).startswith("tarot-art/"):
            return tag
        uri = _tarot_data_uri(href.group(1))
        return _HREF_ATTR.sub(f' href="{uri}"', tag, count=1) if uri else ""

    return _IMAGE_TAG.sub(swap, svg) if "<image" in svg else svg

# 西洋轮：取 `figures._wheels` 记下的那一层（`source`：根 / dirChart / natalChart / charts.春分…），整份交给 app 的 AstroChartCircle。
# 不走 app 画法的：巴比伦（无宫位体系，app 用另一套 components/babylon）。合盘双圈走 drawDoubleChart（bi_wheel）。
_WHEEL_SKIP_TOOLS = frozenset({"babylon"})
_ZIWEI_TOOLS = frozenset({"ziwei_birth", "ziweizeri"})
_GUOLAO_TOOLS = frozenset({"guolao_chart", "qizhengzeri"})
_LIURENG_TOOLS = frozenset({"liureng_gods", "liureng_runyear", "liurengzeri"})  # 七政择日动盘（qizhengelection）是另一种盘，不在此列
_HEAVY_KEYS = frozenset({"export_snapshot", "technique_card", "snapshot_text"})


def _dig(data: Any, path: list[str] | tuple[str, ...]) -> Any:
    for key in path:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def _jinkou_payload(source: dict[str, Any]) -> dict[str, Any] | None:
    prerequisites = source.get("prerequisites") if isinstance(source.get("prerequisites"), dict) else {}
    if not isinstance(source.get("board_context"), dict) or not isinstance(prerequisites.get("liureng"), dict):
        return None
    return {"board_context": source["board_context"], "liureng": prerequisites["liureng"], "jinkou": source.get("jinkou")}


_SANSHI_TOOLS = frozenset({"sanshiunited", "sanshizeri"})
# 奇门 pan 全给（三式盘的神煞 / 虚实 / 四柱助手各读不同的键），只去掉原始回包与导出段这些大块
_SANSHI_QIMEN_HEAVY = frozenset({"raw", "allRaw", "sections", "source", "backend"})
_QIMEN_PAN_KEYS = ("cells", "ganzhi", "options", "keGanZhi", "juText", "zhiFu", "zhiShi", "xunKong", "kongWang", "xunShou", "allKong",
                   "shiftPalace", "fengJu", "isJinhan", "dateStr", "timeStr", "realSunTime")
_KIN_ZIWEI_KEYS = ("cetian", "dateStr", "hourBranch", "latitude", "longitude", "lunar", "mingGong", "palaceCards", "pillars",
                   "shenGong", "showFlags", "timeStr", "timezone", "xianqin", "yiyu", "ziwei")


def _kin_pan(source: dict[str, Any], key: str) -> dict[str, Any] | None:
    raw = source.get("raw")
    if not isinstance(raw, dict) or not isinstance(raw.get(key), (dict, list)):
        return None
    return {"raw": {name: raw[name] for name in _KIN_ZIWEI_KEYS if name in raw}}


# kind="app"（只有 app 画得出来、skill 没有自绘版）的规格：app 画法 → 从结果里取喂给 adapter 的那几块
_APP_ONLY_PAYLOADS = {
    "jinkou": _jinkou_payload,
    "suzhan": lambda source: ({key: source[key] for key in ("params", "chart", "aspects", "lots", "board_context") if key in source}
                              if isinstance(_dig(source, ["chart", "fixedStarSu28"]), (list, dict)) else None),
    # 米雄：/astroextra/michon 原样响应（正文同一份）
    "michon": lambda source: ({"raw": {key: source["raw"].get(key) for key in ("cusps", "planets", "superpositions", "ayanamsa", "equalHouses")}}
                              if isinstance(source.get("raw"), dict) and isinstance(source["raw"].get("superpositions"), list) else None),
    # 坚七政：kentang 盘原样（正文同一份）；只取圆盘读的几块
    "qizhengkin": lambda source: ({"raw": {key: source["raw"].get(key) for key in ("qizheng", "dateStr", "timeStr", "location", "gender", "timezone")}}
                                  if isinstance(_dig(source, ["raw", "qizheng", "chart"]), dict) else None),
    # 策天 / 演禽：kentang 盘原样，只取 app 转紫微盘（KinAstroMain.buildKinAstroZiWeiChart）读的那些键
    "cetian": lambda source: _kin_pan(source, "cetian"),
    "xianqin": lambda source: _kin_pan(source, "xianqin"),
    # 八字：引擎的 bazi（四柱 / 十神 / 藏干 / 神煞 / 农历）= app BaZiFineChart 的 value
    "bazi": lambda source: ({"bazi": source["bazi"]} if isinstance(source.get("bazi"), dict) and isinstance(source["bazi"].get("fourColumns"), dict) else None),
    # 地占：引擎 reading（十六图形 / 得地 / 记号传本）= app 护盾方盘读的那一份
    "geomancy": lambda source: ({"reading": {key: source["reading"][key] for key in ("figures16", "technique", "settings") if key in source["reading"]}}
                                if isinstance(source.get("reading"), dict) and isinstance(source["reading"].get("figures16"), list) else None),
    # 小六壬：结果即 app 页面的 ke（school / nums / chuan / analysis）
    "xiaoliuren": lambda source: ({"xiaoliuren": source["xiaoliuren"]} if isinstance(source.get("xiaoliuren"), dict) and isinstance(source["xiaoliuren"].get("chuan"), list) else None),
    # 小成图：JS 正文所用 qi 的整卦对象（board_context）+ 起卦法 / 动爻 / 用宫
    "xiaochengtu": lambda source: ({"xiaochengtu": source["xiaochengtu"]} if isinstance(_dig(source, ["xiaochengtu", "board_context", "ben"]), dict) else None),
    # 轨策：JS 的起卦结果（board_context.gua）+ 本次 ctx / settings / 世应输入 → app 的 buildGuicePan
    "guice": lambda source: ({"guice": {"board_context": source["guice"]["board_context"]}, "input_normalized": source.get("input_normalized") or {}}
                             if isinstance(_dig(source, ["guice", "board_context", "gua"]), dict) else None),
    # 灵棋：三层枚数（= app 页面 state.counts）+ 占问类别 + 起卦日干支（六戊日提示）
    "lingqi": lambda source: ({key: source.get(key) for key in ("counts", "category", "day_ganzhi")} if isinstance(source.get("counts"), list) else None),
    # 五兆：kentang 盘的五位与古法层（positions / classic）= app 兆图读的那两块
    "wuzhao": lambda source: ({"raw": {key: source["raw"].get(key) for key in ("positions", "classic")}}
                              if isinstance(_dig(source, ["raw", "positions"]), list) else None),
    # 一掌经：core-js 算正文那份 model 中 renderBoard 读的切片（board_context）
    "yizhangjing": lambda source: ({"yizhangjing": {"board_context": source["yizhangjing"]["board_context"]}}
                                   if isinstance(_dig(source, ["yizhangjing", "board_context", "chart"]), dict) else None),
    # 统摄法：四宫所选八卦（selected）→ app 的 buildTongSheFaModel
    "tongshefa": lambda source: ({"tongshefa": {"selected": source["tongshefa"]["selected"]}} if isinstance(_dig(source, ["tongshefa", "selected"]), dict) else None),
    # 天文地图：/location/acg 原样响应（= app AcgD3Map 的 value）
    # （出厂设置下交映 / 交叉点图层都关着，只送 meta + planets）
    "acg": lambda source: ({"acg": {key: source["acg"][key] for key in ("meta", "planets") if key in source["acg"]}}
                           if isinstance(_dig(source, ["acg", "planets"]), (dict, list)) else None),
    # 塔罗：JS 算正文的同一个 reading（牌 id + sid / 朝向 / 牌位 / 牌组 / 口径）= app TarotMain.renderCenter 摆的那一副
    "tarot": lambda source: ({"board_context": source["board_context"]}
                             if isinstance(_dig(source, ["board_context", "draws"]), list) and source["board_context"]["draws"] else None),
    # 飞宫：起局三要素（起支 / 日干 / 日支）= JS 算正文时用的那一份，app 的 buildJu 照同一调用再起
    "feigong": lambda source: ({"feigong": {key: source["feigong"].get(key) for key in ("qiZhi", "dayGan", "dayZhi")}}
                               if isinstance(source.get("feigong"), dict) and all(source["feigong"].get(k) for k in ("qiZhi", "dayGan", "dayZhi")) else None),
    # 河洛：core-js 正文那一份 chart / dayun / judge / solarTerm + board_context（纳音、chartExtras）+ 取法口径 = app getModel 的 m
    "heluo": lambda source: ({"heluo": source["heluo"], "input_normalized": source.get("input_normalized") or {}}
                             if isinstance(_dig(source, ["heluo", "board_context", "extras"]), dict) else None),
}


def enabled() -> bool:
    return os.environ.get("HOROSA_APP_CHARTS", "1").strip().lower() not in {"0", "false", "off", "no"}


def plan(tool_name: str, data: Any, figures: list[dict[str, Any]]) -> list[tuple[int, dict[str, Any]]]:
    """(规格序号, Node 请求) 列表：哪几张图可以换成 app 的画法、喂什么数据。"""
    if not isinstance(data, dict):
        return []
    source = data["base"] if data.get("pan_moment") and isinstance(data.get("base"), dict) else data
    requests: list[tuple[int, dict[str, Any]]] = []
    for index, spec in enumerate(figures):
        kind = spec.get("kind")
        if isinstance(spec.get("app_request"), dict):
            # 出报告时补算的盘（reports/aux_charts.py）：引擎整盘已按 app 页面的喂法备好，原样转交
            requests.append((index, spec["app_request"]))
        elif kind == "wheel" and spec.get("outer_bodies") and isinstance(_dig(source, ["inner", "chart"]), dict) and isinstance(_dig(source, ["outer", "chart"]), dict):
            # 合盘双圈：与自绘图同一安排（内圈甲方宫位与行星、外圈乙方行星）= app AstroDoubleChartMain 的「星盘B」页
            pick = lambda layer: {key: layer[key] for key in ("params", "chart", "aspects", "lots") if key in layer}  # noqa: E731
            requests.append((index, {"kind": "bi_wheel", "data": {"natualChart": pick(source["inner"]), "dirChart": pick(source["outer"])},
                                     "options": {"size": 760}}))
        elif kind == "wheel" and tool_name == "babylon" and isinstance(source.get("board_context"), dict) and isinstance(_dig(source, ["raw", "chart"]), dict):
            # 巴比伦：app 的星盘是恒星黄道宫带 + 七曜（BabylonHoroscope.renderWheel），不是西洋轮；正文同一 jdn / opts
            requests.append((index, {"kind": "babylon", "data": {"raw": {"chart": source["raw"]["chart"]}, "board_context": source["board_context"]},
                                     "options": {}}))
        elif kind == "wheel" and tool_name not in _WHEEL_SKIP_TOOLS and not spec.get("outer_bodies") and isinstance(spec.get("source"), list):
            layer = _dig(source, spec["source"])
            if isinstance(layer, dict) and isinstance(layer.get("chart"), dict):
                payload = {key: value for key, value in layer.items() if key not in _HEAVY_KEYS}
                if not isinstance(payload.get("aspects"), dict):
                    # 自绘轮连了相位线 = 这一层的相位在根上 / raw 里（本命类、卜卦、择日）；没连就给空表，app 也不画线。
                    aspects = (_dig(source, ["aspects"]) or _dig(source, ["raw", "aspects"])) if spec.get("aspects") else None
                    payload["aspects"] = aspects if isinstance(aspects, dict) else {"normalAsp": {}}
                if not isinstance(payload.get("params"), dict) and isinstance(source.get("params"), dict):
                    payload["params"] = source["params"]  # 黄道 / 界 / 三分主星口径跟着本次请求走
                requests.append((index, {"kind": "natal_wheel", "data": payload, "options": {"size": 760}}))
        elif kind == "grid12" and tool_name in _SANSHI_TOOLS and isinstance(source.get("board_context"), dict) and isinstance(source.get("qimen"), dict):
            # 三式合一：app 的三式合一盘（外圈星盘 + 奇门 + 六壬 + 课传）替换自绘的六壬天地盘；同一次起课的各层
            prereq = source.get("prerequisites") if isinstance(source.get("prerequisites"), dict) else {}
            suffix = spec["title"][len("六壬天地盘"):] if str(spec.get("title") or "").startswith("六壬天地盘") else ""
            requests.append((index, {"kind": "sanshi", "title": f"三式合一盘{suffix}", "data": {
                "board_context": source["board_context"], "qimen": {key: value for key, value in source["qimen"].items() if key not in _SANSHI_QIMEN_HEAVY},
                "liureng": source.get("liureng") or {}, "displaySolarTime": prereq.get("displaySolarTime")}, "options": {}}))
        elif kind == "grid12" and spec.get("layout") == "india_south" and isinstance(source.get("chart"), dict):
            # 南印方盘：app 缺省盘式（IndiaSouthChart，HTML）照它的样式表重画成 SVG（adapters/india.js），同一份 chart
            params = source.get("params") if isinstance(source.get("params"), dict) else {}
            varga = params.get("varga") if isinstance(params.get("varga"), dict) else {}
            digits = re.sub(r"\D", "", str(varga.get("label") or "D1").split()[0])
            chartnum = varga.get("chartnum") if isinstance(varga.get("chartnum"), int) else int(digits or 1)
            requests.append((index, {"kind": "india_south", "data": {"chartObj": {"chart": source["chart"]}, "chartnum": chartnum,
                                                                    "lagnaRef": params.get("indiaLagnaRef") or "asc"}, "options": {}}))
        elif kind == "grid12" and tool_name in _ZIWEI_TOOLS and isinstance(source.get("chart"), dict):
            requests.append((index, {"kind": "ziwei", "data": {"chart": source["chart"]}, "options": {"size": 780}}))
        elif kind == "app" and spec.get("app_kind") in _APP_ONLY_PAYLOADS:
            payload = _APP_ONLY_PAYLOADS[spec["app_kind"]](source)
            if payload is not None:
                options: dict[str, Any] = {"size": 760, **(spec.get("app_options") or {})}
                if spec["app_kind"] == "tarot":
                    options["art"] = tarot_art_sizes()  # 随包牌面图：app 照图的宽高比排牌，没有的牌回落符号牌面
                requests.append((index, {"kind": spec["app_kind"], "data": payload, "options": options}))
        elif kind == "taiyi" and isinstance(source.get("pan") if isinstance(source.get("pan"), dict) else source.get("taiyi"), dict):
            # 与 figures._taiyi 同一份 pan（太乙 / 太乙择时在 pan，三式合一 / 三式择时在 taiyi）→ app 的 TaiyiBoardSvg
            pan = source["pan"] if isinstance(source.get("pan"), dict) else source["taiyi"]
            requests.append((index, {"kind": "taiyi", "data": {"pan": pan}, "options": {}}))
        elif kind == "hexagram" and isinstance(source.get("lines"), list) and isinstance(source.get("nongli"), dict):
            # 六爻：只在自绘图敢画完整的时候换（变卦与本卦 + 动爻对得上 = 两栏，或根本没有动爻）——app 会从动爻自己翻出之卦，
            # 对不上时它画的之卦正文里没有。
            moving = any(isinstance(line, dict) and line.get("change") for line in source["lines"])
            if len(spec.get("columns") or []) == 2 or not moving:
                payload = {key: source.get(key) for key in ("lines", "nongli", "liuyao_settings")}
                requests.append((index, {"kind": "liuyao", "data": payload, "options": {"width": 900, "height": 620}}))
        elif kind == "grid9" and isinstance(source.get("pan"), dict) and isinstance(source["pan"].get("cells"), list) and not source["pan"].get("isJinhan"):
            # 奇门：app 遁甲盘（HTML）照 DunJiaBoard 的尺寸与配色重画成 SVG（adapters/qimen.js），同一份 pan
            pan = source["pan"]
            requests.append((index, {"kind": "qimen", "data": {"pan": {key: pan.get(key) for key in _QIMEN_PAN_KEYS if key in pan}}, "options": {}}))
        elif kind == "dial90" and isinstance(source.get("chart"), dict):
            # 量化盘 90° 度盘：本命点 + 引擎给的 8 颗 TNP（raw.tnp，与自绘图同一份）→ app 的 UranianDial
            tnp = _dig(source, ["raw", "tnp"]) if isinstance(_dig(source, ["raw", "tnp"]), list) else source.get("tnp")
            if isinstance(tnp, list):
                requests.append((index, {"kind": "uranian_dial", "data": {"chart": source["chart"], "raw": {"tnp": tnp}}, "options": {"size": 720}}))
        elif kind == "grid12" and tool_name in _LIURENG_TOOLS and isinstance(_dig(source, ["board_context", "chart"]), dict):
            # 六壬：runner 留下的起课盘 + gods 结果 + 引擎实际用的口径 → app 的 RengChart（三式合一里的六壬是另一种盘，不在此列）
            payload = {key: source.get(key) for key in ("board_context", "liureng", "runyear", "headless_liureng")}
            requests.append((index, {"kind": "liureng", "data": payload, "options": {"size": 760}}))
        elif kind == "grid12" and tool_name in _GUOLAO_TOOLS and isinstance(_dig(source, ["chart", "fixedStarSu28"]), (list, dict)):
            payload = {key: source[key] for key in ("params", "chart", "aspects", "lots") if key in source}
            requests.append((index, {"kind": "guolao", "data": payload, "options": {"size": 760}}))
    return requests


def attach_app_svgs(figures: list[dict[str, Any]], tool_name: str, data: Any, client: Any) -> list[dict[str, Any]]:
    """给能换的规格配上 app 原版 SVG（`app_svg`），其余标 `renderer: builtin` + 原因。返回新列表，不改入参。"""
    out = [dict(spec) for spec in figures]
    requests = plan(tool_name, data, out) if enabled() else []
    for spec in out:
        spec.setdefault("renderer", "builtin")
    if not requests:
        return _drop_undrawn_app_only(out)
    results = None
    failure = "app-charts bundle unavailable"
    render = getattr(client, "render_app_charts", None)
    if callable(render):
        try:
            results = render([{key: value for key, value in request.items() if key != "title"} for _index, request in requests])
        except Exception as exc:  # noqa: BLE001 — 拿不到 app 的图就画原来的图，原因写进每张规格的 renderer_note
            failure = f"app-charts call failed: {type(exc).__name__}: {exc}"
            results = None
    for position, (index, request) in enumerate(requests):
        result = results[position] if results else None
        if result and result.get("ok") and isinstance(result.get("svg"), str):
            out[index].update(renderer="app", app_kind=request["kind"], app_svg=result["svg"])
            if request.get("title"):
                out[index]["title"] = request["title"]  # app 的这张盘与自绘图不是同一种（三式：自绘六壬天地盘 → app 三式合一盘）
        else:
            reason = failure if results is None else str((result or {}).get("error") or "render failed")
            out[index]["renderer_note"] = f"app {request['kind']}: {reason}"
    return _drop_undrawn_app_only(out)


def _drop_undrawn_app_only(figures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """kind="app" 的盘没有自绘版：app 没画出来就整张不出（规格里本就只有图名，留着只会印一个空框）。
    补算的那张（`aux`）留给 aux_charts.settle：它要据此留下被换的原图并写明原因。"""
    return [spec for spec in figures if spec.get("kind") != "app" or spec.get("app_svg") or spec.get("aux")]


# ───────────────────────────── SVG 规整 ─────────────────────────────

_VAR = re.compile(r"var\(\s*--[\w-]+\s*,\s*((?:[^()]|\([^()]*\))*)\)")
_RGBA = re.compile(r'(fill|stroke)="rgba\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\)"')
_WEIGHT = re.compile(r'font-weight="(\d+|bold|normal)"')
_FAMILY = re.compile(r'font-family="([^"]*)"')
_TEXT_OPEN = re.compile(r"<(text|tspan)\b([^>]*)>")
_STYLE = re.compile(r'\sstyle="([^"]*)"')
_LIFTED = ("font-family", "font-weight", "font-style", "dominant-baseline", "alignment-baseline")
# svglib 不认 dominant-baseline（字一律落在基线上）：按浏览器的位置折成 dy（em 跟字号走）。app 的图里 middle / central
# 上千处（紫微星曜与宫名、星盘度数），不折的话整体上移约 0.35em，竖排星名的首字压出格子上沿（演禽）。
_BASELINE_DY = {"middle": "0.35em", "central": "0.35em", "hanging": "0.8em", "text-before-edge": "0.8em"}
_BASELINE = re.compile(r'\s(?:dominant|alignment)-baseline="([^"]*)"')


def _baseline(match: re.Match[str]) -> str:
    tag, attrs = match.groups()
    found = _BASELINE.search(attrs)
    if not found:
        return match.group(0)
    attrs = _BASELINE.sub("", attrs)
    shift = _BASELINE_DY.get(found.group(1).strip())
    if shift and ' dy="' not in attrs:
        attrs = f'{attrs.rstrip("/")} dy="{shift}"' + ("/" if attrs.endswith("/") else "")
    return f"<{tag}{attrs}>"


def _lift_style(match: re.Match[str]) -> str:
    """React 的 style={{ fontFamily }} 落成内联 style：字族 / 字重 / 斜体提成属性，好让下面按属性换成注册过的字族
    （巴比伦星盘的七曜符号字体就写在 style 里；不提的话 svglib 拿到一个没注册的字族名，符号印成字母）。"""
    tag, attrs = match.groups()
    style = _STYLE.search(attrs)
    if not style:
        return match.group(0)
    keep: list[str] = []
    lifted: list[str] = []
    for decl in style.group(1).split(";"):
        key, _, value = decl.partition(":")
        key, value = key.strip().lower(), value.strip()
        if not key:
            continue
        if key in _LIFTED and f'{key}="' not in attrs:
            lifted.append(f'{key}="{value}"')
        else:
            keep.append(f"{key}:{value}")
    rest = _STYLE.sub(f' style="{";".join(keep)}"' if keep else "", attrs, count=1)
    return f"<{tag}{rest}{''.join(' ' + item for item in lifted)}>"


def _resolve_vars(svg: str) -> str:
    for _ in range(4):  # var(--a, var(--b, #fff)) 嵌套最多两三层
        updated = _VAR.sub(lambda m: m.group(1).strip(), svg)
        if updated == svg:
            break
        svg = updated
    return svg


def _rgba(match: re.Match[str]) -> str:
    attr, r, g, b, a = match.groups()
    return f'{attr}="#{int(float(r)):02x}{int(float(g)):02x}{int(float(b)):02x}" {attr}-opacity="{a}"'


def _family(value: str, bold: bool) -> str:
    for name in (part.strip().strip("'\"").lower() for part in value.split(",")):
        if name in GLYPH_FONTS:
            return GLYPH_FONTS[name][1]
        if name == OPTIONAL_GLYPH_SVG_FAMILY:
            return OPTIONAL_FAMILY
    return TEXT_BOLD_FAMILY if bold else TEXT_FAMILY


def normalize_svg(svg: str) -> str:
    # 悬停提示（<title> / <desc>）在浏览器里从不显示，svglib 却会把它当正文画出来
    svg = re.sub(r"<(title|desc)\b[^>]*>.*?</\1>", "", svg, flags=re.S)
    svg = _resolve_vars(svg)
    svg = re.sub(r'(fill|stroke)="transparent"', r'\1="none"', svg)
    svg = _RGBA.sub(_rgba, svg)
    svg = _TEXT_OPEN.sub(_lift_style, svg)
    svg = _TEXT_OPEN.sub(_baseline, svg)

    def text_tag(match: re.Match[str]) -> str:
        tag, attrs = match.groups()
        weight = _WEIGHT.search(attrs)
        bold = bool(weight) and (weight.group(1) == "bold" or (weight.group(1).isdigit() and int(weight.group(1)) >= 600))
        family = _FAMILY.search(attrs)
        if tag == "tspan" and not family and not weight:
            return match.group(0)  # 不带字族的 tspan 继承 <text> 的
        attrs = _WEIGHT.sub("", _FAMILY.sub("", attrs))
        return f'<{tag}{attrs} font-family="{_family(family.group(1) if family else "", bold)}">'

    svg = _TEXT_OPEN.sub(text_tag, svg)
    # 外层 <g> 上的 font-family / font-weight（文字继承）也要落到我们注册过的字族
    svg = re.sub(r'(<g\b[^>]*?)font-family="([^"]*)"', lambda m: f'{m.group(1)}font-family="{_family(m.group(2), False)}"', svg)
    svg = _WEIGHT.sub("", svg)
    return svg


# ───────────────────────────── SVG → reportlab ─────────────────────────────

# svglib 只肯把字族映射到 PDF 标准 14 字体（映射到别的已注册字体会静默落回 Helvetica）。于是文字字族先映射到 Courier /
# Courier-Bold（app 从不用 Courier，规整时其余字族都已改成这两个占位名），转完再把这两个名字换成报告嵌入的 TrueType 字体。
# 斜体（巴比伦宫名的楔文转写）svglib 映到 Oblique；报告的中文字体没有斜体，照常体画
# 可省的符号走 Times-Roman 占位（app 的图里没有别的字落到 Times）：印得出来换成报告字体 / 补字字体，印不出来就去掉。
_TEXT_PLACEHOLDERS = {"Courier": "regular", "Courier-Bold": "bold", "Courier-Oblique": "regular", "Courier-BoldOblique": "bold",
                      "Times-Roman": "optional"}


def _register_fonts() -> None:
    from svglib.fonts import get_global_font_map

    font_map = get_global_font_map()
    for file_name, rl_name in sorted({(f, n) for f, n in GLYPH_FONTS.values()}):
        font_map.register_font(rl_name, str(FONT_DIR / file_name), rlgFontName=rl_name)
    font_map.register_font(TEXT_FAMILY, rlgFontName="Courier")
    font_map.register_font(TEXT_BOLD_FAMILY, rlgFontName="Courier-Bold")
    font_map.register_font(TEXT_FAMILY, style="italic", rlgFontName="Courier-Oblique")
    font_map.register_font(TEXT_BOLD_FAMILY, style="italic", rlgFontName="Courier-BoldOblique")
    font_map.register_font(OPTIONAL_FAMILY, rlgFontName="Times-Roman")


_SYMBOL_CHAIN: list[tuple[str, str, int, frozenset[int]]] | None = None


def _symbol_chain() -> list[tuple[str, str, int, frozenset[int]]]:
    """报告渲染器的补字字体链（Apple Symbols / Segoe UI Symbol / DejaVu…）：app 图里的 ℞ 等符号报告正文字体没有字形。"""
    global _SYMBOL_CHAIN
    if _SYMBOL_CHAIN is None:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        from horosa_skill.reports.renderers import _PDF_GLYPH_FALLBACK_CANDIDATES, _load_ttf

        chain: list[tuple[str, str, int, frozenset[int]]] = []
        for index, path in enumerate(_PDF_GLYPH_FALLBACK_CANDIDATES["sc"]):
            font = _load_ttf(TTFont, f"HorosaAppSymbol{index}", path, None)
            if font is None:
                continue
            pdfmetrics.registerFont(font)
            source = getattr(font, "horosa_source", None) or (path, 0)
            chain.append((font.fontName, str(source[0]), int(source[1]), frozenset(font.face.charToGlyph)))
        _SYMBOL_CHAIN = chain
    return _SYMBOL_CHAIN


def _charset(font_name: str) -> frozenset[int] | None:
    from reportlab.pdfbase import pdfmetrics

    try:
        return frozenset(pdfmetrics.getFont(font_name).face.charToGlyph)
    except Exception:  # noqa: BLE001 - CID 回退字体没有 face：不补字（探针，None 即答案）
        return None


def _swap_text_fonts(node: Any, text_font: str, bold_font: str) -> None:
    from reportlab.graphics.shapes import String

    covered = {name: _charset(name) for name in {text_font, bold_font}}
    chain = _symbol_chain()

    def walk(current: Any) -> None:
        for child in list(getattr(current, "contents", []) or []):
            if not isinstance(child, String):
                walk(child)
                continue
            role = _TEXT_PLACEHOLDERS.get(child.fontName)
            if not role:
                continue
            child.fontName = bold_font if role == "bold" else text_font
            charset = covered.get(child.fontName)
            missing = {ord(ch) for ch in child.text if not ch.isspace()} - charset if charset is not None else set()
            if missing:
                need = {ord(ch) for ch in child.text if not ch.isspace()}
                font = next((name for name, _path, _index, glyphs in chain if need <= glyphs), None)
                if font:
                    child.fontName = font
                elif role == "optional":
                    current.contents.remove(child)  # 装饰符号：哪款字体都印不出来就不印（不出方块，PNG 也不因它拒绝出图）

    walk(node)


def svg_drawing(svg: str, width: float, *, text_font: str, bold_font: str, problems: list[str] | None = None) -> Any | None:
    """app SVG → 宽 `width` 的 reportlab Drawing（矢量）。转不了返回 None 并把原因追加进 `problems`，调用方画原来的图。"""
    try:
        from svglib.svglib import svg2rlg

        _register_fonts()
        drawing = svg2rlg(io.BytesIO(embed_images(normalize_svg(svg)).encode("utf-8")))
    except Exception as exc:  # noqa: BLE001 — 任何解析失败都退回原画法；原因交给调用方写进 renderer_note
        if problems is not None:
            problems.append(f"{type(exc).__name__}: {exc}")
        return None
    if drawing is None or not drawing.width:
        if problems is not None:
            problems.append("svglib returned an empty drawing")
        return None
    _swap_text_fonts(drawing, text_font, bold_font)
    factor = width / float(drawing.width)
    drawing.scale(factor, factor)
    drawing.width, drawing.height = drawing.width * factor, drawing.height * factor
    return drawing


def glyph_font_files() -> dict[str, tuple[str, int]]:
    """reportlab 字体名 → (字体文件, 子字体序号)：位图（DOCX / PNG）画 app 图时要用到符号字体与补字字体。"""
    files = {rl_name: (str(FONT_DIR / file_name), 0) for file_name, rl_name in GLYPH_FONTS.values()}
    files.update({name: (path, index) for name, path, index, _glyphs in _symbol_chain()})
    return files
