#!/usr/bin/env python3
"""Guard the `src/tools/*.js` → `src/vendor/**` boundary: no offered key may be one the engine
never reads, and no mirrored pillar-key array may drift from the engine's own declaration.

Why this exists (issue #15's full evidence chain): `horosa-core-js/src/tools/**` was the only part
of the JS tree with **no static guard at all** — `loadcheck.mjs` walks `src/vendor/**`, the vendor
manifest tracks engine files not their callers, `selfcheck.mjs` had zero coverage of the affected
tools, and the offline fakes hand-wrote their answers so the engines never ran. Six layers green,
and 八字格局 still shipped 正官格 where the truth was 正财格, because the caller wrote `hour:` and
all three engines read `time`. The same shape shipped again in tiebanFramework (`minute` offered,
`ke` read → 96 局 collapsed to 12) and canping (`lunarMonth`/`lunarDay` in hand, never forwarded →
起运岁 stuck at 1). Every one is: **caller offers a key the callee never reads**, the callee's
destructuring default fills in, output stays plausible, presence-level assertions stay green.

Two checks:

1. **Dead-key** — every key in `contracts/js_boundary_contracts.json` must appear somewhere in the
   callee module's text. A weak oracle (appearing ≠ being read), but exact for the shape that has
   actually shipped bugs, and it cannot produce false greens on a genuinely absent name.
2. **Anchored constants** — where a tool mirrors an engine's pillar/position key array
   (`['year','month','day','time']` and friends), that array must equal the engine's own
   declaration. N-way agreement between callers is not evidence; only the source is.
   (Same principle as `verify_builder_parity.py::SHARED_MANIFEST_CONSTANTS`.)

Exemptions live in the contract's `exemptions` block, each with a reason, and are ratcheted: the
verifier fails if an exemption is no longer needed, so the list can only shrink.

Stdlib-only, exits non-zero with an explanation. Wired into CI.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
PKG_ROOT = SCRIPTS.parent
CORE_JS = PKG_ROOT / "horosa-core-js"
TOOLS_DIR = CORE_JS / "src" / "tools"
CONTRACT = PKG_ROOT / "contracts" / "js_boundary_contracts.json"

# 锚定向：调用方镜像的常量数组 -> 引擎自己的声明。左边是 tools 里出现的字面量，右边是引擎文件
# 与它在那里的声明名。`hour`/`time` 之争就发生在这个数组上，所以它必须锚到源头而不是互相印证。
ANCHORED_KEY_ARRAYS = {
    "src/vendor/bazi/baziWuxing.js": {
        "literal": ["year", "month", "day", "time"],
        "why": "四柱键序：baziWuxing / baziMangPai / baziGejuYongShen 三个引擎一律按它取柱；"
        "写成 hour 会让时柱静默缺席（issue #15）。",
    },
}


def _fail(errors: list[str]) -> int:
    print(
        "js-boundary-contract guard FAILED — a tool hands an engine keys it does not read "
        "(the issue #15 shape):",
        file=sys.stderr,
    )
    for err in errors:
        print(f"  - {err}", file=sys.stderr)
    print(
        "\nFix the call site (or, if the key is genuinely optional/aliased, add an exemption with a "
        "reason to contracts/js_boundary_contracts.json), then re-run "
        "`uv run python scripts/gen_js_boundary_contracts.py`.",
        file=sys.stderr,
    )
    return 1


_REL_IMPORT_RE = re.compile(r"from\s*'(\.[^']+\.js)'")


def _module_text(module_rel: str) -> str | None:
    """The callee module's text **plus one hop of its own relative imports**.

    Engines routinely forward the whole params object on: `personBazi(params)` immediately calls
    `buildLocalBaziResult(params)` in another module, so `date`/`time` are alive even though
    `riziEngine.js` never spells them. Searching the callee alone reports those as dead keys.
    One hop is deliberate — it removes the forwarding false-positives while a name that appears
    in neither the callee nor its direct dependencies is still definitively unread.
    """
    path = (TOOLS_DIR / module_rel).resolve()
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    parts = [text]
    for m in _REL_IMPORT_RE.finditer(text):
        dep = (path.parent / m.group(1)).resolve()
        if dep.is_file():
            parts.append(dep.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _check_dead_keys(contract: dict, errors: list[str]) -> set[tuple[str, int, str]]:
    """Returns the set of (tool, line, key) that were exempted and turned out to be alive."""
    exemptions = {
        (e["tool"], e["key"]): e for e in contract.get("exemptions", {}).get("dead_key", [])
    }
    stale: set[tuple[str, int, str]] = set()
    cache: dict[str, str | None] = {}
    for tool, sites in sorted(contract.get("tools", {}).items()):
        for site in sites:
            module = site["module"]
            if module not in cache:
                cache[module] = _module_text(module)
            text = cache[module]
            if text is None:
                errors.append(f"{tool}:{site['line']} imports {module}, which does not exist")
                continue
            for key in site["keys"]:
                # 引擎里出现即算「读得到」：解构 `{ key }`、`opts.key`、`params['key']` 都覆盖。
                present = re.search(rf"(?<![\w$]){re.escape(key)}(?![\w$])", text) is not None
                exempt = exemptions.get((tool, key))
                if present and exempt:
                    stale.add((tool, site["line"], key))
                elif not present and not exempt:
                    errors.append(
                        f"{tool}:{site['line']} → {site['callee']}() offers `{key}`, but "
                        f"{module} never mentions it (dead key: the engine will use its default "
                        f"and the output will still look plausible)"
                    )
    return stale


def _check_anchored_arrays(errors: list[str]) -> None:
    for module_rel, spec in ANCHORED_KEY_ARRAYS.items():
        engine = CORE_JS / module_rel
        if not engine.is_file():
            errors.append(f"anchored-array source {module_rel} is missing")
            continue
        text = engine.read_text(encoding="utf-8")
        literal = spec["literal"]
        # 引擎必须逐个声明这些键（顺序无关，缺一即算漂移）。
        missing = [k for k in literal if f"'{k}'" not in text and f'"{k}"' not in text and f".{k}" not in text]
        if missing:
            errors.append(
                f"{module_rel} no longer declares {missing} — the mirrored key array in "
                f"src/tools/ would now be anchored to nothing ({spec['why']})"
            )
        # 调用方那份镜像必须与引擎一致。
        for tool in sorted(TOOLS_DIR.glob("*.js")):
            src = tool.read_text(encoding="utf-8")
            for m in re.finditer(r"\[\s*((?:'[\w$]+'\s*,\s*)+'[\w$]+')\s*\]", src):
                found = [p.strip().strip("'") for p in m.group(1).split(",")]
                if set(found) & set(literal) and set(found) != set(literal):
                    errors.append(
                        f"{tool.name} mirrors a pillar-key array {found} that overlaps but does not "
                        f"equal the engine's {literal} — anchor it to {module_rel} ({spec['why']})"
                    )


def main() -> int:
    if not CONTRACT.is_file():
        print(
            f"missing {CONTRACT.relative_to(PKG_ROOT)} — run "
            "`uv run python scripts/gen_js_boundary_contracts.py`",
            file=sys.stderr,
        )
        return 1
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    errors: list[str] = []
    stale = _check_dead_keys(contract, errors)
    _check_anchored_arrays(errors)

    if stale:
        # 棘轮：豁免只减不增。还清了要响，否则豁免集会变成谁也不敢动的化石。
        listing = ", ".join(f"{t}:{k}" for t, _line, k in sorted(stale))
        errors.append(
            f"these dead-key exemptions are no longer needed ({listing}) — the engine now reads "
            "them. Delete the exemption entries; a stale exemption hides the next real drift."
        )

    if errors:
        return _fail(errors)

    sites = sum(len(v) for v in contract.get("tools", {}).values())
    keys = sum(len(s["keys"]) for v in contract.get("tools", {}).values() for s in v)
    exempt = len(contract.get("exemptions", {}).get("dead_key", []))
    print(
        f"js-boundary-contract OK: {keys} offered keys across {sites} call sites all reach an "
        f"engine that mentions them ({exempt} documented exemption(s)); mirrored pillar-key arrays "
        f"match their engine declarations."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
