"""手工件（curated / 自上游抽出的 bespoke）的源 sha 守卫（scripts/revendor_core_js.py）。

v3.9.4 真值校准的两处修正静默滞留了四轮同步：`liureng/LRConst.js`（curated）六亲表两格、
`ziwei/zwLuckItems.js`（bespoke，抽自 ZWLuckPanel.js）的干支年基准。`--from-manifest` 对非 verbatim
条目只断言「名字还在」（extracts 仍导出 / 上游无同名文件），内容漂移零信号；`manifest_drift()`
更是直接跳过它们，于是 `verify_upstream_sync` 对手工件永远是绿的。现在每个手工件都记最近一次
人工核对时上游源文件的 sha256：源一动即红，复核后 `--restamp` 才灭。
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "revendor_core_js.py"
_spec = importlib.util.spec_from_file_location("revendor_core_js", _SCRIPT)
rv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rv)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_curated_entry_without_a_stamp_is_a_problem(tmp_path: Path) -> None:
    (tmp_path / "a.js").write_text("export const X = 1;\n", encoding="utf-8")
    problem = rv.hand_made_drift(tmp_path, "v/a.js", {"mode": "curated", "upstream": "a.js", "extracts": []})
    assert problem and "unstamped" in problem and "--restamp v/a.js" in problem


def test_curated_entry_with_a_matching_stamp_is_quiet(tmp_path: Path) -> None:
    (tmp_path / "a.js").write_text("export const X = 1;\n", encoding="utf-8")
    entry = {"mode": "curated", "upstream": "a.js", "extracts": [], "upstream_sha256": _sha("export const X = 1;\n")}
    assert rv.hand_made_drift(tmp_path, "v/a.js", entry) is None


def test_curated_entry_goes_red_when_the_upstream_source_moves(tmp_path: Path) -> None:
    """LRConst.js 的形状：上游改了两格常量，vendored 子集还是旧值——必须有人被叫去复核。"""
    entry = {"mode": "curated", "upstream": "a.js", "extracts": [], "upstream_sha256": _sha("'乙': '父母',\n")}
    (tmp_path / "a.js").write_text("'乙': '子孙',\n", encoding="utf-8")
    problem = rv.hand_made_drift(tmp_path, "v/a.js", entry)
    assert problem and "changed upstream since the last audit" in problem and "--restamp v/a.js" in problem


def test_bespoke_without_derived_from_is_unwatched_by_declaration(tmp_path: Path) -> None:
    assert rv.hand_made_drift(tmp_path, "v/b.js", {"mode": "bespoke", "why": "skill-authored"}) is None
    assert rv.watched_source({"mode": "verbatim", "upstream": "x.js"}) is None


def test_bespoke_with_derived_from_is_watched_like_curated(tmp_path: Path) -> None:
    """zwLuckItems.js 的形状：bespoke 的 basename 检查永远过（上游没有同名文件），但它抽出的
    ZWLuckPanel.js 一动，抽出件就可能落后——derived_from 把这条边接上。"""
    (tmp_path / "Panel.js").write_text("old\n", encoding="utf-8")
    entry = {"mode": "bespoke", "derived_from": "Panel.js", "derived_sha256": _sha("old\n")}
    assert rv.hand_made_drift(tmp_path, "v/items.js", entry) is None
    (tmp_path / "Panel.js").write_text("new\n", encoding="utf-8")
    problem = rv.hand_made_drift(tmp_path, "v/items.js", entry)
    assert problem and problem.startswith("v/items.js: BESPOKE source Panel.js changed upstream")


def test_a_vanished_upstream_source_is_reported_not_ignored(tmp_path: Path) -> None:
    problem = rv.hand_made_drift(tmp_path, "v/a.js", {"mode": "curated", "upstream": "gone.js", "upstream_sha256": "x"})
    assert problem and "gone upstream" in problem


def test_manifest_drift_no_longer_skips_hand_made_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """以前 `manifest_drift()` 对非 verbatim 直接 continue —— verify_upstream_sync 的 check 3 对它们恒绿。"""
    (tmp_path / "a.js").write_text("export const X = 1;\n", encoding="utf-8")
    monkeypatch.setattr(rv, "load_manifest", lambda: {"v/a.js": {"mode": "curated", "upstream": "a.js", "extracts": []}})
    out = rv.manifest_drift(tmp_path)
    assert out and "v/a.js: CURATED entry is unstamped" in out[0]


def test_real_manifest_stamps_every_hand_made_entry() -> None:
    """守卫只对「声明了源」的条目起作用；本仓的 6 个 curated 与 7 个抽出型 bespoke 必须全部打上戳。"""
    files = json.loads(rv.MANIFEST.read_text(encoding="utf-8"))["files"]
    hand_made = {k: e for k, e in files.items() if rv.watched_source(e)}
    assert {k for k, e in files.items() if e.get("mode") == "curated"} <= set(hand_made)
    for vendor_rel, entry in hand_made.items():
        _rel, field = rv.watched_source(entry)
        stamp = entry.get(field) or ""
        assert len(stamp) == 64 and all(c in "0123456789abcdef" for c in stamp), f"{vendor_rel}: {field} 未打戳"
    # 两个真事故的当事文件必须在受看守之列。
    assert files["liureng/LRConst.js"]["mode"] == "curated"
    assert files["ziwei/zwLuckItems.js"].get("derived_from") == "components/ziwei/ZWLuckPanel.js"
