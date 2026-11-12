"""星运（v3.13.1 同步，C1）：推运图族四法请求键 ↔ 上游后端 / Java 白名单的逐键看守（需 HOROSA_SOURCE_ROOT；无上游检出时 skip）。

上游 v3.13.1（06f25f21）在 AstroExtraController.java:39-40 OPTIONAL_KEYS 登记了推运图族的专属键
（nerK / nerT0 / nerKeepDec / maxAge / jayFrom / mzSwap / mzEqual，「漏登记会被静默丢弃」），后端
astropy/astrostudy/directed_figures.py:532-638 按 `data.get('<键>')` 读、读不到回落缺省——键名一旦拼错或上游改名，
盘照常出、设置静默不生效（与 v3.12 期间 orbs/orbScale 在 astroextra 族被白名单吞掉同型）。本仓的 runner
（service/runners/predictive.py `_directed_figure_request_fields`）只与 vendored JS 映射逐键互检，对后端键名零信号。

这里钉两件事：
1. runner 对四法（缺省 + 全非缺省设置）实发的每个技法专属键，后端 directed_figures.py 真的按这个名字读；
2. 同一批键（除 headless 直连 Python 才发的 withChart）都在 Java OPTIONAL_KEYS 里——桌面版 / Java 路由同名可达。

负向对照：把 runner 里 jayprofection 的 `"jayFrom"` 改成 `"jayStart"` → 第 1、2 条都红（实跑过，已复原）。
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from horosa_skill.service.runners.predictive import PredictiveRunners as R

_ROOT = os.environ.get("HOROSA_SOURCE_ROOT")
_WEB = Path(_ROOT) / "Horosa-Web" if _ROOT else None
_BACKEND = _WEB / "astropy" / "astrostudy" / "directed_figures.py" if _WEB else None
_JAVA = (
    _WEB / "astrostudysrv" / "astrostudy" / "src" / "main" / "java" / "spacex" / "astrostudy" / "controller" / "AstroExtraController.java"
    if _WEB
    else None
)
requires_upstream = pytest.mark.skipif(
    _BACKEND is None or not _BACKEND.is_file() or not _JAVA.is_file(),
    reason="[upstream-checkout] HOROSA_SOURCE_ROOT (Horosa-Public checkout) not set",
)

# 全非缺省设置（各取值域里一个非缺省档）：确保每个可选键都实际出现在请求体里。
_NON_DEFAULT = {
    "neroman": {"nerK": 300, "nerT0": 0.5, "nerKeepDec": True, "nerOrb": 2},
    "bezzafigure": {"bezzaOrb": 3},
    "jayprofection": {"jayFrom": 24},
    "michon": {"michonOrb": 2, "michonSwap": True, "michonEqual": True},
}


def _sent_keys(technique: str) -> set[str]:
    keys: set[str] = set()
    for payload in ({}, _NON_DEFAULT[technique]):
        settings = R._directed_figure_settings(R.__new__(R), payload, technique)
        keys |= set(R._directed_figure_request_fields(technique, settings))
    return keys


def _java_optional_keys() -> set[str]:
    text = _JAVA.read_text(encoding="utf-8")
    block = text[text.index("OPTIONAL_KEYS = new String[] {") : text.index("};", text.index("OPTIONAL_KEYS"))]
    block = re.sub(r"//[^\n]*", "", block)
    return set(re.findall(r'"([A-Za-z0-9_]+)"', block))


@requires_upstream
@pytest.mark.parametrize("technique", sorted(_NON_DEFAULT))
def test_directed_figure_request_keys_are_read_by_upstream_backend(technique: str) -> None:
    backend = set(re.findall(r"data\.get\('([A-Za-z0-9_]+)'", _BACKEND.read_text(encoding="utf-8")))
    sent = _sent_keys(technique)
    assert sent, technique
    assert sent <= backend, sorted(sent - backend)
    # runner 另发的目标时刻与 withChart 也须是后端认的名字
    assert {"targetDate", "targetTime", "withChart"} <= backend


@requires_upstream
@pytest.mark.parametrize("technique", sorted(_NON_DEFAULT))
def test_directed_figure_request_keys_are_in_java_whitelist(technique: str) -> None:
    allowed = _java_optional_keys()
    assert {"nerK", "nerT0", "nerKeepDec", "jayFrom", "mzSwap", "mzEqual", "orb"} <= allowed  # 解析自检
    sent = _sent_keys(technique) | {"targetDate", "targetTime"}
    assert sent <= allowed, sorted(sent - allowed)
