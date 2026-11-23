"""上游 v3.15.0 同步 · 主限法相位集 `pdaspects`（挂载齿轮新字段，页面起盘表单同九档）。

上游 recordPdAspects：九档内去重升序、数字串照收、空 / 全坏 → 托勒密五相。skill 照收照排，坏值报错（主限值域闸同律）。
负向对照：_pd_normalize_aspects 不归一（直接 return）→ 去重升序用例红；九档表少一档 → 对拍红。
"""
from __future__ import annotations

import re

import pytest
from skips import needs_upstream, upstream_source

from horosa_skill.errors import ToolValidationError
from horosa_skill.service.text import pd_zr

UI = "Horosa-Web/astrostudyui/src"


@needs_upstream(f"{UI}/utils/techniqueMountSettings.js", f"{UI}/utils/aiAnalysisContext/catalog.js")
def test_choices_and_default_are_the_upstream_tables() -> None:
    mount = upstream_source(f"{UI}/utils/techniqueMountSettings.js")
    choices = re.search(r"PD_ASPECT_CHOICES\s*=\s*\[([^\]]*)\]", mount)
    default = re.search(r"DEFAULT_PD_ASPECTS\s*=\s*\[([^\]]*)\]", upstream_source(f"{UI}/utils/aiAnalysisContext/catalog.js"))
    assert choices and default
    assert tuple(int(x) for x in choices.group(1).split(",")) == pd_zr._PD_ASPECT_CHOICES
    assert tuple(int(x) for x in default.group(1).split(",")) == pd_zr._PD_DEFAULT_ASPECTS


@pytest.mark.parametrize(("given", "sent"), [
    ([180, "45", 0, 45], [0, 45, 180]),        # 上游 pdAspectsMount.test 同例（去掉坏值 999：skill 报错，见下）
    ([], [0, 60, 90, 120, 180]),
    ([0, 30.0], [0, 30]),
])
def test_valid_sets_are_deduped_sorted_and_empty_means_ptolemy(given, sent) -> None:
    payload = {"pdaspects": given}
    pd_zr._pd_validate_options(payload, "pd")
    assert payload["pdaspects"] == sent


@pytest.mark.parametrize("bad", [[7], [0, 999], ["x"], [True], "0,60", 60])
def test_unknown_aspects_are_refused(bad) -> None:
    with pytest.raises(ToolValidationError) as err:
        pd_zr._pd_validate_options({"pdaspects": bad}, "pdchart")
    assert err.value.details["field"] == "pdaspects"
