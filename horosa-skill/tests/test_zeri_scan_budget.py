"""择时区间扫描的 JS 墙钟按窗口给（v0.48.1-dev）。

92 天上限原先只是「60 秒内跑得完」的估计；三式合一在 Windows x64 上 92 天要约 70 秒，于是上限承诺的窗口在全局 60 秒墙钟下
必然 `js_engine.timeout`。现在扫描那一次调用的墙钟 = 窗口天数 × 每天预算（封顶 540 秒，客户端按 600 秒配）。
负向对照：去掉 runner 里的 `engine_timeout_at_least` → 扫描时读到的下限是 None → 红。
"""
from __future__ import annotations

from typing import Any

import pytest

from horosa_skill.config import Settings
from horosa_skill.engine import js_client as js_client_module
from horosa_skill.errors import ToolTransportError
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.service.runners.zeri import ZeriRunners
from horosa_skill.testing_payloads import build_sample_payloads

HOURLY_SCAN_TOOLS = [name for name, spec in ZeriRunners._ZERI_SCAN_TOOLS.items() if spec.get("hourly")]


def _service(tmp_path) -> HorosaSkillService:
    settings = Settings(
        server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs", runtime_root=tmp_path / "runtime",
    )
    return HorosaSkillService(settings, store=MemoryStore(settings))


def _floor_seen_by_scan(tmp_path, monkeypatch, tool: str, start: str, end: str) -> Any:
    """跑一次择时，记下 zeri_scan 那次调用时生效的墙钟下限，然后让扫描失败（不需要真跑 JS）。"""
    service = _service(tmp_path)
    seen: list[Any] = []

    def spy(tool_name: str, payload: dict) -> dict:
        if tool_name == "zeri_scan":
            seen.append(js_client_module._MIN_TIMEOUT_SECONDS.get())
            raise ToolTransportError("stop here", code="js_engine.timeout")
        raise AssertionError(f"unexpected JS call before the scan: {tool_name}")

    monkeypatch.setattr(service.js_client, "run", spy)
    payload = {**build_sample_payloads()[tool], "startDate": start, "endDate": end, "agent_confirmed_settings": True}
    env = service.run_tool(tool, payload, save_result=False)
    assert env.ok is False and env.error.code == "js_engine.timeout"
    assert js_client_module._MIN_TIMEOUT_SECONDS.get() is None  # 作用域只罩住扫描那一次
    assert len(seen) == 1
    return seen[0]


def test_hourly_scan_tools_are_the_ones_this_guards() -> None:
    assert set(HOURLY_SCAN_TOOLS) >= {"sanshizeri", "taiyizeri", "liurengzeri", "ziweizeri", "bazizeri"}


@pytest.mark.parametrize("tool", HOURLY_SCAN_TOOLS)
def test_the_full_window_gets_a_wall_clock_sized_to_it(tmp_path, monkeypatch, tool: str) -> None:
    # 2028-04-01 … 2028-07-01 = 92 天（两端都算），即缺省上限。
    floor = _floor_seen_by_scan(tmp_path, monkeypatch, tool, "2028-04-01", "2028-07-01")
    assert floor == 92 * ZeriRunners._ZERI_SCAN_SECONDS_PER_DAY
    assert floor > Settings().js_engine_timeout_seconds  # 上限窗口拿到的墙钟比全局缺省长


def test_one_day_window_keeps_the_configured_wall_clock(tmp_path, monkeypatch) -> None:
    floor = _floor_seen_by_scan(tmp_path, monkeypatch, "sanshizeri", "2028-04-01", "2028-04-01")
    assert floor == ZeriRunners._ZERI_SCAN_SECONDS_PER_DAY  # 低于 60 秒：client 取 max，照用配置


def test_budget_is_capped_below_the_client_tool_timeout(tmp_path, monkeypatch) -> None:
    # 黄历择日按日粒度，上限 366 天：按天算会超过客户端的 600 秒，封顶。
    floor = _floor_seen_by_scan(tmp_path, monkeypatch, "huanglizeri", "2028-01-01", "2028-12-31")
    assert floor == ZeriRunners._ZERI_SCAN_MAX_TIMEOUT_SECONDS < 600
