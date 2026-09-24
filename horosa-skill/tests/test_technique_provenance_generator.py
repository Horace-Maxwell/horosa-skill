"""契约 == 生成器输出（AGENTS §5.10「输出幂等」）。

v0.40.0 前，`gen_technique_provenance.py` 只看 runner 本体，经 helper 调用的证据（神数心易 / 演禽、择日扫描端点、
世俗盘卡）和逐工具说明（bazi_inverse / guolao_chart）都是手改在契约里的；重跑生成器即被抹掉，还会把 bazi_inverse
误判成 python_chart_backend。另有 9 处契约反而落后于生成器（择日八键 export_technique 仍是 null）。现在这些知识
住在生成器里，本测试锁死两者逐字节一致。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gen_technique_provenance.py"


def test_committed_provenance_contract_equals_generator_output() -> None:
    proc = subprocess.run([sys.executable, str(SCRIPT), "--check"], capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr
