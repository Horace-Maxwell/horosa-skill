"""星阙 v3.12.0+ 印度律盘：[未能计算] 段 = 上游 buildIndiaSnapshotDataSections（IndiaChart.js:1315-1331）。

回包 jyotish.partialErrors 非空 → 快照末尾（Jyotish 各段之后）出 [未能计算]，逐项列出没算出来的段（中文标签取
indiaMain/jyotishData.js INDIA_PARTIAL_LABELS）。此前 skill 的 JS 工具只调 buildJyotishSnapshotLines + buildDashaSnapshotLines，
这一段永远不出 —— AI 会把「没算出来」读成「没有」。
"""

from __future__ import annotations

import copy
import re

from test_sync311_w3b_gim import INDIA_FIX, _india_run, requires_node


def _titles(text: str) -> list[str]:
    return [m.group(1) for m in re.finditer(r"^\[(.+)\]$", text, re.M)]


@requires_node
def test_partial_errors_become_the_last_data_section(tmp_path) -> None:
    """负向对照：Python 侧不认 `_indiaDataSections`（退回分开的两键）→ 无 [未能计算]，断言红（实跑过）。"""
    chart = copy.deepcopy(INDIA_FIX["india_chart"])
    chart["jyotish"]["partialErrors"] = ["kp.deep", "muhurta.panchaka"]
    env, _ = _india_run(tmp_path, chart=chart)
    assert env.ok, env.error
    text = env.data["snapshot_text"]
    titles = _titles(text)
    assert titles[-1] == "未能计算"
    body = text.split("[未能计算]\n", 1)[1].strip()
    assert body == "以下各段本次未能计算(不是没有,而是没算出来):KP 深化(六级细分 / 宫头次主星 / 当令星 / 意义者)、Panchaka 五忌"
    exp = env.data["export_snapshot"]
    assert exp["unknown_detected_sections"] == [] and "未能计算" in exp["export_text"]


@requires_node
def test_no_partial_errors_no_section(tmp_path) -> None:
    env, _ = _india_run(tmp_path)
    assert env.ok, env.error
    assert "未能计算" not in _titles(env.data["snapshot_text"])
