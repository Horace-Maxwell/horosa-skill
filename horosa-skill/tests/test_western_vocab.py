"""西占 / 推运 / 七政择日的枚举类设置词表（v0.50.0，western_vocab；审计 C-03 + C-11 + CN-N5/N6 + 调波越界 + 扫尾）。

C-03 的症状：westNodeType 只认字面 "true"——True / "真交点" 按平交点算，[起盘信息] 的「古典口径（非默认项）」行却写「真交点」；
triplicity "ptolemaic" / "托勒密" 行写原值、盘按 Dorothean；vocMode "byOrb" / orbSystem "whole_sign" / lotProjection "Sign" 静默按缺省。
根因：原值原样下发，后端不认按缺省算，口径行照抄原值。修法：每个键一张词表挂在 schema 字段上，规范值是唯一真值。

这里三层守卫：
1. 表驱动的认 / 拒：每张词表的规范值、别名、乱写各走一遍（`_VOCAB_CASES`）；
2. 词表值域 ≡ 上游 spec（CLASSICAL_PARAM_SPEC_NON_DEFAULT，与 vendored classicalParamSpec.js 由别的测试互锚）；
3. 性质测试：古典口径每个键、每个非缺省规范值的一组变体写法，要么被拒，要么**规范化后整份入参与规范写法逐字段相同**
   （= 后端请求、口径行、[古典格局] 请求体都相同）——绝不出现「行写 X、算的是缺省」。

负向对照（实跑过，见 LESSONS v0.50.0-dev「古典口径词表」）：
- BirthInput._classical_vocabulary 改成原样返回 → 性质测试与表驱动测试红（ptolemaic 未拒也未归一）；
- _calibre_phrase 恢复「不在表里就照抄原值」→ test_calibre_line_never_prints_a_raw_value 红；
- classical_backend_overrides 的 float 不卡档去掉（恢复卡档）→ test_off_list_orb_is_stated_where_it_is_computed 红。
"""
from __future__ import annotations

import math
from typing import Any

import pytest
from pydantic import ValidationError

from horosa_skill.engine import astro_snapshot as snap
from horosa_skill.schemas.tools import BirthInput
from horosa_skill.schemas.tools.astro import HarmonicInput, MundaneInput, PlanetCyclesInput
from horosa_skill.schemas.tools.cn_divination import SuZhanInput
from horosa_skill.schemas.tools.election import ElectionInput, HoraryInput, QizhengElectionInput
from horosa_skill.schemas.tools.predictive import DecennialsInput
from horosa_skill.western_vocab import (
    CLASSICAL_FIELD_KEYS,
    OPEN_ORB_RANGES,
    classical_spec_values,
    classical_vocabulary,
)

_BIRTH = {"date": "1990-05-17", "time": "14:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"}
_SPEC = {key: (default, options) for key, _backend, _vt, default, _aliases, options in snap.CLASSICAL_PARAM_SPEC_NON_DEFAULT}


def _dump(model: type, extra: dict[str, Any], base: dict[str, Any] | None = None) -> dict[str, Any]:
    return model.model_validate({**(_BIRTH if base is None else base), **extra}).model_dump(exclude_none=True)


def _refused(model: type, extra: dict[str, Any], base: dict[str, Any] | None = None) -> dict[str, Any]:
    with pytest.raises(ValidationError) as info:
        model.model_validate({**(_BIRTH if base is None else base), **extra})
    errors = info.value.errors(include_url=False)
    assert errors and errors[0]["type"] == "horosa_field", errors
    ctx = errors[0]["ctx"]
    assert ctx["code"] == "tool.invalid_option"
    return ctx


# ───────────────────────── 1. 表驱动：认 / 拒 ─────────────────────────

_PC = {"startYear": 1950, "endYear": 1960}
_M = {"year": 2025, "zone": "+08:00", "lat": "39n54", "lon": "116e23"}
# (模型, 基础载荷, 字段, [(写法, 规范值)…], [该拒的写法…])
_VOCAB_CASES: list[tuple[type, dict[str, Any] | None, str, list[tuple[Any, Any]], list[Any]]] = [
    (BirthInput, None, "westNodeType", [("true", "true"), (True, "true"), ("真交点", "true"), ("TRUE", "true"), ("mean", "mean"), (False, "mean"), ("平交点", "mean")],
     ["truenode2", 1, "bogus"]),
    (BirthInput, None, "westLilithType", [("true", "true"), ("真", "true"), ("真实远地点", "true"), ("Mean", "mean")], ["osculation", 2]),
    (BirthInput, None, "triplicity", [("Ptolemaic", "Ptolemaic"), ("ptolemaic", "Ptolemaic"), ("托勒密", "Ptolemaic"), ("dorotheus", "Dorothean")],
     ["ptolemy2", 3]),
    (BirthInput, None, "sectBuffer", [("ptolemy5", "ptolemy5"), ("Ptolemy5", "ptolemy5"), ("视地平", "apparent")], [5, "5°"]),
    (BirthInput, None, "vocMode", [("by_orb", "by_orb"), ("byOrb", "by_orb"), ("lilly", "classic"), ("kenodromia", "kenodromia")], ["no_such_mode", 2]),
    (BirthInput, None, "orbSystem", [("wholeSign", "wholeSign"), ("whole_sign", "wholeSign"), ("整星座位相", "wholeSign")], ["whole", "lilly"]),
    (BirthInput, None, "lotProjection", [("sign", "sign"), ("Sign", "sign"), ("整星座", "sign")], ["signs", 1]),
    (BirthInput, None, "termsVariant", [(1, 1), ("2", 2), ("埃及", 0), (3.0, 3)], ["ptolemy", 5, -1, True]),
    (BirthInput, None, "lotReversal", [(0, 0), (False, 0), ("关", 0), ("1", 1)], [2, "maybe"]),
    (BirthInput, None, "luminaryOrbBonus", [(10, 10), ("20", 20)], [15, "10%%"]),
    (BirthInput, None, "houseCuspAdvance", [(3, 3), ("0", 0)], [2, 6]),
    (BirthInput, None, "cazimiOrb", [("16′", 16 / 60), (17 / 60, 17 / 60), ("1°", 1), (0.5, 0.5)], [17, -0.1, "bogus"]),
    (BirthInput, None, "combustOrb", [(8, 8), ("8.5", 8.5), (9, 9)], [31, "far"]),
    (BirthInput, None, "starOrb", [(2, 2), ("1.5°", 1.5), (2.5, 2.5)], [40, True]),
    (BirthInput, None, "starOrbMode", [("byMagnitude", "byMagnitude"), ("按星等", "byMagnitude")], [1, "magnitude"]),
    (BirthInput, None, "sunriseMode", [("apparent", "apparent"), ("Apparent", "apparent")], ["sunrise", "bogus"]),
    (DecennialsInput, None, "orderType", [("chaldean", "chaldean"), ("迦勒底", "chaldean"), ("Zodiacal", "zodiacal")], ["chaldaean", 1]),
    (DecennialsInput, None, "calendarType", [("calendar_365_25", "calendar_365_25"), ("365.25", "calendar_365_25"), ("360天", "calendar_360")], ["365", "julian2"]),
    (DecennialsInput, None, "dayMethod", [("hephaistio", "hephaistio"), ("Hephaistio", "hephaistio")], ["hephaestion"]),
    (DecennialsInput, None, "startMode", [("sect_light", "sect_light"), ("木星", "Jupiter"), ("saturn", "Saturn")], ["Pluto", "north node"]),
    (DecennialsInput, None, "aiMode", [("l2_in_l1", "l2_in_l1")], ["l2", "all"]),
    (HarmonicInput, None, "harmonic", [(7, 7), ("H7", 7), (7.0, 7), (360, 360), (1, 1)], [0, -3, 1000, 7.5, "H0", True]),
    (QizhengElectionInput, None, "kind", [("lunar", "lunar"), ("月食", "lunar"), ("日食", "solar"), ("Lunar", "lunar")], ["eclipse", "total"]),
    (QizhengElectionInput, None, "plate", [("tian", "tian"), ("天盘", "tian"), ("地盘", "di"), ("REN", "ren")], ["bogus", "zhong"]),
    (QizhengElectionInput, None, "ziZheng", [("true", "true"), (True, "true"), ("磁北", "magnetic"), ("magnetic", "magnetic")], [False, "false", 0]),
    (QizhengElectionInput, None, "eleLifeMode", [("sunset", "sunset"), ("正午", "noon")], ["bogus"]),
    (QizhengElectionInput, None, "nodeType", [("真", "true"), (True, "true"), ("mean", "mean")], ["bogus"]),
    (QizhengElectionInput, None, "body", [("月", "月"), ("Moon", "月"), ("金星", "金")], ["bogus", "冥"]),
    (PlanetCyclesInput, _PC, "p1", [("Saturn", "Saturn"), ("土星", "Saturn"), ("uranus", "Uranus"), ("北交点", "Node")], ["bogus", "Ceres"]),
    (PlanetCyclesInput, _PC, "center", [("helio", "helio"), ("日心", "helio"), ("heliocentric", "helio")], ["barycentric"]),
    (HoraryInput, None, "category", [("wealth", "wealth"), ("财物", "wealth"), ("Wealth", "wealth")], ["money"]),
    (HoraryInput, None, "school", [("renaissance", "renaissance"), ("文艺复兴", "renaissance")], ["bogus"]),
    (ElectionInput, None, "topicId", [("marriage", "marriage"), ("入宅", "move_in")], ["wedding"]),
    (ElectionInput, None, "school", [("persian", "persian"), ("波斯-阿拉伯", "persian")], ["bogus"]),
    (SuZhanInput, None, "houseStartMode", [(1, 1), ("1", 1), (True, 1), ("上升", 1), (0, 0)], [2, -1]),
    (MundaneInput, _M, "mhKind", [("weather", "weather"), ("物价", "price")], ["bogus", "election"]),
]


@pytest.mark.parametrize(("model", "base", "field", "accepted", "refused"), _VOCAB_CASES,
                         ids=[f"{case[0].__name__}.{case[2]}" for case in _VOCAB_CASES])
def test_vocabulary_accepts_known_spellings_and_refuses_the_rest(model, base, field, accepted, refused) -> None:
    for spelling, canonical in accepted:
        got = _dump(model, {field: spelling}, base).get(field)
        if model is BirthInput and field == "sunriseMode" and canonical == "center":
            canonical = None
        assert got == canonical and type(got) is type(canonical), (field, spelling, got)
    for spelling in refused:
        ctx = _refused(model, {field: spelling}, base)
        if field in ("harmonic",) or CLASSICAL_FIELD_KEYS.get(field) in OPEN_ORB_RANGES:
            continue  # 量程类：没有全表，可选写法在 expected 里
        assert ctx["options"], (field, spelling)


def test_refusal_reaches_the_envelope_with_the_accepted_list(tmp_path) -> None:
    """服务层：tool.invalid_option、details.field、details.options（全表）；不发任何请求。"""
    from fakes import FakeClient, FakeJsClient

    from horosa_skill.config import Settings
    from horosa_skill.errors import ToolValidationError
    from horosa_skill.memory.store import MemoryStore
    from horosa_skill.service import HorosaSkillService

    class Recording(FakeClient):
        def __init__(self) -> None:
            super().__init__()
            self.endpoints: list[str] = []

        def call(self, endpoint: str, payload: dict) -> dict:
            self.endpoints.append(endpoint)
            return super().call(endpoint, payload)

    settings = Settings(server_root="http://127.0.0.1:9", db_path=tmp_path / "m.db", output_dir=tmp_path / "runs")
    client = Recording()
    service = HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=FakeJsClient())
    with pytest.raises(ToolValidationError) as info:
        service.run_tool("chart", {**_BIRTH, "triplicity": "ptolemy2", "defaults_accepted": True}, save_result=False)
    assert info.value.code == "tool.invalid_option"
    assert info.value.details["field"] == "triplicity"
    assert [o["value"] for o in info.value.details["options"]] == ["Dorothean", "Ptolemaic", "PtolemaicWaterVariant"]
    assert client.endpoints == []
    # 前端名 fixedStarOrb（未声明的 extra 键）同一张词表，错误里点名的是它自己。
    with pytest.raises(ToolValidationError) as info:
        service.run_tool("chart", {**_BIRTH, "fixedStarOrb": "far", "defaults_accepted": True}, save_result=False)
    assert info.value.details["field"] == "fixedStarOrb"


# ───────────────────────── 2. 词表值域 ≡ 上游 spec ─────────────────────────

def test_classical_vocabularies_cover_exactly_the_upstream_spec() -> None:
    ours = classical_spec_values()
    assert set(ours) == set(_SPEC), "古典口径词表与 CLASSICAL_PARAM_SPEC_NON_DEFAULT 键集不同"
    for key, (default, options) in _SPEC.items():
        expected = set(options) if options is not None else {0, 1}
        assert set(ours[key]) == expected, key
        assert default in ours[key], key
    # BirthInput 上每个后端名都挂着词表（声明了才有 BeforeValidator）。
    declared = set(BirthInput.model_fields)
    for field, key in CLASSICAL_FIELD_KEYS.items():
        if field not in ("fixedStarOrb", "fixedStarOrbMode"):
            assert field in declared, field


# ───────────────────────── 3. 性质测试：规范化 or 拒，绝不「行写 X、算缺省」 ─────────────────────────

def _variants(value: Any, key: str) -> list[Any]:
    out: list[Any] = []
    if isinstance(value, str):
        out += [value.upper(), value.lower(), value.swapcase(), f" {value} ", value.replace("_", ""), value + "x", value[:-1]]
    else:
        out += [str(value), f"{value}°", float(value), int(value) if float(value) == int(value) else value * 2, -1, 1e9]
        if key not in OPEN_ORB_RANGES:
            out += [True, False, "true", "开"]
    vocab = classical_vocabulary(next(f for f, k in CLASSICAL_FIELD_KEYS.items() if k == key))
    out.append(vocab.labels[value])
    return out


def _non_default_cases() -> list[tuple[str, str, Any]]:
    cases = []
    for field, key in CLASSICAL_FIELD_KEYS.items():
        if field in ("fixedStarOrb", "fixedStarOrbMode"):
            continue
        default, _options = _SPEC[key]
        for value in classical_spec_values()[key]:
            if value != default and (key, value) != ("termsVariant", 4):  # 4 要随盘界表，见下一条
                cases.append((field, key, value))
    return cases


@pytest.mark.parametrize(("field", "key", "value"), _non_default_cases(), ids=lambda v: str(v)[:14])
def test_every_spelling_normalises_to_the_canonical_run_or_is_refused(field: str, key: str, value: Any) -> None:
    canonical = _dump(BirthInput, {field: value})
    canonical_line = snap.build_classical_calibre_line(canonical)
    for spelling in _variants(value, key):
        try:
            got = _dump(BirthInput, {field: spelling})
        except ValidationError as exc:
            assert exc.errors(include_url=False)[0]["ctx"]["code"] == "tool.invalid_option", (field, spelling)
            continue
        if got.get(field) == canonical.get(field):
            # 读成了这个档：整份入参（= /chart 请求体）、口径行逐字段相同。
            assert got == canonical, (field, spelling)
            assert snap.build_classical_calibre_line(got) == canonical_line, (field, spelling)
            continue
        # 读成了别的值（数字类：表内另一档 / 量程内任意数；开关：另一档）——那也必须是规范值，且口径行与之一致。
        other = got.get(field)
        assert other is None or other in classical_spec_values()[key] or key in OPEN_ORB_RANGES, (field, spelling, other)
        line = snap.build_classical_calibre_line(got)
        default = _SPEC[key][0]
        if other is not None and other != default and not (isinstance(other, float) and math.isclose(other, float(default))):
            assert line, (field, spelling, other)


def test_calibre_line_never_prints_a_raw_value() -> None:
    """即使有人绕过 schema 直接喂原值（旧存档、内部调用），「古典口径」行也只写有名字的档——不认识的值不写。"""
    raw = {"triplicity": "ptolemaic", "sectBuffer": 5, "westNodeType": "True", "leoBoundFirst": 2, "orbSystem": "whole_sign"}
    assert snap.build_classical_calibre_line(raw) == ""
    assert snap.build_classical_calibre_line({"triplicity": "Ptolemaic", "westNodeType": "true"}) == (
        "古典口径（非默认项）：三分集=托勒密二主；月交点=真交点。"
    )


def test_off_list_orb_is_stated_where_it_is_computed() -> None:
    """容许度类（float）收量程内任意数：/chart 照算，口径行与 [古典格局] 请求体（classical_backend_overrides）也照写。"""
    dumped = _dump(BirthInput, {"combustOrb": 9, "antisciaOrb": 2.5})
    assert dumped["combustOrb"] == 9 and dumped["antisciaOrb"] == 2.5
    assert snap.classical_backend_overrides_from_fields(dumped) == {"combustOrb": 9.0, "antisciaOrb": 2.5}
    assert snap.build_classical_calibre_line(dumped) == "古典口径（非默认项）：燃烧上界=9°；映点容许度=2.5°。"


def test_custom_terms_without_tables_is_refused_not_silently_egyptian() -> None:
    """termsVariant=4 无 customTermsDay：后端静默按埃及界算、口径行写「界系=自定义界表」→ 入口拒；带 12 座表照收。"""
    ctx = _refused(BirthInput, {"termsVariant": 4})
    assert ctx["code"] == "tool.invalid_option" and "customTermsDay" in ctx["zh"]
    table = [[["Jupiter", 6]] for _ in range(12)]
    dumped = _dump(BirthInput, {"termsVariant": "4", "customTermsDay": table})
    assert dumped["termsVariant"] == 4
    assert "界系=自定义界表" in snap.build_classical_calibre_line(dumped)
