"""日界两开关与公元前写法：入口只留一种形态，所有消费方吃同一个值（v0.50.0 深审 C-09 / CN-N2 / C-22 ad）。

一、日界（after23NewDay / lateZiHourUseNextDay）
  太乙不给开关时快照印「换日：24点算第二天」而日柱按 23 点进位；options.after23NewDay 只到了快照，/nongli/time 与 /taiyi/pan
  用顶层 → 盘头辛酉、正文壬戌；大六壬把 options 里的这两个键当未知键拒掉，奇门 / 神数又照收——同一个开关三种规矩。
  现在（input_normalization._lift_day_switches）：顶层与口径对象（options / 三式合一三层口径）都可以写，入口合成一个顶层值，
  两处不同 → tool.field_conflict；取值只收 1 / 0（旧代码把 'bogus'、2 悄悄读成 24 点换日）。生效值缺省 = 上游出厂 1 / 1。
二、公元前（ad）
  `ad=-1` + 不带负号的日期：太乙农历按公元前、年柱按公元；金口诀月将卯 / 戌；正传 / 小六壬 / 轨策 / 小成图 / 神数 ×14 / 灵棋 /
  河洛 / 参评整个丢掉 ad。带负号的写法各技法一致 → 入口改写成带负号的日期（input_normalization._fold_era），ad 只收 1 / -1。

负向对照（实跑过，见 LESSONS 2026-11-12「日界与公元前」）：
- 删掉 `_lift_day_switches` 调用 → 提升 / 冲突 / 太乙三方一致用例红；
- 太乙 runner 把 JS 的 options 改回 `payload.get("options")`（不补缺省）→ 「缺省时快照与引擎同值」用例红；
- 删掉 `_fold_era` 里的改写 → 改写用例与 live 公元前全目录用例红；
- `parse_day_switch` 改回「不是 1 就当 0」→ 拒绝表红。
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

import pytest
from test_local_js_tools import make_service, requires_runtime

from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.errors import ToolValidationError
from horosa_skill.input_fields import FieldIssue, input_notes_scope, parse_day_switch, parse_era
from horosa_skill.input_normalization import normalize_request_payload
from horosa_skill.testing_payloads import build_sample_payloads

TAIYI = TOOL_DEFINITIONS["taiyi"].input_model
HELUO = TOOL_DEFINITIONS["heluo"].input_model
DAY_TOOLS = sorted(name for name, d in TOOL_DEFINITIONS.items() if "after23NewDay" in getattr(d.input_model, "model_fields", {}))


# ───────────── 取值表 ─────────────

@pytest.mark.parametrize("value, expected", [
    (1, 1), (0, 0), (True, 1), (False, 0), ("1", 1), ("0", 0), ("true", 1), ("false", 0), ("True", 1), (1.0, 1),
])
def test_day_switch_accepts(value: Any, expected: int) -> None:
    assert parse_day_switch(value).value == expected


@pytest.mark.parametrize("value", ["bogus", 2, -1, "2", "23点", 0.5, "yes please"])
def test_day_switch_refuses(value: Any) -> None:
    with pytest.raises(FieldIssue) as caught:
        parse_day_switch(value)
    assert caught.value.code == "tool.invalid_option"
    assert {item["value"] for item in caught.value.options} == {0, 1}


@pytest.mark.parametrize("value, expected", [
    (1, 1), (-1, -1), ("1", 1), ("-1", -1), ("−1", -1), ("BC", -1), ("bce", -1), ("公元前", -1), ("AD", 1), ("公元", 1), (-1.0, -1),
])
def test_era_accepts(value: Any, expected: int) -> None:
    assert parse_era(value).value == expected


@pytest.mark.parametrize("value", [0, "0", 2, True, False, "BCE?", "-2", ""])
def test_era_refuses(value: Any) -> None:
    with pytest.raises(FieldIssue) as caught:
        parse_era(value)
    assert caught.value.code == "tool.invalid_option"
    assert [item["value"] for item in caught.value.options] == [1, -1]


# ───────────── 入口：日界只有一个值 ─────────────

def test_day_switch_in_options_is_lifted_to_top_level() -> None:
    with input_notes_scope() as notes:
        out = normalize_request_payload({"date": "2028-04-06", "options": {"after23NewDay": 0, "style": 3}}, model=TAIYI)
    assert out["after23NewDay"] == 0 and out["options"] == {"style": 3}
    assert any("options.after23NewDay" in note for note in notes)


@pytest.mark.parametrize("holder", ["qimen_options", "taiyi_options", "liureng_options"])
def test_sanshiunited_layer_options_are_lifted_too(holder: str) -> None:
    model = TOOL_DEFINITIONS["sanshiunited"].input_model
    out = normalize_request_payload({"date": "2028-04-06", holder: {"lateZiHourUseNextDay": "0"}}, model=model)
    assert out["lateZiHourUseNextDay"] == 0 and out[holder] == {}


def test_day_switch_conflict_is_refused() -> None:
    with pytest.raises(ToolValidationError) as caught:
        normalize_request_payload({"date": "2028-04-06", "after23NewDay": 1, "options": {"after23NewDay": 0}}, model=TAIYI)
    assert caught.value.code == "tool.field_conflict"
    assert caught.value.details["field"] == "options.after23NewDay"


def test_same_value_in_both_places_is_fine() -> None:
    out = normalize_request_payload({"date": "2028-04-06", "after23NewDay": True, "options": {"after23NewDay": "1"}}, model=TAIYI)
    assert out["after23NewDay"] == 1 and "after23NewDay" not in out["options"]


def test_bad_day_switch_value_in_options_is_refused_with_its_path() -> None:
    with pytest.raises(ToolValidationError) as caught:
        normalize_request_payload({"date": "2028-04-06", "options": {"after23NewDay": "bogus"}}, model=TAIYI)
    assert caught.value.code == "tool.invalid_option" and caught.value.details["field"] == "options.after23NewDay"


def test_tools_without_the_switch_keep_their_options_untouched() -> None:
    model = TOOL_DEFINITIONS["tarot"].input_model
    out = normalize_request_payload({"options": {"after23NewDay": 0}}, model=model)
    assert out["options"] == {"after23NewDay": 0} and "after23NewDay" not in out


# ───────────── 入口：公元前只有一种写法 ─────────────

def test_ad_minus_one_with_unsigned_date_becomes_the_signed_date() -> None:
    with input_notes_scope() as notes:
        out = normalize_request_payload({"date": "0500-04-06", "ad": "-1"}, model=TAIYI)
    assert out["date"] == "-0500-04-06" and out["ad"] == -1
    assert any("公元前" in note for note in notes)
    # 幂等：第二遍不再改、不再记说明
    with input_notes_scope() as again:
        assert normalize_request_payload(out, model=TAIYI) == out
    assert again == []


def test_signed_date_without_ad_is_left_alone() -> None:
    out = normalize_request_payload({"date": "-0500-04-06"}, model=TAIYI)
    assert out == {"date": "-0500-04-06"}


def test_gua_date_folds_with_gua_ad() -> None:
    model = TOOL_DEFINITIONS["liureng_runyear"].input_model
    out = normalize_request_payload({"date": "1990-01-01", "guaDate": "0300-05-01", "guaAd": -1}, model=model)
    assert out["guaDate"] == "-0300-05-01" and out["date"] == "1990-01-01"


def test_undeclared_ad_is_folded_then_dropped() -> None:
    out = normalize_request_payload({"date": "0500-04-06", "ad": -1}, model=HELUO)
    assert out == {"date": "-0500-04-06"}


def test_nested_parties_fold_too() -> None:
    out = normalize_request_payload({"birth": {"date": "0500-04-06", "ad": -1}}, model=None)
    assert out["birth"]["date"] == "-0500-04-06"


def test_ad_zero_is_refused() -> None:
    with pytest.raises(ToolValidationError) as caught:
        normalize_request_payload({"date": "0500-04-06", "ad": 0}, model=TAIYI)
    assert caught.value.code == "tool.invalid_option" and caught.value.details["field"] == "ad"


# ───────────── 太乙：农历前置、ken、快照吃同一个值 ─────────────

class _Recorder:
    def __init__(self, service) -> None:
        self.remote: dict[str, dict[str, Any]] = {}
        self.js_options: dict[str, Any] | None = None
        service._call_remote = self.call_remote
        service.js_client.run = self.js_run

    def call_remote(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.remote[endpoint] = payload
        if endpoint == "/taiyi/pan":
            return {"source": "kintaiyi"}
        return {"birth": "2028-04-06 23:30:00", "jiedelta": "", "dayGanZi": "壬戌"}

    def js_run(self, tool: str, payload: dict[str, Any]) -> dict[str, Any]:
        if tool == "taiyi":
            self.js_options = dict(payload.get("options") or {})
        return {"data": {}, "snapshot_text": "[起盘信息]\n占位"}


@pytest.mark.parametrize("variant, expected", [
    ({}, 1),
    ({"after23NewDay": 1}, 1),
    ({"after23NewDay": 0}, 0),
    ({"options": {"after23NewDay": 1}}, 1),
    ({"options": {"after23NewDay": 0}}, 0),
])
def test_taiyi_feeds_one_day_boundary_value_to_every_consumer(tmp_path, variant: dict[str, Any], expected: int) -> None:
    service = make_service(tmp_path)
    recorder = _Recorder(service)
    payload = {**build_sample_payloads()["taiyi"], "time": "23:30:00", **variant}
    service.run_tool("taiyi", payload, save_result=False)
    assert recorder.js_options is not None, "taiyi formatter never ran"
    assert recorder.js_options["after23NewDay"] == expected  # 快照「换日」行
    for endpoint in ("/nongli/time", "/taiyi/pan"):
        sent = recorder.remote[endpoint].get("after23NewDay")
        # 缺省不发 = 引擎缺省 1（live 用例钉住）；显式给了就照发
        assert (sent if sent is not None else 1) == expected, endpoint


# ───────────── live：盘头与正文对得上（全部带开关的技法 × 有无 options） ─────────────

def _export(service, tool: str, payload: dict[str, Any]) -> str:
    env = service.run_tool(tool, payload, save_result=False)
    assert env.ok, (tool, env.error)
    return ((env.data.get("export_snapshot") or {}).get("export_text")) or env.data.get("snapshot_text") or ""


def _digest(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()


@requires_runtime
@pytest.mark.parametrize("tool", DAY_TOOLS)
def test_live_day_boundary_header_and_body_agree(tmp_path, tool: str) -> None:
    samples = build_sample_payloads()
    if tool not in samples:
        pytest.skip(f"no sample payload for {tool}")
    service = make_service(tmp_path)
    base = {k: v for k, v in samples[tool].items() if k not in ("after23NewDay", "lateZiHourUseNextDay")}
    base["time"] = "23:30:00"
    if "startDate" in base:
        base.update({"startDate": "2028-04-06", "endDate": "2028-04-06"})
    options = dict(base.get("options") or {})
    texts = {
        label: _export(service, tool, {**base, **extra})
        for label, extra in (
            ("omit", {}), ("top1", {"after23NewDay": 1}), ("top0", {"after23NewDay": 0}),
            ("opt1", {"options": {**options, "after23NewDay": 1}}), ("opt0", {"options": {**options, "after23NewDay": 0}}),
        )
    }
    # 缺省 = 23 点换日；写在顶层还是 options 里结果都一样
    assert _digest(texts["omit"]) == _digest(texts["top1"]) == _digest(texts["opt1"]), tool
    assert _digest(texts["top0"]) == _digest(texts["opt0"]), tool
    # 印了日界标签的技法：标签与所用开关一致（三种写法：「换日：23点算第二天」「23 点换日：是」「日柱开关【23点…】」）
    for label, text in texts.items():
        want = "24" if label.endswith("0") else "23"
        printed = re.findall(r"换日：(2[34])点", text) + re.findall(r"日柱开关【(2[34])点", text)
        printed += ["23" if yes == "是" else "24" for yes in re.findall(r"23 ?点换日：(是|否)", text)]
        assert all(value == want for value in printed), (tool, label, printed)


# ───────────── 公元前：全目录同一种写法 ─────────────

DATE_TOOLS = sorted(name for name, d in TOOL_DEFINITIONS.items() if "date" in getattr(d.input_model, "model_fields", {}))


@pytest.mark.parametrize("tool", DATE_TOOLS)
def test_every_dated_technique_sees_one_bc_form(tool: str) -> None:
    """ad=-1 + 不带负号的日期 与 带负号的日期 + ad=-1，归一后逐字段相同——于是每个技法的结果也相同（同一份载荷）。"""
    model = TOOL_DEFINITIONS[tool].input_model
    unsigned = normalize_request_payload({"date": "0500-04-06", "time": "09:33:00", "ad": -1}, model=model)
    signed = normalize_request_payload({"date": "-0500-04-06", "time": "09:33:00", "ad": -1}, model=model)
    assert unsigned == signed
    assert unsigned["date"] == "-0500-04-06"


# 以前丢掉 ad（或一半用 ad、一半用日期）的技法 + 公元前改由入口统一后需要自己读带符号年的两个（巴比伦、老黄历）。
_BC_LIVE = ("taiyi", "jinkou", "zhengchuan", "lingqi", "tieban", "sanshiunited", "chart", "babylon", "calendar_month", "huangli", "heluo")


@requires_runtime
@pytest.mark.parametrize("tool", _BC_LIVE)
def test_live_bc_forms_agree_and_differ_from_ad(tmp_path, tool: str) -> None:
    service = make_service(tmp_path)
    sample = build_sample_payloads()[tool]

    def outcome(date: str, ad: int) -> tuple[str, str]:
        try:
            env = service.run_tool(tool, {**sample, "date": date, "ad": ad}, save_result=False)
        except ToolValidationError as exc:
            return "refused", exc.code
        if not env.ok:
            return "refused", env.error.code
        text = ((env.data.get("export_snapshot") or {}).get("export_text")) or env.data.get("snapshot_text") or ""
        return "ok", re.sub(r"-?0500([-/])04\1(0?6)", "<D>", text)

    unsigned, signed, ad_form = outcome("0500-04-06", -1), outcome("-0500-04-06", -1), outcome("0500-04-06", 1)
    assert unsigned == signed, tool
    if unsigned[0] == "refused":
        # 引擎算不了公元前的技法明确拒（以前悄悄按公元算或出空盘）
        assert unsigned[1] == "tool.date_range_unsupported", (tool, unsigned)
    else:
        assert unsigned != ad_form, f"{tool}: the BC chart equals the AD 500 chart"


@pytest.mark.parametrize("message, code", [
    ("公元 1~9999 年之外(输入 -500 年)的农历/干支需走星历实算路径,本地速算不适用", "tool.date_range_unsupported"),
    ("heluo requires a birth date.", "tool.heluo_missing_inputs"),
])
def test_local_engine_insufficient_input_is_refused_not_hollow(message: str, code: str) -> None:
    """河洛 / 参评 / 一掌经的本地引擎回 data.ok=false 时以前照回 ok=true（每段都是「未返回」占位）。"""
    from horosa_skill.service.runners.mingli import _raise_if_insufficient

    _raise_if_insufficient("heluo", {"data": {"ok": True}})  # 正常回包不拦
    with pytest.raises(ToolValidationError) as caught:
        _raise_if_insufficient("heluo", {"data": {"ok": False, "reason": "invalid_bazi_input", "message": message}, "snapshot_text": ""})
    assert caught.value.code == code


@pytest.mark.parametrize("date", ["-0500-04-06", "10000-01-01"])
def test_lunar_js_calendar_tools_refuse_dates_outside_their_range(date: str) -> None:
    from horosa_skill.service import HorosaSkillService

    with pytest.raises(ToolValidationError) as caught:
        HorosaSkillService._split_ymd(date, tool="huangli")
    assert caught.value.code == "tool.date_range_unsupported"
    assert caught.value.details["accepted"] == {"min_year": 1, "max_year": 9999}
