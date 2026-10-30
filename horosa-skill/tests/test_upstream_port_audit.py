"""scripts/audit_upstream_ports.py：手抄上游逻辑审计台账（v0.46.0 起）。

vendor 清单只看守 horosa-core-js/src/vendor 下的文件；skill 侧手抄的上游逻辑（Python 移植、tools/*.js 胶水、写死的
缺省值 / 文案 / 常量表）是没人看守的第二份真相 —— v3.13.0 同步时十余处静默过期。台账要求：两个上游 pin 之间
代码变了、且被 skill 提到的每个上游名字都有结论，且台账审到的 pin == 记录在案的上游 pin。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_upstream_ports.py"
_spec = importlib.util.spec_from_file_location("audit_upstream_ports", _SCRIPT)
aup = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aup)


def test_ledger_is_audited_to_the_recorded_upstream_pin() -> None:
    assert aup.check_ledger() == []


def test_a_stale_ledger_or_a_bogus_verdict_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """负向对照：台账 to ≠ 上游 pin、或结论不以四档开头 → 报问题。"""
    ledger = tmp_path / "ledger.json"
    provenance = tmp_path / "prov.json"
    provenance.write_text(json.dumps({"upstream_git_sha": "b" * 40}), encoding="utf-8")
    ledger.write_text(json.dumps({"from": "0" * 40, "to": "a" * 40, "reviewed": {"X_NAME": "looks fine"}}), encoding="utf-8")
    monkeypatch.setattr(aup, "LEDGER", ledger)
    monkeypatch.setattr(aup, "PROVENANCE", provenance)
    problems = aup.check_ledger()
    assert any("audited to aaaaaaaaaaaa" in p for p in problems)
    assert any("X_NAME" in p for p in problems)


def test_hits_are_names_that_skill_code_mentions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "pkg"
    (root / "src").mkdir(parents=True)
    (root / "src" / "port.py").write_text("# 上游 buildFooSnapshot（逐字移植）\nFOO_TABLE = {}\n", encoding="utf-8")
    monkeypatch.setattr(aup, "PKG_ROOT", root)
    monkeypatch.setattr(aup, "SCAN_ROOTS", (root / "src",))
    hits = aup.skill_hits([("buildFooSnapshot", "changed"), ("FOO_TABLE", "removed"), ("msg", "changed"), ("UNUSED_X", "changed")])
    assert set(hits) == {"buildFooSnapshot", "FOO_TABLE"}  # 短 / 全小写名不计；没被提到的不计
    assert hits["FOO_TABLE"] == {"upstream": "removed", "skill_files": ["src/port.py"]}
