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


def test_files_the_skill_cites_by_name_are_hits_too(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """v3.13.1 冬至日柱订正改在 preciseCalcBridge.js 的内部函数里，tools/qimen.js 只提文件名 → 名字级扫描零信号。
    负向对照：main() 里去掉 `hits.update(skill_file_hits(...))` → 真扫 965af0f4..06f25f21 时 file:… 命中全消失（实跑过）；
    这里钉住匹配规则本身：文件名 / ≥8 字驼峰主名算，短而泛的主名（timing）不算，没被提到的不算。"""
    root = tmp_path / "pkg"
    (root / "src").mkdir(parents=True)
    (root / "src" / "qimen.js").write_text("// 照 utils/preciseCalcBridge.js 的 fetchPreciseJieqiSeed\n", encoding="utf-8")
    (root / "src" / "enrich.py").write_text("# preciseCalcBridge.normalizeJieqiParams；timing 口径；见 helper.py\n", encoding="utf-8")
    monkeypatch.setattr(aup, "PKG_ROOT", root)
    monkeypatch.setattr(aup, "SCAN_ROOTS", (root / "src",))
    hits = aup.skill_file_hits([
        "Horosa-Web/astrostudyui/src/utils/preciseCalcBridge.js",
        "Horosa-Web/astropy/astrostudy/perchart_parts/timing.py",
        "Horosa-Web/astropy/astrostudy/helper.py",
        "Horosa-Web/astrostudyui/src/utils/unrelatedThing.js",
    ])
    assert hits == {
        "file:astrostudyui/src/utils/preciseCalcBridge.js": {"upstream": "changed", "skill_files": ["src/enrich.py", "src/qimen.js"]},
        "file:astropy/astrostudy/helper.py": {"upstream": "changed", "skill_files": ["src/enrich.py"]},
    }


def test_redrawn_report_boards_are_in_the_scan() -> None:
    """报告盘图适配器（app-charts/adapters）在扫描范围里：HTML 类盘图是照上游组件「重画」的 SVG，不跑上游代码，bundle pin 守卫
    管不到它的版式。v3.15.0 上游把奇门暗干挪到门上、主字换留白档、金口诀盘去掉文字描边，旧的扫描范围（只有 src/horosa_skill 与
    core-js tools|shared）一条都没报，盘图一直画旧样子。负向对照：去掉这一项，下面断言红；台账里这批结论随之成为「多余」。"""
    roots = {p.relative_to(aup.PKG_ROOT).as_posix() for p in aup.SCAN_ROOTS}
    assert "horosa-core-js/app-charts/adapters" in roots
    assert any(p.name == "qimen.js" for p in (aup.PKG_ROOT / "horosa-core-js" / "app-charts" / "adapters").iterdir())
