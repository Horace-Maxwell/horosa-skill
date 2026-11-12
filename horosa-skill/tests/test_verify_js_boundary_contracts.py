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
    schema_dir = PKG_ROOT / "src" / "horosa_skill" / "schemas" / "tools"  # 包（v0.41.1 起）：扫全部模块
    schema = "\n".join(path.read_text(encoding="utf-8") for path in sorted(schema_dir.rglob("*.py")))
    assert "class BirthInput" in schema, "scanned the wrong place: the check would pass vacuously"
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
    tokens = module.consumer_tokens()
    assert "definitelyNotAConsumedFieldName" not in tokens
    # Schema modules mention their own field names; none of that may count as a consumer (v0.41.1, schemas/tools is a
    # package): a baselined unwired knob appears only inside the schema package, so it must not be a consumer token.
    unwired = module.load_baseline()
    assert unwired and all(entry.split(".", 1)[1] not in tokens for entry in unwired)


def test_a_substring_or_a_sentence_is_not_a_consumer() -> None:
    """C-18 #5 的两个反例：旧扫描按子串查原文，`vargaVariant` 被 JS 里的 `j.vargaVariants` 冒充、`pdYears` 被
    `agent_guidance/contracts.py` 里描述它的那句话冒充——两者在本仓都没有读者（读者在上游后端，见基线指针）。
    负向对照：把扫描换回「子串出现在任意文件原文里」，两个都从 scan() 里消失（实跑过）。"""
    module = _load("verify_schema_knob_wiring")
    dead = module.scan()
    assert "IndiaChartInput.vargaVariant" in dead and "BirthInput.pdYears" in dead
    assert "vargaVariant" not in module.js_tokens("const v = j.vargaVariants; // vargaVariant\n/* vargaVariant */ 'see vargaVariant'")
    assert "vargaVariant" in module.js_tokens("const v = opts.vargaVariant;") and "vargaVariant" in module.js_tokens("x['vargaVariant']")
    assert "pdYears" not in module.python_tokens('# pdYears\nDOC = {"a": "推算年限 pdYears 上限"}\n')
    assert {"pdYears"} <= module.python_tokens('payload.get("pdYears")') and {"pdYears"} <= module.python_tokens("f(pdYears=1)")
    # 只描述旋钮的文件不算读者
    assert any(path.endswith("agent_guidance/") for path in module.DESCRIBING_FILES)


def test_every_baselined_knob_points_at_its_upstream_reader(tmp_path: Path) -> None:
    """基线不是垃圾桶：每条都要写上游读它的文件:行；有上游 checkout 时文件必须存在且提到该字段。"""
    module = _load("verify_schema_knob_wiring")
    baseline = module.load_baseline()
    assert all(pointer.strip() for pointer in baseline.values())
    assert module.pointer_problems({"X.someKnob": ""}, None) and not module.pointer_problems({"X.someKnob": "a.py:1"}, None)
    (tmp_path / "a.py").write_text("data.get('otherKnob')\n", encoding="utf-8")
    assert module.pointer_problems({"X.someKnob": "a.py:1"}, tmp_path)  # 指向的文件根本没提这个字段
    assert module.pointer_problems({"X.someKnob": "missing.py:1"}, tmp_path)
    (tmp_path / "a.py").write_text("data.get('someKnob')\n", encoding="utf-8")
    assert not module.pointer_problems({"X.someKnob": "a.py:1 (reads it)"}, tmp_path)


# ── verify_value_goldens ────────────────────────────────────────────────────────────────────────


def test_value_golden_guard_is_green() -> None:
    assert _run_main(_load("verify_value_goldens")) == 0


def test_a_tool_named_in_a_title_or_comment_is_not_covered() -> None:
    """C-18 #8：旧扫描只要求「值级 check 块里出现技法名」，标题、注释都算——calendarExtras / qimenzeri 的旧金标测的是
    vendored 函数（personBazi / computeQimenScanPan），从没调过 tools/ 那层；placeResolve 靠 placeSearch 块里的一行注释过关。
    现在要求块里**调用**从 src/tools/<名>.js 导入的名字，注释先剥掉。负向对照：去掉注释剥离、或把「调用」放宽成「名字出现」，各红一例（实跑过）。"""
    module = _load("verify_value_goldens")
    header = "import { runTongshu } from '../src/tools/tongshu.js';\nimport { personBazi } from '../src/vendor/calendar/riziEngine.js';\n"
    titled = header + "check('tongshu 值级', () => {\n  // runTongshu 在这里只是注释\n  assert(personBazi({}).xi[0] === '水', 'x');\n});\n"
    commented_call = header + "check('x', () => {\n  /* runTongshu({ date }) 曾经这样调 */ // runTongshu({})\n  assert(personBazi({}).xi[0] === '水', 'x');\n});\n"
    named_in_string = header + "check('x', () => {\n  assert(personBazi({}).label === 'runTongshu 甲', 'runTongshu');\n});\n"
    for text in (titled, commented_call, named_in_string):
        assert "tongshu" not in module.scan(text)[0], text
    called = header + "check('值级', () => {\n  assert(runTongshu({ date: '2028-04-06' }).text.includes('日干支：辛酉'), 'x');\n});\n"
    assert "tongshu" in module.scan(called)[0]
    # 动态 import 解构出来的名字同样算（placeSearch 的写法）；`a.runTongshu(` 这种别人的属性不算。
    dynamic = "try {\n  const { runTongshu: rt } = await import('../src/tools/tongshu.js');\n  assert(rt({}).text === '甲', 'x');\n} catch (e) {}\n"
    assert "tongshu" in module.scan("\n" + dynamic.replace("try {", "try {", 1))[0]
    assert module.tool_bindings("import { a as b, c } from '../src/tools/x.js';") == {"b": "x", "c": "x"}
    # 模板字符串里的中文也算值级断言（jinkou 金标的写法）
    assert module._is_value_level("assert(text.includes(`四柱：${g.year}年`), 'pillars');")


def test_the_real_selfcheck_covers_the_tools_it_claims() -> None:
    module = _load("verify_value_goldens")
    covered, all_tools = module.scan()
    baseline = json.loads((PKG_ROOT / "contracts" / "value_golden_debt.json").read_text(encoding="utf-8"))
    assert set(baseline["covered"]) <= covered
    assert {"calendarExtras", "qimenzeri", "tongshu", "egyptSection", "classicalDerived", "jinkou"} <= covered
    assert set(baseline["covered_via"]) == {"placeResolve"} and baseline["covered_via"]["placeResolve"]["via"] in covered
    assert len(baseline["debt"]) <= 10 and not (set(baseline["debt"]) & covered)
