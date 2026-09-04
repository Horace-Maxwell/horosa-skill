"""v0.36.0 A6 — every key a documented payload carries must be declared on the tool's Input model.

The layer that loses keys is the MCP flat surface: `_signature_for_input_model` advertises exactly the
model's fields, and FastMCP's generated arg model drops undeclared top-level keys before the payload
reaches `run_tool`. CLI / `horosa_tool_run` / dispatch never lose anything (FlexibleModel is
`extra="allow"`), which is why PR #17's "性别恒为未知" reproduced only through MCP. `gender` on
`BaZiBirthInput` was one instance of a whole class: "documented, sampled, silently dropped".

This test closes the class: the sample payload of every technique tool (the same fixtures the
offline suite, HorosaBench and the smoke tests use) must round-trip the advertised signature without
losing a key. Gate/meta keys are declared on FlexibleModel itself, so they pass naturally.
"""
from __future__ import annotations

from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.input_normalization import normalize_request_payload
from horosa_skill.surfaces.mcp_server import _signature_for_input_model
from horosa_skill.testing_payloads import build_sample_payloads


def test_advertised_signature_accepts_every_sample_payload_key() -> None:
    payloads = build_sample_payloads()
    dropped: dict[str, list[str]] = {}
    for tool_name, definition in TOOL_DEFINITIONS.items():
        sample = payloads.get(tool_name)
        if not isinstance(sample, dict):
            continue
        advertised = set(_signature_for_input_model(definition.input_model).parameters) - {"request"}
        # 扁平面收到的是**原始** kwargs：FastMCP 先按广告签名丢未声明键，之后才 normalize。
        missing = sorted(key for key in sample if key not in advertised)
        assert normalize_request_payload(dict(sample)) is not None
        if missing:
            dropped[tool_name] = missing
    assert dropped == {}, (
        "these sample-payload keys are not declared on the tool's Input model, so the MCP flat surface "
        f"silently drops them (declare the field, or fix the sample if the key is dead): {dropped}"
    )


def test_bazi_birth_declares_gender_and_response_view() -> None:
    fields = set(TOOL_DEFINITIONS["bazi_birth"].input_model.model_fields)
    assert {"gender", "response_view"} <= fields
