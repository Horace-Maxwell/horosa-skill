"""tools/list 预算的尺子量的必须是线上真发的东西（sync 3.14.0 budget 批）。

`verify_mcp_list_budget.py` 曾按 `model_dump(exclude_unset=True)` 量：`MCPServer.list_tools` 把 `output_schema` / `icons` / `_meta`
显式传成 None，`exclude_unset` 剔不掉，每个工具多算三个线上并不存在的 null（127 个工具 6 559 B）——硬顶只剩 2.6 KB 的那一轮，
其实还有 9.1 KB。这里起一个真 stdio 子进程，把 tools/list 帧里的 tools 数组与尺子的 `wire_shape` 逐项比：尺子多算、少算一个键都红。

负向对照（实跑过）：`wire_shape` 改回 `exclude_unset=True` → `test_the_ruler_measures_exactly_what_goes_over_stdio` 红在
「尺子多出的键」那一行（127 个工具各多 `outputSchema` / `icons`，123 个多 `_meta`）。
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces.mcp_server import create_mcp_server

PKG_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PKG_ROOT / "scripts" / "verify_mcp_list_budget.py"
# 会改变工具面 / 说明书的开关：子进程按缺省面起，不许从跑测试的 shell 里继承。
_SURFACE_ENV = ("HOROSA_MCP_COMPACT", "HOROSA_TOOLSETS", "HOROSA_OUTPUT_SCHEMA", "HOROSA_JEV", "HOROSA_TRACE_OTLP_ENDPOINT",
                "HOROSA_OUTPUT_SCRIPT")


def _verifier():
    spec = importlib.util.spec_from_file_location("verify_mcp_list_budget_wire_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _stdio_tools(tmp_path: Path, *, compact: bool) -> tuple[list[dict], bytes]:
    """真 stdio 子进程回的 tools/list：解析后的 tools 数组 + 原始帧（一行）。"""
    env = {key: value for key, value in os.environ.items() if key not in _SURFACE_ENV}
    env.update({
        "HOROSA_RUNTIME_ROOT": str(tmp_path / "runtime"), "HOROSA_SKILL_DATA_DIR": str(tmp_path / "data"),
        "HOROSA_SERVER_ROOT": "http://127.0.0.1:9", "HOROSA_CHART_SERVER_ROOT": "http://127.0.0.1:9",
        "HOROSA_TRACE_ENABLED": "0", "PYTHONIOENCODING": "utf-8", **({"HOROSA_MCP_COMPACT": "1"} if compact else {}),
    })
    frames = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "budget-wire", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    # 不能一次把 stdin 喂完就关：stdin 一关服务器就收摊，tools/list 的回帧可能来不及写。逐帧写、读到 id=2 再收。
    process = subprocess.Popen(
        [sys.executable, "-m", "horosa_skill.surfaces.cli", "serve", "--transport", "stdio", "--skip-runtime-start"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env, cwd=str(PKG_ROOT),
    )
    found: list[bytes] = []

    def read_until_answer() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            if line.strip() and json.loads(line).get("id") == 2:
                found.append(line)
                return

    reader = threading.Thread(target=read_until_answer, daemon=True)
    reader.start()
    try:
        assert process.stdin is not None
        for frame in frames:
            process.stdin.write((json.dumps(frame) + "\n").encode("utf-8"))
            process.stdin.flush()
        reader.join(timeout=180)
    finally:
        process.kill()
        process.wait(timeout=30)
    assert found, "stdio 子进程 180 s 内没有回 tools/list"
    return json.loads(found[0])["result"]["tools"], found[0]


def _in_process(tmp_path: Path, verifier, *, compact: bool) -> list[dict]:
    settings = Settings(db_path=tmp_path / "ruler.db", output_dir=tmp_path / "runs", mcp_compact=compact)
    mcp = create_mcp_server(HorosaSkillService(settings, store=MemoryStore(settings)), settings)
    return [verifier.wire_shape(tool) for tool in asyncio.run(mcp.list_tools())]


@pytest.mark.parametrize("compact", [False, True], ids=["full", "compact"])
def test_the_ruler_measures_exactly_what_goes_over_stdio(tmp_path: Path, compact: bool) -> None:
    verifier = _verifier()
    wire, frame = _stdio_tools(tmp_path, compact=compact)
    ruler = _in_process(tmp_path, verifier, compact=compact)
    assert [tool["name"] for tool in ruler] == [tool["name"] for tool in wire]
    extra = {tool["name"]: sorted(set(tool) - set(sent)) for tool, sent in zip(ruler, wire, strict=True) if set(tool) - set(sent)}
    assert not extra, f"尺子多出的键（线上没有，白算字节）：{dict(list(extra.items())[:3])} … 共 {len(extra)} 个工具"
    missing = {tool["name"]: sorted(set(sent) - set(tool)) for tool, sent in zip(ruler, wire, strict=True) if set(sent) - set(tool)}
    assert not missing, f"线上有、尺子没算的键：{dict(list(missing.items())[:3])}"
    assert ruler == wire  # 逐工具逐键逐值
    assert b":null" not in frame and b": null" not in frame, "线上不该有 null 值；有了就说明 SDK 的写法变了，尺子要跟着重看"


def test_nulls_the_sdk_never_sends_are_not_counted() -> None:
    """尺子的单元对照：三个显式 None 的键不进字节数；真有值的 `_meta` 照算。"""
    from mcp import types as mcp_types

    verifier = _verifier()
    bare = mcp_types.Tool(name="t", description="d", input_schema={"type": "object"}, output_schema=None, icons=None, _meta=None)
    assert verifier.wire_shape(bare) == {"name": "t", "description": "d", "inputSchema": {"type": "object"}}
    tagged = mcp_types.Tool(name="t", input_schema={"type": "object"}, _meta={"anthropic/alwaysLoad": True})
    assert verifier.wire_shape(tagged)["_meta"] == {"anthropic/alwaysLoad": True}
