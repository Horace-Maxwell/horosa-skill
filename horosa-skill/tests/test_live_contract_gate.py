"""`requires_current_runtime_contract`（tests/test_local_js_tools.py）的判定函数——纯函数，离线可测。

来历：Windows 维护机把 main（已同步上游 v3.11，`AI_EXPORT_SETTINGS_VERSION` 15）的 live 全套打到公开
v0.39.0 runtime（payload `export_registry_version` 14）上，6 条 sync311 / sanshiunited live 用例红——
它们钉的行为（castSeed 复现、地点行、派生盘标签、ephemeris 金标、三式合一的 `kook`）要下一版
runtime 才有。这不是回归而是偏斜；`requires_chart` 只看「有没有活的、显式点名的实例」，看不出
「实例够不够新」。托管矩阵每周一拿 main 打公开 latest，会以同样 6 条变红。
"""

from __future__ import annotations

import json
from pathlib import Path

from test_local_js_tools import installed_runtime_registry_version, runtime_contract_is_stale


def test_older_installed_payload_is_stale() -> None:
    assert runtime_contract_is_stale(installed=14, tree=15) is True


def test_equal_or_newer_payload_is_current() -> None:
    assert runtime_contract_is_stale(installed=15, tree=15) is False
    assert runtime_contract_is_stale(installed=16, tree=15) is False


def test_unknown_payload_never_skips() -> None:
    """外部 vendored 实例（没有已装 payload）→ 不知道就不跳过：vendored 树的新鲜度由 preflight/mirror 守卫另管。"""
    assert runtime_contract_is_stale(installed=None, tree=15) is False


def test_registry_version_is_read_from_the_installed_manifest(tmp_path: Path) -> None:
    current = tmp_path / "current"
    current.mkdir()
    (current / "runtime-manifest.json").write_text(json.dumps({"version": "0.39.0", "export_registry_version": 14}), encoding="utf-8")
    assert installed_runtime_registry_version(tmp_path) == 14
    assert installed_runtime_registry_version(tmp_path / "nowhere") is None
    (current / "runtime-manifest.json").write_text("{not json", encoding="utf-8")
    assert installed_runtime_registry_version(tmp_path) is None
