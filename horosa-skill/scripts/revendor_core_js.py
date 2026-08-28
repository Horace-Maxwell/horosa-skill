#!/usr/bin/env python
"""Re-vendor a 星阙 frontend JS file into `horosa-core-js/src/vendor/` with the headless transform.

The transform is the one AGENTS.md §5 spells out, applied mechanically so every re-vendor is identical
and reviewable:

1. sibling/relative imports get an explicit `.js` (Node ESM needs it; the browser bundler does not);
2. backend-only imports are dropped (`utils/request`, `{ServerRoot,ResultKey}`, `buildKentangEndpoint`)
   — Python does the fetching, the JS layer never speaks HTTP;
3. exported `fetch*Pan` network helpers are removed wholesale (same reason);
4. everything else — especially the `normalize*` overlays and every `build*SnapshotText` — is copied
   **verbatim**, because byte-identical formatting is the whole point of vendoring instead of porting.

Usage:  python scripts/revendor_core_js.py <upstream-src-root> <relative/path/File.js> [more...]
        (`--check` reports what would change without writing)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VENDOR_ROOT = REPO_ROOT / "horosa-skill/horosa-core-js/src/vendor"
MANIFEST = REPO_ROOT / "horosa-skill/contracts/vendor_manifest.json"

_DROP_IMPORT_PATTERNS = (
    re.compile(r"^import\s+request\s+from\s+['\"][^'\"]*utils/request['\"];?\s*$", re.M),
    re.compile(r"^import\s+\{[^}]*\b(?:ServerRoot|ResultKey)\b[^}]*\}\s+from\s+['\"][^'\"]+['\"];?\s*$", re.M),
    re.compile(r"^import\s+\{[^}]*buildKentangEndpoint[^}]*\}\s+from\s+['\"][^'\"]+['\"];?\s*$", re.M),
    # namespace 形式：`import * as Constants from './constants'`（其 ServerRoot 是后端地址）。
    # 具名形式已在上面覆盖，但上游 utils/*AiSnapshot.js 这一支用的是 namespace 写法。
    re.compile(r"^import\s+\*\s+as\s+Constants\s+from\s+['\"][^'\"]*constants['\"];?\s*$", re.M),
    re.compile(r"^import\s+\w+\s+from\s+['\"][^'\"]*utils/request['\"];?\s*$", re.M),
    re.compile(r"^import\s+\w+\s+from\s+['\"]\./request['\"];?\s*$", re.M),
    # `momentPipeline` 是纯网络编排模块（import request + services/astro + DateTime 组件），
    # 按 §5 归 Python；引用它的求根循环由 _strip_network_orchestrators 连带剥掉。
    re.compile(r"^import\s+\{[^}]*\}\s+from\s+['\"][^'\"]*momentPipeline['\"];?\s*$", re.M),
)
_RELATIVE_IMPORT = re.compile(r"(from\s+['\"])(\.[^'\"]*?)(['\"])")


def _strip_fetch_helpers(text: str) -> tuple[str, list[str]]:
    """Remove `export async function fetch*Pan(...) { … }` blocks by brace matching."""
    removed: list[str] = []
    # 命名放宽到任意导出的 `fetch*`：AGENTS §5 的契约是「Python 发请求，JS 层不说 HTTP」，
    # 按 `fetch` 前缀识别比维护一张函数名清单稳。此前只认 `fetch*Pan`，于是
    # `fetchBabylonEphemeris` / `fetchRiseSetAt` 漏网，vendored 模块带着 ServerRoot 引用不可加载。
    pattern = re.compile(r"^export\s+(?:async\s+)?function\s+(fetch\w+)\s*\(", re.M)
    while True:
        match = pattern.search(text)
        if not match:
            return text, removed
        start = match.start()
        brace = text.index("{", match.end() - 1)
        depth, index = 1, brace + 1
        while depth and index < len(text):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
            index += 1
        removed.append(match.group(1))
        text = text[:start] + text[index:].lstrip("\n")


def _strip_network_orchestrators(text: str, removed: list[str]) -> tuple[str, list[str]]:
    """剥掉引用了已删 `fetch*` 的导出 async 编排函数（`buildXForFields` 一类）。

    这些函数的职责就是「发几个请求再拼数据」，headless 侧由 Python 承担。留着它们不会在加载期报错
    （自由变量到调用期才解析），但会让 vendored 模块看起来还提供一个根本不能用的入口——比留个坏
    import 更隐蔽。按「引用了被删符号」判定，不写死函数名。
    """
    notes: list[str] = []
    if not removed:
        return text, notes
    while True:
        hit = None
        # 也认非导出的 `async function`：上游有「async function X(){} … export { X }」的写法
        # （vedicMundane.js 的 solveVedicSolarIngress），只认 `export async function` 会漏掉它，
        # 留下一个一调用就 ReferenceError 的导出入口。
        for match in re.finditer(r"^(?:export\s+)?async\s+function\s+(\w+)\s*\(", text, re.M):
            start = match.start()
            brace = text.index("{", match.end() - 1)
            depth, index = 1, brace + 1
            while depth and index < len(text):
                if text[index] == "{":
                    depth += 1
                elif text[index] == "}":
                    depth -= 1
                index += 1
            body = text[brace:index]
            if any(re.search(rf"\b{re.escape(name)}\b", body) for name in removed):
                hit = (match.group(1), start, index)
                break
        if not hit:
            return text, notes
        name, start, end = hit
        removed.append(name)
        notes.append(f"stripped network orchestrator {name}")
        text = text[:start] + text[end:].lstrip("\n")


_NAMED_IMPORT = re.compile(r"^import\s+\{\s*([^}]+?)\s*\}\s+from\s+['\"]([^'\"]+)['\"];?\s*$", re.M)


def _drop_orphaned_imports(text: str) -> tuple[str, list[str]]:
    """Remove named imports whose symbols are no longer referenced after the fetch strip.

    Stripping `fetch*Pan` orphans its network-layer helpers (e.g. `cachedKentangFetch` from
    `utils/kentangCache`). Leaving the import behind makes the module unloadable headless — the
    referenced file simply is not in the vendor tree. Keyed on *actual usage* rather than a filename
    denylist, so the next upstream helper is handled without editing this script.

    🔴 每删一条都必须**重新搜索**，不能先 materialize 一批 match 再拿旧偏移去切新字符串——删掉第一条
    之后 text 变短，后面那些 match.start()/end() 全部失效。实测后果不是「漏删」而是**毁文件**：
    两个孤儿 namespace import 会把
        import * as d3 from 'd3';\\nimport * as lodash from 'lodash';\\nexport function f(){…}
    切成  \\nimport * as lodash from 'urn 1; }  —— 整个模块体没了。具名分支同样的病，症状轻些
    （第 2 条起静默残留，留下 utils/kentangCache 这类不在 vendor 树里的 import → ERR_MODULE_NOT_FOUND）。
    """
    notes: list[str] = []

    def _drop_all(pattern: re.Pattern[str], is_orphan, describe) -> None:
        nonlocal text
        while True:
            for match in pattern.finditer(text):
                body = text[: match.start()] + text[match.end() :]
                if is_orphan(match, body):
                    text = body
                    notes.append(describe(match))
                    break  # 重新搜索：偏移量已失效
            else:
                return

    _drop_all(
        _NAMED_IMPORT,
        lambda m, body: (syms := [s.strip().split(" as ")[-1].strip() for s in m.group(1).split(",") if s.strip()])
        and not any(re.search(rf"\b{re.escape(sym)}\b", body) for sym in syms),
        lambda m: "dropped orphaned import {"
        + ", ".join(s.strip().split(" as ")[-1].strip() for s in m.group(1).split(",") if s.strip())
        + "}",
    )
    # namespace 形式 `import * as X from '…'` 同理。上游偶有**死 import**（ZiWeiHelper.js 引了 d3
    # 却一次没用），headless 侧 d3 不在依赖里 → 模块直接加载失败。按「实际是否被引用」判定，
    # 不写死包名黑名单。
    _drop_all(
        re.compile(r"^import\s+\*\s+as\s+(\w+)\s+from\s+['\"][^'\"]+['\"];?\s*$", re.M),
        lambda m, body: not re.search(rf"\b{re.escape(m.group(1))}\s*\.", body),
        lambda m: f"dropped orphaned namespace import {m.group(1)}",
    )
    return text, notes


_INLINE_REQUIRE = re.compile(
    r"^([ \t]*)const\s*\{\s*([^}]+?)\s*\}\s*=\s*require\(\s*['\"]([^'\"]+)['\"]\s*\);?[ \t]*\n",
    re.M,
)


def _rewrite_inline_requires(text: str) -> tuple[str, list[str]]:
    """把函数体内的惰性 `const {X} = require('…')` 改写成顶层静态 import。

    `horosa-core-js` 是 `"type": "module"`，ESM 下 `require` 根本没有定义 → 运行到那一行就
    `ReferenceError`。上游用惰性 require 是为了断模块环（如 `data/accidentalDignity` ↔
    `engine/conditions` 互引），但两处都只在**函数体内**调用符号，而 ESM 的 live binding 对
    这种「求值期不用、调用期才用」的循环本来就安全 —— 静态 import 是等价且可加载的。

    不处理这条的后果不是「少一段」，而是净回归：`horary/timing.js` 的 require 落在 `[应期方位]`
    —— 一个当前已经能用的段，重 vendor 会把它炸掉。
    """
    notes: list[str] = []
    imports: list[str] = []
    for match in list(_INLINE_REQUIRE.finditer(text)):
        symbols = match.group(2).strip()
        target = match.group(3)
        if not target.startswith("."):
            continue  # 第三方包（moment 之类）不在 vendor 闭包里，留给人工判断
        suffixed = target if target.endswith((".js", ".json", ".mjs")) else f"{target}.js"
        # 去重：上游偶有「顶层已静态 import 某符号，函数体内又惰性 require 同一符号」的写法
        # （astroClassicalDerived.js 的 SIGNS）。此时只删 require 行、不再造第二条 import——
        # 否则 `Identifier 'X' has already been declared`，整个模块图加载失败。
        symbol_names = [s.strip().split(" as ")[-1].strip() for s in symbols.split(",") if s.strip()]
        rest = text.replace(match.group(0), "", 1)
        already = all(
            re.search(rf"^import\s+(?:\{{[^}}]*\b{re.escape(name)}\b[^}}]*\}}|\*\s+as\s+{re.escape(name)}\b|{re.escape(name)}\b)[^\n]*from\s", rest, re.M)
            for name in symbol_names
        )
        text = rest
        if already:
            notes.append(f"require dropped (already imported): {{{symbols}}}")
            continue
        stmt = f"import {{ {symbols} }} from '{suffixed}';"
        # 同一文件里同一符号可能被惰性 require **多次**（topicModule.js 的 DIR_BY_ELEMENT ×2）——
        # 队列内也要去重，否则 hoist 出两条相同 import → `Identifier 'X' has already been declared`。
        queued = {n for s in imports for n in re.findall(r"\{\s*([^}]+?)\s*\}", s) for n in [x.strip().split(" as ")[-1].strip() for x in n.split(",")]}
        if stmt in imports or any(name in queued for name in symbol_names):
            notes.append(f"require dropped (queued dup): {{{symbols}}}")
            continue
        imports.append(stmt)
        notes.append(f"require→import {{{symbols}}} from {target}")
    # 第三种形态：**表达式内** `require('./x').prop`（既非顶层也非解构语句，直接嵌在表达式里——
    # ZiWeiHelper.js 的 `require('./ziweiOptions').ZWEngineOptions.kuiYue`）。语句形正则抓不到它，
    # ESM 下运行到就 ReferenceError。改写：hoist 成命名空间 import，表达式处换成别名。
    expr_targets: dict[str, str] = {}
    def _expr_alias(match: re.Match[str]) -> str:
        target = match.group(1)
        if not target.startswith("."):
            return match.group(0)  # 第三方包留给人工
        if target not in expr_targets:
            expr_targets[target] = f"__req{len(expr_targets)}"
        return expr_targets[target]
    text = re.sub(r"require\(\s*['\"]([^'\"]+)['\"]\s*\)", _expr_alias, text)
    for target, alias in expr_targets.items():
        suffixed = target if target.endswith((".js", ".json", ".mjs")) else f"{target}.js"
        imports.append(f"import * as {alias} from '{suffixed}';")
        notes.append(f"require-expr→namespace import {alias} ← {target}")
    if imports:
        # 插在最后一条**完整** import 语句之后；文件若无 import 则置顶。
        # 🔴 插入点必须按完整语句匹配（含多行 `import {\n …\n} from '…';` 形态）——按单行匹配时，
        # 多行块的首行 `import {` 也命中，「最后一条 import 之后」会落在块**中间**，把它劈成
        # 两截 → SyntaxError: Unexpected token '}'（lifespanEngine.js 实测踩到）。
        last = None
        for m in re.finditer(r"^import\b[^;'\"]*(?:['\"][^'\"]*['\"])?;?\s*?\n|^import\s*\{[^}]*\}\s*from\s*['\"][^'\"]+['\"];?\s*?\n|^import\b[\s\S]*?from\s*['\"][^'\"]+['\"];?\s*?\n", text, re.M):
            last = m
        block = "\n".join(imports) + "\n"
        text = (text[: last.end()] + block + text[last.end() :]) if last else block + text
    return text, notes


def _prune_default_export(text: str, removed: list[str]) -> tuple[str, list[str]]:
    """把已剥掉的符号从末尾的 `export default { … }` 聚合对象里摘掉。

    只删函数体不够：上游多数模块末尾有一行 `export default { A, B, C }` 汇总导出，其中若仍列着
    被剥掉的网络函数，模块**加载期**就 `ReferenceError`（本轮 solunar.js 踩到）——比留个坏 import
    更早炸，且报错信息只说「X is not defined」，不指向 vendor 流程。

    🔴 与 _drop_orphaned_imports 同一个坑：改一条就要重新搜索，否则第二条 `export { … };` 会拿失效
    偏移去切，产出 `export {export { q };` 这种语法错误（整个模块解析不了）。
    🔴 另一个坑：head 必须由**匹配到的是哪个 pattern** 决定，不能用 `"default" in match.group(0)`
    子串判断——名单里出现 `defaultRules` / `defaultOrb` 这类符号就会把具名导出清单翻成
    `export default { … }`，随后所有 `import { x } from …` 全报 does not provide an export named。
    """
    notes: list[str] = []
    if not removed:
        return text, notes
    removed_set = set(removed)
    for pattern, head in (
        (r"^export default \{([^}]*)\};?\s*$", "export default { "),
        (r"^export \{([^}]*)\};?\s*$", "export { "),
    ):
        compiled = re.compile(pattern, re.M)
        while True:
            for match in compiled.finditer(text):
                names = [s.strip() for s in match.group(1).split(",") if s.strip()]
                kept = [n for n in names if n.split(":")[0].split(" as ")[0].strip() not in removed_set]
                if len(kept) == len(names):
                    continue
                notes.append(f"pruned export list ×{len(names) - len(kept)}")
                replacement = (head + ", ".join(kept) + " };") if kept else ""
                text = text[: match.start()] + replacement + text[match.end():]
                break  # 重新搜索：偏移量已失效
            else:
                break
    return text, notes


def transform(text: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    text, require_notes = _rewrite_inline_requires(text)
    notes.extend(require_notes)
    dropped_symbols: list[str] = []
    for pattern in _DROP_IMPORT_PATTERNS:
        # 先收走该 import 带进来的具名符号：它们是后端层的东西，任何仍在引用它们的导出 async
        # 编排函数（求根循环一类）也该一并剥掉，否则留下的入口在 headless 下一调用就 ReferenceError。
        for match in pattern.finditer(text):
            inner = re.search(r"\{([^}]*)\}", match.group(0))
            if inner:
                dropped_symbols += [s.strip().split(" as ")[-1].strip() for s in inner.group(1).split(",") if s.strip()]
        text, count = pattern.subn("", text)
        if count:
            notes.append(f"dropped {count} backend import(s)")
    text, removed = _strip_fetch_helpers(text)
    removed = removed + dropped_symbols
    if removed:
        notes.append("stripped " + ", ".join(removed))
    text, orch_notes = _strip_network_orchestrators(text, removed)
    notes.extend(orch_notes)
    text, prune_notes = _prune_default_export(text, removed)
    notes.extend(prune_notes)
    text, orphan_notes = _drop_orphaned_imports(text)
    notes.extend(orphan_notes)

    def add_suffix(match: re.Match[str]) -> str:
        target = match.group(2)
        if target.endswith((".js", ".json", ".mjs")):
            return match.group(0)
        return f"{match.group(1)}{target}.js{match.group(3)}"

    text, count = _RELATIVE_IMPORT.subn(add_suffix, text)
    if count:
        notes.append(f"suffixed {count} relative import(s)")

    # 原生 Node ESM 要求 JSON import 显式带 `with { type: 'json' }`；bundler 不需要，所以上游没有。
    # 漏了它模块直接加载失败（"needs an import attribute of type: json"）——AGENTS §5 的老坑，机械化掉。
    text, json_count = re.subn(
        r"(^import\s+[^;\n]*?from\s+['\"][^'\"]+\.json['\"])(\s*;)",
        r"\1 with { type: 'json' }\2",
        text,
        flags=re.M,
    )
    if json_count:
        notes.append(f"added json import attribute ×{json_count}")

    # 同一条规则的**动态** import 形态：`import('./x.json')` 在原生 Node ESM 同样要显式属性。
    # 上游常带 `/* webpackChunkName: … */` 注释（纯 bundler 提示），一并去掉。
    # 静态形态的正则要求同行以 `;` 收尾，天然覆盖不到这里 —— 漏了它模块**能加载**（因为是懒加载），
    # 只在真正调用那条路径时才炸，selfcheck 才抓得到，loadcheck 抓不到（zhengchuan 条文库正是此例）。
    text, dyn_count = re.subn(
        r"import\(\s*(?:/\*.*?\*/\s*)?(['\"][^'\"]+\.json['\"])\s*\)",
        r"import(\1, { with: { type: 'json' } })",
        text,
        flags=re.S,
    )
    if dyn_count:
        notes.append(f"added dynamic json import attribute ×{dyn_count}")
    return text, notes


def _reexport_required(text: str, target: Path) -> tuple[str, list[str]]:
    """把 skill 侧 `tools/*.js` 需要、而上游是模块私有的函数补上 `export`。

    上游把 `normalizeBackendPan` 一类叠加函数留作私有（组件内部自用），但 skill 的 headless 工具层
    正是靠它把 ken 响应叠到本地脚手架上。之前的 vendored 副本是人手加的 export，一次全文件重 vendor
    就会把它抹掉，症状是 `SyntaxError: does not provide an export named …`（本轮踩到）。
    按「谁在 import 它」反查，自动补 export——不写死函数名清单。
    """
    notes: list[str] = []
    tools_dir = VENDOR_ROOT.parent / "tools"
    needed: set[str] = set()
    stem = target.stem
    for tool in tools_dir.glob("*.js") if tools_dir.is_dir() else []:
        for match in re.finditer(r"import\s+\{([^}]+)\}\s+from\s+['\"][^'\"]*" + re.escape(stem) + r"\.js['\"]", tool.read_text(encoding="utf-8")):
            needed |= {s.strip().split(" as ")[0].strip() for s in match.group(1).split(",") if s.strip()}
    # 上游也可能用**尾部导出清单** `export { a, b };` 而不是 `export function a`。只认前者会把
    # 已导出的符号再加一次 `export`，产出 "Duplicate export of 'x'" —— 该模块整个加载不了。
    # （上游 v3.7.x 给 baziLunarLocal 的 buildFlowDays/buildFlowHours 补了尾部清单，正好踩中。）
    exported_by_list: set[str] = set()
    for block in re.findall(r"^export\s*\{([^}]*)\}\s*;", text, re.M):
        exported_by_list |= {s.strip().split(" as ")[0].strip() for s in block.split(",") if s.strip()}
    for name in sorted(needed):
        if name in exported_by_list:
            continue
        if re.search(rf"^export\s+(?:async\s+)?function\s+{re.escape(name)}\b", text, re.M):
            continue
        pattern = re.compile(rf"^(function\s+{re.escape(name)}\b)", re.M)
        if pattern.search(text):
            text = pattern.sub(r"export \1", text, count=1)
            notes.append(f"re-exported {name} (skill tools import it; upstream keeps it module-private)")
    return text, notes


def _relocate_imports(text: str, target: Path) -> tuple[str, list[str]]:
    """把上游 src 布局的相对 import 重指到 vendor 树里该文件的真实位置。

    上游是 `astrostudyui/src/{components,utils,constants}/…`，vendor 树按技法分目录
    （`vendor/bazi/baziLunarLocal.js` 等），所以 `../../utils/baziLunarLocal.js` 在这里解析不到。
    按 basename 在 vendor 树里找唯一匹配后重写；找不到就**报出来**而不是留个坏 import 让模块加载失败
    ——那正是「load 过≠真盘不崩」之前的一步，必须显式暴露给人决定是补 vendor 还是写 shim。
    """
    notes: list[str] = []
    index: dict[str, list[Path]] = {}
    for path in VENDOR_ROOT.rglob("*.js"):
        index.setdefault(path.name, []).append(path)
    # 少数上游模块在本仓不落 vendor 树，而是长在 core-js 自己的 `src/constants`、`src/shared` 下
    # （如 AstroText.js / AstroConst.js —— 它们是 skill 自己也要用的共享常量）。搜索范围要含这两处，
    # 否则 `../../constants/AstroText` 永远 UNRESOLVED，人只能一次次手工改路径。
    for sibling in ("constants", "shared"):
        sibling_dir = VENDOR_ROOT.parent / sibling
        if sibling_dir.is_dir():
            for path in sibling_dir.rglob("*.js"):
                index.setdefault(path.name, []).append(path)

    def fix(match: re.Match[str]) -> str:
        rel = match.group(2)
        resolved = (target.parent / rel).resolve()
        if resolved.exists():
            return match.group(0)
        candidates = index.get(Path(rel).name, [])
        if len(candidates) == 1:
            new_rel = os.path.relpath(candidates[0], target.parent)
            if not new_rel.startswith("."):
                new_rel = f"./{new_rel}"
            notes.append(f"relocated {rel} → {new_rel}")
            return f"{match.group(1)}{new_rel}{match.group(3)}"
        notes.append(f"⚠ UNRESOLVED import {rel} ({len(candidates)} candidates) — vendor it or add a shim")
        return match.group(0)

    return _RELATIVE_IMPORT.sub(fix, text), notes


# --------------------------------------------------------------------------------------------
# Manifest mode
#
# The positional form below infers the vendor destination from the upstream parent directory name.
# That inference is WRONG for most of this tree — `utils/balbillus.js` lands in `vendor/astroextra/`,
# `components/gua/data/*.js` in `vendor/data/`, and so on — so driving it over the existing tree
# forks duplicate parallel copies (`vendor/utils/balbillus.js` beside the real one), with relocate
# then pointing imports at the stale copy. The manifest carries both sides explicitly, which is what
# makes "which files still need re-vendoring?" a mechanical `--check` answer instead of archaeology.
#
# modes:
#   verbatim  — pipeline output (+ declared deviations) must equal the vendored file
#   curated   — never auto-vendored (deliberate subset/shim); every name in `extracts` must still be
#               a top-level upstream export, which is what catches an upstream rename turning a
#               hand-extracted constant into a silent `undefined`
#   bespoke   — skill-authored, no upstream counterpart; asserts none appears, so a file that BECOMES
#               vendorable upstream is loud instead of sitting in the "reported, not failed" bucket
#
# deviations (applied after the transform pipeline, in order):
#   {"kind": "import_redirect", "specifier": "...", "to": "..."}  — pin a specifier relocate mis-picks
#   {"kind": "stub_import", "specifier": "...", "stub": "..."}    — replace a draw-only/browser import
# --------------------------------------------------------------------------------------------

_IMPORT_FROM = r"(from\s+['\"]){spec}(['\"])"
_IMPORT_STMT = r"^import\s+[^;\n]*?from\s+['\"]{spec}['\"]\s*;?\s*$"


def load_manifest() -> dict:
    if not MANIFEST.is_file():
        raise SystemExit(f"vendor manifest not found: {MANIFEST} (run --bootstrap-manifest once)")
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]


def apply_deviations(text: str, deviations: list[dict]) -> tuple[str, list[str]]:
    notes: list[str] = []
    for dev in deviations or []:
        kind, spec = dev.get("kind"), dev.get("specifier", "")
        if kind == "import_redirect":
            pattern = re.compile(_IMPORT_FROM.format(spec=re.escape(spec)))
            text, n = pattern.subn(lambda m: f"{m.group(1)}{dev['to']}{m.group(2)}", text)
            if not n:
                notes.append(f"⚠ import_redirect specifier not found: {spec}")
            else:
                notes.append(f"redirected {spec} → {dev['to']}")
        elif kind == "stub_import":
            pattern = re.compile(_IMPORT_STMT.format(spec=re.escape(spec)), re.M)
            # lambda 而非字符串模板：stub 是 JS，里面出现 `\1` 会被当分组回填、`\c` 直接抛
            # re.error 把整轮 re-vendor 打死。JS stub 里带正则字面量或转义引号是很正常的事。
            stub = dev["stub"].rstrip("\n")
            text, n = pattern.subn(lambda _m: stub, text)
            if not n:
                notes.append(f"⚠ stub_import specifier not found: {spec}")
            else:
                notes.append(f"stubbed {spec}")
        else:
            notes.append(f"⚠ unknown deviation kind: {kind}")
    return text, notes


def _top_level_exports(text: str) -> set[str]:
    names: set[str] = set()
    for match in re.finditer(r"^export\s+(?:async\s+)?(?:const|let|var|function|class)\s+([A-Za-z_$][\w$]*)", text, re.M):
        names.add(match.group(1))
    return names


def render_one(upstream_src: Path, rel_upstream: str, target: Path, deviations: list[dict]) -> tuple[str, list[str]]:
    source = upstream_src / rel_upstream
    if not source.is_file():
        raise SystemExit(f"upstream file not found: {source}")
    text, notes = transform(source.read_text(encoding="utf-8"))
    text, more = _reexport_required(text, target)
    notes.extend(more)
    # Deviations run BEFORE relocate, not after: relocate rewrites specifiers by basename, so a
    # post-relocate redirect would be looking for a specifier that no longer exists, and a stubbed
    # import would already have been reported UNRESOLVED. Running first makes both authoritative —
    # a redirected path is resolvable so relocate leaves it alone, and a stubbed import is gone.
    text, more = apply_deviations(text, deviations)
    notes.extend(more)
    text, more = _relocate_imports(text, target)
    notes.extend(more)
    return text, notes


def run_manifest(upstream_src: Path, only: str | None, check: bool) -> int:
    files = load_manifest()
    problems = 0
    stats = {"unchanged": 0, "updated": 0, "curated": 0, "bespoke": 0}
    upstream_names = {p.name for p in upstream_src.rglob("*.js")}

    for vendor_rel in sorted(files):
        if only and not vendor_rel.startswith(only):
            continue
        entry = files[vendor_rel]
        mode = entry.get("mode")
        target = VENDOR_ROOT / vendor_rel

        if mode == "bespoke":
            stats["bespoke"] += 1
            if Path(vendor_rel).name in upstream_names:
                problems += 1
                print(f"{vendor_rel}: BESPOKE but upstream now ships a file of that name — reclassify")
            continue

        if mode == "curated":
            stats["curated"] += 1
            source = upstream_src / entry["upstream"]
            if not source.is_file():
                problems += 1
                print(f"{vendor_rel}: CURATED but upstream source is gone ({entry['upstream']})")
                continue
            upstream_exports = _top_level_exports(source.read_text(encoding="utf-8"))
            lost = sorted(set(entry.get("extracts") or []) - upstream_exports)
            if lost:
                problems += 1
                print(
                    f"{vendor_rel}: CURATED — {len(lost)} extracted name(s) no longer exported upstream: "
                    f"{', '.join(lost)} (a renamed constant becomes a silent `undefined` key)"
                )
            continue

        if mode != "verbatim":
            problems += 1
            print(f"{vendor_rel}: NEEDS-REVIEW (mode={mode!r}) — classify it before this batch can go green")
            continue

        new_text, notes = render_one(upstream_src, entry["upstream"], target, entry.get("deviations") or [])
        old_text = target.read_text(encoding="utf-8") if target.is_file() else ""
        unresolved = [n for n in notes if n.startswith("⚠")]
        if unresolved:
            problems += 1
            print(f"{vendor_rel}: {'; '.join(unresolved)}")
        if old_text == new_text:
            stats["unchanged"] += 1
            continue
        stats["updated"] += 1
        delta = len(new_text.splitlines()) - len(old_text.splitlines())
        print(f"{vendor_rel}: {'would update' if check else 'updated'} ({delta:+d} lines) [{'; '.join(notes) or 'verbatim'}]")
        if check:
            problems += 1
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(new_text, encoding="utf-8")

    summary = ", ".join(f"{k}={v}" for k, v in stats.items())
    print(f"\nrevendor-manifest: {'FAIL' if problems else 'ok'} ({summary}; {problems} need attention)")
    return 1 if problems else 0


def manifest_drift(upstream_src: Path) -> list[str]:
    """Files whose vendored copy no longer equals the manifest-declared render of upstream.

    This is the precise oracle for "what still needs re-vendoring" — unlike a raw sha256 against
    untransformed upstream, which flags every file that legitimately carries the headless transform.
    """
    out: list[str] = []
    for vendor_rel, entry in sorted(load_manifest().items()):
        if entry.get("mode") != "verbatim":
            continue
        target = VENDOR_ROOT / vendor_rel
        try:
            new_text, notes = render_one(upstream_src, entry["upstream"], target, entry.get("deviations") or [])
        except SystemExit as exc:
            out.append(f"{vendor_rel}: {exc}")
            continue
        if any(n.startswith("⚠") for n in notes):
            out.append(f"{vendor_rel}: {'; '.join(n for n in notes if n.startswith('⚠'))}")
        elif not target.is_file() or target.read_text(encoding="utf-8") != new_text:
            out.append(vendor_rel)
    return out


def bootstrap_manifest(upstream_src: Path) -> None:
    """Generate the manifest from the current tree: clean files become `verbatim`, unmatched become
    `bespoke`, and everything the pipeline would change becomes `needs-review` — i.e. the worklist."""
    index: dict[str, list[Path]] = {}
    for path in upstream_src.rglob("*.js"):
        index.setdefault(path.name, []).append(path)

    files: dict[str, dict] = {}
    for target in sorted(VENDOR_ROOT.rglob("*.js")):
        vendor_rel = target.relative_to(VENDOR_ROOT).as_posix()
        candidates = index.get(target.name, [])
        if not candidates:
            files[vendor_rel] = {"mode": "bespoke", "why": "no upstream file of this name (skill-authored)"}
            continue
        if len(candidates) > 1:  # disambiguate by longest shared trailing path
            def tail(path: Path) -> int:
                a, b = vendor_rel.split("/"), path.relative_to(upstream_src).as_posix().split("/")
                k = 0
                while k < min(len(a), len(b)) and a[-1 - k] == b[-1 - k]:
                    k += 1
                return k

            candidates = sorted(candidates, key=tail, reverse=True)
        rel_upstream = candidates[0].relative_to(upstream_src).as_posix()
        new_text, notes = render_one(upstream_src, rel_upstream, target, [])
        if new_text == target.read_text(encoding="utf-8"):
            files[vendor_rel] = {"upstream": rel_upstream, "mode": "verbatim", "deviations": []}
        else:
            files[vendor_rel] = {
                "upstream": rel_upstream,
                "mode": "needs-review",
                "why": "; ".join(notes) or "body drift",
            }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(
        json.dumps(
            {
                "_comment": (
                    "vendor 树的唯一驱动清单：显式 upstream↔vendor 路径对 + 声明式偏离。"
                    "revendor_core_js.py 的路径推断对本树是错的（会分叉出重复树），故一律用 --from-manifest。"
                ),
                "_modes": {
                    "verbatim": "流水线输出（含 deviations）必须与 vendored 文件逐字相同",
                    "curated": "蓄意子集/shim，永不自动 vendor；断言 extracts 里每个名字仍是上游顶层 export",
                    "bespoke": "skill 自写、上游无对应文件；断言上游确实没有同名文件",
                    "needs-review": "有真实漂移，待人工分类为上面三种之一（这就是 re-vendor 工单）",
                },
                "files": files,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    counts: dict[str, int] = {}
    for entry in files.values():
        counts[entry["mode"]] = counts.get(entry["mode"], 0) + 1
    print(f"bootstrapped {MANIFEST.relative_to(REPO_ROOT)}: {counts}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("upstream_src", type=Path, help="upstream astrostudyui/src root")
    parser.add_argument("files", nargs="*", help="paths relative to the upstream src root")
    parser.add_argument("--vendor-subdir", default=None, help="override the vendor destination subdir")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--from-manifest", action="store_true", help="drive every file in contracts/vendor_manifest.json")
    parser.add_argument("--only", default=None, help="with --from-manifest: restrict to vendor paths under this prefix")
    parser.add_argument("--bootstrap-manifest", action="store_true", help="(re)generate the manifest from the current tree")
    args = parser.parse_args()

    if args.bootstrap_manifest:
        bootstrap_manifest(args.upstream_src)
        return
    if args.from_manifest:
        raise SystemExit(run_manifest(args.upstream_src, args.only, args.check))
    if not args.files:
        parser.error("give files to vendor, or use --from-manifest / --bootstrap-manifest")

    for rel in args.files:
        source = args.upstream_src / rel
        if not source.is_file():
            raise SystemExit(f"upstream file not found: {source}")
        # 落点默认取上游父目录的**末段**(vendor 树是扁平化的),但当完整相对父路径在 vendor 里已存在时
        # 必须用它——否则 `divination/data/x.js` 会新建一棵 `vendor/data/`,与既有 `vendor/divination/data/`
        # 形成同名重复树,后续 relocate 还会把 import 指回旧树,同一模块两份、改一份不生效。
        nested = Path(rel).parent
        if args.vendor_subdir:
            subdir = Path(args.vendor_subdir)
        elif (VENDOR_ROOT / nested).is_dir():
            subdir = nested
        else:
            subdir = Path(nested.name)
        target = VENDOR_ROOT / subdir / Path(rel).name
        new_text, notes = transform(source.read_text(encoding="utf-8"))
        new_text, export_notes = _reexport_required(new_text, target)
        notes.extend(export_notes)
        new_text, reloc_notes = _relocate_imports(new_text, target)
        notes.extend(reloc_notes)
        old_text = target.read_text(encoding="utf-8") if target.is_file() else ""
        status = "unchanged" if old_text == new_text else ("new" if not old_text else "updated")
        delta = len(new_text.splitlines()) - len(old_text.splitlines())
        print(f"{rel} → {target.relative_to(REPO_ROOT)}: {status} ({delta:+d} lines) [{'; '.join(notes) or 'verbatim'}]")
        if not args.check and status != "unchanged":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(new_text, encoding="utf-8")


if __name__ == "__main__":
    main()
