"""doctor 报出数据目录 / 记忆库对本机其他用户可读（审计 O-05）。只报不改，不让 doctor 因此 ok:false。

修前：~/.horosa-skill 0755、memory.db 与存档 0644（同机别的账户能读到姓名、出生时刻地点、问题与解读），报告却是 0600；doctor 不提。
缺省改成 0700 / 0600 与「容器卷上别的进程要读」（test_memory_durability.test_new_artifacts_keep_the_umask_mode）冲突，待用户定；这里只做可见。
负向对照（实跑过）：data_privacy_report 恒返回空 flagged → 第一个用例红。
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from horosa_skill.runtime.manager import data_privacy_report

pytestmark = pytest.mark.skipif(os.name == "nt", reason="[platform] Windows 走 ACL，不查")


class _S:
    def __init__(self, root: Path) -> None:
        self.data_dir = root
        self.db_path = root / "memory.db"


def test_world_readable_data_dir_is_flagged_with_the_fix(tmp_path: Path) -> None:
    root = tmp_path / "data"
    root.mkdir()
    (root / "memory.db").write_bytes(b"")
    root.chmod(0o755)
    (root / "memory.db").chmod(0o644)
    report = data_privacy_report(_S(root))
    assert report["readable_by_others"] is True
    assert {item["what"] for item in report["flagged"]} == {"data_dir", "memory_db"}
    assert report["fix"] == f"chmod 700 '{root}'"


def test_private_data_dir_is_quiet(tmp_path: Path) -> None:
    root = tmp_path / "data"
    root.mkdir()
    (root / "memory.db").write_bytes(b"")
    root.chmod(0o700)
    (root / "memory.db").chmod(0o600)
    report = data_privacy_report(_S(root))
    assert report["readable_by_others"] is False and report["fix"] is None
