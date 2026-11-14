"""horosa_memory_manage（审计待决项 6）：MCP 面也能删 / 放回 / 导出 / 看用量；删除先预演、带 confirm_token 才删。

修前 Claude Desktop / MCPB 用户「把我妈的记录删掉」只能被告知去终端跑命令。
负向对照（实跑过）：不校验 token（任何 token 都删）→ 第二条红；不看 HOROSA_MEMORY_MCP_DELETE → 第四条红。
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from test_memory_facades import _cli_service, _ids, _run

from horosa_skill.errors import ToolValidationError


def test_delete_previews_first_and_needs_the_token(tmp_path: Path) -> None:
    service = _cli_service(tmp_path)
    mine = _run(service, name="王小明")
    preview = service.memory_manage({"action": "delete", "entity": "王小明"})
    assert preview["mode"] == "preview" and preview["must_ask_user"] is True and preview["plan"]["runs"] == 1
    assert _ids(service.query_memory({})) == [mine]                     # 预演什么都没动
    done = service.memory_manage({"action": "delete", "entity": "王小明", "confirm_token": preview["confirm_token"]})
    assert done["mode"] == "deleted" and done["deleted_runs"] == 1 and done["trash_id"]
    assert _ids(service.query_memory({})) == []
    back = service.memory_manage({"action": "restore", "trash_id": done["trash_id"]})
    assert back["restored_runs"] == 1 and _ids(service.query_memory({})) == [mine]


def test_a_token_for_another_selection_or_option_is_refused(tmp_path: Path) -> None:
    service = _cli_service(tmp_path)
    mine = _run(service, name="王小明")
    _run(service, name="李四")
    token = service.memory_manage({"action": "delete", "run_ids": [mine]})["confirm_token"]
    for payload in ({"action": "delete", "entity": "李四", "confirm_token": token},
                    {"action": "delete", "run_ids": [mine], "permanent": True, "confirm_token": token},
                    {"action": "delete", "run_ids": [mine], "confirm_token": "9999999999.deadbeef"}):
        with pytest.raises(ToolValidationError) as caught:
            service.memory_manage(payload)
        assert caught.value.code == "memory.manage.token_invalid" and caught.value.details["must_ask_user"] is True
    assert len(_ids(service.query_memory({}))) == 2


def test_an_expired_token_is_refused(tmp_path: Path, monkeypatch) -> None:
    service = _cli_service(tmp_path)
    mine = _run(service, name="王小明")
    token = service.memory_manage({"action": "delete", "run_ids": [mine]})["confirm_token"]
    later = time.time() + 601
    monkeypatch.setattr(time, "time", lambda: later)
    with pytest.raises(ToolValidationError) as caught:
        service.memory_manage({"action": "delete", "run_ids": [mine], "confirm_token": token})
    assert caught.value.code == "memory.manage.token_expired"


def test_delete_can_be_turned_off(tmp_path: Path) -> None:
    service = _cli_service(tmp_path)
    _run(service, name="王小明")
    service.settings.memory_mcp_delete = False
    with pytest.raises(ToolValidationError) as caught:
        service.memory_manage({"action": "delete", "entity": "王小明"})
    assert caught.value.code == "memory.manage.delete_disabled"
    service.settings.memory_mcp_delete = True
    service.settings.mcp_transport = "streamable-http"      # HTTP 且没有令牌：同样关
    with pytest.raises(ToolValidationError):
        service.memory_manage({"action": "delete", "entity": "王小明"})


def test_usage_and_export(tmp_path: Path) -> None:
    service = _cli_service(tmp_path)
    mine = _run(service, name="王小明")
    usage = service.memory_manage({"action": "usage"})
    assert usage["usage"]["runs"] == 1 and usage["trash_kept_days"] == 30
    exported = service.memory_manage({"action": "export", "run_ids": [mine]})
    assert exported["runs"] == 1 and Path(exported["index"]).is_file()
    with pytest.raises(ToolValidationError) as caught:
        service.memory_manage({"action": "delete"})
    assert caught.value.code == "memory.selection.missing"


def test_bad_payload_and_unknown_trash_batch(tmp_path: Path) -> None:
    service = _cli_service(tmp_path)
    with pytest.raises(ToolValidationError) as bad:
        service.memory_manage({"action": "wipe"})
    assert bad.value.code == "memory.manage.invalid_payload"
    with pytest.raises(ToolValidationError) as unknown:
        service.memory_manage({"action": "restore", "trash_id": "nope"})
    assert unknown.value.code == "memory.trash.unknown"
