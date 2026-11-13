"""上游 v3.14.0 同步 · zeri 批：随盘容许度 orbs / orbScale 进卜卦盘、择日盘与天星择日的选中时刻盘。

上游（Horosa-Public e55c3a66）：
- `utils/classicalChartGlobals.js` 新出口 `chartOrbOverrides`：`orbs` 是非空对象才发、`orbScale` 是有限正数且 ≠ 1 才发；
- `divination/engine/chartRequest.js` `buildChartParams` 末尾 `...chartOrbOverridesFromFields(fields)`（卜卦 / 择日 / 世俗盘壳）；
- `components/zeri/TianxingElectionMain.js` `previewChartParams` 同一行（选中时刻的浮窗盘），并注明扫描判定不读它。

skill 的 /chart 请求由 Python 拼（手抄件）：horary / election 走 `{**payload}` 透传，tianxing 的选中时刻盘是 `_tianxing_moment_payload`。
这里钉四件事：请求里真的带（缺省态不带）、扫描请求不带、认不出的值在入口就拒（后端对它们不报错、只是不用）、改了结果必变（live 值级）。

每条的负向对照（实跑过，红在哪写在 docstring）。上游源对拍只在 HOROSA_SOURCE_ROOT 指向上游 checkout 时跑。
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import pytest
from test_local_js_tools import make_service, requires_chart
from test_sync311_divination import _capture_base_calls, _zeri
from test_sync311_divination import RecordingClient as ScanRecordingClient
from test_sync311_divination import _service as _scan_service
from test_sync311_western import CHART_TRADITIONAL, RecordingClient, _section, _service

from horosa_skill.agent_guidance import build_agent_guidance
from horosa_skill.errors import ToolValidationError
from horosa_skill.schemas.tools.election import CHART_ORB_KEYS, parse_chart_orb_scale, parse_chart_orbs
from horosa_skill.western_options_doc import CHART_ORB_DEFAULTS

PKG = Path(__file__).resolve().parents[1]
CORE_JS_SRC = PKG / "horosa-core-js" / "src"
_UPSTREAM_ROOT = os.environ.get("HOROSA_SOURCE_ROOT")
UPSTREAM_UI = Path(_UPSTREAM_ROOT) / "Horosa-Web" / "astrostudyui" / "src" if _UPSTREAM_ROOT else None
requires_upstream = pytest.mark.skipif(
    UPSTREAM_UI is None or not UPSTREAM_UI.is_dir(), reason="[upstream-checkout] HOROSA_SOURCE_ROOT (upstream checkout) not set"
)

# 提问 / 候选时刻：与 sync311_western_horary 夹具同一刻（2026-03-10 14:20 上海）。
MOMENT = {"date": "2026-03-10", "time": "14:20:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "agent_confirmed_settings": True}


def _chart_client() -> RecordingClient:
    return RecordingClient(chart_for=lambda payload: CHART_TRADITIONAL)


# ── 请求体：给了才带，缺省态与上游一样不带 ────────────────────────────────────────────────────────


@pytest.mark.parametrize("tool", ["horary", "election"])
def test_divination_chart_request_carries_the_orb_pair_only_when_non_default(tmp_path: Path, tool: str) -> None:
    """上游 buildChartParams（chartRequest.js:60-61）`...chartOrbOverridesFromFields(fields)`：非缺省才下发。
    负向对照：在 runner 的 chart_payload 里 pop 掉 orbs / orbScale → 第二、三条断言红（实跑过）。"""
    client = _chart_client()
    service = _service(tmp_path, client)
    assert service.run_tool(tool, MOMENT, save_result=False).ok
    default_body = client.bodies("/chart")[-1]
    assert all(default_body.get(key) is None for key in CHART_ORB_KEYS), "缺省请求体不带容许度对"

    assert service.run_tool(tool, {**MOMENT, "orbs": {"Sun": 10, "Moon": "8.5"}, "orbScale": "1.5"}, save_result=False).ok
    body = client.bodies("/chart")[-1]
    assert body["orbs"] == {"Sun": 10, "Moon": 8.5}
    assert body["orbScale"] == 1.5

    # 缺省态的两种写法（空表 / 倍数 1）归一成不发——与上游 chartOrbOverrides 的输出同（见下面的 JS 差分用例）。
    assert service.run_tool(tool, {**MOMENT, "orbs": {}, "orbScale": 1}, save_result=False).ok
    same = client.bodies("/chart")[-1]
    assert all(same.get(key) is None for key in CHART_ORB_KEYS)


def test_tianxing_moment_chart_carries_the_orb_pair_and_the_scan_does_not(tmp_path: Path) -> None:
    """上游 TianxingElectionMain.previewChartParams（v3.14.0 :421-423）带 `...chartOrbOverridesFromFields(this.props.fields)`，
    并注明「扫描判定不吃它」。负向对照：删掉 `_tianxing_moment_payload` 里那一行 → moment 断言红（KeyError 'orbs'，实跑过）。"""
    client = ScanRecordingClient()
    service = _scan_service(tmp_path, client)
    seen = _capture_base_calls(service)
    env = service.run_tool(
        "tianxing", {**_zeri("tianxing", orbs={"Sun": 6}, orbScale=0.5), "agent_confirmed_settings": True}, save_result=False
    )
    assert env.ok, env.error
    moment = [payload for name, payload in seen if name == "chart"][-1]
    assert (moment["orbs"], moment["orbScale"]) == ({"Sun": 6}, 0.5)
    for scan in client.endpoints("/electionscan/scan") + client.endpoints("/electionscan/explain"):
        assert not any(key in scan for key in CHART_ORB_KEYS), "扫描 / 判读请求不带容许度对"
    # 缺省：选中时刻盘也不带
    seen.clear()
    assert service.run_tool("tianxing", {**_zeri("tianxing"), "agent_confirmed_settings": True}, save_result=False).ok
    default_moment = [payload for name, payload in seen if name == "chart"][-1]
    assert not any(key in default_moment for key in CHART_ORB_KEYS)


# ── 入口校验：后端对认不出的值不报错、只是不用 ───────────────────────────────────────────────────


@pytest.mark.parametrize("tool", ["horary", "election", "tianxing"])
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("orbScale", 0), ("orbScale", -1), ("orbScale", "abc"), ("orbScale", True), ("orbScale", float("nan")), ("orbScale", float("inf")),
        ("orbs", []), ("orbs", "Sun=5"), ("orbs", {"Sun": "x"}), ("orbs", {"Sun": -1}), ("orbs", {"Sun": True}),
    ],
)
def test_unreadable_orb_values_are_rejected_before_any_chart_is_cast(tmp_path: Path, tool: str, field: str, value: Any) -> None:
    """后端 perchart.__init__（:544-557）：orbScale ≤ 0 / 非数 → None（按 1 算）；orbs 里一个值转不成数 → 整张表作废。都不报错。
    页面由容许度面板兜住值域，headless 入口自己兜。负向对照：摘掉三个模型上的 `_orb_pair` 校验 → 这里全红
    （orbScale=0 / orbs={'Sun': -1} 这类 pydantic 类型层收得下的值直接 ok=True，实跑过）。"""
    client = _chart_client()
    service = _service(tmp_path, client)
    base = MOMENT if tool != "tianxing" else {**_zeri("tianxing"), "agent_confirmed_settings": True}
    with pytest.raises(ToolValidationError) as err:
        service.run_tool(tool, {**base, field: value}, save_result=False)
    assert err.value.code == "tool.invalid_option"
    recovery = err.value.details["agent_recovery"]
    assert recovery["kind"] == "input" and recovery["next_action"] == "fix_field_and_retry"
    issue = next(item for item in recovery["fix_fields"] if item["field"] == field)
    assert issue["code"] == "tool.invalid_option" and issue["example"] is not None
    assert client.bodies("/chart") == [], "入参被拒时不该已经起过盘"


def test_orb_table_entries_left_blank_are_treated_as_not_given() -> None:
    """后端同口径（perchart.py:548 `if v is not None and str(v) != ''`）：空项跳过，不算坏值。"""
    assert parse_chart_orbs({"Sun": None, "Moon": "", "Mars": " 7 "}) == {"Mars": 7}
    assert parse_chart_orbs({"Sun": None}) is None and parse_chart_orbs(None) is None
    assert parse_chart_orb_scale("") is None and parse_chart_orb_scale(None) is None
    assert parse_chart_orb_scale(" 2 ") == 2.0 and parse_chart_orb_scale(1.0) is None


@pytest.mark.parametrize("tool", ["horary", "election"])
def test_orb_ids_that_are_not_in_the_chart_are_reported(tmp_path: Path, tool: str) -> None:
    """后端按 `obj.id in orbs` 取值（perchart.applyOrbOverrides :731-733）：写成 `sun` / `太阳` 不报错、只是没用上。
    负向对照：删掉 runner 里的 `_note_unused_orb_ids` 调用 → warnings 为空，断言红（实跑过）。"""
    service = _service(tmp_path, _chart_client())
    env = service.run_tool(tool, {**MOMENT, "orbs": {"sun": 5, "Moon": 9}}, save_result=False)
    assert env.ok
    notes = [w for w in env.warnings if "orbs" in w]
    assert len(notes) == 1 and "sun" in notes[0] and "本盘星体 id" in notes[0] and "Sun" in notes[0]
    assert "Moon 不是" not in notes[0]
    clean = service.run_tool(tool, {**MOMENT, "orbs": {"Sun": 5}}, save_result=False)
    assert not [w for w in clean.warnings if "orbs" in w]


# ── guidance：新口径写在 options_keys ────────────────────────────────────────────────────────────


def get_tool_guidance(tool: str) -> dict[str, Any]:
    return build_agent_guidance(tool_name=tool)["tools"][tool]


def test_guidance_documents_the_orb_pair_on_the_three_tools_that_use_it() -> None:
    for tool in ("horary", "election", "tianxing"):
        text = get_tool_guidance(tool)["options_keys"]["orbs / orbScale"]
        assert "orbScale" in text and "tool.invalid_option" in text and "Sun=15" in text, tool
    assert "扫描判定不读" in get_tool_guidance("tianxing")["options_keys"]["orbs / orbScale"]
    # 其余择日工具的展示盘不是西占盘，上游也不给它们发这一对：不挂说明（挂了就是广告一个死开关）。
    for tool in ("qimenzeri", "huanglizeri", "bazizeri", "taiyizeri", "ziweizeri", "liurengzeri", "sanshizeri", "qizhengzeri", "indiazeri",
                 "qizhengelection"):
        assert "orbs / orbScale" not in (get_tool_guidance(tool).get("options_keys") or {}), tool


def test_technique_card_shows_the_orb_pair_and_who_set_it(tmp_path: Path) -> None:
    """改了结论就变的设置必须逐条回显在技法依据卡上（设置全表只从指引表的 safe_defaults 推）。
    负向对照：删掉 horary 指引表里的 orbScale / orbs 两条 safe_defaults → 卡上没有这两行，KeyError（实跑过）。"""
    service = _service(tmp_path, _chart_client())
    default = service.run_tool("horary", MOMENT, save_result=False).data["technique_card"]["settings"]
    assert (default["orbScale"]["label"], default["orbScale"]["value"], default["orbScale"]["source"]) == ("容许度倍数", 1, "default")
    assert (default["orbs"]["label"], default["orbs"]["value"], default["orbs"]["source"]) == ("逐星容许度", None, "default")
    given = service.run_tool("election", {**MOMENT, "orbScale": 1.5, "orbs": {"Sun": 10}}, save_result=False).data["technique_card"]["settings"]
    assert (given["orbScale"]["value"], given["orbScale"]["source"]) == (1.5, "user")
    assert (given["orbs"]["value"], given["orbs"]["source"]) == ({"Sun": 10}, "user")


# ── 上游源对拍：手抄件的锚 ───────────────────────────────────────────────────────────────────────


def test_python_send_discipline_equals_the_vendored_chart_orb_overrides() -> None:
    """差分：vendored 上游 `chartOrbOverridesFromPlain`（utils/classicalChartGlobals.js）对同一批输入的输出 == Python 归一后会发的键值。
    上游对读不成的值是「不发」，Python 是「拒」——这批只放两边都收的输入；读不成的那批见上面的拒收用例。
    负向对照：把 parse_chart_orb_scale 的「1 → None」去掉 → `{"orbScale": 1}` 这组红（实跑过）。"""
    from node_esm import run_node_esm

    cases: list[dict[str, Any]] = [
        {}, {"orbs": {}}, {"orbScale": 1}, {"orbScale": "1"}, {"orbScale": 1.0000000001}, {"orbScale": 2}, {"orbScale": "0.5"},
        {"orbs": {"Sun": 10}}, {"orbs": {"Sun": 10, "North Node": 3.5}, "orbScale": 1.25},
    ]
    script = (
        "import(process.argv[1]).then((m) => { const cases = JSON.parse(process.argv[2]);"
        " process.stdout.write(JSON.stringify(cases.map((c) => m.chartOrbOverridesFromPlain(c)))); });"
    )
    upstream = json.loads(run_node_esm(script, CORE_JS_SRC / "vendor" / "utils" / "classicalChartGlobals.js", json.dumps(cases)))
    for case, expected in zip(cases, upstream, strict=True):
        sent = {}
        if (orbs := parse_chart_orbs(case.get("orbs"))) is not None:
            sent["orbs"] = orbs
        if (scale := parse_chart_orb_scale(case.get("orbScale"))) is not None:
            sent["orbScale"] = scale
        assert sent == expected, case


@requires_upstream
def test_upstream_still_spreads_the_orb_pair_where_the_python_port_does() -> None:
    """Python 手抄的三处请求（卜卦 / 择日盘、天星择日选中时刻盘）对着上游这三行；上游挪走 / 改名时这里先红。"""
    request = (UPSTREAM_UI / "divination" / "engine" / "chartRequest.js").read_text(encoding="utf-8")
    assert "...chartOrbOverridesFromFields(fields)," in request
    tianxing = (UPSTREAM_UI / "components" / "zeri" / "TianxingElectionMain.js").read_text(encoding="utf-8")
    preview = tianxing[tianxing.index("previewChartParams = (row, which) => {"):]
    preview = preview[: preview.index("\n\t};")]
    assert "...chartOrbOverridesFromFields(this.props.fields)," in preview
    globals_js = (UPSTREAM_UI / "utils" / "classicalChartGlobals.js").read_text(encoding="utf-8")
    assert "export const CHART_ORB_KEYS = ['orbs', 'orbScale'];" in globals_js
    assert CHART_ORB_KEYS == ("orbs", "orbScale")
    # 扫描后端的口径白名单里没有这一对（election_scan.ScanContext 不读它）
    scan = (Path(_UPSTREAM_ROOT) / "Horosa-Web" / "astropy" / "astrostudy" / "election_scan.py").read_text(encoding="utf-8")
    assert "orbScale" not in scan and "'orbs'" not in scan


@requires_upstream
def test_orb_panel_defaults_in_the_guidance_match_upstream_value_for_value() -> None:
    """guidance 里写的「星阙面板的星体与默认度数」抄自 AstroOrbSetting.js DEFAULT_ORBS。负向对照：把 Venus 改成 7 → 红（实跑过）。"""
    text = (UPSTREAM_UI / "components" / "astro" / "AstroOrbSetting.js").read_text(encoding="utf-8")
    block = text[text.index("export const DEFAULT_ORBS = ["):]
    block = block[: block.index("];")]
    upstream = [(body, int(orb)) for body, orb in re.findall(r"\{\s*id:\s*'([^']+)',\s*name:\s*'[^']*',\s*orb:\s*(\d+)\s*\}", block)]
    assert len(upstream) == 11
    assert list(CHART_ORB_DEFAULTS) == upstream


# ── live 值级：改了结果必变 ─────────────────────────────────────────────────────────────────────


def _rows(text: str, title: str) -> list[list[str]]:
    return [[cell.strip() for cell in line.strip("|").split("|")] for line in _section(text, title).splitlines()
            if line.startswith("| ") and "---" not in line]


@requires_chart
def test_live_horary_aspects_follow_the_orb_pair(tmp_path: Path) -> None:
    """2026-03-10 14:20 上海，经典档。期望值是手算：星阙默认容许度（太阳 15 / 月亮 12 / 水星 7 / 火星 8 / 土星 9，
    AstroOrbSetting.DEFAULT_ORBS）乘以倍数或换成 orbs 里的值，再与两星黄经差比——
      太阳 349.68° 合 土星 2.85°：差 13.2°；合 火星 336.04°：差 13.6° —— 只有太阳的 15° 盖得住；
      月亮 247.30° 刑 水星 344.07°：差 6.8° —— 月亮 12° 盖得住，减半（6°）盖不住；
      水星 合 火星：差 8.0° —— 水星 7° / 火星 8° 都差一点，水星 ×1.5（10.5°）才盖住。
    负向对照：runner 的 chart_payload 里 pop 掉 orbs / orbScale → 后三组全红（相位表与缺省相同，实跑过）。"""
    service = make_service(tmp_path)

    def table(**extra: Any) -> set[str]:
        env = service.run_tool("horary", {**MOMENT, **extra}, save_result=False)
        assert env.ok, env.error
        return {" ".join(sorted((row[0], row[2])) + [row[1], row[4]]) for row in _rows(env.data["snapshot_text"], "相位全览")[1:]}

    sun_saturn, sun_mars = "土星 太阳 合相 差 13.2°", "太阳 火星 合相 差 13.6°"
    moon_mercury, mercury_mars = "月亮 水星 四分(刑) 差 6.8°", "水星 火星 合相 差 8.0°"
    default = table()
    assert {sun_saturn, sun_mars, moon_mercury} <= default and mercury_mars not in default
    narrow_sun = table(orbs={"Sun": 2})
    assert sun_saturn not in narrow_sun and sun_mars not in narrow_sun and moon_mercury in narrow_sun
    half = table(orbScale=0.5)
    assert not {sun_saturn, sun_mars, moon_mercury} & half
    wide = table(orbScale=1.5)
    assert {sun_saturn, sun_mars, moon_mercury, mercury_mars} <= wide
    assert table(orbScale=1, orbs={}) == default


@requires_chart
def test_live_election_void_of_course_follows_the_orb_scale(tmp_path: Path) -> None:
    """同一刻的择日盘：月亮离座前唯一的入相是刑水星（差 6.8°）。缺省月亮容许度 12° → 不空亡；倍数 0.5（6°）→ 这一相不成，
    月亮空亡，命中红线。负向对照：同上（pop 掉 orbScale → 两次结果相同，第二组断言红，实跑过）。"""
    service = make_service(tmp_path)
    default = service.run_tool("election", {**MOMENT, "topicId": "marriage"}, save_result=False)
    assert default.ok and "月亮不空亡（入相有果）" in default.data["snapshot_text"]
    assert "命中红线：月亮空亡" not in default.data["snapshot_text"]
    half = service.run_tool("election", {**MOMENT, "topicId": "marriage", "orbScale": 0.5}, save_result=False)
    assert half.ok and "命中红线：月亮空亡" in half.data["snapshot_text"]
    assert "月亮空相（VOC）" in half.data["snapshot_text"]


@requires_chart
def test_live_tianxing_moment_chart_follows_the_orb_pair_while_the_scan_does_not(tmp_path: Path) -> None:
    """[选中时刻星盘] 的标准相位表按「主体星的容许度盖不盖得住」列行（后端 /chart）：把太阳改成 2° / 6°，主体是太阳的行
    只剩误差不超过它的——期望集合由缺省表的误差列手筛出来；命中区间逐字不变（扫描不读容许度）。
    负向对照：删掉 `_tianxing_moment_payload` 里带容许度对的那一行 → 改值后的表与缺省相同，筛选断言红（实跑过）。"""
    service = make_service(tmp_path)
    window = {**MOMENT, "hsys": 0, "startDate": "2026-03-10", "startTime": "14:00", "endDate": "2026-03-10", "endTime": "15:00",
              "conditions": {"kind": "group", "joiner": "all", "children": [{"type": "in_sign", "params": {"planet": "Sun", "signs": [11]}}]}}

    def run(**extra: Any) -> tuple[list[dict[str, Any]], list[float]]:
        env = service.run_tool("tianxing", {**window, **extra}, save_result=False)
        assert env.ok, env.error
        body = env.data["snapshot_text"]
        chart = body[body.index("[选中时刻星盘]"):]
        standard = chart[chart.index("◆ 标准相位") + 1:]
        standard = standard[: standard.index("◆")]  # 到下一张子表（接纳 / 互容…）为止
        errors = [float(cells[4]) for line in standard.splitlines() if line.startswith("| 日 ")
                  for cells in [[c.strip() for c in line.strip("|").split("|")]]]
        return env.data["intervals"], errors

    intervals, default = run()
    assert len(intervals) == 1 and len(default) >= 6 and max(default) > 6 and min(default) < 2
    for orb in (2, 6):
        got_intervals, got = run(orbs={"Sun": orb})
        assert got_intervals == intervals
        assert sorted(got) == sorted(e for e in default if e <= orb), orb
    scaled_intervals, scaled = run(orbScale=0.4)  # 太阳 15° × 0.4 = 6°
    assert scaled_intervals == intervals and sorted(scaled) == sorted(e for e in default if e <= 6)
