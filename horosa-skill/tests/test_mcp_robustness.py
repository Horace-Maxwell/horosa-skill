"""MCP 传输层的健壮性契约（v0.37.0 C4-C8）。

这个文件锁的是「协议面在**非 Claude Code** 的客户端上也不塌」的五条：坏 payload 永远是结构化
信封、工具调用不占住事件循环、长扫描会报进度并在撤单后停下、`maxSpanDays` 是硬上限、
elicitation 不会把会话挂死。

**为什么旧检查抓不到这些**：既有 MCP 测试（test_mcp_server / test_mcp_contract /
test_mcp_list_budget）全部只看 **tools/list 的形状**与 `_normalize_mcp_request` 这类纯函数，
没有一条真的 `await mcp.call_tool(...)` 走完整条调用路径。于是：
  · 门面各写各的异常分支（agent_guidance 干脆没有 try）→ 形状检查照绿，实调返回 isError 裸文本；
  · 每个 `async def` 里直接调同步 service → 形状检查照绿，事件循环被占死；
  · `maxSpanDays` 能把上限抬到 5000 → schema 里字段在、描述在，纯函数测试无从发现行为不符；
  · `ctx.elicit` 无超时 → 只有真的挂起一次才看得见。
"""
from __future__ import annotations

import json
import time

import anyio
import pytest

import horosa_skill.service as service_module
from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces import mcp_server as M


def _make(tmp_path, **kw):
    settings = Settings(
        server_root="http://127.0.0.1:9999",
        db_path=tmp_path / "memory.db",
        output_dir=tmp_path / "runs",
        **kw,
    )
    return settings, HorosaSkillService(settings, store=MemoryStore(settings))


def _text(result) -> str:
    blocks = result[0] if isinstance(result, tuple) else result
    if isinstance(blocks, list) and blocks:
        return getattr(blocks[0], "text", "") or ""
    return getattr(blocks, "text", "") or str(blocks)


# --------------------------------------------------------------------------------------
# C4 — 坏 payload 一律是结构化信封，绝不 isError 裸文本
# --------------------------------------------------------------------------------------

_FACADES = (
    "horosa_agent_guidance",
    "horosa_memory_query",
    "horosa_memory_show",
    "horosa_memory_record_answer",
    "horosa_report_template",
    "horosa_report_render",
    "horosa_technique_report",
    "horosa_report_from_tool",
    "horosa_hecan",
    "horosa_dispatch",
)


@pytest.mark.parametrize("tool_name", _FACADES)
def test_facade_bad_payload_returns_structured_envelope(tmp_path, tool_name) -> None:
    """每个门面收到无法解析的 request 都必须回结构化错误，而不是让异常逃到 lowlevel server。

    逃出去的异常会被 SDK 转成 `isError: true` + 原始字符串，绕过整个 agent_recovery 契约；
    在精简面（HOROSA_MCP_COMPACT=1）下门面**就是**全部工具，这条漏洞覆盖面最大。
    """
    settings, svc = _make(tmp_path)
    mcp = M.create_mcp_server(svc, settings)

    async def _call():
        return await mcp.call_tool(tool_name, {"request": "{not json"})

    payload = json.loads(_text(anyio.run(_call)))
    assert payload.get("ok") is False, payload
    code = payload.get("code") or (payload.get("error") or {}).get("code")
    assert code == "tool.invalid_payload", payload
    details = payload.get("details") or (payload.get("error") or {}).get("details") or {}
    assert "agent_recovery" in details or "next_action" in details, payload


def test_facade_internal_error_is_enveloped_not_raised(tmp_path) -> None:
    """服务层抛的**非预期**异常也必须变信封（三分支护栏的兜底那一支）。"""
    settings, svc = _make(tmp_path)

    def _boom(*_a, **_k):
        raise RuntimeError("renderer exploded")

    svc.query_memory = _boom  # type: ignore[method-assign]
    mcp = M.create_mcp_server(svc, settings)

    async def _call():
        return await mcp.call_tool("horosa_memory_query", {"limit": 1})

    payload = json.loads(_text(anyio.run(_call)))
    assert payload["ok"] is False
    assert payload["code"] == "tool.internal_error"
    assert "renderer exploded" in payload["message"]


# --------------------------------------------------------------------------------------
# C5 — 工具调用跑在工作线程里，事件循环不被占住
# --------------------------------------------------------------------------------------

_QIMEN = {
    "date": "2026-05-18", "time": "10:00", "zone": "+08:00",
    "lat": "31n13", "lon": "121e28", "ad": 1, "agent_confirmed_settings": True,
}


def test_two_concurrent_tool_calls_overlap(tmp_path) -> None:
    """两个各睡 0.5 秒的调用并发跑完必须显著短于串行的 1.0 秒。

    FastMCP 1.x 不替我们卸载同步函数体（`if fn_is_async: await fn() else: fn()`），所以
    `async def` 里直接调 `service.run_tool` 等于把事件循环焊死一整次扫描。
    """
    settings, svc = _make(tmp_path)

    def _slow(*_a, **_k):
        time.sleep(0.5)
        return {"ok": True}

    svc.run_tool = _slow  # type: ignore[method-assign]
    mcp = M.create_mcp_server(svc, settings)

    async def _both():
        started = time.perf_counter()
        async with anyio.create_task_group() as tg:
            tg.start_soon(mcp.call_tool, "horosa_cn_qimen", dict(_QIMEN))
            tg.start_soon(mcp.call_tool, "horosa_cn_qimen", dict(_QIMEN))
        return time.perf_counter() - started

    assert anyio.run(_both) < 0.9


def test_event_loop_stays_responsive_during_a_tool_call(tmp_path) -> None:
    """一次 0.5 秒的工具调用期间，事件循环必须还能跑别的任务（ping / notifications/cancelled）。"""
    settings, svc = _make(tmp_path)

    def _slow(*_a, **_k):
        time.sleep(0.5)
        return {"ok": True}

    svc.run_tool = _slow  # type: ignore[method-assign]
    mcp = M.create_mcp_server(svc, settings)
    ticks = 0

    async def _heartbeat():
        nonlocal ticks
        while True:
            await anyio.sleep(0.02)
            ticks += 1

    async def _main():
        async with anyio.create_task_group() as tg:
            tg.start_soon(_heartbeat)
            await mcp.call_tool("horosa_cn_qimen", dict(_QIMEN))
            tg.cancel_scope.cancel()

    anyio.run(_main)
    assert ticks > 10, f"事件循环只被调度了 {ticks} 次，说明工具调用把它占住了"


def test_concurrency_is_capped(tmp_path, monkeypatch) -> None:
    """并发有上限：每个在跑的工具持一个 JS 子进程或一条后端连接，不设限会打满本机。"""
    monkeypatch.setattr(M, "_MAX_CONCURRENT_TOOLS", 2)
    monkeypatch.setattr(M, "_TOOL_LIMITER", None)
    live = 0
    peak = 0

    def _slow(*_a, **_k):
        nonlocal live, peak
        live += 1
        peak = max(peak, live)
        time.sleep(0.2)
        live -= 1
        return {"ok": True}

    settings, svc = _make(tmp_path)
    svc.run_tool = _slow  # type: ignore[method-assign]
    mcp = M.create_mcp_server(svc, settings)

    async def _many():
        async with anyio.create_task_group() as tg:
            for _ in range(6):
                tg.start_soon(mcp.call_tool, "horosa_cn_qimen", dict(_QIMEN))

    anyio.run(_many)
    monkeypatch.setattr(M, "_TOOL_LIMITER", None)
    assert peak <= 2, f"同时在跑 {peak} 个，超过上限 2"


# --------------------------------------------------------------------------------------
# C6 — 进度上报与取消检查点
# --------------------------------------------------------------------------------------

class _FakeSession:
    def __init__(self) -> None:
        self.notes: list[dict] = []

    async def send_progress_notification(self, **kw) -> None:
        self.notes.append(kw)


def _fake_ctx(mcp, session, *, token: str | None):
    from mcp.server.fastmcp import Context

    meta = type("Meta", (), {"progressToken": token})()
    req = type("Req", (), {
        "meta": meta, "session": session, "request_id": "r",
        "lifespan_context": None, "request": None,
    })()
    return Context(request_context=req, fastmcp=mcp)


def _fake_mcp(ctx):
    return type("FakeMcp", (), {"get_context": lambda _self: ctx})()


def test_segment_loop_reports_progress(tmp_path) -> None:
    """分段扫描每段报一次进度：客户端在几分钟的扫描里不再只能干等或按超时掐断。"""
    settings, svc = _make(tmp_path)
    mcp = M.create_mcp_server(svc, settings)
    session = _FakeSession()
    ctx = _fake_ctx(mcp, session, token="tok")

    def _scan():
        for i in range(1, 4):
            service_module._progress_tick(i - 1, 3, f"seg {i}")
        service_module._progress_tick(3, 3, "done")
        return {"ok": True}

    async def _run():
        return await M._run_tool_blocking(_fake_mcp(ctx), _scan)

    anyio.run(_run)
    assert len(session.notes) == 4, session.notes
    assert session.notes[0]["progress"] == 0 and session.notes[-1]["progress"] == 3


def test_progress_is_silent_without_a_progress_token(tmp_path) -> None:
    """客户端没给 progressToken 时一条通知都不许发（SDK 侧 no-op），但计算照常跑完。"""
    settings, svc = _make(tmp_path)
    mcp = M.create_mcp_server(svc, settings)
    session = _FakeSession()
    ctx = _fake_ctx(mcp, session, token=None)
    ran = []

    def _scan():
        for i in range(3):
            service_module._progress_tick(i, 3, "seg")
            ran.append(i)
        return {"ok": True}

    async def _run():
        return await M._run_tool_blocking(_fake_mcp(ctx), _scan)

    anyio.run(_run)
    assert ran == [0, 1, 2]
    assert session.notes == []


def test_progress_tick_is_a_noop_without_a_sink() -> None:
    """没有表层注入回调时（CLI / 直调 / 测试），tick 必须是零行为、零开销的空操作。"""
    service_module._progress_tick(1, 2, "no sink")  # 不抛即通过


def test_cancelled_request_stops_the_scan_at_a_segment_boundary(tmp_path) -> None:
    """客户端撤单后，工作线程必须在下一个段边界停下。

    撤单只让宿主任务提前返回是不够的：工作线程会把剩下几十次后端扫描全跑完，为一个没人要的
    结果烧掉后端与本机。MCP 的 `notifications/cancelled` 落到 `RequestResponder.cancel()` →
    `anyio.CancelScope.cancel()`，本用例用的就是同一机制。
    """
    settings, svc = _make(tmp_path)
    mcp = M.create_mcp_server(svc, settings)
    session = _FakeSession()
    ctx = _fake_ctx(mcp, session, token="tok")
    segments_run: list[int] = []
    total = 8

    def _scan():
        for i in range(1, total + 1):
            service_module._progress_tick(i - 1, total, f"seg {i}")
            segments_run.append(i)
            time.sleep(0.12)
        return {"ok": True}

    async def _main():
        async with anyio.create_task_group() as tg:
            with anyio.CancelScope() as scope:
                async def _cancel_soon():
                    await anyio.sleep(0.3)
                    scope.cancel()

                tg.start_soon(_cancel_soon)
                await M._run_tool_blocking(_fake_mcp(ctx), _scan)
        # 被 abandon 的线程若没停会继续跑；给它足够时间暴露出来。
        await anyio.sleep(1.4)

    anyio.run(_main)
    assert len(segments_run) < total, f"撤单后仍跑满 {len(segments_run)}/{total} 段"


def test_progress_callback_failure_never_breaks_the_calculation() -> None:
    """进度是旁路：回调自己出错不能带崩正在跑的计算。"""
    def _bad(*_a, **_k):
        raise RuntimeError("notification stream closed")

    with service_module.progress_sink(_bad):
        service_module._progress_tick(1, 2, "seg")  # 不抛即通过


# --------------------------------------------------------------------------------------
# C7 — maxSpanDays 是硬上限，不是能抬高上限的旋钮
# --------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "given,cap,expected",
    [
        (None, 731, 731),      # 缺省 = 上限
        (5000, 731, 731),      # 🔴 旧行为真按 5000 天放行
        (90, 731, 90),         # 只能调低
        ("120", 731, 120),     # 字符串照收
        (0, 731, 731),         # 0 会让任何窗口都超限 → 回落
        (-5, 731, 731),
        ("abc", 731, 731),     # 旧行为在这里直接 ValueError 裸抛
    ],
)
def test_max_span_days_is_clamped(given, cap, expected) -> None:
    payload = {} if given is None else {"maxSpanDays": given}
    assert service_module._clamped_max_span(payload, cap) == expected


def test_span_too_large_hint_does_not_tell_the_agent_to_raise_the_cap() -> None:
    """超限提示不能再暗示「调高 maxSpanDays」——照做只会被同一条错误挡回来，白烧一轮往返。"""
    from horosa_skill.errors import ToolValidationError

    with pytest.raises(ToolValidationError) as excinfo:
        service_module._require_sane_window("2026-01-01", "2030-01-01", max_span=731, tool="tianxing")
    details = excinfo.value.details
    assert details["max_span_days_cap"] == 731
    assert "调高" not in details["hint"]


# --------------------------------------------------------------------------------------
# C8 — elicitation 有超时，不会把会话挂死
# --------------------------------------------------------------------------------------

def test_elicitation_times_out_and_falls_back_to_the_structured_gate(monkeypatch) -> None:
    """客户端声明了 elicitation 能力却不作答时，必须超时回落到结构化闸门。

    `ctx.elicit()` 自身没有超时：表单丢给一个已经走开的用户，这次 tools/call 就永远挂着，
    占着并发名额，而调用方那头只看到工具无响应。
    """
    monkeypatch.setenv("HOROSA_MCP_ELICIT_TIMEOUT_SECONDS", "0.3")

    class _Hanging:
        class session:
            @staticmethod
            def check_client_capability(_):
                return True

        async def elicit(self, **_kw):
            await anyio.sleep(30)

    gate = M._agent_preflight_error("liureng_gods", {"date": "2026-05-18"})
    assert gate is not None

    async def _run():
        started = time.perf_counter()
        out = await M._maybe_elicit_gate(
            _fake_mcp(_Hanging()), "liureng_gods", {"date": "2026-05-18"}, gate
        )
        return out, time.perf_counter() - started

    out, elapsed = anyio.run(_run)
    assert out is None
    assert gate["details"]["elicitation"]["status"] == "timeout"
    assert elapsed < 3.0, f"超时预算 0.3s 却等了 {elapsed:.1f}s"


# --------------------------------------------------------------------------------------
# 注解：会落盘的工具不许标 readOnly
# --------------------------------------------------------------------------------------

def test_technique_report_is_not_advertised_read_only(tmp_path) -> None:
    """`format = docx | pdf` 时它往磁盘写文件。

    标 readOnly 的后果不是目录审核不过，而是自动放行只读工具的客户端（Claude Code 白名单、
    Cline auto-approve、VS Code）会在不问用户的情况下落盘。
    """
    settings, svc = _make(tmp_path)
    mcp = M.create_mcp_server(svc, settings)
    tools = {t.name: t for t in anyio.run(mcp.list_tools)}
    ann = tools["horosa_technique_report"].annotations
    assert ann is not None and ann.readOnlyHint is False
    assert ann.openWorldHint is False
    # v0.40.0 P0：三个报告类工具按 output_path 覆盖磁盘文件（已限定在输出目录 / 白名单根内）→ 如实标 destructive，
    # 客户端对它们保留确认摩擦；report_from_tool 还会重新起盘 + 新 run → 非幂等。memory_record_answer 只追加，仍非 destructive。
    for name in ("horosa_report_render", "horosa_technique_report", "horosa_report_from_tool"):
        a = tools[name].annotations
        assert a is not None and a.destructiveHint is True and a.readOnlyHint is False, name
    assert tools["horosa_report_render"].annotations.idempotentHint is True
    assert tools["horosa_report_from_tool"].annotations.idempotentHint is False
    assert tools["horosa_memory_record_answer"].annotations.destructiveHint is False
