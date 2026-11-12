"""星阙 v3.13.1 七政四余同步：[相位] 改七政相位单源 + 日出 / 日没口径（sunriseMode）进七政取盘与 [起盘信息]。

一、[相位]（release：「入相 / 离相日速与位置同口径；盘上相位连线、右栏相位页与 AI 快照同源」）
  上游 components/guolao/GuoLaoMoiraWheel.js:167-240 新增 computeMoiraAspectPairs（盘面连线 / 右栏相位页 / AI 快照同取）：
  七政七相 MOIRA_ASPECTS（會 0°/12 · 衝 180°/6 · 刑 90°/3 · 合 120°/4 · 半合 60°/2 · 半刑 45°·135°/1.5 · 四合 30°·150°/1），
  出厂只勾 會衝刑合半合；角距按盘面口径（黄仪取黄经、赤仪取赤经）；一对星取表序第一个命中的相位；入相 / 离相 = 两星按
  **与位置同口径**的日速（黄仪 lonspeed、赤仪 raspeed；raspeed 恒 0 的合成点退回 lonspeed）推 0.01 日后误差增减，无速度「—」。
  main/aspectsNodeMode.js:8-23 buildGuolaoAspectRows / main/snapshot.js:1252-1271 buildGuolaoAspectSection(result, _gDisp)。
  此前（v3.13.0）skill 与上游都按后端通用占星 chart.aspects 列（「合 (0°) / 六合 (60°) / 容许」，名称与容许度都与七政盘面
  不同）；skill 的 Python 兜底 _build_guolao_aspect_lines 也读那张表 —— 已删，JS 段 builder 整体失败时 [相位] 为「无」。
二、sunriseMode（main/params.js:29-35 guolaoSunriseMode、:174-177 fieldsToParams 仅 apparent 透传；main/snapshot.js:1153
  [起盘信息]「日出口径」行；后端 perchart_parts/timing.py _sunriseMode；Java ChartController.java:567-570 照转 Python）。
  此前 skill 七政不认这个键：用户选了视日出，日出安命与报时星仍按日心口径。

负向对照（实跑过）：
- computeMoiraAspectPairs 的 `const set = o.aspectSet || MOIRA_DEFAULT_ASPECTS` 改成全七相 → 全表复算红（多出半刑 / 四合行）；
- computeMoiraAspectPairs 里 `moiraObjSpeed(obj, preferLon)` 改成 `moiraObjSpeed(obj, true)`（旧「赤仪也拿黄经日速」）→
  赤仪日速用例红（日刑月判成离相）；
- runner 去掉 `remote["sunriseMode"] = "apparent"` → 请求断言红；_guolao_fields 键表去掉 sunriseMode → 「日出口径」行断言红。
"""

from __future__ import annotations

import copy
import math
import os
import re
from pathlib import Path

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

from horosa_skill.errors import ToolValidationError

# 上游常量（逐值，独立于 vendored JS）：PLANET_DEFS 序（GuoLaoMoiraWheel.js:124-144）+ AstroText.AstroTxtMsg 中文名。
_PLANET_ORDER = (
    ("Sun", "日"), ("Moon", "月"), ("Venus", "金"), ("Jupiter", "木"), ("Mercury", "水"), ("Mars", "火"), ("Saturn", "土"),
    ("South Node", "南交"), ("North Node", "北交"), ("Purple Clouds", "紫气"), ("Dark Moon", "暗月"),
    ("Uranus", "天"), ("Neptune", "海"), ("Pluto", "冥"), ("Asc", "上升"), ("MC", "中天"),
)
# MOIRA_ASPECTS（GuoLaoMoiraWheel.js:168-176）：(名, 角, 副角, 容许度)；出厂勾选 MOIRA_DEFAULT_ASPECTS（:177）。
_MOIRA_ASPECTS = (
    ("會", 0, None, 12), ("衝", 180, None, 6), ("刑", 90, None, 3), ("合", 120, None, 4), ("半合", 60, None, 2),
    ("半刑", 45, 135, 1.5), ("四合", 30, 150, 1),
)
_DEFAULT_SET = ("會", "衝", "刑", "合", "半合")


def _js_number(obj: dict, key: str) -> float:
    """JS `Number(x)`：键缺 → NaN；null → 0。"""
    if key not in obj:
        return math.nan
    value = obj[key]
    return 0.0 if value is None else float(value)


def _speed(obj: dict, prefer_lon: bool) -> float | None:
    lon_speed = _js_number(obj, "lonspeed") if "lonspeed" in obj else _js_number(obj, "speed")
    if not prefer_lon and obj.get("raspeed") is not None:
        ra_speed = float(obj["raspeed"])
        if math.isfinite(ra_speed) and (ra_speed != 0 or not math.isfinite(lon_speed) or lon_speed == 0):
            return ra_speed
    return lon_speed if math.isfinite(lon_speed) else None


def _sep(a: float, b: float) -> float:
    g = abs(a - b) % 360
    return 360 - g if g > 180 else g


def _js_round3(x: float) -> str:
    v = math.floor(x * 1000 + 0.5) / 1000
    return str(int(v)) if v.is_integer() else repr(v)


def _expected_rows(chart: dict) -> list[str]:
    """按上游公式独立复算 [相位] 表体行（不读 vendored JS）。"""
    prefer_lon = chart.get("displayCoord") == "ecliptic"
    objs = {o["id"]: o for o in chart["objects"] if isinstance(o, dict)}
    items = []
    for pid, cn in _PLANET_ORDER:
        obj = objs.get(pid)
        if obj is None:
            continue
        raw = obj.get("lon") if prefer_lon and "lon" in obj else (obj.get("ra") if "ra" in obj else obj.get("lon"))
        if raw is None:
            continue
        items.append((cn, float(raw) % 360, _speed(obj, prefer_lon)))
    rows = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            (na, da, sa), (nb, db, sb) = items[i], items[j]
            gap = _sep(da, db)
            hit = None
            for key, angle, alt, orb in _MOIRA_ASPECTS:
                if key not in _DEFAULT_SET:
                    continue
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
            rows.append(f"| {na} | {hit[0]} {hit[1]}° | {nb} | {state} | {_js_round3(err)} |")
    return rows


@requires_node
def test_guolao_aspect_section_is_the_qizheng_single_source_table(tmp_path) -> None:
    env, _ = _guolao_run(tmp_path)
    assert env.ok, env.error
    body = _section(env.data["snapshot_text"], "相位").split("\n")
    assert body[:2] == ["| 主体 | 相位 | 对象 | 状态 | 误差 |", "| --- | --- | --- | --- | --- |"]
    expected = _expected_rows(GUOLAO_FIX["chart_natal"]["chart"])
    assert len(expected) > 10
    assert body[2:] == expected
    # 不再是后端通用占星表：无「容许」态、无「六合 / 三合 / 方」名、无半刑 / 四合（出厂未勾）。
    joined = "\n".join(body)
    for stale in ("容许", "六合", "三合", "(0°)", "半刑", "四合"):
        assert stale not in joined


def _equatorial_patch(chart: dict) -> dict:
    """赤仪盘：日 ra 10°（赤经日速 +1、黄经日速故意 −1）、月 ra 100.5°（+0.2）→ 刑 90° 误差 0.5，按赤经日速是入相，
    旧「赤仪也拿黄经日速」会判成离相；紫气 ra 280.9°、raspeed 恒 0（后端合成点）、lonspeed +1 → 与月衝 180° 误差 0.4，
    退回黄经日速是离相（拿 0 当日速会判入相）。"""
    inner = chart["chart"]
    inner["displayCoord"] = "equatorial"
    for obj in inner["objects"]:
        if obj.get("id") == "Sun":
            obj.update(ra=10.0, raspeed=1.0, lonspeed=-1.0)
        elif obj.get("id") == "Moon":
            obj.update(ra=100.5, raspeed=0.2, lonspeed=0.2)
        elif obj.get("id") == "Purple Clouds":
            obj.update(ra=280.9, raspeed=0, lonspeed=1.0)
    return chart


@requires_node
def test_applying_state_uses_the_speed_of_the_displayed_coordinate(tmp_path) -> None:
    env, _ = _guolao_run(tmp_path, chart_patch=_equatorial_patch)
    assert env.ok, env.error
    body = _section(env.data["snapshot_text"], "相位").split("\n")
    assert "| 日 | 刑 90° | 月 | 入相 | 0.5 |" in body
    assert "| 月 | 衝 180° | 紫气 | 离相 | 0.4 |" in body
    patched = _equatorial_patch(copy_fix())
    assert body[2:] == _expected_rows(patched["chart"])


def copy_fix() -> dict:
    return copy.deepcopy(GUOLAO_FIX["chart_natal"])


@requires_node
def test_js_section_failure_leaves_aspect_none_not_generic_astrology_rows(tmp_path) -> None:
    """JS 段 builder 整体失败：[相位] =「无」（旧版回退读后端 chart.aspects 的通用占星行式，与上游七政相位定义相悖）。"""
    client = GuolaoReplayClient(GUOLAO_FIX)
    service = _service(tmp_path, client)
    real_run = service.js_client.run

    def failing_run(tool, payload, *args, **kwargs):
        if tool == "guolao_moira" and isinstance(payload, dict) and payload.get("action") == "info_sections":
            raise RuntimeError("boom")
        return real_run(tool, payload, *args, **kwargs)

    service.js_client.run = failing_run
    env = service.run_tool("guolao_chart", dict(GUOLAO_FIX["payload"]), save_result=False)
    assert env.ok, env.error
    assert GUOLAO_FIX["chart_natal"]["aspects"]["normalAsp"]  # 桩里确有后端通用相位表（旧兜底读的就是它）
    assert _section(env.data["snapshot_text"], "相位") == "无"
    assert any("[神煞]/[相位] 本次为「无」" in f"{w}" for w in env.warnings)


# ─────────────────────────────── sunriseMode ───────────────────────────────

_SUNRISE_LINE = "日出口径：日面上缘 · 含大气折射(日出安命与报时星按此刻)"


@requires_node
@pytest.mark.parametrize("extra", [{}, {"sunriseMode": "center"}])
def test_sunrise_mode_default_is_not_sent_and_adds_no_line(tmp_path, extra) -> None:
    env, client = _guolao_run(tmp_path, extra)
    assert env.ok, env.error
    assert all("sunriseMode" not in req for req in client.requests("/chart"))   # 缺省不发 = 零回归
    assert _SUNRISE_LINE not in env.data["snapshot_text"]


@requires_node
def test_apparent_sunrise_mode_reaches_backend_and_setup_line(tmp_path) -> None:
    env, client = _guolao_run(tmp_path, {"sunriseMode": "apparent", "guolaoLifeMode": "yumao"})
    assert env.ok, env.error
    charts = client.requests("/chart")
    assert len(charts) >= 2 and all(req.get("sunriseMode") == "apparent" for req in charts)   # 本命 / Java 命度点 / 流年
    (moira,) = client.requests("/qizheng/moira")
    assert moira["params"]["sunriseMode"] == "apparent"
    lines = _section(env.data["snapshot_text"], "起盘信息").split("\n")
    at = next(i for i, line in enumerate(lines) if line.startswith("罗计取法："))
    assert lines[at + 1] == _SUNRISE_LINE   # main/snapshot.js:1152-1153 紧随罗计取法行


def test_invalid_sunrise_mode_is_refused_before_any_backend_call(tmp_path) -> None:
    client = GuolaoReplayClient(GUOLAO_FIX)
    with pytest.raises(ToolValidationError) as info:
        _service(tmp_path, client).run_tool("guolao_chart", {**GUOLAO_FIX["payload"], "sunriseMode": "sunrise"}, save_result=False)
    # v0.50.0 起 sunriseMode 走古典口径词表（western_vocab），拒码 = tool.invalid_option、可选值在 options。
    assert info.value.code == "tool.invalid_option"
    assert [o["value"] for o in info.value.details["options"]] == ["center", "apparent"]
    assert client.requests("/chart") == []


# ─────────────────────────────── live（vendored v3.13.1 实例）───────────────────────────────

@requires_runtime
@requires_node
def test_live_apparent_sunrise_moves_the_backend_sunrise_earlier(tmp_path) -> None:
    """后端真认 sunriseMode：同盘视日出（上缘 + 折射）比日心口径早几分钟（中纬约 4 分钟）。"""
    seen: dict[str, dict] = {}
    for mode in ("center", "apparent"):
        service = make_service(tmp_path / mode)
        real = service._call_remote

        def spy(endpoint, payload, *args, _mode=mode, _real=real, **kwargs):
            resp = _real(endpoint, payload, *args, **kwargs)
            if endpoint == "/chart" and not payload.get("predictive") and kwargs.get("backend") != "java":
                seen.setdefault(_mode, resp)
            return resp

        service._call_remote = spy
        env = service.run_tool("guolao_chart", {**GUOLAO_FIX["payload"], "sunriseMode": mode}, save_result=False)
        assert env.ok, env.error
        assert (_SUNRISE_LINE in env.data["snapshot_text"]) is (mode == "apparent")
    center = seen["center"]["chart"]["sunRiseTime"]
    apparent = seen["apparent"]["chart"]["sunRiseTime"]

    def secs(t: str) -> int:
        h, m, s = (int(x) for x in t.split(":"))
        return h * 3600 + m * 60 + s

    assert 60 < secs(center) - secs(apparent) < 15 * 60, (center, apparent)


# ─────────────────────────────── 上游表漂移哨兵 ───────────────────────────────

_UPSTREAM = Path(os.environ.get("HOROSA_SOURCE_ROOT", "")) / "Horosa-Web/astrostudyui/src/components/guolao/GuoLaoMoiraWheel.js"


@pytest.mark.skipif(not os.environ.get("HOROSA_SOURCE_ROOT") or not _UPSTREAM.is_file(), reason="[upstream-checkout] needs HOROSA_SOURCE_ROOT")
def test_independent_aspect_table_matches_upstream() -> None:
    src = _UPSTREAM.read_text(encoding="utf-8")
    block = src[src.index("const MOIRA_ASPECTS = ["):src.index("const MOIRA_DEFAULT_ASPECTS")]
    rows = re.findall(r"\{key: '([^']+)', angle: (\d+)(?:, alt: (\d+))?, orb: ([\d.]+)", block)
    assert tuple((k, int(a), int(alt) if alt else None, float(o)) for k, a, alt, o in rows) == tuple(
        (k, a, alt, float(o)) for k, a, alt, o in _MOIRA_ASPECTS
    )
    default = re.search(r"const MOIRA_DEFAULT_ASPECTS = \[([^\]]+)\]", src).group(1)
    assert tuple(re.findall(r"'([^']+)'", default)) == _DEFAULT_SET
