"""`ad` 只属于它配对的那个日期（v0.50.0 深审余项）。

症状（复现于共享引擎，公元前生人 ad=-1 + 公元 2028 年的搜索窗 / 起课 / 流年）：天星择日、七政择时、印度择时把窗口读成公元前 2028 年
（命中区间全是 -2028-…，印度择时直接 electionscan_failed）；七政四余 [流年流曜] 乙亥（应为丙午）；六壬行年起课盘真太阳时 -2028。
根因：入口已把 ad=-1 折进命主日期的负号（_fold_era），runner 却把同一个 `payload["ad"]` 跟窗口 / 起课 / 流年日期一起发给后端。
现在：凡是和「不是这个载荷自己的 date」一起发出去的纪元，都由那个日期自己的负号定（`_ad_of_date`），窗口恒 ad=1（日期自带负号）。

守卫（源码扫描）：service 层里，读载荷 `ad` 的请求体，其 `date` 必须读同一个载荷的 `date`；例外逐个写明理由。
负向对照（实跑过）：把天星择日的 `"ad": 1` 改回 `payload.get("ad", 1)` → 扫描用例红、live 用例命中区间变成 -2028 → 红。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
from test_local_js_tools import make_service, requires_runtime

from horosa_skill.testing_payloads import build_sample_payloads

SERVICE = Path(__file__).resolve().parents[1] / "src" / "horosa_skill" / "service"

# (文件, 函数) → 为什么这里读载荷的 ad 是对的。
ALLOWED: dict[tuple[str, str], str] = {
    ("enrich.py", "_jieqi_sidereal_recharts"): "节气年表的交节时刻与 year 同一纪元（ad 管的是 year）",
    ("runners/mundane.py", "_run_mundane_tool"): "入宫求根种子按 year 取（ad 管的是 year）",
    ("runners/mingli.py", "_bazi_params"): "date 就是载荷的 date（已补负号）",
    ("runners/mingli.py", "_run_ziwei_tool"): "java_payload 的 date 取自同一载荷",
    ("text/chinese.py", "_compact_jieqi_seed_row"): "节气行自带的 ad（item 自己的）",
}


def _reads_key(node: ast.AST, key: str) -> str | None:
    """`X.get(key…)` / `X[key]` → X 的名字；BoolOp 取任一支。"""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get" and node.args \
            and isinstance(node.args[0], ast.Constant) and node.args[0].value == key:
        return ast.unparse(node.func.value)
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) and node.slice.value == key:
        return ast.unparse(node.value)
    if isinstance(node, ast.BoolOp):
        return next((name for value in node.values if (name := _reads_key(value, key))), None)
    return None


def _offenders() -> list[str]:
    found: list[str] = []
    for path in sorted(SERVICE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        rel = str(path.relative_to(SERVICE))
        for func in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            for node in ast.walk(func):
                if isinstance(node, ast.Dict):
                    keys = {k.value: v for k, v in zip(node.keys, node.values) if isinstance(k, ast.Constant)}
                    source = _reads_key(keys["ad"], "ad") if "ad" in keys else None
                    if source is None:
                        continue
                    date_source = _reads_key(keys["date"], "date") if "date" in keys else None
                elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Subscript) \
                        and isinstance(node.targets[0].slice, ast.Constant) and node.targets[0].slice.value == "ad":
                    source = _reads_key(node.value, "ad")
                    if source is None:
                        continue
                    date_source = None
                else:
                    continue
                if date_source == source or (rel, func.name) in ALLOWED:
                    continue
                found.append(f"{rel}:{node.lineno} {func.name}: ad 读自 {source}，同一请求的 date 不是 {source} 的 date")
    return found


def test_era_travels_only_with_its_own_date() -> None:
    assert _offenders() == []


def test_allowlist_is_not_stale() -> None:
    names = {(str(p.relative_to(SERVICE)), n.name) for p in SERVICE.rglob("*.py")
             for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))) if isinstance(n, ast.FunctionDef)}
    assert set(ALLOWED) <= names, set(ALLOWED) - names


S = build_sample_payloads()


@requires_runtime
@pytest.mark.parametrize("tool, marker", [("tianxing", "共 "), ("qizhengzeri", "时间范围"), ("indiazeri", "时间范围")])
def test_bc_birth_does_not_move_the_search_window(tmp_path, tool: str, marker: str) -> None:
    service = make_service(tmp_path)
    ad = service.run_tool(tool, S[tool], save_result=False)
    bc = service.run_tool(tool, {**S[tool], "ad": -1, "date": "0500-04-06"}, save_result=False)
    assert ad.ok and bc.ok, (ad.error, bc.error)
    hits = lambda env: [line for line in env.data["export_snapshot"]["export_text"].splitlines() if line[:3].strip(". ").isdigit()]  # noqa: E731
    assert hits(bc) and hits(bc) == hits(ad), "命主纪元改变了搜索窗"
    assert not any("-2028" in line for line in hits(bc))


@requires_runtime
def test_guolao_annual_pillar_follows_the_transit_date(tmp_path) -> None:
    service = make_service(tmp_path)
    ad = service.run_tool("guolao_chart", S["guolao_chart"], save_result=False)
    bc = service.run_tool("guolao_chart", {**S["guolao_chart"], "ad": -1, "date": "0500/04/06"}, save_result=False)
    line = lambda env: next(x for x in env.data["export_snapshot"]["export_text"].splitlines() if x.startswith("流年干支"))  # noqa: E731
    assert line(bc) == line(ad), (line(ad), line(bc))


@requires_runtime
def test_liureng_runyear_gua_chart_keeps_its_own_era(tmp_path) -> None:
    payload = {k: v for k, v in S["liureng_runyear"].items() if k != "guaAd"}
    env = make_service(tmp_path).run_tool("liureng_runyear", {**payload, "ad": -1, "date": "0500-04-06"}, save_result=False)
    assert env.ok, env.error
    solar = next(x for x in env.data["export_snapshot"]["export_text"].splitlines() if x.startswith("真太阳时"))
    assert "-2028" not in solar and "2028-04-06" in solar, solar
