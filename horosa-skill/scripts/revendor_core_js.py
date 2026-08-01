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
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VENDOR_ROOT = REPO_ROOT / "horosa-skill/horosa-core-js/src/vendor"

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
        for match in re.finditer(r"^export\s+async\s+function\s+(\w+)\s*\(", text, re.M):
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
    """
    notes: list[str] = []
    for match in list(_NAMED_IMPORT.finditer(text)):
        symbols = [s.strip().split(" as ")[-1].strip() for s in match.group(1).split(",") if s.strip()]
        body = text[: match.start()] + text[match.end() :]
        if symbols and not any(re.search(rf"\b{re.escape(sym)}\b", body) for sym in symbols):
            text = body
            notes.append(f"dropped orphaned import {{{', '.join(symbols)}}}")
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
        imports.append(f"import {{ {symbols} }} from '{suffixed}';")
        text = text.replace(match.group(0), "", 1)
        notes.append(f"require→import {{{symbols}}} from {target}")
    if imports:
        # 插在最后一条既有 import 之后；文件若无 import 则置顶。
        last = None
        for m in re.finditer(r"^import\s[^\n]*\n", text, re.M):
            last = m
        block = "\n".join(imports) + "\n"
        text = (text[: last.end()] + block + text[last.end() :]) if last else block + text
    return text, notes


def _prune_default_export(text: str, removed: list[str]) -> tuple[str, list[str]]:
    """把已剥掉的符号从末尾的 `export default { … }` 聚合对象里摘掉。

    只删函数体不够：上游多数模块末尾有一行 `export default { A, B, C }` 汇总导出，其中若仍列着
    被剥掉的网络函数，模块**加载期**就 `ReferenceError`（本轮 solunar.js 踩到）——比留个坏 import
    更早炸，且报错信息只说「X is not defined」，不指向 vendor 流程。
    """
    notes: list[str] = []
    if not removed:
        return text, notes
    match = re.search(r"^export default \{([^}]*)\};?\s*$", text, re.M)
    if not match:
        return text, notes
    names = [s.strip() for s in match.group(1).split(",") if s.strip()]
    kept = [n for n in names if n.split(":")[0].strip() not in set(removed)]
    if len(kept) == len(names):
        return text, notes
    notes.append(f"pruned default export ×{len(names) - len(kept)}")
    replacement = "export default { " + ", ".join(kept) + " };"
    return text[: match.start()] + replacement + text[match.end():], notes


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
    for name in sorted(needed):
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("upstream_src", type=Path, help="upstream astrostudyui/src root")
    parser.add_argument("files", nargs="+", help="paths relative to the upstream src root")
    parser.add_argument("--vendor-subdir", default=None, help="override the vendor destination subdir")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

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
