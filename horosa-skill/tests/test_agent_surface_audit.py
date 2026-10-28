"""2026-10 surface audit: what an agent meets when it drives Horosa through CLI / MCP / HTTP with no prior context.

Each test pins one defect the live audit found (all 110 techniques were run through the full MCP surface, the compact
`horosa_tool_run`, `horosa-skill tool run`, and Streamable HTTP; every facade, resource and prompt was called):

1. Technique names have two spellings (`chart` / `horosa_astro_chart`). The CLI, `horosa_tool_run`, `report from-tool`
   and hecan's `tools` accepted only the registry key, and the gate let an unknown spelling through unenforced.
2. dispatch / hecan silently ignored flat birth fields (the shape every technique tool takes), then asked the user for
   the birth data they had already given.
3. Validation errors on memory / report facades told the agent to ask the *user* for its own fields (ai_answer, run_id).
4. Compact-surface clients got server instructions describing the 120-tool full surface.
5. CLI help: 19 commands had no description; `--surface` and `knowledge search` help carried stale counts.
6. Guidance gave a copyable example payload for 9 of 110 techniques.
7. qimenzeri's technique card always said "measured engine ≠ declaration".
"""

from __future__ import annotations

import asyncio
import json

import click
import pytest
import typer
from typer.testing import CliRunner

from horosa_skill.agent_guidance import (
    EXAMPLE_NOTE,
    build_tool_input_contract,
    build_validation_recovery,
    validate_agent_preflight,
)
from horosa_skill.config import Settings
from horosa_skill.engine.registry import MCP_NAME_ALIASES, TOOL_DEFINITIONS, resolve_tool_name
from horosa_skill.errors import ToolValidationError
from horosa_skill.input_normalization import normalize_request_payload
from horosa_skill.memory.store import MemoryStore
from horosa_skill.schemas.tools import DispatchInput, HecanInput
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces import cli
from horosa_skill.surfaces.mcp_server import (
    COMPACT_SURFACE_TOOL_COUNT,
    FACADE_TOOL_COUNT,
    _server_instructions,
    create_mcp_server,
)

BIRTH = {"date": "1995-06-03", "time": "05:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"}


def _service(tmp_path) -> tuple[Settings, HorosaSkillService]:
    settings = Settings(
        server_root="http://127.0.0.1:9", chart_server_root="http://127.0.0.1:9",
        data_dir=tmp_path, runtime_root=tmp_path / "runtime",
        db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs", trace_enabled=False,
    )
    return settings, HorosaSkillService(settings, store=MemoryStore(settings))


# --- 1. two spellings of a technique name -----------------------------------------------------------------------


def test_every_mcp_name_resolves_to_its_registry_key() -> None:
    assert len(MCP_NAME_ALIASES) == len(TOOL_DEFINITIONS)
    for key, definition in TOOL_DEFINITIONS.items():
        assert resolve_tool_name(key) == key
        assert resolve_tool_name(definition.mcp_name) == key
        assert resolve_tool_name(f"  {definition.mcp_name} ") == key
    for bad in ("", "nope", "horosa_astro_nope", None, 3):
        assert resolve_tool_name(bad) is None


def test_gate_is_enforced_for_the_mcp_spelling() -> None:
    # Before: an unrecognised name (the MCP spelling) returned ok/enforced=False — a gate bypass once the
    # executor learned the alias. The gate must see the same technique under either name.
    for name in ("chart", "horosa_astro_chart"):
        gate = validate_agent_preflight(name, dict(BIRTH))
        assert gate["ok"] is False and gate["code"] == "agent_guidance.required", name
    assert validate_agent_preflight("horosa_astro_chart", {**BIRTH, "agent_confirmed_settings": True})["ok"] is True


def test_service_run_tool_accepts_both_spellings_and_unknown_lists_the_catalog(tmp_path) -> None:
    _, service = _service(tmp_path)
    by_key = service.run_tool("knowledge_registry", {}, save_result=False)
    by_mcp = service.run_tool("horosa_knowledge_registry", {}, save_result=False)
    assert by_key.ok and by_mcp.ok and by_mcp.tool == "knowledge_registry"
    with pytest.raises(ToolValidationError) as caught:
        service.run_tool("horosa_astro_nope", {}, save_result=False)
    assert caught.value.code == "tool.unknown"
    details = caught.value.details
    assert sum(len(v) for v in details["catalog"].values()) == len(TOOL_DEFINITIONS)
    assert "horosa_astro_chart" in details["accepted_forms"] and "tool list" in details["hint"]


def test_cli_tool_run_accepts_the_mcp_spelling_and_keeps_the_gate(monkeypatch, tmp_path) -> None:
    _, service = _service(tmp_path)
    monkeypatch.setattr(cli, "_service", lambda: service)
    runner = CliRunner()
    (tmp_path / "empty.json").write_text("{}", encoding="utf-8")
    ok = runner.invoke(cli.app, ["tool", "run", "horosa_knowledge_registry", "--input", str(tmp_path / "empty.json")])
    assert ok.exit_code == 0, ok.output
    assert json.loads(ok.stdout)["tool"] == "knowledge_registry"
    (tmp_path / "birth.json").write_text(json.dumps(BIRTH), encoding="utf-8")
    gated = runner.invoke(cli.app, ["tool", "run", "horosa_astro_chart", "--input", str(tmp_path / "birth.json")])
    assert gated.exit_code == 2 and "agent_guidance.required" in gated.output
    unknown = runner.invoke(cli.app, ["tool", "run", "no_such_tool", "--input", str(tmp_path / "empty.json")])
    assert unknown.exit_code == 2 and "tool.unknown" in unknown.output and "catalog" in unknown.output


def test_compact_tool_run_accepts_the_mcp_spelling(tmp_path) -> None:
    settings, service = _service(tmp_path)
    settings.mcp_compact = True
    server = create_mcp_server(service, settings)

    def call(name: str) -> dict:
        result = asyncio.run(server.call_tool("horosa_tool_run", {"tool_name": name, "request": {}}))
        blocks = result[0] if isinstance(result, tuple) else result
        return json.loads(blocks[0].text)

    assert call("horosa_knowledge_registry")["ok"] is True
    assert call("knowledge_registry")["ok"] is True
    unknown = call("horosa_astro_nope")
    assert unknown["ok"] is False and unknown["error"]["code"] == "tool.unknown"


def test_input_contract_and_hecan_accept_the_mcp_spelling() -> None:
    assert build_tool_input_contract("horosa_cn_qimen")["tool_name"] == "qimen"
    assert HecanInput.model_validate({"query": "x", "tools": ["horosa_cn_bazi_birth"]}).tools == ["horosa_cn_bazi_birth"]


# --- 2. flat birth fields for dispatch / hecan -----------------------------------------------------------------


@pytest.mark.parametrize("model", [DispatchInput, HecanInput])
def test_flat_birth_fields_are_lifted_into_birth(model) -> None:
    flat = {"query": "帮我排个八字", **BIRTH, "gender": 1, "agent_confirmed_settings": True, "clarification_notes": "ok"}
    data = model.model_validate(flat).model_dump(exclude_none=True)
    assert {key: data["birth"][key] for key in ("date", "time", "zone", "lat", "lon", "gender")} == {**BIRTH, "gender": 1}
    assert data["agent_confirmed_settings"] is True and "agent_confirmed_settings" not in data["birth"]
    # explicit birth / subject win; without a date nothing is guessed
    explicit = model.model_validate({"query": "x", "birth": {**BIRTH, "date": "2000-01-01"}, "date": "1999-01-01"}).model_dump()
    assert explicit["birth"]["date"] == "2000-01-01"
    assert model.model_validate({"query": "x", "subject": {"name": "某人"}, "date": "1999-01-01"}).birth is None
    assert model.model_validate({"query": "今天黄历"}).birth is None


# --- 3. who fixes a validation error ---------------------------------------------------------------------------


@pytest.mark.parametrize("operation", ["memory_record_answer", "horosa_memory_record_answer", "report_render", "horosa_report_template", "technique_report"])
def test_facade_validation_errors_are_agent_fixable(operation) -> None:
    recovery = build_validation_recovery(operation_name=operation, errors=[{"loc": ("ai_answer",), "msg": "Field required"}])
    assert recovery["must_ask_user"] is False
    assert recovery["fix_fields"] == [{"field": "ai_answer", "problem": "Field required"}]
    assert recovery["next_action"] == "fix_payload_fields_and_retry"
    assert "retry_requires_one_of" not in recovery


def test_technique_and_dispatch_validation_errors_still_ask_the_user() -> None:
    errors = [{"loc": ("date",), "msg": "Field required"}]
    for kwargs in ({"operation_name": "tool.chart", "tool_name": "chart"}, {"operation_name": "horosa_dispatch", "tool_name": "dispatch"},
                   {"operation_name": "horosa_hecan", "tool_name": "hecan"}):
        assert build_validation_recovery(errors=errors, **kwargs)["must_ask_user"] is True


def test_record_answer_without_ai_answer_is_agent_fixable_end_to_end(tmp_path) -> None:
    _, service = _service(tmp_path)
    with pytest.raises(ToolValidationError) as caught:
        service.record_ai_answer({"run_id": "missing"})
    recovery = caught.value.details["agent_recovery"]
    assert recovery["must_ask_user"] is False and recovery["fix_fields"][0]["field"] == "ai_answer"


# --- 4. compact-surface instructions -----------------------------------------------------------------------------


def test_compact_instructions_describe_the_compact_surface_within_budget(tmp_path) -> None:
    for jev in (False, True):
        full = _server_instructions(decision_layer_on=jev)
        compact = _server_instructions(decision_layer_on=jev, compact=True)
        assert len(full.encode("utf-8")) <= 2048 and len(compact.encode("utf-8")) <= 2048
        assert f"({FACADE_TOOL_COUNT + len(TOOL_DEFINITIONS)} tools)" in full
        assert f"({FACADE_TOOL_COUNT + len(TOOL_DEFINITIONS)} tools)" not in compact
        assert f"{len(TOOL_DEFINITIONS)} techniques via horosa_tool_run" in compact
        assert "horosa_astro_chart" in compact
    settings, service = _service(tmp_path)
    settings.mcp_compact = True
    assert create_mcp_server(service, settings).instructions == _server_instructions(decision_layer_on=False, compact=True)


# --- 5. CLI help is the API reference for shell-only agents -------------------------------------------------------


def _commands() -> list[tuple[str, click.Command]]:
    found: list[tuple[str, click.Command]] = []

    def walk(command: click.Command, path: list[str]) -> None:
        found.append((" ".join(path), command))
        if hasattr(command, "commands"):  # typer 0.27 自带 click 副本：别用 isinstance(click.Group)
            for name, sub in command.commands.items():
                walk(sub, path + [name])

    walk(typer.main.get_command(cli.app), [])
    return found


def test_every_cli_command_and_parameter_has_help() -> None:
    missing_commands = [path for path, command in _commands() if path and not (command.help or "").strip()]
    assert missing_commands == []
    missing_params = [
        f"{path} {param.name}" for path, command in _commands() for param in command.params
        if param.name not in {"help", "install_completion", "show_completion"} and not (getattr(param, "help", None) or "").strip()
    ]
    assert missing_params == []


def test_cli_help_counts_come_from_the_registry() -> None:
    commands = dict(_commands())
    surface = next(p for p in commands["client config"].params if p.name == "surface")
    assert f"{FACADE_TOOL_COUNT + len(TOOL_DEFINITIONS)} 个工具" in surface.help
    assert f"{COMPACT_SURFACE_TOOL_COUNT} 个门面工具" in surface.help
    query = next(p for p in commands["knowledge search"].params if p.name == "query")
    assert not any(ch.isdigit() for ch in query.help)


# --- 6. a working example payload for every technique -------------------------------------------------------------


@pytest.mark.parametrize("tool_name", sorted(TOOL_DEFINITIONS))
def test_every_tool_contract_carries_an_example_that_passes_gate_and_model(tool_name) -> None:
    contract = build_tool_input_contract(tool_name)
    example = contract["example_payload"]
    # `{}` is a real example for tools that take no input (ziwei_rules); a missing example has no example_note.
    assert contract.get("example_note") == EXAMPLE_NOTE, f"{tool_name}: no example payload"
    if TOOL_DEFINITIONS[tool_name].input_model.model_fields and any(
        field.is_required() for field in TOOL_DEFINITIONS[tool_name].input_model.model_fields.values()
    ):
        assert example, f"{tool_name}: required fields but an empty example"
    assert validate_agent_preflight(tool_name, example)["ok"] is True
    TOOL_DEFINITIONS[tool_name].input_model.model_validate(normalize_request_payload(json.loads(json.dumps(example))))
    blob = json.dumps(example, ensure_ascii=False)
    assert "gpsLat" not in blob and "gpsLon" not in blob and "self-check fixture" not in blob


# --- 7. qimenzeri's engine declaration ----------------------------------------------------------------------------


@pytest.mark.parametrize("pan", ["kinqimen", "local_route_calcDunJia"])
def test_qimenzeri_card_matches_its_declaration(pan) -> None:
    from horosa_skill.reports.technique_card import build_technique_card

    card = build_technique_card(
        tool_name="qimenzeri", technique_key="qimenzeri", input_normalized={},
        response_data={"compute_sources": {"scan": "local_calcDunJia", "pan": pan}},
        skill_version="test", envelope_schema="test",
    )
    assert card["compute"]["matches_declaration"] is True


# --- 8. concurrent first start on a fresh data dir ----------------------------------------------------------------


def test_concurrent_schema_migration_tolerates_a_column_added_by_another_process(tmp_path) -> None:
    import sqlite3

    _, service = _service(tmp_path)
    store = service.store

    class StaleView:
        """What the second process sees: PRAGMA said the column was missing, but the first process added it since."""

        def __init__(self, conn: sqlite3.Connection) -> None:
            self.conn = conn

        def execute(self, sql: str, *args):
            if sql.startswith("PRAGMA table_info"):
                return self.conn.execute("SELECT NULL AS name WHERE 0")
            return self.conn.execute(sql, *args)

    with store.connect() as conn:
        store._ensure_column(StaleView(conn), "runs", "answer_meta_json", "TEXT")  # already there: must not raise
        with pytest.raises(sqlite3.OperationalError):
            StaleView(conn).execute("ALTER TABLE runs ADD COLUMN answer_meta_json TEXT")  # the raw race, for contrast
        with pytest.raises(sqlite3.OperationalError):  # other migration errors still surface
            store._ensure_column(StaleView(conn), "no_such_table", "x", "TEXT")


def test_parallel_first_start_on_a_fresh_data_dir(tmp_path) -> None:
    import multiprocessing

    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(6) as pool:
        results = pool.map(_init_store_in_child, [str(tmp_path)] * 12)
    assert results == ["ok"] * 12


def _init_store_in_child(root: str) -> str:
    from pathlib import Path

    settings = Settings(data_dir=Path(root), runtime_root=Path(root) / "runtime", db_path=Path(root) / "memory.db",
                        output_dir=Path(root) / "runs", trace_enabled=False)
    try:
        MemoryStore(settings)
    except Exception as exc:  # noqa: BLE001 - reported to the parent
        return f"{type(exc).__name__}: {exc}"
    return "ok"
