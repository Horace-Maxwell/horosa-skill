"""上游 v3.15.0 同步 · [盘面细节] 按表取全表（挂载齿轮 detailFullTables → chartDetailTablesText.buildChartDetailFullTables）。

上游把细节页那张表的 React 树（tableOf 同一份列定义）转成 Markdown，以「■ 全表·表名」小标题接在摘要后、仍在 [盘面细节] 段内。
skill 走报告盘图 bundle 的 app-text 通道跑这份上游代码（app-charts/adapters/texts.js），不另抄列定义。
负向对照：enrich 里不把全表接到摘要后 → 全表用例红；表名词表不认 → schema 用例红。
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fakes import CaptureClient
from test_sync314_western_chart_details import BIRTH, DETAIL_KEYS, FX, _calls, _freeze, _section, _service

from horosa_skill.config import Settings
from horosa_skill.engine.js_client import HorosaJsEngineClient
from horosa_skill.errors import ToolValidationError

PKG_ROOT = Path(__file__).resolve().parents[1]


def _with_real_texts(service, tmp_path):
    real = HorosaJsEngineClient(Settings(server_root="http://127.0.0.1:9", runtime_root=tmp_path / "rt", db_path=tmp_path / "m.db",
                                         output_dir=tmp_path / "o"))
    real._candidate_engine_roots = lambda: [PKG_ROOT / "horosa-core-js"]  # type: ignore[method-assign]
    service.js_client.run_app_texts = real.run_app_texts
    return service


def test_full_tables_follow_the_summary_inside_the_section(tmp_path, monkeypatch) -> None:
    _freeze(monkeypatch, "+08:00")
    client = CaptureClient()
    service = _with_real_texts(_service(tmp_path, client=client), tmp_path)
    result = service.run_tool("chart", {**BIRTH, "detailFullTables": "定位星链, topics"}, save_result=False)
    assert result.ok, result.error
    body = _section(result.data["snapshot_text"], "盘面细节")
    # 上游摘要与全表之间空一行（[summary, full].join('\n\n')）；skill 的快照渲染段内不留空行（段间才留），内容逐行相同
    summary, _, full = body.partition("\n■ 全表·")
    assert summary == FX["texts"]["seattle-night"]
    assert full.startswith("定位星链\n| 星 | 星链 | 终止 |") and "\n■ 全表·专题主星\n| 专题 | 日 | 月 |" in full   # 照所给的先后
    for endpoint in ("/astroextra/chartdetails", "/astroextra/analysis"):   # /chart 现照旧带着细节口径键（既有行为，后端忽略）
        assert "detailFullTables" not in _calls(client, endpoint)[0], endpoint
    plain = _service(tmp_path / "p").run_tool("chart", BIRTH, save_result=False)
    assert "■ 全表·" not in plain.data["snapshot_text"]


def test_bundle_unavailable_keeps_the_summary_and_says_so(tmp_path, monkeypatch) -> None:
    _freeze(monkeypatch, "+08:00")
    service = _service(tmp_path)
    service.js_client.run_app_texts = lambda calls: None
    result = service.run_tool("chart", {**BIRTH, "detailFullTables": ["topics"]}, save_result=False)
    assert result.ok and _section(result.data["snapshot_text"], "盘面细节") == FX["texts"]["seattle-night"]
    assert any("全表" in note for note in result.warnings)


def test_unknown_table_is_refused(tmp_path) -> None:
    with pytest.raises(ToolValidationError) as err:
        _service(tmp_path).run_tool("chart", {**BIRTH, "detailFullTables": ["topics", "nope"]}, save_result=False)
    assert err.value.code == "tool.invalid_option" and "detailFullTables" in str(err.value) and "nope" in str(err.value)
    assert "detailFullTables" not in DETAIL_KEYS   # 旧常量只列五口径 + 当前表
