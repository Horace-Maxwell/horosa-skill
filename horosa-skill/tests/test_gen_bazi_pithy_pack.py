"""`generated_at` of the 八字断语 pack is the source file's last commit, so a shallow clone stamps its own history boundary.

2026-11-04（v3.13.2 再同步）：`git clone --depth 3` 把 2026-02-22 写成 2026-10-29；旧逻辑不报错，只有逐行读 diff 才看得见。
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gen_bazi_pithy_pack.py"
_spec = importlib.util.spec_from_file_location("gen_bazi_pithy_pack", SCRIPT)
pack = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pack)

OLD_DATE = "2026-02-22T18:12:59-08:00"


def _git(root: Path, *args: str, date: str | None = None) -> None:
    env = {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date} if date else {}
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        check=True, capture_output=True, env={"PATH": os.environ["PATH"], **env},
    )


@pytest.fixture
def upstream(tmp_path: Path) -> Path:
    """The pithy file changes in the first commit only; later commits touch something else (as in a real release)."""
    root = tmp_path / "upstream"
    target = root / pack.UPSTREAM_REL
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({"类": {"键": "文"}}, ensure_ascii=False), encoding="utf-8")
    _git(root.parent, "init", "-q", str(root))
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "pithy", date=OLD_DATE)
    for index in range(3):
        (root / "other.txt").write_text(str(index), encoding="utf-8")
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", f"later {index}", date=f"2026-11-0{index + 1}T00:00:00+00:00")
    return root


def test_full_history_stamps_the_files_real_last_commit(upstream: Path) -> None:
    assert pack.build(upstream)["generated_at"] == OLD_DATE


def test_shallow_clone_is_refused_instead_of_stamping_its_boundary(upstream: Path, tmp_path: Path) -> None:
    shallow = tmp_path / "shallow"
    subprocess.run(["git", "clone", "-q", "--depth", "2", upstream.as_uri(), str(shallow)], check=True, capture_output=True)
    with pytest.raises(SystemExit, match="shallow"):
        pack.build(shallow)
