#!/usr/bin/env python3
"""Every declared Input-schema field must have a consumer somewhere. Ratcheted.

A schema field is a promise to the agent: "pass this and it changes the result." v0.33.1 found
fifteen fields that kept that promise nowhere — 11 on `ElectionInput` (whose own comment cited
`electionParams.js`'s 13 keys while the fields below it matched **none** of them), 4 on
`HoraryInput` (two of which, `receptionMode`/`almutenScheme`, are names that exist in no engine
vocabulary at all), plus `zuoShan`, which upstream had already deleted as a "double ghost". They
were documented, described, and inert across three releases: the agent reads the description,
passes the knob, and the output silently ignores it while looking exactly as authoritative.

A field is "wired" when its name occurs as a **code token** in a consumer file outside the schema package: a Python
name / attribute / keyword / argument, or a string literal that *is* the name (`payload.get("pdYears")`); a JS
identifier or a string literal that is the name. Comments, prose strings and docs do not count, and neither do the
files that only *describe* knobs (sample payloads, agent guidance, the MCP field-doc / advertising layer, script
conversion tables, the benchmark). The first version searched raw text for a substring, so `vargaVariant` was "wired"
by a JS line reading `j.vargaVariants`, and `pdYears` by the sentence describing it in `agent_guidance/contracts.py`
(C-18 #5; `tests/test_verify_js_boundary_contracts.py` keeps both counter-examples). Value-level proof is still
`selfcheck.mjs`'s job: a token is evidence of a reader, not of the right reading.

**One deliberate blind spot, and why the baseline is not empty**: fields forwarded verbatim to the
remote backend (`/chart`, `/india/*`, the ken endpoints) are consumed by name *in the upstream
astropy source*, which is not in this repo and is not on CI. They therefore appear "unwired" here
while being perfectly live. Each baselined entry therefore carries its pointer — the upstream file and the
line that reads it (`"BirthInput.pdYears": "Horosa-Web/astropy/astrostudy/perchart.py:462 …"`). An entry with an
empty pointer fails; when `HOROSA_SOURCE_ROOT` names the Horosa-Public checkout, the pointed-at file must exist and
contain the field name. So the baseline means "verified live via the backend", not "known broken", and a NEW name
still fails: the promise this guard actually enforces is that nobody adds a field without pointing at its consumer.

Baseline in `contracts/schema_knob_debt.json`; `--update-baseline` keeps the pointers it has and writes new entries with
an empty pointer (which fails until someone fills it in). Stdlib-only. Wired into CI.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys

# Windows 控制台默认 cp1252/cp936：脚本自己 print 的中文会抛 UnicodeEncodeError 并让脚本 exit 1
# （v0.38.0 的 repack 脚本在「打印成功信息」那一步失败过）。统一在入口把两条流改成 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
PKG_ROOT = SCRIPTS.parent
# 输入模型自 v0.41.1 是包 schemas/tools/（按技法族分模块）。声明从包里每个模块读；草堆排除整个包——只排除某一个文件时，
# 「只在兄弟 schema 模块里出现过的字段名」会被当成有人消费（schema 自己提到自己不算接线）。
SCHEMA_DIR = PKG_ROOT / "src" / "horosa_skill" / "schemas" / "tools"


def _schema_files() -> list[Path]:
    files = sorted(SCHEMA_DIR.rglob("*.py"))
    if not files:
        raise SystemExit(f"no schema modules under {SCHEMA_DIR} — the scan would pass vacuously")
    return files
BASELINE = PKG_ROOT / "contracts" / "schema_knob_debt.json"

SEARCH_ROOTS = (
    PKG_ROOT / "src" / "horosa_skill",
    PKG_ROOT / "horosa-core-js" / "src",
)
SEARCH_SUFFIXES = (".py", ".js", ".mjs")

# Fields whose consumption is structural rather than by-name: they are read via `**payload`
# forwarding, by the transport layer, or by pydantic itself. Listing them here is cheaper and
# far more honest than teaching the scanner to model every passthrough.
STRUCTURAL_FIELDS = frozenset(
    {
        "date", "time", "zone", "lat", "lon", "ad", "options", "chart", "predictive", "tradition",
    }
)


# Files that describe knobs to the agent / the user / the tests without reading them: a field named only here is
# advertised, not consumed. Paths relative to the package root.
DESCRIBING_FILES = (
    "src/horosa_skill/testing_payloads.py",
    "src/horosa_skill/agent_guidance/",
    "src/horosa_skill/western_options_doc.py",
    "src/horosa_skill/surfaces/mcp_field_docs.py",
    "src/horosa_skill/surfaces/mcp_schema.py",
    "src/horosa_skill/textscript/",
    "src/horosa_skill/benchmark/",
)

_IDENT = re.compile(r"[A-Za-z_$][\w$]*\Z")
# JS: comments and string / template literals are matched first so identifiers inside them are not read as code.
_JS_TOKEN = re.compile(
    r"""//[^\n]*|/\*.*?\*/|'(?:\\.|[^'\\\n])*'|"(?:\\.|[^"\\\n])*"|`(?:\\.|[^`\\])*`|[A-Za-z_$][\w$]*""", re.S
)


def _declared_fields() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for node in (n for path in _schema_files() for n in ast.parse(path.read_text(encoding="utf-8")).body):
        if not isinstance(node, ast.ClassDef):
            continue
        names = [
            stmt.target.id
            for stmt in node.body
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
            and "ClassVar" not in ast.unparse(stmt.annotation)  # class constants (HSYS_FAMILY …) are not fields
        ]
        if names:
            out[node.name] = names
    return out


def python_tokens(text: str) -> set[str]:
    """Names a Python file reads or writes: identifiers, attributes, keywords, parameters, and string literals that
    are exactly an identifier (dict keys / `.get("x")`). Comments vanish with the AST; prose strings do not match."""
    tokens: set[str] = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Name):
            tokens.add(node.id)
        elif isinstance(node, ast.Attribute):
            tokens.add(node.attr)
        elif isinstance(node, ast.keyword) and node.arg:
            tokens.add(node.arg)
        elif isinstance(node, ast.arg):
            tokens.add(node.arg)
        elif isinstance(node, ast.alias):
            tokens.add(node.asname or node.name.rsplit(".", 1)[-1])
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and _IDENT.match(node.value):
            tokens.add(node.value)
    return tokens


def js_tokens(text: str) -> set[str]:
    """Identifiers outside comments / strings, plus string literals that are exactly an identifier."""
    tokens: set[str] = set()
    for token in _JS_TOKEN.findall(text):
        if token.startswith(("//", "/*")):
            continue
        if token[0] in "'\"`":
            if _IDENT.match(token[1:-1]):
                tokens.add(token[1:-1])
        else:
            tokens.add(token)
    return tokens


def _consumer_files() -> list[Path]:
    files: list[Path] = []
    for root in SEARCH_ROOTS:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.suffix not in SEARCH_SUFFIXES or SCHEMA_DIR in path.parents:
                continue
            if "__pycache__" in path.parts or "node_modules" in path.parts:
                continue
            rel = path.relative_to(PKG_ROOT).as_posix()
            if any(rel == d or (d.endswith("/") and rel.startswith(d)) for d in DESCRIBING_FILES):
                continue
            files.append(path)
    return files


def consumer_tokens() -> set[str]:
    tokens: set[str] = set()
    for path in _consumer_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        tokens |= python_tokens(text) if path.suffix == ".py" else js_tokens(text)
    return tokens


def scan(tokens: set[str] | None = None) -> list[str]:
    tokens = consumer_tokens() if tokens is None else tokens
    dead: list[str] = []
    for cls, fields in sorted(_declared_fields().items()):
        for field in fields:
            if field in STRUCTURAL_FIELDS:
                continue
            if field in tokens:
                continue
            dead.append(f"{cls}.{field}")
    return dead


def load_baseline() -> dict[str, str]:
    if not BASELINE.is_file():
        return {}
    unwired = json.loads(BASELINE.read_text(encoding="utf-8")).get("unwired") or {}
    return dict(unwired) if isinstance(unwired, dict) else {name: "" for name in unwired}


def pointer_problems(baseline: dict[str, str], source_root: Path | None) -> list[str]:
    """Every baselined knob names its upstream reader; with the checkout at hand the reader must really mention it."""
    problems: list[str] = []
    for entry, pointer in sorted(baseline.items()):
        if not str(pointer).strip():
            problems.append(f"{entry}: no consumer pointer (\"<upstream file>:<line> …\")")
            continue
        if source_root is None:
            continue
        rel = str(pointer).split()[0].rsplit(":", 1)[0]
        target = source_root / rel
        field = entry.split(".", 1)[1]
        if not target.is_file():
            problems.append(f"{entry}: pointer file {rel} does not exist under {source_root}")
        elif field not in target.read_text(encoding="utf-8", errors="replace"):
            problems.append(f"{entry}: {rel} does not mention {field}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--update-baseline", action="store_true")
    args = ap.parse_args()

    dead = scan()
    baseline = load_baseline()
    if args.update_baseline:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(
            json.dumps(
                {
                    "_comment": (
                        "Fields with no consumer inside this repo, each with the upstream file:line that reads it "
                        "(they are forwarded verbatim to the astropy / ken endpoints). An empty pointer fails the guard: "
                        "point at the consumer before baselining, or the guard degrades into a dumping ground. "
                        "Refresh with `uv run python scripts/verify_schema_knob_wiring.py --update-baseline` "
                        "(keeps existing pointers)."
                    ),
                    "unwired": {name: baseline.get(name, "") for name in dead},
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8", newline="\n",
        )
        print(f"baseline updated: {len(dead)} unwired schema knob(s)")
        return 0

    allowed = set(baseline)
    new = sorted(set(dead) - allowed)
    fixed = sorted(allowed - set(dead))
    source_env = os.environ.get("HOROSA_SOURCE_ROOT")
    source_root = Path(source_env) if source_env and Path(source_env).is_dir() else None
    pointers = pointer_problems(baseline, source_root)

    if new:
        print("schema-knob-wiring guard FAILED — these declared fields have no consumer:", file=sys.stderr)
        for name in new:
            print(f"  - {name}", file=sys.stderr)
        print(
            "\nWire it (service.py forwarding + the engine that reads it), or delete the field. "
            "A documented knob that does nothing is worse than a missing one: the agent will pass "
            "it, read the confident output, and never learn it was ignored.",
            file=sys.stderr,
        )
        return 1
    if fixed:
        print(
            f"schema-knob debt dropped by {len(fixed)} ({', '.join(fixed)}). Run "
            "`uv run python scripts/verify_schema_knob_wiring.py --update-baseline` to lock it in.",
            file=sys.stderr,
        )
        return 1

    if pointers:
        print("schema-knob-wiring guard FAILED — baselined knobs without a verifiable consumer pointer:", file=sys.stderr)
        for line in pointers:
            print(f"  - {line}", file=sys.stderr)
        return 1

    checked = "pointers checked against HOROSA_SOURCE_ROOT" if source_root else "pointers present (set HOROSA_SOURCE_ROOT to check them)"
    print(f"schema-knob-wiring OK: every declared field has a consumer ({len(allowed)} baselined exception(s), {checked}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
