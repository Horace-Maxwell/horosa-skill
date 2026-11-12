"""调度的说明行写「原文见 results.<tool>.warnings」：这条路径在每个面上都得是真的（v0.50.0 深审余项）。

面：service / CLI 的整份信封、存档里的调度产物、MCP 阅读视图、horosa_memory_show 的阅读视图。此前 memory_show 的阅读视图把调度产物
里的 results 换成 {ok, see} 占位——说明行照抄进去，指的键却不存在。现在占位里留着 warnings。
负向对照（实跑过）：result_view 占位去掉 warnings → memory_show 用例红。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fakes import FakeClient, FakeJsClient

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.result_view import READING, Budget, ViewRequest, shape_result
from horosa_skill.service import HorosaSkillService

POINTER = "results.<tool>.warnings"


def _service(tmp_path: Path) -> HorosaSkillService:
    settings = Settings(server_root="http://127.0.0.1:9", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs")
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())


def _assert_pointer_true(view: dict[str, Any]) -> None:
    line = next(w for w in view["warnings"] if POINTER in w)
    named = re.findall(r"(?:—|；)\s*([a-z_0-9]+)：", line)
    assert named, line
    for tool in named:
        assert view["results"][tool]["warnings"], (tool, view["results"][tool])


def test_dispatch_warning_pointer_is_true_on_every_surface(tmp_path: Path) -> None:
    service = _service(tmp_path)
    envelope = service.dispatch({
        "query": "看看我的八字", "save_result": True, "agent_confirmed_settings": True,
        "birth": {"date": "1990年5月3日", "time": "8点半", "zone": "东八区", "lat": "31n13", "lon": "121e28", "gender": 1},
    })
    full = envelope.model_dump(mode="json")
    _assert_pointer_true(full)                                                          # service / CLI（CLI 打印同一份 model_dump）
    _assert_pointer_true(json.loads(Path(envelope.memory_ref.artifact_path).read_text(encoding="utf-8")))  # 存档
    budget = Budget(max_tokens=40_000, max_chars=48_000)
    _assert_pointer_true(shape_result(full, ViewRequest(view=READING), budget))         # MCP 阅读视图
    shown = shape_result(service.show_memory({"run_id": envelope.memory_ref.run_id, "include_payload": True}),
                         ViewRequest(view=READING), budget)                             # horosa_memory_show
    record = shown.get("result") or shown
    dispatch = next(a for a in record["artifacts"] if a.get("kind") == "dispatch_result")
    _assert_pointer_true(dispatch["payload"])
