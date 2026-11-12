"""服务层的调用作用域：logger、降级说明收集器（_degrade → envelope.warnings）、自然语言原话、进度上报与取消检查点。"""
from __future__ import annotations

import contextlib
import contextvars
import logging
from collections.abc import Iterator
from typing import Any

from horosa_skill.errors import bilingual

logger = logging.getLogger("horosa_skill.service")  # 显式名：模块拆进子包后日志名不变

# ---- 降级说明收集器（v0.36.0 A2）----
# 35 处「富化失败不许带崩主盘」的 except 分支此前只写 logger.warning：日志里有、信封里没有，agent 看到的是
# ok=True + warnings=[] + 少几段——静默降级。`_degrade` 把同一句话同时写日志并投进当前 run_tool 的收集器，
# 出信封时并入 envelope.warnings；嵌套 run_tool（三式合一/合参）的说明冒泡到外层。守卫：
# scripts/verify_silent_degrades.py（包内 `_degrade(` 计数棘轮，基线 0——降级点一律走 `_degrade`）。
_DEGRADE_NOTES: contextvars.ContextVar[list[str] | None] = contextvars.ContextVar("horosa_degrade_notes", default=None)
# 当前 run_tool 的自然语言原话（dispatch 传入的 query_text）：决策层的门类分类要读它，runner 签名不变。
_RUN_QUERY_TEXT: contextvars.ContextVar[str | None] = contextvars.ContextVar("horosa_run_query_text", default=None)


@contextlib.contextmanager
def _run_query_scope(query_text: str | None) -> Iterator[None]:
    token = _RUN_QUERY_TEXT.set(query_text)
    try:
        yield
    finally:
        _RUN_QUERY_TEXT.reset(token)


# ---- 调用深度与展示键（v0.50.0-dev，F4）----
# runner 会拿自己的载荷再调一次 `run_tool` 拼子盘（择日的展示盘、三式合一的奇门 / 太乙、七政的果老盘）。
# 「返回体长什么样」的键不是算法输入：跟着载荷进了子调用，子信封就被裁掉快照，外层读到空串（黄历择日
# 14 段里 7 段变成占位文字）。规则只有一条、只在一处：进入嵌套的 run_tool 时摘掉这些键，视图只裁最外层的信封。
PRESENTATION_KEYS: tuple[str, ...] = ("response_view",)
_RUN_TOOL_DEPTH: contextvars.ContextVar[int] = contextvars.ContextVar("horosa_run_tool_depth", default=0)


@contextlib.contextmanager
def _run_tool_scope() -> Iterator[int]:
    """一次 run_tool 的作用域；给出深度（1 = 调用方直接调的那一次，>1 = runner 里拼子盘的调用）。"""
    depth = _RUN_TOOL_DEPTH.get() + 1
    token = _RUN_TOOL_DEPTH.set(depth)
    try:
        yield depth
    finally:
        _RUN_TOOL_DEPTH.reset(token)


def run_tool_depth() -> int:
    return _RUN_TOOL_DEPTH.get()


def without_presentation_keys(payload: Any) -> Any:
    """子调用的载荷：去掉只管返回体形状的键（非 dict 原样返回，交给后面的校验去报错）。"""
    if not isinstance(payload, dict) or not any(key in payload for key in PRESENTATION_KEYS):
        return payload
    return {key: value for key, value in payload.items() if key not in PRESENTATION_KEYS}


def _degrade(fmt: str, *args: Any, note: str | None = None) -> str:
    """记一次优雅降级：日志一句 + 当前工具调用的收集器一条（→ envelope.warnings）。返回给调用方的说明。"""
    message = (fmt % args) if args else fmt
    logger.log(logging.WARNING, "%s", message)
    text = note or f"降级：{message}——相关段落缺席，其余结果仍可用。"
    notes = _DEGRADE_NOTES.get()
    if notes is not None and text not in notes:
        notes.append(text)
    return text


# 存档是旁路：写不进本地记忆不许丢掉已经算好的结果。run_tool 与 dispatch 的存档块都走这里，warnings 带这个码。
MEMORY_SAVE_FAILED = "memory.save_failed"


def _memory_save_failed(exc: Exception) -> str:
    """记一次存档失败，返回要放进 warnings 的那句话（结果照回，memory_ref=None）。"""
    reason = f"{type(exc).__name__}: {exc}"
    note = f"{MEMORY_SAVE_FAILED}: " + bilingual(
        f"这次结果没写进本地记忆（{reason}），所以没有 run_id；结果本身完整可用。",
        f"this result was not saved to local memory ({reason}), so there is no run_id; the result itself is complete.",
    )
    return _degrade("memory save failed: %s", reason, note=note)


# ---- 进度上报与取消检查点（v0.37.0 C6）----
# 分段扫描一次可跑 60 次后端请求、几分钟墙钟；这期间客户端**什么也看不到**，只能干等或按超时掐断
# （Codex 的 tool_timeout_sec 默认 60 秒，Cursor/VS Code 也各有默认）。ContextVar 让表层注入一个
# tick 回调，服务层每完成一段调一次；没人注入时是 no-op（CLI/测试路径零开销、零行为变化）。
# tick 同时是**取消检查点**：MCP 侧的实现先调 `anyio.from_thread.check_cancelled()`，客户端撤单后
# 下一段边界就抛 CancelledError（BaseException，不会被下面的 except Exception 吞掉），长扫描因此
# 能在段边界停下，而不是把剩下 50 次后端请求全跑完才发现没人要结果。
_TOOL_PROGRESS: contextvars.ContextVar[Any | None] = contextvars.ContextVar(
    "horosa_tool_progress", default=None
)


@contextlib.contextmanager
def progress_sink(tick: Any) -> Iterator[None]:
    """在本作用域内把进度回调交给服务层（表层用；tick 签名 (done, total, label)）。"""
    token = _TOOL_PROGRESS.set(tick)
    try:
        yield
    finally:
        _TOOL_PROGRESS.reset(token)


def _progress_tick(done: int, total: int, label: str) -> None:
    """报一次进度。未注入回调即 no-op；回调自身出错绝不能带崩正在跑的计算。"""
    tick = _TOOL_PROGRESS.get()
    if tick is None:
        return
    try:
        tick(done, total, label)
    except Exception:  # noqa: BLE001 - 进度是旁路，取消走 BaseException 不经此处
        logger.debug("progress tick failed", exc_info=True)


# ---- 出报告时补算盘图的旁路（v0.49.0-dev）----
# 报告要画的某些盘，runner 算的时候手上有、却不进结果（七政 Moira 规则全集 + 流年盘：结果只留正文用的那几键）。出报告时
# 在这个作用域里重跑同一工具（save_result=False），runner 把那几样交到这里；作用域外是 no-op —— 工具调用的返回体与存档不变。
_FIGURE_CAPTURE: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar("horosa_figure_capture", default=None)


@contextlib.contextmanager
def figure_capture() -> Iterator[dict[str, Any]]:
    captured: dict[str, Any] = {}
    token = _FIGURE_CAPTURE.set(captured)
    try:
        yield captured
    finally:
        _FIGURE_CAPTURE.reset(token)


def _capture_figure_data(key: str, value: Any) -> None:
    captured = _FIGURE_CAPTURE.get()
    if captured is not None:
        captured[key] = value


@contextlib.contextmanager
def _degrade_collector() -> Iterator[list[str]]:
    """一次 run_tool 的降级说明作用域；退出时冒泡到外层调用（嵌套工具的缺段外层也要知道）。"""
    parent = _DEGRADE_NOTES.get()
    notes: list[str] = []
    token = _DEGRADE_NOTES.set(notes)
    try:
        yield notes
    finally:
        _DEGRADE_NOTES.reset(token)
        if parent is not None:
            parent.extend(item for item in notes if item not in parent)
