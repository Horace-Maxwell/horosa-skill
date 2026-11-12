"""Every technique declares whose moment its date/time slot holds (engine/time_roles.py, v0.50.0-dev).

Before: horosa_dispatch sent the same birth payload to every selected technique, so 「今天黄历」 read the birth day,
qimen cast the birth moment and tarot seeded from the birth time, all ok=true. The role table is the one place that
says which moment each technique wants; the payload planner and the gate read it.
"""
from __future__ import annotations

import pytest

from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.engine.time_roles import (
    LOOKUP,
    MOMENT,
    NATAL,
    NATAL_MOMENT,
    NATAL_TARGET,
    ROLES,
    TARGET_STYLE,
    TIME_ROLES,
    TWO_PARTY,
    WINDOW,
    YEAR,
    target_fields,
)


def test_every_registered_technique_has_exactly_one_time_role() -> None:
    assert set(TIME_ROLES) == set(TOOL_DEFINITIONS), (
        f"missing: {sorted(set(TOOL_DEFINITIONS) - set(TIME_ROLES))}; ghosts: {sorted(set(TIME_ROLES) - set(TOOL_DEFINITIONS))}"
    )
    assert set(TIME_ROLES.values()) <= set(ROLES)


@pytest.mark.parametrize("tool", sorted(TOOL_DEFINITIONS))
def test_time_role_matches_what_the_input_model_takes(tool: str) -> None:
    fields = set(TOOL_DEFINITIONS[tool].input_model.model_fields)
    role = TIME_ROLES[tool]
    if role in (NATAL, MOMENT, NATAL_TARGET, NATAL_MOMENT):
        assert "date" in fields, f"{tool}: role {role} needs a date slot"
    if role in (NATAL_TARGET, NATAL_MOMENT):
        assert tool in TARGET_STYLE, f"{tool}: say where the target goes"
        assert set(target_fields(tool)) <= fields, f"{tool}: target fields {target_fields(tool)} not in the model"
    else:
        assert tool not in TARGET_STYLE, f"{tool}: only target roles take a target style"
    if role == WINDOW:
        assert {"startDate", "endDate"} <= fields
    if role == YEAR:
        assert "year" in fields
    if role == TWO_PARTY:
        assert {"inner", "outer"} <= fields
    if role == LOOKUP:
        required = {name for name, info in TOOL_DEFINITIONS[tool].input_model.model_fields.items() if info.is_required()}
        assert not ({"date", "time"} & required), f"{tool}: a lookup must not require a moment"
