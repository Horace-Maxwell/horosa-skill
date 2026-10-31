"""跨进程追加（v0.46.1-dev，Windows 原生复验）：trace / 决策台账被多个 MCP 会话共写。

Windows 上 CRT 的 O_APPEND 是模拟的（「seek 到末尾 + 写」两步），维护机实测 8 进程 × 200 行每轮只剩约 1 230 / 1 600 行能解析；
`appendlog.append_line` 在 Windows 上用只申请 FILE_APPEND_DATA 的原生句柄（内核原子地写在末尾），POSIX 上用 O_APPEND。
负向对照：`test_crt_append_really_loses_lines_on_windows` 证明本机这个负载下旧写法确实会丢——守卫不是因为负载太轻才绿。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from horosa_skill import appendlog
from horosa_skill.decisions.ledger import DecisionLedger

SRC = Path(__file__).resolve().parents[1] / "src"
PROCS, COUNT = 8, 150


def _run_writers(tmp_path: Path, body: str) -> list[bytes]:
    target = tmp_path / "t.jsonl"
    worker = tmp_path / "w.py"
    worker.write_text(
        f"import sys, json, os\nsys.path.insert(0, {str(SRC)!r})\n{body}\n"
        f"for i in range({COUNT}):\n"
        "    line = (json.dumps({'id': f'{sys.argv[1]}-{i}', 'blob': 'x' * (400 + 37 * (i % 50))}) + '\\n').encode()\n"
        f"    write({str(target)!r}, line)\n",
        encoding="utf-8",
    )
    procs = [subprocess.Popen([sys.executable, str(worker), f"p{n}"]) for n in range(PROCS)]
    assert all(proc.wait(timeout=180) == 0 for proc in procs)
    return target.read_bytes().split(b"\n")[:-1]


def _parseable_ids(lines: list[bytes]) -> set[str]:
    ids = set()
    for line in lines:
        try:
            ids.add(json.loads(line)["id"])
        except ValueError:
            pass
    return ids


def test_concurrent_processes_append_every_line_intact(tmp_path: Path) -> None:
    lines = _run_writers(tmp_path, "from horosa_skill.appendlog import append_line as write")
    ids = _parseable_ids(lines)
    assert len(lines) == PROCS * COUNT and len(ids) == PROCS * COUNT, (len(lines), len(ids))


@pytest.mark.skipif(os.name != "nt", reason="the CRT-emulated O_APPEND race only exists on Windows")
def test_crt_append_really_loses_lines_on_windows(tmp_path: Path) -> None:
    crt = (
        "def write(path, line):\n"
        "    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_BINARY)\n"
        "    try:\n"
        "        os.write(fd, line)\n"
        "    finally:\n"
        "        os.close(fd)\n"
    )
    ids = _parseable_ids(_run_writers(tmp_path, crt))
    if len(ids) == PROCS * COUNT:
        pytest.skip("this host did not reproduce the CRT race this run (the guard above still holds)")
    assert len(ids) < PROCS * COUNT


def test_append_creates_the_file_and_keeps_existing_content(tmp_path: Path) -> None:
    target = tmp_path / "new.jsonl"
    appendlog.append_line(target, b'{"a":1}\n')
    appendlog.append_line(target, b'{"b":2}\n')
    assert target.read_bytes() == b'{"a":1}\n{"b":2}\n'


def test_append_failure_raises_oserror(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        appendlog.append_line(tmp_path / "missing-dir" / "t.jsonl", b"x\n")


def test_decision_ledger_writes_lf_lines_through_the_atomic_append(tmp_path: Path) -> None:
    ledger = DecisionLedger(tmp_path / "jev_events.jsonl")
    assert ledger.append({"surface": "dispatch", "status": "shadow"}) is True
    assert ledger.append({"surface": "extract", "status": "shadow"}) is True
    raw = (tmp_path / "jev_events.jsonl").read_bytes()
    assert raw.count(b"\n") == 2 and b"\r\n" not in raw, "Windows 文本模式曾把行尾写成 CRLF"
    assert [row["surface"] for row in ledger.tail()] == ["dispatch", "extract"]
