"""续读只回正文（审计 O-11：horosa_memory_show(response_sections=…) 每次带约 8 KB 与正文无关的信封，同一份输入出现 4 遍）。

负向对照（实跑过）：_shape_memory 里不走 _continuation_shape → 第一条红。
"""
from __future__ import annotations

import json
from pathlib import Path

from test_result_view_catalogue import call_all, mcp_server, offline_service

from horosa_skill.testing_payloads import build_sample_payloads


def test_a_continuation_read_returns_only_the_text(tmp_path: Path) -> None:
    service = offline_service(tmp_path)
    run_id = service.run_tool("sixyao", build_sample_payloads()["sixyao"], save_result=True).memory_ref.run_id
    mcp = mcp_server(service)
    (_, cont_bytes, cont), (_, full_bytes, full) = call_all(mcp, [
        ("cont", ("horosa_memory_show", {"run_id": run_id, "response_tool": "sixyao", "response_sections": [2]})),
        ("whole", ("horosa_memory_show", {"run_id": run_id})),
    ])
    body = json.loads(cont)
    result = body["result"]
    assert result["continuation"] is True and result["run_id"] == run_id and result["tool"] == "sixyao"
    assert set(result) == {"run_id", "continuation", "tool", "export_snapshot"}, set(result)
    assert result["export_snapshot"]["export_text"].startswith("[")
    assert "subject" not in cont and "tool_calls" not in cont and cont_bytes < full_bytes / 2, (cont_bytes, full_bytes)
    assert "tool_calls" in json.loads(full)["result"]     # 不点段的读回照旧是整条记录
