"""v0.36.0 A2 — graceful degradation must reach the caller (envelope.warnings), not just the log.

Before: 35 `logger.warning` sites in service.py, 2 of which pushed `_warnings`; a real qimen archive
had `missing_selected_sections` 10/17 with `warnings: []`. These tests pin the three plumbing rules:
`_degrade` notes land in the envelope, nested tool calls bubble up, and a preset section that did
not get produced is announced in both `warnings` and `summary`.
"""
from __future__ import annotations

from test_response_budget import _service

from horosa_skill.service import _degrade, _degrade_collector, _missing_sections_warning
from horosa_skill.testing_payloads import build_sample_payloads


def test_degrade_outside_any_collector_only_logs() -> None:
    text = _degrade("orphan enrichment failed: %s", "boom")
    assert text.startswith("降级：orphan enrichment failed: boom")


def test_degrade_notes_dedupe_and_bubble_to_parent_collector() -> None:
    with _degrade_collector() as outer:
        with _degrade_collector() as inner:
            _degrade("child failed: %s", "boom")
            _degrade("child failed: %s", "boom")
            assert len(inner) == 1
            assert outer == []  # bubbles on exit, not on write
        assert outer == inner
    # after the outer scope closes nothing leaks into a fresh collector
    with _degrade_collector() as fresh:
        assert fresh == []


def test_custom_note_replaces_generic_text_but_keeps_log_message() -> None:
    with _degrade_collector() as notes:
        _degrade("bazi geju engine failed: %s", "x", note="八字格局引擎本次不可用。")
    assert notes == ["八字格局引擎本次不可用。"]


def test_missing_sections_warning_shape() -> None:
    text = _missing_sections_warning(
        {"export_snapshot": {"selected_sections": list("abcd"), "missing_selected_sections": ["b", "d"]}}
    )
    assert text is not None
    assert text.startswith("结果不完整：预设 4 段中 2 段未产出（b、d）")
    assert _missing_sections_warning({"export_snapshot": {"missing_selected_sections": []}}) is None
    assert _missing_sections_warning({"export_snapshot": "nope"}) is None
    assert _missing_sections_warning(None) is None


def test_enrichment_failure_reaches_envelope_warnings(tmp_path, monkeypatch) -> None:
    service = _service(tmp_path)
    original = service.js_client.run

    def failing(tool_name: str, payload: dict) -> dict:
        # 夹具 JS 客户端对天王附注段本就不产 → 把那次失败换成可辨认的异常文本，证明它原样到达信封。
        try:
            return original(tool_name, payload)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("engine exploded") from exc

    monkeypatch.setattr(service.js_client, "run", failing)
    envelope = service.run_tool("germany", build_sample_payloads()["germany"], save_result=False)
    assert envelope.ok is True
    hits = [w for w in envelope.warnings if "uranian extra sections failed" in w and "engine exploded" in w]
    assert hits, envelope.warnings
    assert hits[0].startswith("降级：")


def test_missing_preset_sections_are_announced_in_warnings_and_summary(tmp_path) -> None:
    service = _service(tmp_path)
    envelope = service.run_tool("taiyi", build_sample_payloads()["taiyi"], save_result=False)
    assert envelope.ok is True
    missing = envelope.data["export_snapshot"]["missing_selected_sections"]
    assert missing, "fixture taiyi is expected to leave preset sections unproduced (十六宫标记/起盘)"
    notes = [w for w in envelope.warnings if w.startswith("结果不完整：")]
    assert len(notes) == 1
    assert f"{len(missing)} 段未产出" in notes[0]
    assert envelope.summary[-1] == notes[0]
    assert envelope.summary[0] != notes[0]  # the headline stays the headline (dispatch reads summary[:1])
