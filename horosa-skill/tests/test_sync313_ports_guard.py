"""手抄上游常量表的逐值看守（需 HOROSA_SOURCE_ROOT；CI 无上游检出时 skip，preflight 在维护者机器上跑）。

v3.13.0 同步时发现 `_INDIA_MOUNT_VARGA_OPTIONS`（chart_family.py，抄自 AstroConst.js INDIA_MOUNT_VARGA_OPTIONS）
停在 v3.11：上游 v3.12.0 把 16 档里 12 档改了标签（D9 婚姻→D9 合作 …），skill 的 [附加分盘] 小标题仍写旧名，
而 vendor 清单只看守 horosa-core-js 下的 JS，Python 手抄件零信号。这里把 Python 侧的手抄表对上游逐值比对。
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from horosa_skill.service.text import chart_family

_ROOT = os.environ.get("HOROSA_SOURCE_ROOT")
_ASTRO_CONST = Path(_ROOT) / "Horosa-Web" / "astrostudyui" / "src" / "constants" / "AstroConst.js" if _ROOT else None
requires_upstream = pytest.mark.skipif(
    _ASTRO_CONST is None or not _ASTRO_CONST.is_file(), reason="HOROSA_SOURCE_ROOT (Horosa-Public checkout) not set"
)


def _upstream_block(name: str) -> str:
    text = _ASTRO_CONST.read_text(encoding="utf-8")
    start = text.index(f"export const {name} = [")
    return text[start: text.index("];", start)]


@requires_upstream
def test_india_mount_varga_options_match_upstream_value_for_value() -> None:
    """负向对照：把 Python 表里 D9 改回「D9 婚姻」→ 红（实跑过）。"""
    upstream = [(int(v), label) for v, label in re.findall(r"\{\s*value:\s*(\d+),\s*label:\s*'([^']*)'\s*\}",
                                                           _upstream_block("INDIA_MOUNT_VARGA_OPTIONS"))]
    assert len(upstream) == 16
    assert list(chart_family._INDIA_MOUNT_VARGA_OPTIONS) == upstream


@requires_upstream
def test_india_extra_varga_max_matches_upstream() -> None:
    text = _ASTRO_CONST.read_text(encoding="utf-8")
    assert re.search(r"export const INDIA_MOUNT_EXTRA_VARGA_MAX = (\d+);", text).group(1) == str(
        chart_family._INDIA_MOUNT_EXTRA_VARGA_MAX)


def test_india_chart_always_sends_transit_date_and_tajaka_year_in_the_chart_zone(monkeypatch) -> None:
    """IndiaChart.fieldsToParams:89-94（v3.12.0）：过运日 / 年度盘年份恒下发，未给 = 本盘时区的今天 / 今年。
    后端 _compute_tajaka 只在给了 tajakaYear 时才算 —— skill 此前两键都不发，缺省盘 Tajika 各段恒缺席。
    冻结此刻 = UTC 2026-12-31 20:30：东八区已是 2027-01-01，西五区仍是 2026-12-31（跨日、跨年两向都钉住）。
    负向对照：删掉 _india_chart_remote_payload 末尾的缺省补键块 → 前两条断言红（实跑过）。"""
    from datetime import datetime, timezone

    from horosa_skill.service import _clock

    frozen = datetime(2026, 12, 31, 20, 30, tzinfo=timezone.utc)
    monkeypatch.setattr(_clock, "now", lambda tz=None: frozen.astimezone(tz) if tz else frozen)
    east = chart_family._india_chart_remote_payload({"date": "1990-05-18", "zone": "+08:00"})
    assert (east["transitDate"], east["tajakaYear"]) == ("2027/01/01", 2027)
    west = chart_family._india_chart_remote_payload({"date": "1990-05-18", "zone": "-05:00"})
    assert (west["transitDate"], west["tajakaYear"]) == ("2026/12/31", 2026)
    explicit = chart_family._india_chart_remote_payload(
        {"date": "1990-05-18", "zone": "+08:00", "transitDate": "2030/02/03", "tajakaYear": 2031})
    assert (explicit["transitDate"], explicit["tajakaYear"]) == ("2030/02/03", 2031)
