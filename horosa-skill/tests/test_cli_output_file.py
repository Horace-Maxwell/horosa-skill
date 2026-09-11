"""`--output <file>` on the payload commands (v0.38.0 B0).

stdout stays the JSON contract; the file is an additional UTF-8 copy for shells whose pipes re-encode
bytes (Windows PowerShell 5.1 pipes native output through the console code page, so CJK in a piped
envelope is mangled before an agent reads it). ci.yml's Windows smoke had been calling
`tool run … --output` since v0.30 while the option did not exist — see tests/test_ci_workflow_shape.py.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from horosa_skill.surfaces import cli


def test_emit_json_writes_utf8_file_and_keeps_stdout_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "nested" / "out.json"
    cli._emit_json({"ok": True, "snapshot": "戊午 · 值符天蓬"}, target)
    written = json.loads(target.read_bytes().decode("utf-8"))
    assert written["snapshot"] == "戊午 · 值符天蓬"
    printed = json.loads(capsys.readouterr().out)
    assert printed == written


def test_emit_json_without_output_only_prints(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli._emit_json({"ok": False}, None)
    assert json.loads(capsys.readouterr().out) == {"ok": False}
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("command", [cli.tool_run, cli.dispatch, cli.ask, cli.hecan])
def test_every_payload_command_accepts_output(command) -> None:
    assert "output" in inspect.signature(command).parameters, f"{command.__name__} lost --output"
