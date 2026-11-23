"""surface_audit.py treats an unadvertised registry key (bazi_direct, audit S-16) as "must answer tool.unknown", not as a technique.

Why (v0.52.0 release check): 6008fd80 took horosa_cn_bazi_direct off the flat MCP list; the live surface audit kept calling it like
any technique and went red 1/386 (`[mcp-full] bazi_direct: tool.unknown`) — the product was right, the audit was stale. The audit is
not in CI (it needs the vendored instance), so the per-tool verdict is checked here offline against the server's real reply.
"""
from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path

from horosa_skill.engine.registry import TOOL_DEFINITIONS, UNADVERTISED_TECHNIQUES
from horosa_skill.surfaces.mcp_runner import _unknown_tool_result

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "surface_audit.py"
_spec = importlib.util.spec_from_file_location("surface_audit", _SCRIPT)
audit = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("surface_audit", audit)
_spec.loader.exec_module(audit)

LISTED = {d.mcp_name for name, d in TOOL_DEFINITIONS.items() if name not in UNADVERTISED_TECHNIQUES}


def _reply(tool: str) -> dict:
    return audit.envelope_of(_unknown_tool_result(TOOL_DEFINITIONS[tool].mcp_name))


def test_every_unadvertised_key_passes_on_the_real_reply() -> None:
    assert UNADVERTISED_TECHNIQUES
    for tool in UNADVERTISED_TECHNIQUES:
        assert audit.judge_unadvertised(_reply(tool), LISTED) == (True, ""), tool


def test_the_old_per_technique_verdict_is_what_went_red() -> None:
    """Negative control: judging the reply like an ordinary technique fails — the v0.52.0 red row."""
    assert audit.judge(_reply("bazi_direct")) == (False, "tool.unknown")


def test_a_replacement_that_is_not_listed_fails() -> None:
    ok, detail = audit.judge_unadvertised(_reply("bazi_direct"), LISTED - {"horosa_cn_bazi_birth"})
    assert not ok and detail["got"] == ["tool.unknown", "horosa_cn_bazi_birth"]


def test_a_plain_error_fails() -> None:
    assert audit.judge_unadvertised({"ok": False, "error": {"code": "runtime.unavailable"}}, LISTED)[0] is False


def test_the_full_surface_routes_unadvertised_keys_to_that_verdict() -> None:
    source = inspect.getsource(audit.mcp_surface)
    assert "elif tool in UNADVERTISED_TECHNIQUES:" in source and "judge_unadvertised(" in source
