"""写错的参数名不再「只告警、照样算」（审计 S-13）。

修前：horosa_predict_solarreturn {…, "target_year": 2027} → ok:true、「推运时间：2026-03-08 14:30」，warnings 一行「不是本技法的参数：target_year」——
拿缺省值算了另一年的返照。本仓原则「认不出的值不许原样流向引擎、不许换缺省值」，键名同理。
- 推运目标的常见写法（target_year / targetDate …）在技法声明了 datetime 时直接按 datetime 读；
- 与本技法某个参数只差几个字（忽略大小写与 _，编辑距离 ≤ 2）→ tool.unknown_argument 拒绝，给最接近的合法键；离得远的多余键照旧只告警。
负向对照（实跑过）：拒绝分支改回只记说明 → 第二、三个用例红；去掉 TARGET_ALIASES → 第一个用例红。
"""
from __future__ import annotations

import pytest

from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.errors import ToolValidationError
from horosa_skill.input_normalization import normalize_collecting_issues
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService

BIRTH = {"date": "1990-05-03", "time": "08:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"}


@pytest.mark.parametrize("key", ["target_year", "targetYear", "target_date"])
def test_target_spellings_set_the_target(key) -> None:
    out, issues = normalize_collecting_issues({**BIRTH, key: 2027}, model=TOOL_DEFINITIONS["solarreturn"].input_model)
    assert issues == [] and str(out["datetime"]).startswith("2027")


@pytest.mark.parametrize(("tool", "typo", "meant"), [
    ("chart", "hsyss", "hsys"), ("chart", "zodiac", "zodiacal"), ("bazi_birth", "phaseTyp", "phaseType"),
])
def test_a_near_miss_of_a_real_parameter_is_refused_with_the_valid_key(tool, typo, meant) -> None:
    out, issues = normalize_collecting_issues({**BIRTH, "gender": 1, typo: 1}, model=TOOL_DEFINITIONS[tool].input_model)
    assert [(i["code"], i["field"]) for i in issues] == [("tool.unknown_argument", typo)]
    assert f"`{meant}`" in issues[0]["message"] and issues[0]["ask_user"] is False


def test_service_refuses_before_computing_and_unrelated_extras_still_only_warn(tmp_path) -> None:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path,
                        runtime_root=tmp_path / "runtime", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs",
                        trace_enabled=False)
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    with pytest.raises(ToolValidationError) as excinfo:
        service.run_tool("chart", {**BIRTH, "hsyss": 3, "defaults_accepted": True}, save_result=False)
    assert excinfo.value.code == "tool.unknown_argument"
    assert excinfo.value.details["agent_recovery"]["next_action"] == "fix_field_and_retry"
    out, issues = normalize_collecting_issues({**BIRTH, "foo": 1}, model=TOOL_DEFINITIONS["chart"].input_model)
    assert issues == []   # 离得远：照旧只是一条「不是本技法的参数」说明


@pytest.mark.parametrize(("tool", "extra"), [
    ("ziwei_birth", {"gender": 1, "byLon": False}),   # 八字真有的参数（合参会交过来），与 lon 差 2 处也不算写错
    ("qimenzeri", {"tree": None}),                     # 没给（None）不算；短键 tree 与 time 差 2 处也不算
    ("chart", {"direction": "converse"}),              # 与 pdProjection 相似度 0.76，但编辑距离远
])
def test_other_techniques_keys_and_far_or_empty_keys_are_not_refused(tool, extra) -> None:
    _out, issues = normalize_collecting_issues({**BIRTH, **extra}, model=TOOL_DEFINITIONS[tool].input_model)
    assert not [i for i in issues if i["code"] == "tool.unknown_argument"], issues
