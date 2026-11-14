"""技法卡上的设置不印原始键名（审计 O-13：114 张卡里 64 张至少一项是 maxSpanDays / godKeyPos / byLon… 这类键名，同样印在报告封面与附录）。

叫法来源：结果敏感表 → 专门表 → 指引 → 字段说明「：」之前那一截 → 键名（最后一档由本守卫拦住）。
负向对照（实跑过）：_described_label 恒返回键名、_EXTRA_LABELS 删掉新增的 → 红。
"""
from __future__ import annotations

from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.reports import technique_card as tc


def test_no_setting_label_equals_its_key() -> None:
    labels = {field: label for field, label, _domains in tc._RESULT_SENSITIVE_FIELDS}
    raw = sorted({
        (tool, spec["key"]) for tool in TOOL_DEFINITIONS for spec in tc.result_setting_specs(tool)
        if (labels.get(spec["key"]) or tc._EXTRA_LABELS.get(spec["key"]) or spec.get("label") or tc._described_label(tool, spec["key"])) == spec["key"]
    })
    assert raw == [], raw


def test_derived_labels_drop_value_ranges() -> None:
    assert tc._described_label("returntimeline", "count") == "年数"
