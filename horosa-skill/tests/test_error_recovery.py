"""v0.36.0 B4 — every error code carries an agent-executable, bilingual recovery."""
from __future__ import annotations

import re
from pathlib import Path

from horosa_skill.errors import RECOVERY_KINDS, RECOVERY_TABLE, ToolValidationError, bilingual, classify_code, recovery_for
from horosa_skill.service import _with_operational_recovery
from horosa_skill.surfaces.mcp_server import _mcp_error_envelope, _mcp_error_payload

SRC = Path(__file__).resolve().parents[1] / "src" / "horosa_skill"


def _all_codes() -> set[str]:
    codes: set[str] = set()
    for py in SRC.rglob("*.py"):
        codes.update(re.findall(r'code="([a-z_.]+)"', py.read_text(encoding="utf-8")))
    return codes


def test_every_code_in_the_package_classifies() -> None:
    unclassified = sorted(code for code in _all_codes() if classify_code(code)[0] is None)
    assert unclassified == [], unclassified
    assert len(_all_codes()) >= 100


def test_classification_layers() -> None:
    assert classify_code("tool.backend_param_error") == ("input", "exact")
    assert classify_code("tool.qimenzeri_missing_window") == ("input", "suffix")
    assert classify_code("tool.tianxing_invalid_conditions") == ("input", "suffix")
    assert classify_code("tool.zhengchuan_calc_failed") == ("retry_or_doctor", "suffix")
    assert classify_code("tool.mundane_ingress_unavailable") == ("retry_or_doctor", "suffix")
    assert classify_code("runtime.install_download_failed") == ("runtime", "prefix")
    assert classify_code("runtime.state_invalid") == ("runtime", "prefix")
    assert classify_code("transport.http_error") == ("transport", "prefix")
    assert classify_code("js_engine.node_unavailable") == ("js_engine", "prefix")
    assert classify_code("report.technique.no_cards") == ("input", "exact")
    assert classify_code("client.command_timeout") == ("environment", "prefix")
    assert classify_code("") == (None, None)
    assert classify_code("tool.something_new_and_vague") == (None, None)


def test_recovery_for_fills_kind_prompt_next_action_and_hint() -> None:
    details = recovery_for("tool.qimenzeri_missing_window", {"tool": "qimenzeri"})
    rec = details["agent_recovery"]
    assert rec["kind"] == "input" and rec["source"] == "suffix" and rec["code"] == "tool.qimenzeri_missing_window"
    assert " / " in rec["prompt_to_user"]  # bilingual
    assert rec["next_action"] == "ask_user_or_fix_input"
    assert details["hint"] == rec["prompt_to_user"] and details["next_action"] == rec["next_action"]
    assert details["tool"] == "qimenzeri"  # 原 details 保留


def test_existing_recovery_and_hint_are_not_overwritten() -> None:
    details = recovery_for(
        "runtime.java_backend_unavailable",
        {"hint": "custom hint", "agent_recovery": {"prompt_to_user": "already there"}},
    )
    assert details["hint"] == "custom hint"
    assert details["agent_recovery"]["prompt_to_user"] == "already there"
    assert details["agent_recovery"]["kind"] == "runtime"  # 缺的键补上
    assert details["agent_recovery"]["next_action"] == "run_doctor_or_retry_after_cooldown"


def test_legacy_kinds_preserved_for_runtime_transport_js_engine() -> None:
    assert _with_operational_recovery("runtime.not_installed", {})["agent_recovery"]["kind"] == "runtime"
    assert _with_operational_recovery("transport.connection_error", {})["agent_recovery"]["kind"] == "transport"
    assert "retry" in _with_operational_recovery("transport.connection_error", {})["agent_recovery"]
    assert _with_operational_recovery("js_engine.node_unavailable", {})["agent_recovery"]["kind"] == "js_engine"
    assert "uv run horosa-skill install" in _with_operational_recovery("runtime.not_installed", {})["agent_recovery"]["commands"]


def test_mcp_error_envelope_and_payload_carry_recovery() -> None:
    exc = ToolValidationError("bad", code="tool.tianxing_missing_conditions", details={"x": 1})
    env = _mcp_error_envelope(exc, tool_name="tianxing")
    assert env.ok is False and env.details["agent_recovery"]["kind"] == "input" and env.details["x"] == 1
    payload = _mcp_error_payload(exc)
    assert payload["details"]["next_action"] == "ask_user_or_fix_input"
    assert payload["error"]["details"] is payload["details"]


def test_bilingual_helper_and_kind_table_are_bilingual() -> None:
    assert bilingual("你好", "hello") == "你好 / hello"
    assert bilingual("你好", "") == "你好" and bilingual("", "hello") == "hello"
    for kind, entry in RECOVERY_KINDS.items():
        assert re.search(r"[一-鿿]", entry["prompt_to_user"]) and re.search(r"[A-Za-z]{3,}", entry["prompt_to_user"]), kind
    for code, entry in RECOVERY_TABLE.items():
        assert entry.get("kind") in RECOVERY_KINDS, code
