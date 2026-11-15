"""技法登记普查（审计 A-1 第 0 期 / PF-21）：一个技法散在几十张表里，新增 / 改名时漏一张没人知道。

  uv run python scripts/technique_census.py            # 汇总：多少张表、每个技法在几张里
  uv run python scripts/technique_census.py chart      # 这个技法在哪些表里、不在哪些表里
  uv run python scripts/technique_census.py --write    # 重录 contracts/technique_census.json（有意的改动）
  uv run python scripts/technique_census.py --check    # 与契约逐技法比对（tests/test_technique_census.py 跑这个）

表 = 包内任一模块的模块级容器（dict 键 / set / frozenset / tuple / list），元素里技法注册名过半且至少 3 个。
运行期导入后取（静态扫描看不见派生出来的表）；只看「刚导入完」的状态——运行中才填的缓存（_VERIFIED_EXAMPLES 之类）随调用顺序变，
所以 --check 要在新进程里跑（测试用子进程）。不改任何运行时代码；第 1 期再把这些表改成从一份 TechniqueSpec 派生。
Stdlib + 本包。
"""
from __future__ import annotations

import importlib
import json
import pkgutil
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")

PKG_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = PKG_ROOT / "contracts" / "technique_census.json"
# 导入有副作用或只在特定平台可导入的模块不扫（入口脚本 / 平台专用）。
_SKIP_PREFIXES = ("horosa_skill.__main__",)


def _tool_names() -> set[str]:
    from horosa_skill.engine.registry import TOOL_DEFINITIONS

    return set(TOOL_DEFINITIONS)


def census() -> dict[str, list[str]]:
    """{表 id（模块:名字）: 其中的技法名（排序）}。"""
    import horosa_skill

    tools = _tool_names()
    tables: dict[str, list[str]] = {}
    owners: dict[int, str] = {}   # 同一个对象被别的模块 import 进来：只记第一次（字典序最小的模块）见到它的那个 id
    for info in pkgutil.walk_packages(horosa_skill.__path__, prefix="horosa_skill."):
        if info.name.startswith(_SKIP_PREFIXES):
            continue
        try:
            module = importlib.import_module(info.name)
        except Exception:  # noqa: BLE001 — 导入不了的模块（可选依赖缺失）不算表；普查不该因此崩
            continue
        for attr, value in vars(module).items():
            if attr.startswith("__") or not isinstance(value, (dict, set, frozenset, tuple, list)):
                continue
            items = list(value.keys()) if isinstance(value, dict) else list(value)
            names = [item for item in items if isinstance(item, str) and item in tools]
            if len(names) >= 3 and len(names) * 2 > len(items):
                table_id = f"{info.name.removeprefix('horosa_skill.')}:{attr}"
                if id(value) in owners:
                    continue
                owners[id(value)] = table_id
                tables[table_id] = sorted(set(names))
    return dict(sorted(tables.items()))


def per_technique(tables: dict[str, list[str]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {name: [] for name in sorted(_tool_names())}
    for table_id, members in tables.items():
        for name in members:
            out[name].append(table_id)
    return out


def main(argv: list[str]) -> int:
    tables = census()
    techniques = per_technique(tables)
    if "--write" in argv:
        CONTRACT.write_text(json.dumps({"_comment": __doc__.splitlines()[0], "tables": len(tables), "techniques": techniques},
                                       ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        print(f"technique census written: {len(tables)} tables, {len(techniques)} techniques")
        return 0
    if "--check" in argv:
        recorded = json.loads(CONTRACT.read_text(encoding="utf-8"))["techniques"]
        problems = []
        for name in sorted(set(recorded) | set(techniques)):
            before, after = set(recorded.get(name, [])), set(techniques.get(name, []))
            if before != after:
                problems.append(f"{name}: +{sorted(after - before)} -{sorted(before - after)}")
        if problems:
            print("technique census changed (re-record with --write if intended):\n  " + "\n  ".join(problems[:40]))
            return 1
        print(f"technique census OK: {len(tables)} tables, {len(techniques)} techniques")
        return 0
    names = [arg for arg in argv if not arg.startswith("-")]
    if names:
        for name in names:
            inside = techniques.get(name)
            if inside is None:
                print(f"{name}: not a registered technique")
                continue
            print(f"{name}: in {len(inside)} table(s)")
            for table_id in inside:
                print(f"  ✓ {table_id}")
            peers = sorted(t for t in tables if t not in inside)
            print(f"  not in {len(peers)} table(s) (most are feature subsets — check the ones a new technique of this family needs)")
        return 0
    counts = sorted(((len(v), k) for k, v in techniques.items()), reverse=True)
    print(f"{len(tables)} tables; techniques per table count: max {counts[0]}, min {counts[-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
