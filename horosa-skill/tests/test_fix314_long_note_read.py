"""读一条长的自备笔记（不带翻页参数）：首页能到模型手里，翻页指针还在（审计 O-03）。

修前：27,636 字的笔记 {"domain":"user","key":"奇門筆記"} → data: {"omitted":"omitted_for_model_budget","chars":27636}，warnings 让加
response_view="full"；正确做法 from_line / max_lines 没提，next_from_line 也被一起丢了。根因：一页 20,000「字」而预算按 token 算，
正文在结果里有三份（lines / text / rendered_text）。
负向对照（实跑过）：READ_MAX_CHARS 改回 20_000 → 红。
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces.mcp_server import create_mcp_server


def test_the_first_page_of_a_long_note_reaches_the_model_with_its_page_pointer(tmp_path: Path) -> None:
    notes = tmp_path / "notes"
    notes.mkdir()
    body = ["# 奇門筆記"] + [f"第{i}行：" + "值符值使八门九星天盘地盘三奇六仪" * 3 for i in range(1, 520)]
    (notes / "奇門筆記.md").write_text("\n".join(body), encoding="utf-8")
    settings = Settings(server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9", data_dir=tmp_path,
                        runtime_root=tmp_path / "runtime", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs",
                        trace_enabled=False, user_knowledge_dir=notes)
    service = HorosaSkillService(settings, store=MemoryStore(settings))
    result = asyncio.run(create_mcp_server(service, settings).call_tool("horosa_knowledge_read", {"domain": "user", "key": "奇門筆記"}))
    result = getattr(result, "content", result)
    blocks = result[0] if isinstance(result, tuple) else result
    data = json.loads(blocks[0].text)["data"]
    assert "omitted" not in data, data
    assert data["next_from_line"] > 1 and data["total_lines"] == 520 and "第1行" in data["text"]
