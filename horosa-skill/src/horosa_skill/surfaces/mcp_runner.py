"""MCP 调用的执行：并发上限（HOROSA_MCP_MAX_CONCURRENT_TOOLS）、把阻塞的 service 调用放进线程、进度上报、门面工具的统一兜底。"""
from __future__ import annotations

import functools
import os
from typing import Any

import anyio
from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from horosa_skill.errors import ToolValidationError
from horosa_skill.service import progress_sink
from horosa_skill.surfaces.mcp_errors import (
    _mcp_error_payload,
    _mcp_internal_error_payload,
    _mcp_validation_error_payload,
)

# 工作线程并发上限：每个在跑的工具会持有一个 JS 子进程或一条后端 HTTP 连接，无限并发会
# 把本机 CPU 与后端连接池打满。4 是「几个客户端同时问一句」的常见峰值。
_MAX_CONCURRENT_TOOLS = max(1, int(os.environ.get("HOROSA_MCP_MAX_CONCURRENT_TOOLS", "4") or 4))
_TOOL_LIMITER: Any = None


def _tool_limiter() -> Any:
    """并发上限。必须在事件循环里惰性构造（CapacityLimiter 绑定当前 async 后端）。"""
    global _TOOL_LIMITER
    if _TOOL_LIMITER is None:
        _TOOL_LIMITER = anyio.CapacityLimiter(_MAX_CONCURRENT_TOOLS)
    return _TOOL_LIMITER


async def _run_blocking(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """把同步的 service 调用挪到工作线程。

    🔴 每个工具都是 `async def` 却直接调同步的 `service.run_tool`（内含阻塞 httpx 与
    subprocess.run），而 FastMCP 1.x 不会替我们卸载（func_metadata: `if fn_is_async: await fn()
    else: fn()`）。后果是**整个事件循环被占住**：一次 tianxing 731 天扫描（约 24 段串行后端调用）
    期间服务器答不了 ping、处理不了 notifications/cancelled，streamable-HTTP 下所有客户端串行。
    Claude Desktop / VS Code 会把它标成无响应。

    anyio 4.13 的 to_thread 会 `copy_context()`，所以 `_DEGRADE_NOTES` 这类 ContextVar
    与 lowlevel 的 request_ctx 在工作线程里都可见 —— 这是这个改法成立的前提，已核实。
    """
    return await anyio.to_thread.run_sync(
        functools.partial(fn, *args, **kwargs), limiter=_tool_limiter(), abandon_on_cancel=True
    )


def _progress_tick_for(mcp: FastMCP) -> Any:
    """构造交给服务层的 tick 回调（工作线程里被调用）。取不到请求上下文时返回 None。

    两件事，顺序不可换：
      1. `check_cancelled()` —— 客户端发了 notifications/cancelled 后，工作线程在**下一个段边界**
         抛 CancelledError（BaseException，穿过服务层的 `except Exception` 旁路兜底）。没有它，
         撤单只是让宿主任务提前返回，工作线程照样把剩下的几十次后端扫描跑完，白烧后端与本机。
      2. `ctx.report_progress` —— 客户端没给 progressToken 时 SDK 自身 no-op，无需在这里判断。
    """
    try:
        ctx = mcp.get_context()
    except Exception:  # noqa: BLE001 - 不在请求上下文里（直调/测试）时安静降级为无进度
        return None

    def _tick(done: int, total: int, label: str) -> None:
        anyio.from_thread.check_cancelled()
        anyio.from_thread.run(ctx.report_progress, float(done), float(total), label)

    return _tick


async def _run_tool_blocking(mcp: FastMCP, fn: Any, *args: Any, **kwargs: Any) -> Any:
    """`_run_blocking` + 把 MCP 进度/取消接到服务层的分段循环上。"""
    tick = _progress_tick_for(mcp)
    if tick is None:
        return await _run_blocking(fn, *args, **kwargs)
    # ContextVar 在**事件循环侧**设好，to_thread 的 copy_context 才会把它带进工作线程。
    with progress_sink(tick):
        return await _run_blocking(fn, *args, **kwargs)


async def _guarded_facade(
    mcp: FastMCP, operation_name: str, fn: Any, *args: Any, **kwargs: Any
) -> dict[str, Any]:
    """门面工具的统一异常护栏 **兼**线程卸载入口。

    🔴 门面此前各写各的（`horosa_agent_guidance` 干脆没有 try，memory 族只 catch
    ToolValidationError）。漏网的异常会被 lowlevel server 转成 `isError: true` + 裸字符串，
    绕过整个 agent_recovery 契约 —— 而在精简面（HOROSA_MCP_COMPACT=1）下门面**就是**全部工具，
    所以这条漏洞在最省 token 的那个配置里覆盖面最大。三分支与技法工具逐字同款。

    fn 在工作线程里跑（`_run_blocking`）：门面同样会做磁盘 I/O（报告渲染、SQLite 查询）与后端
    HTTP 调用，留在事件循环上会让 ping/cancel/其他工具全部排队。归一化也放进线程，这样
    `_normalize_mcp_request` 抛的 ToolValidationError 一样落进本护栏，而不是从工具体外逃逸。
    """
    try:
        return await _run_tool_blocking(mcp, fn, *args, **kwargs)
    except ToolValidationError as exc:
        return _mcp_error_payload(exc)
    except ValidationError as exc:
        return _mcp_validation_error_payload(operation_name, None, exc)
    except Exception as exc:  # noqa: BLE001 - 兜底也必须是 envelope，不能变 isError 裸文本
        return _mcp_internal_error_payload(exc)
