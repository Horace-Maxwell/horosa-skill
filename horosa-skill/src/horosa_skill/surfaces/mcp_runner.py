"""MCP 调用的执行：并发上限（HOROSA_MCP_MAX_CONCURRENT_TOOLS）、把阻塞的 service 调用放进线程、进度上报、门面工具的统一兜底。"""
from __future__ import annotations

import functools
import os
from contextvars import ContextVar
from typing import Any

import anyio
from mcp import types as mcp_types
from mcp.server.mcpserver import Context, MCPServer
from pydantic import ValidationError

from horosa_skill.errors import ToolValidationError
from horosa_skill.service import progress_sink
from horosa_skill.textscript import SIMPLIFIED
from horosa_skill.textscript.localize import localize
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
    subprocess.run），而 SDK 只替**同步**工具函数卸载（2.x 起；1.x 的 FastMCP 连这个也不做），我们的工具都是 async。后果是**整个事件循环被占住**：一次 tianxing 731 天扫描（约 24 段串行后端调用）
    期间服务器答不了 ping、处理不了 notifications/cancelled，streamable-HTTP 下所有客户端串行。
    Claude Desktop / VS Code 会把它标成无响应。

    anyio 4.13 的 to_thread 会 `copy_context()`，所以 `_DEGRADE_NOTES` 这类 ContextVar
    与 `_CURRENT_CONTEXT` 在工作线程里都可见 —— 这是这个改法成立的前提，已核实。
    """
    return await anyio.to_thread.run_sync(
        functools.partial(fn, *args, **kwargs), limiter=_tool_limiter(), abandon_on_cancel=True
    )


# SDK 2.x 去掉了 `mcp.get_context()`：请求上下文只作为参数传进 `call_tool`。我们的工具签名是合成的 `**kwargs`
# （120 个，不便逐个加 ctx 参数），所以由 `HorosaMCPServer.call_tool` 把它放进 ContextVar，进度 / 撤单 / elicitation /
# 协议版本都从这里取。不在请求里（直调、测试）就是 None。
_CURRENT_CONTEXT: ContextVar[Context | None] = ContextVar("horosa_mcp_context", default=None)


def current_context() -> Context | None:
    return _CURRENT_CONTEXT.get()


def _progress_tick_for(mcp: MCPServer) -> Any:
    """构造交给服务层的 tick 回调（工作线程里被调用）。取不到请求上下文时返回 None。

    两件事，顺序不可换：
      1. `check_cancelled()` —— 客户端发了 notifications/cancelled 后，工作线程在**下一个段边界**
         抛 CancelledError（BaseException，穿过服务层的 `except Exception` 旁路兜底）。没有它，
         撤单只是让宿主任务提前返回，工作线程照样把剩下的几十次后端扫描跑完，白烧后端与本机。
      2. `ctx.report_progress` —— 客户端没给 progressToken 时 SDK 自身 no-op，无需在这里判断。
    """
    ctx = current_context()
    if ctx is None or ctx._request_context is None:  # 不在请求里（直调 / 测试）：安静降级为无进度
        return None

    def _tick(done: int, total: int, label: str) -> None:
        anyio.from_thread.check_cancelled()
        anyio.from_thread.run(ctx.report_progress, float(done), float(total), label)

    return _tick


async def _run_tool_blocking(mcp: MCPServer, fn: Any, *args: Any, **kwargs: Any) -> Any:
    """`_run_blocking` + 把 MCP 进度/取消接到服务层的分段循环上。"""
    tick = _progress_tick_for(mcp)
    if tick is None:
        return await _run_blocking(fn, *args, **kwargs)
    # ContextVar 在**事件循环侧**设好，to_thread 的 copy_context 才会把它带进工作线程。
    with progress_sink(tick):
        return await _run_blocking(fn, *args, **kwargs)


async def _guarded_facade(
    mcp: MCPServer, operation_name: str, fn: Any, *args: Any, **kwargs: Any
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


# 不转繁体的工具：给 AI 的协议与注册表（段名、知识库键、选项要原样送回），以及回显用户自己贴来的导出文本。
UNLOCALIZED_TOOLS = frozenset({
    "horosa_agent_guidance", "horosa_export_registry", "horosa_knowledge_registry", "horosa_export_parse",
})


class HorosaMCPServer(MCPServer):
    """MCPServer + 输出文字转换 + 报告文件链接。所有工具（含错误信封）都经 `call_tool` 出门，所以只在这一处处理。

    取工具的**原始返回值**（`convert_result=False`），按 textscript.localize 的白名单转完，再交回 SDK 自己的
    `convert_result` 序列化——内容块与 structuredContent 的形状与简体时完全一致。`InputRequiredResult`（2026-07-28
    的 MRTR 多轮：缺设置时让客户端问用户）原样放行，不转换、不加链接。
    依赖 mcp 2.x 的 `_tool_manager.call_tool(name, arguments, context, convert_result=)` 与
    `Tool.fn_metadata.convert_result`；SDK 改了这两处，tests/test_textscript.py 的内存客户端用例会红。
    """

    output_script: str = SIMPLIFIED

    async def call_tool(self, name: str, arguments: dict[str, Any], context: Context | None = None) -> Any:
        if context is None:
            context = Context(mcp_server=self, subscriptions=self._subscriptions)
        tool = self._tool_manager.get_tool(name)
        if tool is None:
            return await super().call_tool(name, arguments, context)
        token = _CURRENT_CONTEXT.set(context)
        try:
            raw = await self._tool_manager.call_tool(name, arguments, context, convert_result=False)
        finally:
            _CURRENT_CONTEXT.reset(token)
        if isinstance(raw, mcp_types.InputRequiredResult):
            return raw
        if self.output_script != SIMPLIFIED and name not in UNLOCALIZED_TOOLS:
            # 一份结果可达数百 KB 文本（合参 / 调度会带多个技法），转换放进线程，别卡住事件循环上的 ping / cancel。
            raw = await anyio.to_thread.run_sync(localize, raw, self.output_script)
        protocol = context.protocol_version if context._request_context is not None else None
        return _with_file_link(raw, tool.fn_metadata.convert_result(raw), str(protocol or ""))


# resource_link 内容块随 MCP 2025-06-18 修订进入规范。只给协商到该修订或更新的客户端：更早的客户端按旧联合类型
# 校验整个结果，多一个不认识的块可能让整条结果作废（与 outputSchema 让 Claude Code 工具列表消失同一类风险）。
RESOURCE_LINK_SINCE = "2025-06-18"


def _with_file_link(raw: Any, converted: Any, protocol: str) -> Any:
    """报告类工具（结果里有 `file` 文件卡）在 JSON 正文之外再附一个 resource_link，客户端可直接打开 / 附带文件。"""
    card = raw.get("file") if isinstance(raw, dict) else None
    if not isinstance(card, dict) or not card.get("uri") or not protocol or protocol < RESOURCE_LINK_SINCE:
        return converted
    link = mcp_types.ResourceLink(type="resource_link", uri=card["uri"], name=str(card.get("name") or "report"),
                                  mime_type=card.get("mime"), size=card.get("bytes"))
    if isinstance(converted, mcp_types.CallToolResult):
        return converted.model_copy(update={"content": [*converted.content, link]})
    return [*converted, link]

