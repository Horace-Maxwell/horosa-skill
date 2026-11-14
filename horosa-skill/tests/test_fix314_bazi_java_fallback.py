"""八字 Java 回退恒走 /bazi/direct：bazi_birth 不再在公元前 / 域外年份 / byLon 时丢掉大运（审计 S-16 复核时 live 发现）。

上游 AI 无头复算 buildBaziSnapshotForParams（BaZi.js:642）与「其他模块取八字底稿」都经 fetchBaziDirectCached（:824-845）：本地引擎优先，
抛错回退 Java /bazi/direct。本仓 bazi_birth 以前回退 /bazi/birth——那个响应的 core 没有 direction，快照只剩
「本次本地计算结果未返回「大运」细项」，而同参数的 bazi_direct 有整套大运 / 小运。现在两个技法同一条回退，输出逐字相同。
负向对照（实跑过）：endpoint 改回按技法分 → 第一个用例红；live 用例在引擎上同样变红。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from test_local_js_tools import requires_runtime

BIRTH = {"date": "1990-05-03", "time": "08:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gender": 0,
         "defaults_accepted": True, "byLon": True}   # byLon 只有 Java 实现 → 必走回退


class _Stop(Exception):
    pass


@pytest.mark.parametrize("tool", ["bazi_birth", "bazi_direct"])
def test_java_fallback_uses_the_direct_endpoint_for_both_tools(tmp_path: Path, tool: str) -> None:
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path,
                        runtime_root=tmp_path / "runtime", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs",
                        trace_enabled=False)
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    called: list[str] = []

    def remote(endpoint, body):
        called.append(endpoint)
        raise _Stop

    service._call_remote = remote  # type: ignore[attr-defined]
    service.run_tool(tool, BIRTH, save_result=False)
    assert called == ["/bazi/direct"]


@requires_runtime
def test_live_bazi_birth_keeps_the_luck_cycles_on_the_java_path(tmp_path: Path) -> None:
    settings = Settings.from_env().model_copy(update={"db_path": tmp_path / "m.db", "output_dir": tmp_path / "runs", "data_dir": tmp_path / "d"})
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    birth = service.run_tool("bazi_birth", BIRTH, save_result=False)
    direct = service.run_tool("bazi_direct", BIRTH, save_result=False)
    assert birth.ok and direct.ok, (birth.error, direct.error)
    text = birth.data["export_snapshot"]["export_text"]
    assert "未返回「大运」" not in text and "小运" in text
    assert text == direct.data["export_snapshot"]["export_text"]
