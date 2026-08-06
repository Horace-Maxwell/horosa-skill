"""Unit tests for the re-vendor transform (scripts/revendor_core_js.py).

Four defects pinned here, all shipped in v0.26.0 and all of the same family: a batch of regex
matches was materialized up front, then the text was re-spliced using those now-stale offsets.
Deleting the first match shortens the string, so every later `match.start()/end()` points at the
wrong place. The mildest symptom is a silently-skipped removal; the worst is a **destroyed file**.

`horosa-core-js/src/vendor/` is git-tracked, so a corrupted re-vendor lands in the repo — and
`loadcheck.mjs` only catches it if the wreckage happens to break an import.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "revendor_core_js.py"
_spec = importlib.util.spec_from_file_location("revendor_core_js", _SCRIPT)
rv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rv)


# --- stale offsets: orphaned imports -----------------------------------------------------------


def test_two_orphaned_namespace_imports_do_not_destroy_the_file() -> None:
    """The reproduction: v0.26.0 turned this into `\\nimport * as lodash from 'urn 1; }`."""
    src = "import * as d3 from 'd3';\nimport * as lodash from 'lodash';\nexport function f(){ return 1; }\n"
    out, notes = rv._drop_orphaned_imports(src)
    assert "export function f(){ return 1; }" in out, f"module body was destroyed: {out!r}"
    assert "d3" not in out and "lodash" not in out
    assert len(notes) == 2


def test_second_orphaned_named_import_is_also_dropped() -> None:
    """`utils/kentangCache` is the case the function's own docstring names; it used to survive."""
    src = (
        "import { aa } from './x.js';\n"
        "import { cachedKentangFetch, someHelper } from './utils/kentangCache.js';\n"
        "const K = 1;\nexport function real(){ return K; }\n"
    )
    out, _ = rv._drop_orphaned_imports(src)
    assert "kentangCache" not in out, "2nd orphaned import survived — ERR_MODULE_NOT_FOUND at load"
    assert "export function real" in out


def test_imports_actually_in_use_are_kept() -> None:
    src = "import * as AstroConst from './progConst.js';\nexport const X = AstroConst.SUN;\n"
    assert rv._drop_orphaned_imports(src)[0] == src


# --- stale offsets + head selection: export lists ----------------------------------------------


def test_two_export_lists_do_not_produce_invalid_js() -> None:
    """v0.26.0 produced `export {export { q };` — the module stopped parsing entirely."""
    src = "const a = 1;\nexport { p, fetchA };\nconst IMPORTANT = 42;\nexport { q, fetchB };\n"
    out, _ = rv._prune_default_export(src, ["fetchA", "fetchB"])
    assert "export {export" not in out, f"invalid JS emitted: {out!r}"
    assert "const IMPORTANT = 42;" in out, "code between the two export lists was eaten"
    assert "export { p };" in out and "export { q };" in out


def test_a_named_list_containing_the_substring_default_stays_named() -> None:
    """Head was picked with `"default" in match.group(0)`, so `defaultRules` flipped the whole
    list to `export default { … }` and every `import { keeper }` broke."""
    src = "export { fetchThing, defaultRules, keeper };\n"
    out, _ = rv._prune_default_export(src, ["fetchThing"])
    assert not out.strip().startswith("export default"), f"named list turned into a default export: {out!r}"
    assert out.strip() == "export { defaultRules, keeper };"


def test_a_real_default_export_is_still_pruned_as_default() -> None:
    src = "export default { fetchX, keep };\n"
    out, _ = rv._prune_default_export(src, ["fetchX"])
    assert out.strip() == "export default { keep };"


# --- stub_import must not be treated as a regex replacement template ---------------------------


def test_stub_import_stub_is_inserted_literally() -> None:
    """A JS stub containing a regex literal or an escape is normal. As an `re.sub` template, `\\1`
    silently splices the captured import back in and `\\c` raises `re.error`, killing the run."""
    src = "import { x } from './helper.js';\nconst y = 1;\n"
    stub = "const x = (s) => s.replace(/\\d+/g, '\\\\1');"
    out, notes = rv.apply_deviations(src, [{"kind": "stub_import", "specifier": "./helper.js", "stub": stub}])
    assert stub in out, f"stub was reinterpreted as a template: {out!r}"
    assert "import {" not in out
    assert notes == ["stubbed ./helper.js"]


def test_dead_prune_helper_is_gone() -> None:
    assert not hasattr(rv, "_prune_default_export_unused"), "dead near-duplicate should stay deleted"
