"""脚手架启动器绝不「成功什么都不做」（v0.38.1 R19）。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]


def test_windows_scaffold_launcher_fails_loudly(tmp_path: Path) -> None:
    completed = subprocess.run(
        [sys.executable, str(PKG_ROOT / "scripts" / "scaffold_windows_runtime.py"), "--output", str(tmp_path), "--version", "0.0.1"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    assert completed.returncode == 0, completed.stderr
    start = (tmp_path / "runtime-payload" / "Horosa-Web" / "start_horosa_local.ps1").read_text(encoding="utf-8-sig")
    stop = (tmp_path / "runtime-payload" / "Horosa-Web" / "stop_horosa_local.ps1").read_text(encoding="utf-8-sig")
    for script in (start, stop):
        assert "exit 3" in script and "exit 0" not in script, script
        assert "Write-Error" in script and "scaffold" in script
