#!/usr/bin/env python
"""算源声明守卫 —— `contracts/technique_provenance.json` 必须覆盖每个注册工具，且与源码一致。

为什么需要它：AGENTS §4 的「工具算源普查」一直是**散文**。代码里唯一能机读的算源线索是
`ToolDefinition.execution`（`local`/`remote`），而它**说明不了算源**——`qimen` 是 `execution="local"`
却整盘由 ken 后端算。技法依据卡/报告要如实回答「这一段是谁算的」，就必须有一份可断言的声明；
否则那张卡只是把 `execution` 换了个说法印出来，会**系统性说错**。

三条断言，都能做真：

1. **覆盖率**：声明键集 == `TOOL_DEFINITIONS` 键集。新增技法不声明算源即红——这补上了 §5 布线清单
   一直缺的一环（新技法过去只被要求进 schema/registry/router/preset/guidance，算源无人过问）。
2. **ken 一致性**：声明 `ken_backed` 的工具，其 runner 必须真的调过 `_require_ken_pan`；反过来，
   调了 `_require_ken_pan` 的也必须声明成 `ken_backed`。ken 端点失败也回 HTTP 200（§4），
   这条守卫是「谁必须有那道断言」的登记表。
3. **端点登记**：声明里出现的 chart 服务端点必须在 `service._PYTHON_CHART_ENDPOINTS` 里。
   漏登记会让请求落到 Java 通路（§4 端点注册法则）。

刻意**不**断言 endpoints 与 AST 扫描完全相等：神数族的 `/{technique}/pan` 是按技法拼的，
composite 型还会按分支打不同端点——把「扫得出来的」当成「全部」会得到一条恒红的守卫，
而恒红的守卫等于没有守卫。
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = PKG_ROOT / "contracts" / "technique_provenance.json"
SERVICE = PKG_ROOT / "src" / "horosa_skill" / "service.py"


def _load_tools() -> set[str]:
    sys.path.insert(0, str(PKG_ROOT / "src"))
    from horosa_skill.engine.registry import TOOL_DEFINITIONS

    return set(TOOL_DEFINITIONS)


def _chart_endpoints() -> set[str]:
    sys.path.insert(0, str(PKG_ROOT / "src"))
    from horosa_skill.service import _PYTHON_CHART_ENDPOINTS

    return set(_PYTHON_CHART_ENDPOINTS)


def runners_calling_require_ken_pan() -> set[str]:
    """扫 service.py，返回「函数体里调过 `_require_ken_pan` 的 `_run_*_tool`」的工具名。"""
    tree = ast.parse(SERVICE.read_text(encoding="utf-8"))
    service_cls = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name.endswith("Service")
    )
    out: set[str] = set()
    for func in service_cls.body:
        if not isinstance(func, ast.FunctionDef):
            continue
        if not (func.name.startswith("_run_") and func.name.endswith("_tool")):
            continue
        for node in ast.walk(func):
            if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "_require_ken_pan":
                out.add(func.name[len("_run_"):-len("_tool")])
                break
    return out


def main() -> None:
    if not CONTRACT.is_file():
        raise SystemExit(f"technique-provenance: FAIL — missing {CONTRACT.relative_to(PKG_ROOT)}")
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    declared = data.get("tools") or {}
    classes = set(data.get("_classes") or {})
    registered = _load_tools()
    failures: list[str] = []

    missing = sorted(registered - set(declared))
    extra = sorted(set(declared) - registered)
    if missing:
        failures.append(
            f"{len(missing)} registered tool(s) have no compute-source declaration: {missing}\n"
            "    每个技法都要能回答「这一段是谁算的」——技法依据卡按它标注算源（AGENTS §5 布线清单）。"
        )
    if extra:
        failures.append(f"declaration lists {len(extra)} tool(s) that are not registered: {extra}")

    unknown_class = sorted({k for k, v in declared.items() if v.get("compute_class") not in classes})
    if unknown_class:
        failures.append(f"unknown compute_class on: {unknown_class} (known: {sorted(classes)})")

    ken_declared = {k for k, v in declared.items() if v.get("compute_class") == "ken_backed"}
    ken_guarded = runners_calling_require_ken_pan()
    if ken_declared - ken_guarded:
        failures.append(
            f"declared ken_backed but the runner never calls _require_ken_pan: {sorted(ken_declared - ken_guarded)}\n"
            "    ken 端点失败也回 HTTP 200（§4）——没有那道断言，失败会静默回退本地脚手架 = 错结果无报错。"
        )
    if ken_guarded - ken_declared:
        failures.append(
            f"calls _require_ken_pan but is not declared ken_backed: {sorted(ken_guarded - ken_declared)}"
        )

    # 端点登记：只查每个工具的**算盘端点**，不是它打过的所有端点。
    # ken 族与神数族合法地先打 Java 脚手架（qimen 要 /nongli/time + /jieqi/year，jinkou 要
    # /liureng/gods），那些**本来就不该**在 chart 集里——把「打过的都得登记」当判据会得到一条恒红
    # 的守卫，而恒红的守卫等于没有守卫。
    known_endpoints = _chart_endpoints()
    for name, entry in sorted(declared.items()):
        klass = entry.get("compute_class")
        endpoints = entry.get("endpoints") or []
        if klass in {"ken_backed", "chart_service_shenshu"}:
            compute_endpoints = [e for e in endpoints if e.endswith("/pan")]
            if not compute_endpoints:
                failures.append(f"{name}: declared {klass} but no /…/pan compute endpoint is recorded")
        elif klass == "python_chart_backend":
            compute_endpoints = [e for e in endpoints if e in known_endpoints]
            if endpoints and not compute_endpoints:
                failures.append(
                    f"{name}: declared python_chart_backend but none of {endpoints} is in "
                    "service._PYTHON_CHART_ENDPOINTS —— 漏登记会让请求落到 Java 通路（§4 端点注册法则）"
                )
            continue
        else:
            continue
        for endpoint in compute_endpoints:
            if endpoint not in known_endpoints:
                failures.append(
                    f"{name}: compute endpoint {endpoint} not in service._PYTHON_CHART_ENDPOINTS —— "
                    "漏登记会让请求落到 Java 通路（§4 端点注册法则）"
                )

    if failures:
        raise SystemExit("technique-provenance: FAIL\n- " + "\n- ".join(failures))

    counts: dict[str, int] = {}
    for entry in declared.values():
        counts[entry["compute_class"]] = counts.get(entry["compute_class"], 0) + 1
    summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    print(f"technique-provenance: ok ({len(declared)} tools; {summary})")


if __name__ == "__main__":
    main()
