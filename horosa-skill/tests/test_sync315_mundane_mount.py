"""上游 v3.15.0 同步 · 世俗盘两个新挂载设置：吠陀世运入境盘 vedicEvent、地区盘推运目标年 regionTargetYear。

上游 regenMundane：vedicEvent ∈ MUNDANE_VEDIC_EVENTS（梅沙 / 夏 / 秋 / 冬，认不出回梅沙）→ solveVedicSolarIngress(ev, year) 起盘；
regionTargetYear → progTargetYear（缺省给了地区取起课年）。skill：同值域、认不出报错；没给 regionTargetYear 照旧取 year。
负向对照：vedicEvent 不进求根（恒 ingress_0）→ 夏季盘用例红；regionTargetYear 不读 → 目标年用例红。
"""
from __future__ import annotations

import re

import pytest
from skips import needs_upstream, upstream_path
from test_sync311_mundane_election import MUNDANE, ScriptedClient, _section, _service
from test_sync311_w3b_gim import _expected_region_progression, _region_run
from test_sync311_w3b_gim import _section as _gim_section

from horosa_skill.service import HorosaSkillService

UI = "Horosa-Web/astrostudyui/src"


@needs_upstream(f"{UI}/utils/aiAnalysisContext/regenMundane.js", f"{UI}/utils/techniqueMountSettings/schema.js")
def test_vedic_events_are_the_upstream_list_and_labels() -> None:
    regen = upstream_path(f"{UI}/utils/aiAnalysisContext/regenMundane.js").read_text(encoding="utf-8")
    keys = re.findall(r"'(\w+)'", re.search(r"MUNDANE_VEDIC_EVENTS = \[([^\]]*)\]", regen).group(1))
    schema = upstream_path(f"{UI}/utils/techniqueMountSettings/schema.js").read_text(encoding="utf-8")
    line = next(x for x in schema.splitlines() if "name: 'vedicEvent'" in x)
    labels = dict(re.findall(r"value: '(\w+)', label: '([^']+)'", line))
    assert tuple((k, labels[k]) for k in keys) == HorosaSkillService._MUNDANE_VEDIC_EVENTS


def test_summer_ingress_chart_is_cast_at_the_90_degree_ingress(tmp_path) -> None:
    client = ScriptedClient(vedic=True)
    env = _service(tmp_path, client).run_tool("mundane", {**MUNDANE, "mundaneType": "vedicmundane", "vedicEvent": "ingress_90"},
                                              save_result=False)
    assert env.ok, env.error
    text = env.data["snapshot_text"]
    head = _section(text, "吠陀世运")
    # 桩星历：恒星太阳日行 0.98565°、2025-04-14 06:00 为 0° → 90° 在 2025-07-14 13:26:50 左右
    assert head[2] == "入境盘：夏季盘" and head[3].startswith("入境时刻：2025-07-14 13:2"), head
    assert _section(text, "吠陀世运·年度盘")[0] == head[3].replace("入境时刻", "当前入境时刻")
    assert "梅沙入境时刻" not in text


def test_unknown_vedic_event_is_refused(tmp_path) -> None:
    env = _service(tmp_path, ScriptedClient(vedic=True)).run_tool(
        "mundane", {**MUNDANE, "mundaneType": "vedicmundane", "vedicEvent": "ingress_60"}, save_result=False)
    assert env.ok is False and env.error.code == "tool.mundane_invalid_setting"


@pytest.mark.parametrize(("extra", "target"), [({"year": 2026, "regionTargetYear": 2038}, 2038), ({"year": 2027}, 2027)])
def test_region_target_year_overrides_year(tmp_path, extra, target) -> None:
    env, _ = _region_run(tmp_path, extra)
    assert env.ok, env.error
    assert env.data["progTargetYear"] == target
    assert _gim_section(env.data["snapshot_text"], "地区盘推运").split("\n")[:5] == _expected_region_progression("aries", 1066, target)
