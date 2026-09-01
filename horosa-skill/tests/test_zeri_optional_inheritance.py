from __future__ import annotations

from horosa_skill.exports.registry import (
    AI_EXPORT_OPTIONAL_SECTIONS,
    AI_EXPORT_PRESET_SECTIONS,
    ZERI_DERIVED_KEYS,
)


def test_zeri_keys_inherit_the_base_optional_sections() -> None:
    # A derived 择日 key spreads its base preset wholesale; without inheriting the base's optional
    # set, every base-conditional section becomes mandatory for the derived key and live exports
    # report spurious missing_selected_sections (5 of 10 zeri tools did at v0.34.0). Offline tests
    # emit full section sets and cannot see this — only a real runtime can.
    for zeri_key, base_key in ZERI_DERIVED_KEYS:
        base_optional = set(AI_EXPORT_OPTIONAL_SECTIONS.get(base_key, []))
        derived_optional = set(AI_EXPORT_OPTIONAL_SECTIONS.get(zeri_key, []))
        assert base_optional <= derived_optional, (zeri_key, sorted(base_optional - derived_optional))
        # Every optional section must still be a preset section (optional ⊆ preset — §5.5 双登记).
        assert derived_optional <= set(AI_EXPORT_PRESET_SECTIONS[zeri_key]), zeri_key


def test_liureng_zeri_treats_quxiang_as_conditional() -> None:
    # `取象` is mandatory for a liureng birth chart but liurengZeriSnapshot.js never emits it for a
    # moment chart — a dead preset entry for the derived key, registered conditional (§5.4 / §5.5).
    assert "取象" in AI_EXPORT_OPTIONAL_SECTIONS["liurengzeri"]
    assert "取象" in AI_EXPORT_PRESET_SECTIONS["liurengzeri"]
