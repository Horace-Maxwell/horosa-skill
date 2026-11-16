"""命主档案导出 / 导入的 MCP 入口（审计待决项 8）：导出写成 0600 文件只回路径；导入先预演、带 confirm_token 才写；坏一条一条不写。

负向对照（实跑过）：_profile_transfer 不校验 token → 第二条红；导出把出生数据内联进结果 → 第一条红。
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest
from test_memory_facades import _cli_service

from horosa_skill.errors import ToolValidationError

MOM = {"date": "1960-03-01", "time": "08:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gender": 0}


def test_export_writes_a_private_file_and_returns_only_names(tmp_path: Path) -> None:
    service = _cli_service(tmp_path)
    service.profile({"action": "save", "name": "妈妈", "data": MOM})
    out = service.profile({"action": "export"})
    path = Path(out["path"])
    assert out["names"] == ["妈妈"] and "1960-03-01" not in json.dumps(out, ensure_ascii=False)
    assert json.loads(path.read_text(encoding="utf-8"))["profiles"][0]["name"] == "妈妈"
    if os.name != "nt":  # Windows 没有 POSIX 权限位（chmod 只设只读标志，私密靠用户目录 ACL）；windows-smoke 在这里拿到 0o666
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_import_previews_and_needs_the_token(tmp_path: Path) -> None:
    source = _cli_service(tmp_path / "a")
    source.profile({"action": "save", "name": "妈妈", "data": MOM})
    exported = Path(source.profile({"action": "export"})["path"])
    target = _cli_service(tmp_path / "b")
    copy = Path(target.store.output_dir) / "exports" / "p.json"
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.write_bytes(exported.read_bytes())
    preview = target.profile({"action": "import", "data": {"path": str(copy)}})
    assert preview["mode"] == "preview" and preview["would_add"] == ["妈妈"] and preview["must_ask_user"] is True
    assert target.profile({"action": "list"})["count"] == 0
    with pytest.raises(ToolValidationError) as caught:
        target.profile({"action": "import", "data": {"path": str(copy), "overwrite": True, "confirm_token": preview["confirm_token"]}})
    assert caught.value.code == "profile.import_token_invalid"
    done = target.profile({"action": "import", "data": {"path": str(copy), "confirm_token": preview["confirm_token"]}})
    assert done["imported"] == ["妈妈"] and target.profile({"action": "list"})["count"] == 1


def test_import_refuses_paths_outside_the_output_roots(tmp_path: Path) -> None:
    service = _cli_service(tmp_path)
    outside = tmp_path / "elsewhere.json"
    outside.write_text("{}", encoding="utf-8")
    with pytest.raises(ToolValidationError) as caught:
        service.profile({"action": "import", "data": {"path": str(outside)}})
    assert caught.value.code == "report.output_path_not_allowed"
