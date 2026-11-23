"""No `x := …` inside a module-level comprehension (v0.52.0).

Why: an assignment expression inside a comprehension binds in the ENCLOSING scope. At module level that makes `x` a module
global. `surfaces/mcp_requests.py` built `_MODEL_TOOL_NAMES` with `len(names := [...]) == 1` over a frozenset of input
models, so the module kept a stray `names` — the list for whichever model the frozenset (ordered by object address) yielded
last. When that was a model several techniques share (predictive 6 / shenshu 11 / astro chart 3), `technique_census.py`
saw `surfaces.mcp_requests:names` as a registration table and the census check went red. The v0.52.0 release matrix
hit it on the Windows ARM lane only — the other two lanes happened to iterate differently.
"""
from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "horosa_skill"
_COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def leaked_walrus(source: str) -> list[tuple[int, str]]:
    """(line, name) of every `name := …` inside a comprehension that is not inside a function (module or class body)."""
    hits: list[tuple[int, str]] = []

    def visit(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, _SCOPES):
                continue  # inside a function the leak stays a local
            if isinstance(child, _COMPREHENSIONS):
                hits.extend((n.lineno, n.target.id) for n in ast.walk(child)
                            if isinstance(n, ast.NamedExpr) and isinstance(n.target, ast.Name))
                continue
            visit(child)

    visit(ast.parse(source))
    return hits


def test_no_module_level_comprehension_leaks_a_walrus_target() -> None:
    found = [f"{path.relative_to(SRC)}:{line} {name}"
             for path in sorted(SRC.rglob("*.py")) for line, name in leaked_walrus(path.read_text(encoding="utf-8"))]
    assert not found, "module-level comprehension leaks a global via := (compute it in a function): " + ", ".join(found)


def test_mcp_requests_has_no_stray_names_global() -> None:
    from horosa_skill.surfaces import mcp_requests

    assert "names" not in vars(mcp_requests)
    shared = {"givenyear", "lunarreturn", "pd", "pdchart", "solararc", "solarreturn"}
    assert not shared & set(mcp_requests._MODEL_TOOL_NAMES.values())  # one model, many techniques → no single name


def test_the_scanner_catches_the_original_code() -> None:
    """Negative control: the pre-fix `_MODEL_TOOL_NAMES` comprehension is flagged; the same thing inside a function is not."""
    original = (
        "_MODEL_TOOL_NAMES = {\n"
        "    model: names[0]\n"
        "    for model in _TECHNIQUE_MODELS\n"
        "    if len(names := [n for n, d in TOOL_DEFINITIONS.items() if d.input_model is model]) == 1\n"
        "}\n"
    )
    assert leaked_walrus(original) == [(4, "names")]
    assert leaked_walrus("class C:\n    X = [y for x in range(3) if (y := x)]\n") == [(2, "y")]
    assert leaked_walrus("def f():\n    return [y for x in range(3) if (y := x)]\n") == []
