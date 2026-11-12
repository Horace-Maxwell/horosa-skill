"""doctor 不凭一次探测就判「半边没起」（v0.47.3 发版时 windows-smoke 抓到的偶发红）。

CI 42330590503（第一次尝试）：`start` 刚报 java_backend + python_chart 都可达，紧接着 doctor 只探到 java_backend，报
services:chart_not_running，`setup` 因此 ok:false —— 同一轮真实排盘冒烟却全过，重跑即绿。doctor 全程 0.374 秒，比单次
探测的 1.5 秒超时还短，所以是快速失败（连接被拒 / 重置 / 5xx），不是慢。抖动本身的原因日志里没有，这里不猜。

只有「一边通、一边不通」才复探：那是运行中的 runtime，抖动说得通。两边都不通（根本没起）一次定论，不让 doctor 变慢。
"""

from __future__ import annotations

from pathlib import Path
from types import MethodType

import pytest
# v0.50.0-dev：doctor 先定模式，外部（网关）模式不报 services:*。conftest 把两个根钉到 :9 = 外部模式；这里测的是本机 runtime，
# 所以和 test_runtime_manager 一样用 _managed_mode 清掉那两个变量（否则「因为错误的原因」走进网关分支）。
from test_runtime_manager import _managed_mode, create_runtime_archive  # noqa: F401 - _managed_mode 是 autouse fixture

from horosa_skill.config import Settings
from horosa_skill.runtime import manager as manager_module
from horosa_skill.runtime.manager import HorosaRuntimeManager


def _endpoints(java: bool, chart: bool) -> list[dict[str, object]]:
    return [
        {"label": "java_backend", "url": "http://127.0.0.1:9999", "reachable": java},
        {"label": "python_chart", "url": "http://127.0.0.1:8899", "reachable": chart},
    ]


@pytest.fixture()
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    recorded: list[float] = []
    # 替换复探自己的接缝，不碰全局 time.sleep：全局替换会把同进程别的线程的 sleep（subprocess 轮询 0.001 s）
    # 也记进来，render 分支的门禁里就因此偶发红过一次。
    monkeypatch.setattr(manager_module, "_reprobe_sleep", recorded.append)
    return recorded


def _doctor(tmp_path: Path, script: list[list[dict[str, object]]]) -> tuple[dict, list[int]]:
    """按 script 依次回放 _service_status；探完了就一直回最后一份。"""
    settings = Settings(
        runtime_root=tmp_path / "runtime-root", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs",
        runtime_start_timeout_seconds=0.5,
    )
    manager = HorosaRuntimeManager(settings)
    manager.install(archive=str(create_runtime_archive(tmp_path)))
    calls = [0]

    def replay(self: HorosaRuntimeManager) -> list[dict[str, object]]:
        calls[0] += 1
        return script[min(calls[0] - 1, len(script) - 1)]

    manager._service_status = MethodType(replay, manager)
    return manager.doctor(), calls


def _service_issues(report: dict) -> list[str]:
    """只看服务那几条。夹具只造了 macOS 布局，Linux / Windows 上整体 `ok` 会因 missing:* 为 False——
    52007d4 断言 `ok is True`，本机（macOS）绿、CI 两个平台红。"""
    return [issue for issue in report["issues"] if issue.startswith("services:")]


def test_a_blip_on_one_service_is_not_reported_as_that_service_being_down(tmp_path: Path, sleeps: list[float]) -> None:
    """负向对照：doctor 改回直接调 `_service_status` → issues 带 chart_not_running，本条红（实跑过）。"""
    report, calls = _doctor(tmp_path, [_endpoints(True, False), _endpoints(True, True)])
    assert _service_issues(report) == [], report["issues"]
    assert calls[0] == 2 and len(sleeps) == 1


@pytest.mark.parametrize(("java", "chart", "issue"), [
    (True, False, "services:chart_not_running"),
    (False, True, "services:java_backend_not_running"),
])
def test_a_service_that_stays_down_is_still_reported(tmp_path: Path, sleeps: list[float], java: bool, chart: bool, issue: str) -> None:
    """负向对照：复探把「一直不通」也吞掉（循环结束回全通）→ 本条红（实跑过）。复探有上限，总等待有界。"""
    report, calls = _doctor(tmp_path, [_endpoints(java, chart)])
    assert issue in report["issues"]
    attempts = manager_module._PARTIAL_REPROBE_ATTEMPTS
    assert calls[0] == attempts + 1 and len(sleeps) == attempts
    assert sum(sleeps) <= 2.0


def test_nothing_running_is_answered_at_once(tmp_path: Path, sleeps: list[float]) -> None:
    """全都不通 = 根本没起，不复探。负向对照：去掉 `_any_services_reachable` 条件 → 本条红（实跑过）。"""
    report, calls = _doctor(tmp_path, [_endpoints(False, False)])
    assert "services:not_running" in report["issues"]
    assert calls[0] == 1 and sleeps == []


def test_all_up_is_answered_at_once(tmp_path: Path, sleeps: list[float]) -> None:
    report, calls = _doctor(tmp_path, [_endpoints(True, True)])
    assert _service_issues(report) == [], report["issues"]
    assert calls[0] == 1 and sleeps == []
