"""七政 [相位] 的显示偏好：guolaoAspects / guolaoAspectOrbs / guolaoHiddenPlanets（星阙 v3.13.1 @06f25f21）。

上游：页面显示偏好 horosaGuolaoDisplay（components/guolao/GuoLaoChartStyle.js:355 GUOLAO_ALL_ASPECTS、:367-391
GUOLAO_DEFAULT_DISPLAY.aspects / hiddenPlanets / aspectOrbs、:392-407 normHiddenList / normAspectOrbs 0–30）；
无头复算以本机偏好为底（main/snapshot.js:1098-1112 guolaoSnapshotDisplayFromFields → getStoredGuolaoDisplay），
main/snapshot.js:1221 buildGuolaoAspectSection(result, _gDisp) → main/aspectsNodeMode.js:12-23 buildGuolaoAspectRows →
GuoLaoMoiraWheel.js:200-240 computeMoiraAspectPairs（只列勾选相位、按容许度覆盖、隐藏的曜不参与；PLANET_DEFS :124-144 标签）。
挂载齿轮（techniqueMountSettings.js）不收这三项，快照也不印设置行 —— 只改 [相位] 表体。
此前 skill 的 vendored 引擎早已收 display 三键（tools/guolaoMoira.js 透传），但 GuoLaoInput 没有入口：用户改不了七政相位口径。

负向对照（实跑过）：
- runners/guolao._guolao_display_settings 去掉 `display.update(self._guolao_aspect_display_prefs(payload))` → 相位集 / 空集 /
  容许度 / 隐藏四条与非法值六条红（表体回到出厂、非法值不再报错）；
- _guolao_aspect_display_prefs 的 `if picked != set(...DEFAULT...)` 改成恒真 → 缺省零回归用例（同集换序 / 简体别名）红（JS 收到 aspects 键）；
- runner 表 _GUOLAO_ASPECT_BUILTIN_ORBS 把 刑 3 改 4 → 上游逐值看守红（「与内置同值」用例也红：刑 3 被当成覆盖下发）。
"""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any

import pytest
from test_local_js_tools import make_service, requires_runtime
from test_sync311_w3b_gim import (
    GUOLAO_FIX,
    GuolaoReplayClient,
    _guolao_run,
    _section,
    _service,
    requires_node,
)
from test_sync3131_guolao import _MOIRA_ASPECTS, _PLANET_ORDER, _js_round3, _sep, _speed

from horosa_skill.errors import ToolValidationError
from horosa_skill.service.runners.guolao import GuolaoRunners

# 测试侧独立的 PLANET_DEFS 标签（id → 盘面标签，GuoLaoMoiraWheel.js:124-144）。
_LABEL = {
    "Sun": "日", "Moon": "月", "Venus": "金", "Jupiter": "木", "Mercury": "水", "Mars": "火", "Saturn": "土",
    "South Node": "计", "North Node": "罗", "Purple Clouds": "炁", "Dark Moon": "孛", "Uranus": "天", "Neptune": "海",
    "Pluto": "冥", "Asc": "升", "MC": "顶",
}
_DEFAULT_SET = ("會", "衝", "刑", "合", "半合")


def _rows(chart: dict, aspect_set=_DEFAULT_SET, orbs: dict | None = None, hidden: tuple[str, ...] = ()) -> list[str]:
    """按上游 computeMoiraAspectPairs 公式独立复算 [相位] 表体（不读 vendored JS）。hidden = 盘面标签。"""
    orbs = orbs or {}
    prefer_lon = chart.get("displayCoord") == "ecliptic"
    objs = {o["id"]: o for o in chart["objects"] if isinstance(o, dict)}
    items = []
    for pid, cn in _PLANET_ORDER:
        obj = objs.get(pid)
        if obj is None or _LABEL[pid] in hidden:
            continue
        raw = obj.get("lon") if prefer_lon and "lon" in obj else (obj.get("ra") if "ra" in obj else obj.get("lon"))
        if raw is None:
            continue
        items.append((cn, float(raw) % 360, _speed(obj, prefer_lon)))
    out = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            (na, da, sa), (nb, db, sb) = items[i], items[j]
            gap = _sep(da, db)
            hit = None
            for key, angle, alt, orb in _MOIRA_ASPECTS:
                if key not in aspect_set:
                    continue
                orb = orbs.get(key, orb)
                if abs(gap - angle) <= orb:
                    hit = (key, angle)
                    break
                if alt is not None and abs(gap - alt) <= orb:
                    hit = (key, alt)
                    break
            if not hit:
                continue
            err = abs(gap - hit[1])
            state = "—"
            if sa is not None and sb is not None:
                nxt = abs(_sep(da + sa * 0.01, db + sb * 0.01) - hit[1])
                state = "精确" if err < 1e-6 else ("入相" if nxt < err else "离相")
            out.append(f"| {na} | {hit[0]} {hit[1]}° | {nb} | {state} | {_js_round3(err)} |")
    return out


def _body(env) -> list[str]:
    assert env.ok, env.error
    return _section(env.data["snapshot_text"], "相位").split("\n")


def _without_aspects(text: str) -> str:
    return text[: text.index("[相位]\n")]


_CHART = GUOLAO_FIX["chart_natal"]["chart"]


@requires_node
@pytest.mark.parametrize("extra", [
    {},
    {"guolaoAspects": ["衝", "會", "合", "半合", "刑"]},              # 与出厂同集（换序）
    {"guolaoAspects": "会,冲,刑,合,半合"},                           # 简体别名 + 逗号串
    {"guolaoAspectOrbs": {"會": 12, "刑": 3.0}},                     # 与内置容许度同值
    {"guolaoAspectOrbs": {}, "guolaoHiddenPlanets": []},
])
def test_default_or_factory_equal_prefs_change_nothing(tmp_path, extra) -> None:
    """缺省不下发 = 零回归：整份快照逐字等于录制的 live 快照，JS 收到的 display 不带三键。"""
    client = GuolaoReplayClient(GUOLAO_FIX)
    service = _service(tmp_path, client)
    seen: list[dict[str, Any]] = []
    real_run = service.js_client.run

    def spy(tool, payload, *args, **kwargs):
        if tool == "guolao_moira" and isinstance(payload, dict) and payload.get("action") == "info_sections":
            seen.append(dict(payload["display"]))
        return real_run(tool, payload, *args, **kwargs)

    service.js_client.run = spy
    env = service.run_tool("guolao_chart", {**GUOLAO_FIX["payload"], **extra}, save_result=False)
    assert env.ok, env.error
    assert env.data["snapshot_text"] == GUOLAO_FIX["live_snapshot_text"]
    assert len(seen) == 1 and not {"aspects", "aspectOrbs", "hiddenPlanets"} & set(seen[0])


@requires_node
def test_aspect_set_picks_which_qizheng_aspects_are_listed(tmp_path) -> None:
    picked = ("會", "半刑", "四合")
    body = _body(_guolao_run(tmp_path, {"guolaoAspects": list(picked)})[0])
    expected = _rows(_CHART, picked)
    assert body[2:] == expected and expected != _rows(_CHART)
    joined = "\n".join(body)
    assert "半刑 " in joined and "四合 " in joined and "衝 180°" not in joined


@requires_node
def test_empty_aspect_set_lists_nothing(tmp_path) -> None:
    """上游 `if(!set || !set.length) return []` → 段为「无」。"""
    assert _body(_guolao_run(tmp_path, {"guolaoAspects": []})[0]) == ["无"]


@requires_node
def test_orb_override_widens_only_that_aspect(tmp_path) -> None:
    body = _body(_guolao_run(tmp_path, {"guolaoAspectOrbs": {"刑": 8}})[0])
    expected = _rows(_CHART, orbs={"刑": 8})
    assert body[2:] == expected
    added = set(expected) - set(_rows(_CHART))
    assert added and all(" 刑 90° " in row for row in added)


@requires_node
def test_hidden_planets_drop_out_of_the_aspect_table(tmp_path) -> None:
    env, _ = _guolao_run(tmp_path, {"guolaoHiddenPlanets": "月,Sun,羅"})   # 标签 / id / 繁体标签
    body = _body(env)
    assert body[2:] == _rows(_CHART, hidden=("月", "日", "罗"))
    for row in body[2:]:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        assert not {"日", "月", "北交"} & {cells[0], cells[2]}, row
    # 只改 [相位]：其余各段（含 [起盘信息]，上游不印设置行）逐字同缺省。
    assert _without_aspects(env.data["snapshot_text"]) == _without_aspects(GUOLAO_FIX["live_snapshot_text"])


@requires_node
@pytest.mark.parametrize("extra,field", [
    ({"guolaoAspects": ["六合"]}, "guolaoAspects"),
    ({"guolaoAspects": 7}, "guolaoAspects"),
    ({"guolaoAspectOrbs": {"刑": 31}}, "guolaoAspectOrbs.刑"),
    ({"guolaoAspectOrbs": {"刑": -1}}, "guolaoAspectOrbs.刑"),
    ({"guolaoAspectOrbs": {"刑": "宽"}}, "guolaoAspectOrbs.刑"),
    ({"guolaoAspectOrbs": {"三合": 4}}, "guolaoAspectOrbs"),
    ({"guolaoHiddenPlanets": ["太阳"]}, "guolaoHiddenPlanets"),
])
def test_invalid_prefs_are_refused_before_any_backend_call(tmp_path, extra, field) -> None:
    """非法值报错（上游 norm* 静默滤掉 → 用户以为改了、其实没变）；类型错由 pydantic 先拦（tool.invalid_payload）。"""
    client = GuolaoReplayClient(GUOLAO_FIX)
    try:
        env = _service(tmp_path, client).run_tool("guolao_chart", {**GUOLAO_FIX["payload"], **extra}, save_result=False)
    except ToolValidationError as exc:
        code, details = exc.code, exc.details
    else:
        assert not env.ok
        code, details = env.error.code, env.error.details
    assert code in ("tool.guolao_invalid_display_setting", "tool.invalid_payload")
    if code == "tool.guolao_invalid_display_setting":
        assert details["field"] == field
    assert client.requests("/chart") == []


def test_prefs_are_hidden_from_tools_list_but_documented_in_guidance() -> None:
    from horosa_skill.agent_guidance import build_agent_guidance
    from horosa_skill.engine.registry import TOOL_DEFINITIONS
    from horosa_skill.surfaces.mcp_schema import advertised_technique_schema

    keys = {"guolaoAspects", "guolaoAspectOrbs", "guolaoHiddenPlanets"}
    schema = advertised_technique_schema("guolao_chart", TOOL_DEFINITIONS["guolao_chart"].input_model.model_json_schema())
    assert not keys & set(schema["properties"])
    assert keys <= set(build_agent_guidance(tool_name="guolao_chart")["tools"]["guolao_chart"]["options_keys"])


# ─────────────────────────────── 上游表逐值看守 ───────────────────────────────

_ROOT = os.environ.get("HOROSA_SOURCE_ROOT")
_GUOLAO_DIR = Path(_ROOT) / "Horosa-Web" / "astrostudyui" / "src" / "components" / "guolao" if _ROOT else None
requires_upstream = pytest.mark.skipif(
    _GUOLAO_DIR is None or not _GUOLAO_DIR.is_dir(), reason="[upstream-checkout] HOROSA_SOURCE_ROOT (Horosa-Public checkout) not set"
)


@requires_upstream
def test_runner_tables_match_upstream_value_for_value() -> None:
    style = (_GUOLAO_DIR / "GuoLaoChartStyle.js").read_text(encoding="utf-8")
    wheel = (_GUOLAO_DIR / "GuoLaoMoiraWheel.js").read_text(encoding="utf-8")
    const = (_GUOLAO_DIR.parent.parent / "constants" / "AstroConst.js").read_text(encoding="utf-8")

    def str_list(pattern: str, text: str) -> list[str]:
        return re.findall(r"'([^']+)'", re.search(pattern, text).group(1))

    assert tuple(str_list(r"export const GUOLAO_ALL_ASPECTS = \[([^\]]+)\]", style)) == GuolaoRunners._GUOLAO_ALL_ASPECTS
    default_display = style[style.index("export const GUOLAO_DEFAULT_DISPLAY = {"):]
    assert tuple(str_list(r"aspects: \[([^\]]+)\]", default_display)) == GuolaoRunners._GUOLAO_DEFAULT_ASPECTS
    assert tuple(str_list(r"const MOIRA_DEFAULT_ASPECTS = \[([^\]]+)\]", wheel)) == GuolaoRunners._GUOLAO_DEFAULT_ASPECTS
    block = wheel[wheel.index("const MOIRA_ASPECTS = ["):wheel.index("const MOIRA_DEFAULT_ASPECTS")]
    orbs = {k: float(o) for k, o in re.findall(r"\{key: '([^']+)', angle: \d+(?:, alt: \d+)?, orb: ([\d.]+)", block)}
    assert orbs == {k: float(v) for k, v in GuolaoRunners._GUOLAO_ASPECT_BUILTIN_ORBS.items()}
    norm = style[style.index("function normAspectOrbs"):style.index("function normLifeMasterMode")]
    assert "num >= 0 && num <= 30" in norm and GuolaoRunners._GUOLAO_ASPECT_ORB_MAX == 30
    ids = dict(re.findall(r"^export const ([A-Z_]+) = '([^']+)'", const, re.MULTILINE))
    defs_block = wheel[wheel.index("const PLANET_DEFS = ["):wheel.index("];", wheel.index("const PLANET_DEFS = ["))]
    defs = tuple((ids[name], label) for name, label in re.findall(r"\{id: AstroConst\.([A-Z_]+), label: '([^']+)'\}", defs_block))
    assert defs == GuolaoRunners._GUOLAO_PLANET_DEFS
    assert {pid: label for pid, label in defs} == _LABEL   # 测试侧独立表也对上游


# ─────────────────────────────── live（vendored v3.13.1 实例）───────────────────────────────

@requires_runtime
@requires_node
def test_live_prefs_reshape_the_aspect_table_from_the_backend_chart() -> None:
    """真后端盘：缺省 [相位] = 出厂复算；非缺省三键 = 按偏好复算，且与缺省不同（盘取自本次 /chart 响应，不手算）。"""
    prefs = {"guolaoAspects": ["會", "衝", "刑", "半刑"], "guolaoAspectOrbs": {"刑": 6, "會": 4}, "guolaoHiddenPlanets": ["土"]}
    bodies: dict[str, list[str]] = {}
    charts: dict[str, dict] = {}
    for label, extra in (("default", {}), ("prefs", prefs)):
        service = make_service(Path(tempfile.mkdtemp()))
        real = service._call_remote

        def spy(endpoint, payload, *args, _label=label, _real=real, **kwargs):
            resp = _real(endpoint, payload, *args, **kwargs)
            if endpoint == "/chart" and not payload.get("predictive") and kwargs.get("backend") != "java":
                charts.setdefault(_label, resp)
            return resp

        service._call_remote = spy
        bodies[label] = _body(service.run_tool("guolao_chart", {**GUOLAO_FIX["payload"], **extra}, save_result=False))
    assert bodies["default"][2:] == _rows(charts["default"]["chart"])
    assert bodies["prefs"][2:] == _rows(charts["prefs"]["chart"], ("會", "衝", "刑", "半刑"), {"刑": 6, "會": 4}, ("土",))
    assert bodies["prefs"] != bodies["default"]
