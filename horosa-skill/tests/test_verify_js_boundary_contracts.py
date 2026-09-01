"""Twin tests for the three v0.33.1 guards born out of the issue #15 bug family.

Each guard gets, at minimum, one test that shows **why the pre-existing checks could not catch the
bug it targets** — the repo's established twin pattern (cf.
`test_version_equality_alone_would_have_missed_it`). A guard whose twin only asserts "it runs" is
the same decoration problem one level up.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PKG_ROOT / "scripts"
TOOLS_DIR = PKG_ROOT / "horosa-core-js" / "src" / "tools"


def _run_main(module, argv: list[str] | None = None) -> int:
    """Call a guard's `main()` with a clean argv.

    Guards that take flags parse `sys.argv`; under pytest that argv is pytest's own, so a bare
    `main()` dies on "unrecognized arguments" instead of running the check.
    """
    import sys

    saved = sys.argv
    sys.argv = [module.__name__, *(argv or [])]
    try:
        return module.main()
    finally:
        sys.argv = saved


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# ── verify_js_boundary_contracts ────────────────────────────────────────────────────────────────


def test_boundary_guard_is_green_on_the_current_tree() -> None:
    assert _run_main(_load("verify_js_boundary_contracts")) == 0


def test_contract_covers_the_local_variable_shape_issue_15_actually_had() -> None:
    """issue #15's literal never appeared at the call site — it was `const four = {…}` one line up.

    A generator that only scanned inline first arguments (`fn({…})`) would have produced a contract
    with **no entry at all** for `computeWuxingStrength`, so the dead-key check would have been
    green while the bug shipped. This asserts the local-variable resolution is actually in play.
    """
    contract = json.loads((PKG_ROOT / "contracts" / "js_boundary_contracts.json").read_text(encoding="utf-8"))
    sites = contract["tools"]["baziGeju.js"]
    pillar_sites = [s for s in sites if s.get("via_local") == "four"]
    assert pillar_sites, "the `const four = {…}` boundary is not in the contract — issue #15 would slip"
    for site in pillar_sites:
        assert "time" in site["keys"] and "hour" not in site["keys"], (
            f"{site['callee']} must be handed the `time` pillar key, not `hour`: {site['keys']}"
        )


def test_dead_key_would_be_caught(tmp_path: Path) -> None:
    """Inject the historical `hour` key and confirm the guard reports it."""
    module = _load("verify_js_boundary_contracts")
    contract = json.loads((PKG_ROOT / "contracts" / "js_boundary_contracts.json").read_text(encoding="utf-8"))
    for site in contract["tools"]["baziGeju.js"]:
        if site.get("via_local") == "four":
            site["keys"] = sorted(set(site["keys"]) - {"time"} | {"hour"})
    errors: list[str] = []
    module._check_dead_keys(contract, errors)
    assert any("`hour`" in e for e in errors), f"the dead-key oracle missed `hour`: {errors}"


def test_exemptions_survive_regeneration() -> None:
    """Regenerating must not wipe the hand-written exemptions.

    Regeneration is the *normal* action right after fixing a call site, so a generator that
    overwrote the exemption block would mean no exemption ever outlives one repair cycle.
    """
    gen = _load("gen_js_boundary_contracts")
    built = gen.build()
    assert "exemptions" in built, "regeneration dropped the exemption block"
    assert built["exemptions"]["dead_key"], "exemption entries were lost"


# ── verify_silent_returns ───────────────────────────────────────────────────────────────────────


def test_silent_return_ratchet_is_green() -> None:
    assert _run_main(_load("verify_silent_returns")) == 0


def test_empty_return_with_an_error_code_does_not_count_as_debt() -> None:
    """The fixed shape must actually clear the ratchet, or paying debt is impossible.

    `tiebanFramework.js` was one of the four sites fixed in v0.33.1: it now returns
    `{ text: '', data: { ok: false, … } }`. If the scanner still counted that, the ratchet would
    punish the repair.
    """
    module = _load("verify_silent_returns")
    found = module.scan()
    src = (TOOLS_DIR / "tiebanFramework.js").read_text(encoding="utf-8")
    assert "incomplete_four_pillars" in src, "the fixture this test relies on has changed"
    assert "tiebanFramework.js" not in found, (
        "a signalled empty return is still counted as silent debt — repairs would never clear it"
    )


# ── verify_schema_knob_wiring ───────────────────────────────────────────────────────────────────


def test_schema_knob_guard_is_green() -> None:
    assert _run_main(_load("verify_schema_knob_wiring")) == 0


def test_the_deleted_invented_knobs_are_really_gone() -> None:
    """`receptionMode`/`almutenScheme`/`dignityScheme` named nothing in any engine vocabulary.

    They were documented, described, and inert for three releases. The point of deleting them
    rather than leaving them "harmlessly present" is that a described knob is a promise the agent
    has no way to test.
    """
    schema = (PKG_ROOT / "src" / "horosa_skill" / "schemas" / "tools.py").read_text(encoding="utf-8")
    for invented in ("receptionMode:", "almutenScheme:", "dignityScheme:", "medicalCritical:"):
        assert invented not in schema, f"{invented} is back in the schema with no engine that reads it"


def test_a_name_alone_is_not_evidence_the_old_way_would_have_passed() -> None:
    """Why the pre-existing checks missed all fifteen dead knobs.

    Nothing in the repo compared schema fields against consumers: `test_mcp_contract` asserts the
    schemas *serialize*, `verify_docs_sync` counts tools, and the JSON-schema round-trip is happy
    with any field at all. Every one of those stayed green across three releases while the knobs
    did nothing. This test pins the property that now closes it: the guard's own scan must be able
    to name an unwired field when one exists.
    """
    module = _load("verify_schema_knob_wiring")
    declared = module._declared_fields()
    assert "ElectionInput" in declared and "HoraryInput" in declared
    # The scan must be discriminating, not vacuous: it rejects a name nothing consumes.
    assert "definitelyNotAConsumedFieldName" not in module._haystack()
