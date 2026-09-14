"""A stdio server must exit promptly once its client closes stdin — on every platform.

Why this exists (v0.38.1 post-release): the Windows CI OpenClaw smoke once timed out at 150 s although the captured
stdout already held the complete tool result (run 34893381989, attempt 1). mcporter documents exactly that symptom
("prints a tool response but the process never exits") and names the usual culprit: a child MCP server that keeps the
stdio transport alive. The TypeScript SDK starts the server with stderr inherited, so a server that lingers after EOF
also keeps the *caller's* captured pipe open. Nothing asserted that our server actually exits on EOF: the in-process
MCP tests bypass the transport, and the SDK-driven conformance tests would silently kill a lingering server on exit.

An orphaned `horosa-skill serve` is not cosmetic either: it stays registered as an attached client, so
`runtime stop` / `upgrade` refuse with `runtime.stop_refused_clients_attached` until it dies.

The spawn mirrors a real client: no `--skip-runtime-start` (the warm-up thread runs), initialize, one real tool call,
then close stdin and time the exit. On Windows `.venv\\Scripts\\python.exe` is a launcher with the interpreter as its
child, so the test also covers the extra process layer every uv-launched client has.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
EXIT_BUDGET_SECONDS = 15.0


def _pump(stream, sink: "queue.Queue[bytes | None]") -> None:
    for line in iter(stream.readline, b""):
        sink.put(line)
    sink.put(None)


def _await_response(lines: "queue.Queue[bytes | None]", request_id: int, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        assert remaining > 0, f"no JSON-RPC response for id={request_id} within {timeout:.0f}s"
        line = lines.get(timeout=remaining)
        assert line is not None, f"server closed stdout before answering id={request_id}"
        message = json.loads(line)
        if message.get("id") == request_id:
            return message


def _send(proc: subprocess.Popen, message: dict) -> None:
    assert proc.stdin is not None
    proc.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
    proc.stdin.flush()


def test_stdio_server_exits_promptly_after_the_client_closes_stdin(tmp_path: Path) -> None:
    from mcp.types import LATEST_PROTOCOL_VERSION

    env = {
        **os.environ,
        "HOROSA_RUNTIME_ROOT": str(tmp_path / "runtime"),
        "HOROSA_SKILL_DATA_DIR": str(tmp_path / "data"),
        "HOROSA_SERVER_ROOT": "http://127.0.0.1:9",
        "HOROSA_CHART_SERVER_ROOT": "http://127.0.0.1:9",
        "HOROSA_TRACE_ENABLED": "0",
        "PYTHONUNBUFFERED": "1",
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "horosa_skill.surfaces.cli", "serve", "--transport", "stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=str(PKG_ROOT),
    )
    stdout_lines: "queue.Queue[bytes | None]" = queue.Queue()
    stderr_lines: "queue.Queue[bytes | None]" = queue.Queue()
    readers = [
        threading.Thread(target=_pump, args=(proc.stdout, stdout_lines), daemon=True),
        threading.Thread(target=_pump, args=(proc.stderr, stderr_lines), daemon=True),
    ]
    for reader in readers:
        reader.start()
    try:
        _send(proc, {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": LATEST_PROTOCOL_VERSION, "capabilities": {},
                       "clientInfo": {"name": "stdin-eof-exit-test", "version": "0"}},
        })
        init = _await_response(stdout_lines, 1, timeout=90)
        assert "result" in init, init
        _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        _send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                     "params": {"name": "horosa_knowledge_registry", "arguments": {}}})
        call = _await_response(stdout_lines, 2, timeout=90)
        assert "result" in call, call

        closed_at = time.monotonic()
        assert proc.stdin is not None
        proc.stdin.close()
        try:
            proc.wait(timeout=EXIT_BUDGET_SECONDS + 30)
        except subprocess.TimeoutExpired:
            pass
        elapsed = time.monotonic() - closed_at
        stderr_tail = b"".join(line for line in list(stderr_lines.queue) if line)[-2000:].decode("utf-8", "replace")
        assert proc.returncode is not None, (
            f"the stdio server was still running {elapsed:.1f}s after its client closed stdin — every stdio client "
            f"(OpenClaw/mcporter, Claude Desktop, Cursor, Codex) would leave an orphan here. stderr tail:\n{stderr_tail}"
        )
        assert elapsed <= EXIT_BUDGET_SECONDS, (
            f"the stdio server took {elapsed:.1f}s to exit after stdin EOF (budget {EXIT_BUDGET_SECONDS:.0f}s; "
            f"the TypeScript SDK escalates to SIGTERM after 2 s). stderr tail:\n{stderr_tail}"
        )
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=30)
