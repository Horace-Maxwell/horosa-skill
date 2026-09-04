"""响应体预算守卫（v0.36.0 A1）——堵「导出段 data 逐段整份复制」这一类放大。

事故原文：`_pick_section_data` 兜底 `return response_data`，`_build_generated_export_snapshot` 把它塞进
每个段的 `data` → 真实存档 qimen 5.07 MB（正文 2.9 KB，550:1）、india_chart 101 MB；行数守卫只数行，
单行 JSON dump 漏进 export_text。此前唯一的反膨胀测试只数文本探针出现次数，对 `data` 一字不提。

这里三条守卫都是**结构性**的（不依赖夹具大小）：段不带 data、引擎对象只出现一次、信封字节数被内容
（data 基线 + 3×正文）封顶。
"""

from __future__ import annotations

import json

import pytest
from test_service import FakeClient, FakeJsClient

from horosa_skill.config import Settings
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import TOOL_EXPORT_TECHNIQUE_MAP, HorosaSkillService, _build_generated_export_snapshot
from horosa_skill.testing_payloads import build_sample_payloads


def _service(tmp_path) -> HorosaSkillService:
    settings = Settings(
        server_root="http://127.0.0.1:9999", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs"
    )
    return HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())


@pytest.mark.parametrize(
    ("tool", "engine_key"),
    [("qimen", "pan"), ("chart", "chart"), ("liureng_gods", "liureng"), ("bazi_birth", "bazi")],
)
def test_export_sections_carry_body_only_and_engine_data_once(tmp_path, tool: str, engine_key: str) -> None:
    service = _service(tmp_path)
    result = service.run_tool(tool, build_sample_payloads()[tool], save_result=False)
    assert result.ok is True, result.error
    export = result.data["export_snapshot"]
    assert export["sections"], "导出段不能为空"
    for section in export["sections"]:
        assert set(section) == {"index", "raw_title", "title", "included", "body"}, section.keys()
    engine_obj = result.data.get(engine_key)
    if engine_obj is None:
        pytest.skip(f"{tool} 的样例响应没有 {engine_key} 键（桩形状不同）")
    probe = json.dumps(engine_obj, ensure_ascii=False, sort_keys=True)
    serialized = json.dumps(result.data, ensure_ascii=False, sort_keys=True)
    assert serialized.count(probe) == 1, f"{engine_key} 引擎对象在响应体里出现了 {serialized.count(probe)} 次，应恰 1 次"


def test_every_technique_envelope_is_bounded_by_its_content(tmp_path) -> None:
    """全工具循环：信封字节 ≤ 基线（data 去掉 export_snapshot/snapshot_text）+ 3×正文 + 16 KB 松量。
    正文合法地存三份（snapshot_text / export_text / 段 body），再多就是放大。"""
    service = _service(tmp_path)
    payloads = build_sample_payloads()
    violations: list[str] = []
    checked = 0
    for tool in sorted(TOOL_EXPORT_TECHNIQUE_MAP):
        if tool not in payloads:
            continue
        result = service.run_tool(tool, payloads[tool], save_result=False)
        if not result.ok or not isinstance(result.data, dict):
            continue
        data = result.data
        export = data.get("export_snapshot") if isinstance(data.get("export_snapshot"), dict) else {}
        export_text = export.get("export_text") if isinstance(export.get("export_text"), str) else ""
        base = {k: v for k, v in data.items() if k not in {"export_snapshot", "snapshot_text"}}
        base_bytes = len(json.dumps(base, ensure_ascii=False).encode("utf-8"))
        total_bytes = len(json.dumps(data, ensure_ascii=False).encode("utf-8"))
        budget = base_bytes + 3 * len(export_text.encode("utf-8")) + 16_384
        checked += 1
        if total_bytes > budget:
            violations.append(f"{tool}: {total_bytes} B > budget {budget} B (base {base_bytes}, text {len(export_text)})")
    assert checked >= 50, f"样例循环只跑了 {checked} 个工具，守卫覆盖面不够"
    assert violations == [], "\n".join(violations)


def test_section_body_fallback_is_byte_guarded() -> None:
    """段未进快照时兜底正文按**字节+行数**双守卫：单行 20 KB 的输入回显不得再漏进 export_text。"""
    huge_input = {"date": "2028-04-06", "blob": "x" * 20_000}
    snapshot = _build_generated_export_snapshot(
        technique="qimen",
        input_normalized=huge_input,
        response_data={"pan": {"palaces": [{"i": i} for i in range(9)]}},
        snapshot_text="[盘型]\n阳遁四局",
        parsed_snapshot={"sections": [{"title": "盘型", "body": "阳遁四局"}], "missing_selected_sections": []},
    )
    assert snapshot is not None
    by_title = {s["title"]: s for s in snapshot["sections"]}
    assert by_title["盘型"]["body"] == "阳遁四局", "快照里有的段以快照正文为准"
    assert "x" * 100 not in by_title["起盘信息"]["body"], "超字节的输入回显必须换成「未产出」占位"
    assert len(snapshot["export_text"].encode("utf-8")) < 8_192, "整份 export_text 不该被单段撑大"
    for section in snapshot["sections"]:
        assert "data" not in section
