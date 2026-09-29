"""上游 v3.11.2（Horosa-Public 9cd9078f，aiExport v58 不变）同步的 Python 侧回归：南半球月令 southMonth 全链、时间基准标签、
Java 回退岁数对齐、河洛按出生地当地日期取节气。每条写明「旧代码为什么会红」（负向对照）。

值级权威：
- 南半球月令：上游 baziLunarLocal.js flipMonthPillar（月支 +6、月干按年干五虎遁重起）；BaZi.js:406-410 快照行；
  1990-07-15 14:30 悉尼（33s52 151e12, +10:00）：不对冲 癸未月 → 对冲 己丑月（未+6=丑；庚年戊寅起 → 丑月己丑）。
- Java 参数：astrostudycn `/bazi/birth` `/bazi/direct` 读 `southMonth`（chong / none，进缓存键）—— 上游
  docs/windows-porting-and-release-checklist.md「v3.11.2 同步要点 · 共享 Java」。
- 时间基准标签：utils/timeBasisLine.js:5（'2' → '春分定卯时(尚无独立换算,按钟表时刻)'）。
"""
from __future__ import annotations

import shutil

import pytest
from test_service import CaptureClient
from test_sync311_mingli import _SH, _row, _section, _service

from horosa_skill.agent_guidance import TOOL_GUIDANCE, build_agent_guidance
from horosa_skill.reports.technique_card import _RESULT_SENSITIVE_FIELDS
from horosa_skill.schemas.tools import BaZiBirthInput, BaZiDirectInput
from horosa_skill.service import HorosaSkillService
from horosa_skill.time_basis import TIME_ALG_LABEL, time_basis_label

requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

_SYD = {"date": "1990-07-15", "time": "14:30:00", "zone": "+10:00", "lat": "33s52", "lon": "151e12", "gender": 1,
        "agent_confirmed_settings": True}


def test_south_month_is_declared_with_the_upstream_vocabulary() -> None:
    """旧代码：schema 不认 southMonth → MCP 扁平面静默丢键（FlexibleModel extra=allow 只救 CLI/tool_run），
    `_BAZI_OPTION_VOCAB` 无此键 → `_bazi_option` KeyError。"""
    for model in (BaZiBirthInput, BaZiDirectInput):
        field = model.model_fields["southMonth"]
        assert field.default is None and "只对南纬出生生效" in (field.description or "")
    assert HorosaSkillService._BAZI_OPTION_VOCAB["southMonth"] == ("none", "chong")
    assert HorosaSkillService._BAZI_OPTION_DEFAULTS["southMonth"] == "none", "上游 BaZi.js:1031 genParams 缺省 'none'"


def test_bazi_params_forward_south_month_with_upstream_default(tmp_path) -> None:
    service = _service(tmp_path)
    params, _ = service._bazi_params({"date": "1990-07-15", "time": "14:30:00", **_SYD})
    assert params["southMonth"] == "none"
    params, _ = service._bazi_params({"date": "1990-07-15", "time": "14:30:00", **_SYD, "southMonth": "chong"})
    assert params["southMonth"] == "chong"


@requires_node
def test_south_month_flips_the_month_pillar_only_for_southern_births(tmp_path) -> None:
    """值级金标（上游 flipMonthPillar）：悉尼 1990-07-15 14:30 → 不对冲 癸未 / 对冲 己丑；北纬同键无效；
    [四柱与三元] 只在南纬出「南半球月令」行。旧代码：键被丢 → 两次同盘、无该行。"""
    client = CaptureClient()
    service = _service(tmp_path, client=client, real={"bazi_local"})
    plain = service.run_tool("bazi_birth", _SYD, save_result=False)
    chong = service.run_tool("bazi_birth", {**_SYD, "southMonth": "chong"}, save_result=False)
    assert plain.ok and chong.ok, (plain.error, chong.error)
    assert not [ep for ep, _ in client.calls if ep.startswith("/bazi/")], "可靠域内不得打 Java"
    assert _row(_section(plain.data["snapshot_text"], "四柱与三元"), "月柱")[1] == "癸未"
    assert _row(_section(chong.data["snapshot_text"], "四柱与三元"), "月柱")[1] == "己丑"
    # 上游把这一行放在 [四柱与三元] 的「胎元」之后（BaZi.js:405-410），不在 [起盘信息]。
    assert "南半球月令：不对冲(月柱同北半球)" in _section(plain.data["snapshot_text"], "四柱与三元")
    assert "南半球月令：对冲(月支取对冲之支)" in _section(chong.data["snapshot_text"], "四柱与三元")
    north = service.run_tool("bazi_birth", {"date": "1990-07-15", "time": "14:30:00", **_SH, "gender": 1, "southMonth": "chong"},
                             save_result=False)
    assert north.ok and "南半球月令" not in north.data["snapshot_text"]
    assert _row(_section(north.data["snapshot_text"], "四柱与三元"), "月柱")[1] == "癸未"
    # 技法依据卡回显：换过开关时报告里必须能看见（AGENTS §10）
    assert ("southMonth", "南半球月令", frozenset({"cn", "shenshu"})) in _RESULT_SENSITIVE_FIELDS
    bad = service.run_tool("bazi_birth", {**_SYD, "southMonth": "flip"}, save_result=False)
    assert bad.ok and any("八字 southMonth='flip' 无法识别" in w for w in bad.warnings), bad.warnings


@requires_node
def test_south_month_reaches_java_when_the_chart_routes_there(tmp_path) -> None:
    """Java 回退路径（byLon → 只有 Java 实现）必须把 southMonth 一起发：astrostudycn 读同名参数并进缓存键。
    旧代码：params 无此键 → Java 收不到 → 南纬对冲盘退回 Java 时悄悄变成不对冲。"""
    client = CaptureClient()
    service = _service(tmp_path, client=client, real={"bazi_local"})
    env = service.run_tool("bazi_birth", {**_SYD, "southMonth": "chong", "byLon": True}, save_result=False)
    assert env.ok, env.error
    sent = [p for ep, p in client.calls if ep == "/bazi/birth"]
    assert sent and sent[0]["southMonth"] == "chong", sent
    assert env.data["compute_sources"] == {"bazi": "java"}


def test_guidance_asks_about_south_month_only_for_southern_births() -> None:
    policy = TOOL_GUIDANCE["bazi_birth"]
    ask = next(q for q in policy["ask_if_missing"] if q["field"] == "southMonth")
    assert ask["values"] == ["none", "chong"] and "南半球" in ask["question"] and ask.get("when")
    assert {"field": "southMonth", "value": "none", "meaning": "星阙默认：南半球月令不对冲（北纬出生无影响）"} in policy["safe_defaults"]
    guidance = build_agent_guidance(tool_name="bazi_birth")
    assert "southMonth" in str(guidance.get("options_keys") or guidance), "options_keys 必须列出 southMonth 的取值表"


def test_time_basis_label_follows_v3112_upstream() -> None:
    """timeBasisLine.js:5（9cd9078f）把 '2' 的标签改成「春分定卯时(尚无独立换算,按钟表时刻)」；Python 港口逐字跟。"""
    assert TIME_ALG_LABEL["2"] == "春分定卯时(尚无独立换算,按钟表时刻)"
    assert time_basis_label(2) == TIME_ALG_LABEL["2"] and time_basis_label("0") == "真太阳时(经度+均时差校正)"
