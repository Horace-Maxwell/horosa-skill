"""任何响应视图都不许改变一盘算出了什么（v0.50.0-dev，冷客户端审计 F4）。

`response_view` 是「返回体长什么样」的开关，不是算法输入。v0.49.0 及以前它跟着载荷进了 runner 的子调用：
择日类先算一张展示盘再读它的 `snapshot_text`，子调用把视图也用上了，快照被清空，外层读到空串 →
黄历择日 14 段里 7 段成了「本次本地计算结果未返回…细项」，还多出一条假的「结果不完整」告警。

这里对整张技法表逐个对照：每种视图下的段落（序号、标题、正文）与告警，跟不带视图的那一次完全一致。
离线用 fakes（整张表三遍约 2 秒）；live 变体打共享引擎，覆盖十个择日技法。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fakes import FakeClient, FakeJsClient
from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.testing_payloads import build_sample_payloads

SERVICE_VIEWS = ("sections", "titles")
ZERI_TOOLS = (
    "tianxing", "qimenzeri", "huanglizeri", "bazizeri", "taiyizeri", "ziweizeri", "liurengzeri", "sanshizeri",
    "qizhengzeri", "indiazeri",
)
# 视图自己加的那一句不算「多出来的告警」。
_VIEW_NOTE = "response_view="


def offline_service(tmp_path: Path) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
                        db_path=tmp_path / "m.db", output_dir=tmp_path / "runs", runtime_root=tmp_path / "rt",
                        data_dir=tmp_path / "data")
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())


def section_rows(envelope: dict[str, Any]) -> list[tuple[Any, Any]]:
    snapshot = (envelope.get("data") or {}).get("export_snapshot") or {}
    return [(row.get("index"), row.get("title")) for row in snapshot.get("sections") or []]


def section_bodies(envelope: dict[str, Any]) -> list[Any]:
    snapshot = (envelope.get("data") or {}).get("export_snapshot") or {}
    return [row.get("body") for row in snapshot.get("sections") or []]


def view_drift(raw: dict[str, Any], viewed: dict[str, Any], *, bodies: bool) -> list[str]:
    """一个视图相对原始结果变了什么（空 = 没变）。"""
    problems: list[str] = []
    if section_rows(raw) != section_rows(viewed):
        problems.append(f"sections {len(section_rows(raw))} -> {len(section_rows(viewed))}")
    elif bodies and section_bodies(raw) != section_bodies(viewed):
        changed = [row[1] for row, a, b in zip(section_rows(raw), section_bodies(raw), section_bodies(viewed)) if a != b]
        problems.append(f"bodies changed: {changed[:3]}")
    extra = [w for w in viewed.get("warnings") or [] if w not in (raw.get("warnings") or []) and _VIEW_NOTE not in w]
    if extra:
        problems.append(f"new warning: {extra[0][:60]}")
    return problems


def test_service_views_never_change_what_was_computed(tmp_path: Path) -> None:
    """负向对照：run_tool 里去掉「嵌套调用先摘掉展示键」→ 7 个择日技法（黄历 / 八字 / 太乙 / 紫微 / 六壬 / 三式 / 七政）红（实跑过）。"""
    service = offline_service(tmp_path)
    payloads = build_sample_payloads()
    checked = 0
    drift: dict[str, list[str]] = {}
    for name in TOOL_DEFINITIONS:
        raw = service.run_tool(name, payloads[name], save_result=False).model_dump(mode="json")
        assert raw["ok"], (name, raw.get("code"))
        if not isinstance((raw.get("data") or {}).get("export_snapshot"), dict):
            continue
        checked += 1
        for view in SERVICE_VIEWS:
            viewed = service.run_tool(name, {**payloads[name], "response_view": view}, save_result=False).model_dump(mode="json")
            problems = view_drift(raw, viewed, bodies=view == "sections")
            if problems:
                drift[f"{name}[{view}]"] = problems
    assert checked >= 100, checked   # 整张表都在比，不是只比了几个
    assert not drift, drift


def test_nested_calls_drop_presentation_keys_and_stay_unviewed(tmp_path: Path) -> None:
    """子调用拿到的载荷里没有展示键，子信封也不裁；最外层那一次照旧按视图裁。"""
    service = offline_service(tmp_path)
    seen: list[tuple[str, bool, int]] = []
    original = service._compute_tool_result

    def spy(call):  # noqa: ANN001, ANN202
        from horosa_skill.service._context import run_tool_depth

        seen.append((call.tool_name, "response_view" in call.input_normalized, run_tool_depth()))
        return original(call)

    service._compute_tool_result = spy  # type: ignore[method-assign]
    payload = {**build_sample_payloads()["huanglizeri"], "response_view": "titles"}
    envelope = service.run_tool("huanglizeri", payload, save_result=False)
    outer = [row for row in seen if row[2] == 1]
    inner = [row for row in seen if row[2] > 1]
    assert [row[0] for row in outer] == ["huanglizeri"] and outer[0][1] is True
    assert inner and not any(row[1] for row in inner), seen
    # 最外层仍然是 titles 视图：段只剩序号与标题。
    assert all(set(row) == {"index", "title"} for row in envelope.data["export_snapshot"]["sections"])
