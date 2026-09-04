"""v0.36.0 A7 — the advertised `hsys` description must follow the upstream house-system index table.

`BirthInput.hsys` used to say "1=Placidus"; the vendored table (perchart / ASTRO_HOUSE_SYSTEM_TEXT) has
1 = Alcabitus and 3 = Placidus. An agent that read the description and passed 1 for Placidus got a
different chart with no warning. Lockstep the prose to the table so it cannot drift again.
"""
from __future__ import annotations

from horosa_skill.schemas.tools import BirthInput
from horosa_skill.service import ASTRO_HOUSE_SYSTEM_TEXT


def test_hsys_description_matches_house_system_table() -> None:
    description = BirthInput.model_fields["hsys"].description or ""
    assert "1=Placidus" not in description
    for index, label in ASTRO_HOUSE_SYSTEM_TEXT.items():
        token = "整宫" if label == "整宫制" else label
        assert f"{index}={token}" in description, f"hsys description misses {index}={label}: {description}"
