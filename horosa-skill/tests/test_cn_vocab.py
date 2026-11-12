"""中式技法的设置词表 + 「给了却用不了」清扫（v0.50.0 深审 C-14 / C-22 中式 / CN-N7 / 六爻同族）。

一、词表（horosa_skill/cn_vocab.py，`Vocabulary` 机制挂 schema BeforeValidator）：每个规范值与别名都收、认不出的拒
   （tool.invalid_option，options = 全表）。规范值逐个锚到它的消费方源码（adapter / vendored 选项表），上游改值即红。
   不收进词表的、理由：只经 /nongli/time 的 timeAlg（小六壬 / 飞宫 / 小成图 / 轨策 / 正传：后端自己判，0 / 1 / 3 都有义）；
   自由文本（askEvent / question / text）；guice 的十开关（JS 按上游 GUICE 元表校验并报错，不是静默回落）；
   qizhengelection 的 kind / plate / ziZheng（西占批）；六爻 liuyaoSettings（认不出的值回执在 warnings，六爻批定的口径）。
二、给了却用不了 → 拒，并在结果里说清起课方式（同六爻 data.cast_method）：小六壬 nums、灵棋 counts、梅花卦义 name；
   统摄法没给的轴照上游缺省并点名（selection_source）；塔罗 / 金口诀标明抽牌 / 起课方式。
三、飞宫命主性别（C-14）走同一个性别解析器，`gender` 是别名；神数 ×14 的 gender=2（上游后端 gender_cn 当女，前端只发 0 / 1）一律拒。

负向对照（实跑过）：词表某值改成别名不认 → 接受表红；validate_cn_field 直接返回原值 → 拒绝表红；小六壬 / 灵棋的「用不了就拒」
删掉 → 起课用例红（回到悄悄以时起课）；飞宫 runner 改回 `payload.get("mingGender", "male")` → 「女 / Female / 0」用例红。
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

import pytest
from test_local_js_tools import make_service

from horosa_skill.cn_vocab import CN_VOCABULARIES, MEIYI_TRIGRAM_CODES, parse_ziwei_time_alg, validate_cn_field
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.errors import ToolValidationError
from horosa_skill.input_fields import FieldIssue
from horosa_skill.input_normalization import normalize_request_payload
from horosa_skill.testing_payloads import build_sample_payloads

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "horosa-core-js" / "src"
requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="[host] node not on PATH")

# 词表的规范值必须在它的消费方源码里出现（同一个字面量）——换句话说，表里不许有引擎不认的值。
_CONSUMER = {
    "xiaoliuren": ["tools/xiaoliuren.js"], "feigong": ["tools/feigong.js", "vendor/feigong/feigongJu.js"],
    "xiaochengtu": ["tools/xiaochengtu.js", "vendor/xiaochengtu"], "zhengchuan": ["tools/zhengchuan.js", "vendor/zhengchuan"],
    "canping": ["tools/canping.js"], "heluo": ["tools/heluo.js"], "yizhangjing": ["tools/yizhangjing.js", "vendor/yizhangjing"],
    "tongshefa": ["vendor/tongshefa/TongSheFaCore.js"], "lingqi": ["vendor/lingqi"],
}
CASES = [(tool, field) for tool, fields in CN_VOCABULARIES.items() for field in fields]


def _source(paths: list[str]) -> str:
    text = ""
    for rel in paths:
        target = CORE / rel
        files = sorted(target.rglob("*.js")) if target.is_dir() else [target]
        text += "".join(path.read_text(encoding="utf-8") for path in files)
    return text


@pytest.mark.parametrize("tool, field", CASES)
def test_every_canonical_value_and_alias_is_accepted(tool: str, field: str) -> None:
    vocab = CN_VOCABULARIES[tool][field]
    for value in vocab.labels:
        assert validate_cn_field(tool, field, value) == value
    for key, value in vocab._lookup.items():
        assert vocab.parse(key).value == value


@pytest.mark.parametrize("tool, field", CASES)
def test_unknown_values_are_refused_with_the_full_table(tool: str, field: str) -> None:
    vocab = CN_VOCABULARIES[tool][field]
    for bogus in ("bogus", "道家-ish", 99):
        with pytest.raises(FieldIssue) as caught:
            vocab.parse(bogus)
        assert caught.value.code == "tool.invalid_option"
        assert [item["value"] for item in caught.value.options] == list(vocab.labels)


@pytest.mark.parametrize("tool, field", [case for case in CASES if case[0] in _CONSUMER and case[1] != "timeAlg"])
def test_canonical_values_are_what_the_engine_reads(tool: str, field: str) -> None:
    source = _source(_CONSUMER[tool])
    for value in CN_VOCABULARIES[tool][field].labels:
        if isinstance(value, int):
            continue
        assert re.search(rf"['\"`]{re.escape(str(value))}['\"`]", source), (tool, field, value)


@pytest.mark.parametrize("tool, field, value, expected", [
    ("xiaoliuren", "school", "道家", "dao"), ("xiaoliuren", "school", "主流六宫", "main"),
    ("feigong", "koujing", "异说", "yi"), ("yizhangjing", "dingYue", "nongli", "lunar"),
    ("tongshefa", "taiyin", "離", "离"), ("tongshefa", "taiyang", "☰", "乾"), ("geomancy", "profile", "Arabic_Raml", "arabic_raml"),
    ("lingqi", "category", "婚姻", "marriage"), ("heluo", "zhiZunEnabled", "false", 0), ("canping", "timeAlg", "平太阳时", 3),
])
def test_chinese_names_are_read(tool: str, field: str, value: Any, expected: Any) -> None:
    assert validate_cn_field(tool, field, value) == expected


def test_ziwei_time_alg_has_two_steps_and_reads_mean_solar_as_true_solar() -> None:
    assert parse_ziwei_time_alg(1).value == 1 and parse_ziwei_time_alg("0").value == 0
    mean = parse_ziwei_time_alg(3)
    assert mean.value == 0 and "平太阳时" in mean.note_zh
    with pytest.raises(FieldIssue):
        parse_ziwei_time_alg(2)  # 旧 runner：2 → 真太阳时


@pytest.mark.parametrize("tool, payload, field", [
    ("xiaoliuren", {"school": "bogus"}, "school"),
    ("ziwei_birth", {"timeAlg": 2}, "timeAlg"),
    ("geomancy", {"profile": "bogus"}, "profile"),
    ("bazi_inverse", {"pillars": ["甲子", "丙寅", "戊辰", "庚申"], "count": 50}, "count"),
    ("bazi_inverse", {"pillars": ["甲子", "丙寅", "戊辰", "庚申"], "count": "lots"}, "count"),
    ("tongshefa", {"taiyin": "bogus"}, "taiyin"),
    ("heluo", {"ziShuMode": "x"}, "ziShuMode"),
    ("gua_meiyi", {"name": ["111111"]}, "name"),
])
def test_schema_refuses_unknown_values(tool: str, payload: dict[str, Any], field: str) -> None:
    from pydantic import ValidationError

    from horosa_skill.input_normalization import tool_error_from_validation

    model = TOOL_DEFINITIONS[tool].input_model
    try:
        model.model_validate(payload)
    except ToolValidationError as exc:  # gua_meiyi 逐项错误直接是结构化错误
        assert exc.code == "tool.invalid_option" and exc.details["fields"][0]["field"].startswith(field)
        return
    except ValidationError as exc:
        error = tool_error_from_validation(exc, tool_name=tool)
        entries = [item for item in error.details["fields"] if item["field"] == field]
        assert entries and entries[0]["code"] == "tool.invalid_option", error.details["fields"]
        return
    raise AssertionError(f"{tool}.{field} accepted {payload[field]!r}")


def test_meiyi_reads_trigram_names_into_codes() -> None:
    model = TOOL_DEFINITIONS["gua_meiyi"].input_model
    assert model.model_validate({"name": ["乾", "kan", "☷", "011"]}).name == ["111", "010", "000", "011"]
    assert set(MEIYI_TRIGRAM_CODES.values()) == {"乾", "兑", "离", "震", "巽", "坎", "艮", "坤"}


# ───────────── 给了却用不了：拒 + 说明起课方式 ─────────────

def _run(tmp_path, tool: str, payload: dict[str, Any]):
    return make_service(tmp_path).run_tool(tool, {"agent_confirmed_settings": True, **payload}, save_result=False)


@pytest.mark.parametrize("nums", [[5, 20], [0, 1, 2], [5, 20, 7, 1]])
def test_xiaoliuren_unusable_nums_are_refused_not_recast_by_time(tmp_path, nums: list[int]) -> None:
    env = _run(tmp_path, "xiaoliuren", {"nums": nums, "date": "2028-04-06", "time": "09:33:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"})
    assert not env.ok and env.error.code == "tool.xiaoliuren_invalid_cast"
    assert env.error.details["fields"][0]["field"] == "nums"


@pytest.mark.parametrize("counts", [[5, 0, 0], [1, 2], [-1, 2, 3]])
def test_lingqi_unusable_counts_are_refused_not_recast_by_time(tmp_path, counts: list[int]) -> None:
    payload = {**build_sample_payloads()["lingqi"], "counts": counts}
    env = _run(tmp_path, "lingqi", payload)
    assert not env.ok and env.error.code == "tool.lingqi_invalid_cast"


@requires_node
def test_xiaoliuren_and_lingqi_state_their_cast_method(tmp_path) -> None:
    xl = _run(tmp_path, "xiaoliuren", {"nums": [5, 20, 7]})
    assert xl.ok and xl.data["cast_method"] == "nums"
    lq = _run(tmp_path, "lingqi", {**build_sample_payloads()["lingqi"], "counts": [2, 3, 1]})
    assert lq.ok and lq.data["cast_method"] == "counts"


@requires_node
def test_tongshefa_names_the_axes_it_filled_from_the_default(tmp_path) -> None:
    given = _run(tmp_path, "tongshefa", {"taiyin": "乾", "taiyang": "坤", "shaoyang": "离", "shaoyin": "坎"})
    assert given.ok and given.data["selection_source"] == "given" and not any("统摄法" in w for w in given.warnings)
    partial = _run(tmp_path, "tongshefa", {"taiyin": "乾"})
    assert partial.data["selection_source"] == "partial"
    assert partial.data["selection_defaulted"] == ["taiyang", "shaoyang", "shaoyin"]
    assert any("taiyang" in w and "不是用户选的" in w for w in partial.warnings)


@requires_node
@pytest.mark.parametrize("variant", [{"mingGender": "女"}, {"mingGender": "Female"}, {"mingGender": 0}, {"mingGender": "坤造"},
                                     {"gender": 0}, {"gender": "女"}])
def test_feigong_reads_every_female_label(tmp_path, variant: dict[str, Any]) -> None:
    base = {k: v for k, v in build_sample_payloads()["feigong"].items() if k != "mingGender"}
    female = _run(tmp_path, "feigong", {**base, "mingGender": "female"})
    male = _run(tmp_path, "feigong", {**base, "mingGender": "male"})
    env = _run(tmp_path, "feigong", {**base, **variant})
    text = env.data["export_snapshot"]["export_text"]
    assert text == female.data["export_snapshot"]["export_text"] != male.data["export_snapshot"]["export_text"]
    assert "(女)" in text


def test_feigong_refuses_two_different_genders_and_unknown_labels(tmp_path) -> None:
    base = {k: v for k, v in build_sample_payloads()["feigong"].items() if k != "mingGender"}
    conflict = _run(tmp_path, "feigong", {**base, "mingGender": 1, "gender": 0})
    assert not conflict.ok and conflict.error.code == "tool.field_conflict"
    with pytest.raises(ToolValidationError) as caught:
        make_service(tmp_path).run_tool("feigong", {**base, "mingGender": 2, "agent_confirmed_settings": True}, save_result=False)
    assert caught.value.code == "tool.invalid_gender"


SHENSHU = ("tieban", "shaozi", "xianqin", "cetian", "qizhengkin", "beiji", "nanji", "chunzi", "fendjing",
           "wangji", "wuzhao", "taixuan", "jingjue", "shenyishu")


@pytest.mark.parametrize("tool", SHENSHU)
@pytest.mark.parametrize("where", ["top", "options"])
def test_shenshu_gender_two_is_refused_everywhere(tmp_path, tool: str, where: str) -> None:
    """上游后端 gender_cn 把 "2" 读成女，但上游前端只发 0 / 1（kinAstroFieldsSync：女 = 0，其余 = 男 1）：2 不是约定写法，
    同一个性别解析器拒它——顶层与 options 里都一样（runner 会把 options.gender 提到顶层）。"""
    base = {k: v for k, v in build_sample_payloads()[tool].items() if k != "gender"}
    payload = {**base, "gender": 2} if where == "top" else {**base, "options": {**(base.get("options") or {}), "gender": 2}}
    with pytest.raises(ToolValidationError) as caught:
        make_service(tmp_path).run_tool(tool, payload, save_result=False)
    assert caught.value.code == "tool.invalid_gender"


def test_shenshu_female_labels_normalise_to_zero() -> None:
    model = TOOL_DEFINITIONS["tieban"].input_model
    for label in ("女", "Female", "坤造", 0, "0"):
        assert normalize_request_payload({"date": "1998-02-20", "gender": label}, model=model)["gender"] == 0


# ───────────── 日子馆当事人的角色（v0.50.0 深审余项）─────────────
# 以前不传 role：[日子馆·个性化择日] 印「undefined（甲）」，[当事人八字] 的「合婚」行（按 self / spouse 找人）整行缺席。
# 负向对照（实跑过）：CalendarMonthInput 的 rizi 校验器改成原样返回 → 本组三例红。

def _rizi(*persons: dict[str, Any]) -> dict[str, Any]:
    return {"date": "2028-04-06", "zone": "+08:00", "rizi": {"event": "嫁娶", "persons": list(persons)}}


def test_rizi_first_person_defaults_to_self_and_names_are_read() -> None:
    model = TOOL_DEFINITIONS["calendar_month"].input_model
    out = model.model_validate(_rizi({"name": "甲", "date": "1990-05-03"}, {"name": "乙", "date": "1992-03-02", "role": "配偶"}))
    assert [p["role"] for p in out.rizi["persons"]] == ["self", "spouse"]


def test_rizi_later_person_without_role_is_asked() -> None:
    with pytest.raises(ToolValidationError) as caught:
        TOOL_DEFINITIONS["calendar_month"].input_model.model_validate(_rizi({"name": "甲", "date": "1990-05-03"}, {"name": "乙", "date": "1992-03-02"}))
    assert caught.value.details["fields"][0]["field"] == "rizi.persons[1].role"
    assert caught.value.details["fields"][0]["ask_user"] is True


def test_rizi_unknown_role_is_refused() -> None:
    with pytest.raises(ToolValidationError) as caught:
        TOOL_DEFINITIONS["calendar_month"].input_model.model_validate(_rizi({"name": "甲", "date": "1990-05-03", "role": "boss"}))
    assert caught.value.code == "tool.invalid_option"
    assert {o["value"] for o in caught.value.details["fields"][0]["options"]} == {"self", "spouse", "family"}


@requires_node
def test_rizi_roles_are_the_vendored_snapshot_labels() -> None:
    source = (CORE / "vendor" / "calendar" / "riziSnapshot.js").read_text(encoding="utf-8")
    assert "const ROLE_LABEL = { self: '本人', spouse: '配偶', family: '家人' };" in source
