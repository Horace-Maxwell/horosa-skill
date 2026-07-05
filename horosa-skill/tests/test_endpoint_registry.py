"""端点路由登记闸。

`service._call_remote` 按 `_PYTHON_CHART_ENDPOINTS` 决定请求发往 Python chart 服务还是 Java 后端。
chart 服务独有的端点（astroextra/geomancy/jieqi/predict/modern/india/germany/ken 与神数 /pan 族）
若新增调用时忘了登记，会被静默路由到 Java 端口并返回 need.login —— 这是历史上真实踩过的坑。
本闸静态扫描 service.py 里的全部 `_call_remote("<literal>")` 字面量：凡命中 chart-only 前缀者必须
已登记；同时反向校验登记集合里没有拼写漂移（集合成员必须仍被调用或显式豁免）。
"""
from __future__ import annotations

import pathlib
import re

from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.service import _PYTHON_CHART_ENDPOINTS, _SHENSHU_ENDPOINTS

SERVICE_PATH = pathlib.Path(__file__).resolve().parents[1] / "src" / "horosa_skill" / "service.py"

# chart 服务独有的路由前缀（Java 后端不挂载这些路径）。
CHART_ONLY_PREFIXES = (
    "/astroextra/",
    "/geomancy/",
    "/jieqi/",
    "/predict/",
    "/modern/",
    "/india/",
    "/germany/",
    "/qimen/",
    "/taiyi/",
    "/jinkou/",
    "/wangji/",
    "/wuzhao/",
    "/taixuan/",
    "/jingjue/",
    "/shenyishu/",
    "/shaozi/",
    "/tieban/",
    "/fendjing/",
    "/beiji/",
    "/nanji/",
    "/chunzi/",
    "/xianqin/",
    "/cetian/",
    "/qizhengkin/",
)

def _call_site_endpoints() -> set[str]:
    # 调用点 = service.py 字面量调用 ∪ ToolDefinition 声明式端点（经 `_call_remote(definition.endpoint, …)`）
    # ∪ 神数端点映射表（经 `_call_remote(_SHENSHU_ENDPOINTS[name], …)`）。
    text = SERVICE_PATH.read_text(encoding="utf-8")
    literals = set(re.findall(r"_call_remote\(\s*[\"']([^\"']+)[\"']", text))
    declared = {d.endpoint for d in TOOL_DEFINITIONS.values() if d.endpoint}
    return literals | declared | set(_SHENSHU_ENDPOINTS.values())


def test_chart_only_endpoints_are_registered() -> None:
    called = _call_site_endpoints()
    missing = sorted(
        endpoint
        for endpoint in called
        if endpoint.startswith(CHART_ONLY_PREFIXES) and endpoint not in _PYTHON_CHART_ENDPOINTS
    )
    assert not missing, (
        f"这些 chart-only 端点被 _call_remote 调用但未登记进 _PYTHON_CHART_ENDPOINTS（会被误路由到 Java→need.login）：{missing}"
    )


def test_registered_endpoints_have_call_sites() -> None:
    called = _call_site_endpoints()
    stale = sorted(endpoint for endpoint in _PYTHON_CHART_ENDPOINTS if endpoint not in called)
    assert not stale, f"登记集合中的这些端点已无任何调用点（拼写漂移或死项，请更新集合）：{stale}"
