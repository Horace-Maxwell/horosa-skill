#!/usr/bin/env python3
"""Generate `contracts/js_boundary_contracts.json` — what `src/tools/*.js` hands the engines.

`horosa-core-js/src/tools/**` is the glue between the skill and the vendored 星阙 engines. It was,
until v0.33.1, **the only part of the JS tree with no static guard at all**: `loadcheck.mjs` walks
`src/vendor/**` only, `vendor_manifest.json` tracks engine files (not their callers), and `dispatch`
was verified to be a clean pass-through. Every value-level bug this release fixed lived exactly
there — issue #15's `hour` vs `time`, tiebanFramework's `minute` vs `ke`, canping's dropped
`lunarMonth`/`lunarDay`. All of them are the same shape: **the caller offers a key the callee never
reads**, the callee's destructuring default silently fills in, and the output stays plausible.

This generator records, per call site, which keys the caller offers. `verify_js_boundary_contracts.py`
then asserts every offered key actually appears in the callee module's source. That is a deliberately
weak oracle — a key appearing anywhere in the file is not proof it is read — but it is a *cheap and
exact* detector for the dead-key shape, which is the one that has actually shipped bugs.

Regenerate after adding or rewiring a call site:

    uv run python scripts/gen_js_boundary_contracts.py

Stdlib-only. Paths in the contract are repo-relative (never absolute — the file is git-tracked).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
PKG_ROOT = SCRIPTS.parent
CORE_JS = PKG_ROOT / "horosa-core-js"
TOOLS_DIR = CORE_JS / "src" / "tools"
CONTRACT = PKG_ROOT / "contracts" / "js_boundary_contracts.json"

# `import { a, b as c } from '../vendor/x/y.js'` — only vendor imports matter; tool-to-tool calls
# are skill-authored on both ends and move together.
_IMPORT_RE = re.compile(
    r"import\s*\{([^}]*)\}\s*from\s*'(\.\./vendor/[^']+)'",
    re.MULTILINE,
)

# A call to an imported engine function. Object literals are collected from **every** argument
# position, not just the first: `buildTiebanFramework(fp, { ke, birthYear })` puts the hand-written
# boundary in arg 2, and the `minute`-vs-`ke` dead key this guard exists to catch lived exactly there.
# A bare identifier argument is resolved one level: `const four = { … }; computeWuxingStrength(four, …)`
# is the exact shape of issue #15 — the hand-written key set lives in the `const`, not at the call.
# Without this the guard would have been decoration for the very bug it names.
# `fn(payload)` (a parameter, not a local literal) still resolves to nothing and is skipped.
_CALL_HEAD_RE = re.compile(r"\b([A-Za-z_$][\w$]*)\s*\(")

# Top-level `key:` / shorthand `key,` inside one object literal (nesting is skipped by the scanner).
_KEY_RE = re.compile(r"(?:^|[,{])\s*(?:\.\.\.[^,}]+|(?:'([\w$]+)'|\"([\w$]+)\"|([\w$]+))\s*(?=[,:}]))")

# `const four = {` / `let opts = {` — the local whose literal crosses the boundary one line later.
_LOCAL_LITERAL_RE = "(?:const|let|var)\\s+{name}\\s*=\\s*\\{{"


def _strip_comments_and_strings(src: str) -> str:
    """Blank out comments and string/template bodies so the brace scanner can't be fooled.

    Lengths are preserved so every offset in the result still maps to the original text.
    """
    out = list(src)
    i, n = 0, len(src)
    while i < n:
        ch = src[i]
        if ch == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                out[i] = " "
                i += 1
            continue
        if ch == "/" and i + 1 < n and src[i + 1] == "*":
            while i < n and not (src[i] == "*" and i + 1 < n and src[i + 1] == "/"):
                if src[i] != "\n":
                    out[i] = " "
                i += 1
            for _ in range(2):
                if i < n:
                    out[i] = " "
                    i += 1
            continue
        if ch in "'\"`":
            quote = ch
            i += 1
            while i < n:
                if src[i] == "\\":
                    out[i] = " "
                    if i + 1 < n:
                        out[i + 1] = " "
                    i += 2
                    continue
                if src[i] == quote:
                    out[i] = " "
                    i += 1
                    break
                if src[i] != "\n":
                    out[i] = " "
                i += 1
            continue
        i += 1
    return "".join(out)


def _match_braces(blank: str, open_idx: int) -> int | None:
    """Index just past the `}` matching the `{` at `open_idx`, or None if unbalanced."""
    depth = 0
    for i in range(open_idx, len(blank)):
        if blank[i] == "{":
            depth += 1
        elif blank[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    return None


def _top_level_keys(blank_body: str) -> list[str]:
    """Keys written at depth 1 of one object literal (nested literals are a different boundary).

    `blank_body` starts at the `{` and ends just past its match. Nested literals are blanked out so
    a `{ options: { timeAlg: 1 } }` contributes `options`, not `timeAlg` — the inner object is the
    callee's business, and flattening the two would produce false "dead key" reports.
    """
    depth = 0
    buf: list[str] = []
    for ch in blank_body:
        if ch in "{[(":
            depth += 1
            if depth == 1:
                continue
        elif ch in "}])":
            depth -= 1
            if depth == 0:
                break
        buf.append(ch if depth == 1 else " ")
    keys: list[str] = []
    for m in _KEY_RE.finditer("{" + "".join(buf) + "}"):
        name = m.group(1) or m.group(2) or m.group(3)
        if name and name not in keys:
            keys.append(name)
    return keys


_IDENT_RE = re.compile(r"[A-Za-z_$][\w$]*")


def _local_literal_keys(blank: str, name: str) -> list[str]:
    """Keys of the most recent `const <name> = { … }` in this file, or [] if there is none."""
    m = None
    for candidate in re.finditer(_LOCAL_LITERAL_RE.format(name=re.escape(name)), blank):
        m = candidate
    if m is None:
        return []
    open_idx = blank.index("{", m.end() - 1)
    close = _match_braces(blank, open_idx)
    if close is None:
        return []
    return _top_level_keys(blank[open_idx:close])


def _match_parens(blank: str, open_idx: int) -> int | None:
    """Index just past the `)` matching the `(` at `open_idx`, or None if unbalanced."""
    depth = 0
    for i in range(open_idx, len(blank)):
        if blank[i] == "(":
            depth += 1
        elif blank[i] == ")":
            depth -= 1
            if depth == 0:
                return i + 1
    return None


def _imports(src: str) -> dict[str, str]:
    """local name -> vendor module path (repo-relative from horosa-core-js/src/tools/)."""
    mapping: dict[str, str] = {}
    for m in _IMPORT_RE.finditer(src):
        names, module = m.group(1), m.group(2)
        for part in names.split(","):
            part = part.strip()
            if not part:
                continue
            if " as " in part:
                _orig, _, local = part.partition(" as ")
                mapping[local.strip()] = module
            else:
                mapping[part] = module
    return mapping


def collect(tool_path: Path) -> list[dict[str, Any]]:
    src = tool_path.read_text(encoding="utf-8")
    blank = _strip_comments_and_strings(src)
    imported = _imports(src)
    sites: list[dict[str, Any]] = []
    for m in _CALL_HEAD_RE.finditer(blank):
        fn = m.group(1)
        if fn not in imported:
            continue
        args_end = _match_parens(blank, m.end() - 1)
        if args_end is None:
            continue
        # Walk the argument list at depth 1, recording each object-literal argument by position.
        i, arg_index, depth = m.end(), 0, 0
        while i < args_end - 1:
            ch = blank[i]
            if ch in "([":
                depth += 1
            elif ch in ")]":
                depth -= 1
            elif ch == "," and depth == 0:
                arg_index += 1
            elif ch not in " \t\n," and depth == 0 and blank[i:i + 1].isidentifier() and _IDENT_RE.match(blank, i):
                im = _IDENT_RE.match(blank, i)
                name = im.group(0)
                lit = _local_literal_keys(blank, name)
                if lit:
                    sites.append(
                        {
                            "callee": fn,
                            "module": imported[fn],
                            "line": src[: m.start()].count("\n") + 1,
                            "arg": arg_index,
                            "via_local": name,
                            "keys": sorted(lit),
                        }
                    )
                i = im.end()
                continue
            elif ch == "{" and depth == 0:
                close = _match_braces(blank, i)
                if close is None:
                    break
                keys = _top_level_keys(blank[i:close])
                if keys:
                    sites.append(
                        {
                            "callee": fn,
                            "module": imported[fn],
                            "line": src[: m.start()].count("\n") + 1,
                            "arg": arg_index,
                            "keys": sorted(keys),
                        }
                    )
                i = close
                continue
            i += 1
    return sites


def build() -> dict[str, Any]:
    tools: dict[str, Any] = {}
    for path in sorted(TOOLS_DIR.glob("*.js")):
        sites = collect(path)
        if sites:
            tools[path.name] = sites
    # 🔴 豁免块是**手写**的，重新生成必须原样带过去 —— 否则每次 regen 都会把它冲掉，
    # 而 regen 恰恰是修完调用点后的常规动作，等于豁免永远活不过一次修复。
    existing: dict[str, Any] = {}
    if CONTRACT.is_file():
        try:
            existing = json.loads(CONTRACT.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    exemptions = existing.get("exemptions")
    return {
        **({"exemptions": exemptions} if exemptions else {}),
        "_comment": (
            "Generated by scripts/gen_js_boundary_contracts.py. Each entry records the keys a "
            "src/tools/*.js call site hands a vendored engine. verify_js_boundary_contracts.py "
            "asserts every offered key appears in the callee module — the dead-key shape behind "
            "issue #15 (`hour` vs `time`) and tiebanFramework (`minute` vs `ke`)."
        ),
        "_regenerate": "uv run python scripts/gen_js_boundary_contracts.py",
        "tools": tools,
    }


def main() -> int:
    contract = build()
    CONTRACT.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sites = sum(len(v) for v in contract["tools"].values())
    keys = sum(len(s["keys"]) for v in contract["tools"].values() for s in v)
    print(
        f"wrote {CONTRACT.relative_to(PKG_ROOT)}: "
        f"{len(contract['tools'])} tool files, {sites} boundary call sites, {keys} offered keys"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
