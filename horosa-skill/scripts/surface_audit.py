#!/usr/bin/env python3
"""Surface audit: drive every technique through the surfaces an agent actually uses, against a LIVE vendored instance.

`section_harness.py` calls `HorosaSkillService.run_tool` directly, so it never meets the things that only exist at the
surface: the clarification gate, MCP argument handling, the compact `horosa_tool_run` executor, CLI exit codes and
`--input/--output` files, HTTP auth, the facade tools, resources and prompts. The 2026-10 audit that introduced this
script found seven agent-visible defects that every service-level check had passed (two spellings of a tool name, flat
birth fields ignored by dispatch, memory errors telling the agent to ask the user for its own fields, compact clients
told about 120 tools, undocumented CLI commands, examples for 9 of 110 techniques, a technique card always flagged).

What runs (each technique's payload = its `input_contract.example_payload`, the same thing `tool list` / guidance give
an agent, so the examples are proven live too):

  1. MCP stdio, full surface    tools/list count; every technique called by its own tool; export contract clean.
  2. MCP stdio, compact surface tools/list count; every technique through `horosa_tool_run` with the MCP-style name.
  3. CLI                        `horosa-skill tool run <name> --input f --output f` for every technique: exit 0, ok,
                                stdout == --output file, run stored.
  4. Facades / resources / prompts: guidance, dispatch (flat birth), hecan, memory query/show/answer, report
                                template/render/from-tool, technique report; the 3 resources; every prompt.
  5. Streamable HTTP            401 without the token; tools/list and a call with it; the gate on an unconfirmed call.

    bash scripts/start_vendored_instance.sh --with-java
    export HOROSA_CHART_SERVER_ROOT=http://127.0.0.1:8877 HOROSA_SERVER_ROOT=http://127.0.0.1:9977
    uv run python scripts/surface_audit.py [--only chart,qimen] [--skip-http] [--json out.json]

Acceptance for a release: exit 0 (`surface audit: N checks, failed=0`). Never point it at :8899/:9999 (the maintainer's
desktop app). Child processes get an EMPTY runtime root and a throwaway data dir; HOROSA_* settings from the calling
shell are not inherited (values are never printed).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")

PKG_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG_ROOT / "src"))

from horosa_skill.agent_guidance import build_tool_input_contract  # noqa: E402
from horosa_skill.engine.registry import TOOL_DEFINITIONS  # noqa: E402
from horosa_skill.surfaces.mcp_server import COMPACT_SURFACE_TOOL_COUNT, FACADE_TOOL_COUNT  # noqa: E402

DESKTOP_PORTS = (":8899", ":9999")
BIRTH = {"date": "1995-06-03", "time": "05:30:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28", "gender": 1}
CONFIRM = {"agent_confirmed_settings": True, "clarification_notes": "surface audit: settings fixed by the test"}


class Report:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def check(self, area: str, name: str, ok: bool, detail: Any = "") -> None:
        self.rows.append({"area": area, "name": name, "ok": bool(ok), "detail": detail})
        if not ok:
            print(f"FAIL [{area}] {name}: {str(detail)[:300]}", flush=True)

    def summary(self) -> str:
        failed = [r for r in self.rows if not r["ok"]]
        areas = sorted({r["area"] for r in self.rows})
        per_area = ", ".join(f"{a} {sum(1 for r in self.rows if r['area'] == a and r['ok'])}/{sum(1 for r in self.rows if r['area'] == a)}" for a in areas)
        return f"surface audit: {len(self.rows)} checks, failed={len(failed)} ({per_area})"


def child_env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("HOROSA_")}
    env.update({
        "HOROSA_SERVER_ROOT": os.environ["HOROSA_SERVER_ROOT"],
        "HOROSA_CHART_SERVER_ROOT": os.environ["HOROSA_CHART_SERVER_ROOT"],
        "HOROSA_RUNTIME_ROOT": tempfile.mkdtemp(prefix="surface-audit-runtime-"),
        "HOROSA_SKILL_DATA_DIR": tempfile.mkdtemp(prefix="surface-audit-data-"),
        "PYTHONIOENCODING": "utf-8",
    })
    env.update(extra)
    return env


def example_payload(tool: str) -> dict[str, Any]:
    payload = json.loads(json.dumps(build_tool_input_contract(tool)["example_payload"]))
    if not (payload.get("agent_confirmed_settings") or payload.get("defaults_accepted")):
        payload.update(CONFIRM)
    return payload


def envelope_of(result: Any) -> dict[str, Any]:
    if getattr(result, "structuredContent", None):
        content = result.structuredContent
        return content.get("result", content) if isinstance(content, dict) and set(content) == {"result"} else content
    for block in getattr(result, "content", []) or []:
        if getattr(block, "type", "") == "text":
            try:
                return json.loads(block.text)
            except json.JSONDecodeError:
                return {"ok": False, "_text": block.text[:300]}
    return {"ok": False}


def error_code(envelope: dict[str, Any]) -> Any:
    error = envelope.get("error")
    return error.get("code") if isinstance(error, dict) else envelope.get("code")


def judge(envelope: dict[str, Any]) -> tuple[bool, Any]:
    if envelope.get("ok") is not True:
        return False, error_code(envelope)
    data = envelope.get("data") if isinstance(envelope.get("data"), dict) else {}
    card = data.get("technique_card") if isinstance(data.get("technique_card"), dict) else {}
    sections = card.get("sections") or {}
    if sections.get("contract_clean") is False:
        return False, {"missing": sections.get("missing_selected_sections"), "unknown": sections.get("unknown_detected_sections")}
    if (card.get("compute") or {}).get("matches_declaration") is False:
        return False, {"engine_mismatch": card["compute"].get("measured")}
    return True, ""


def server_params(env: dict[str, str]):
    from mcp import StdioServerParameters

    return StdioServerParameters(command=sys.executable, args=["-m", "horosa_skill.surfaces.cli", "serve", "--transport", "stdio"], env=env)


async def mcp_surface(report: Report, tools: list[str], *, compact: bool) -> None:
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client

    area = "mcp-compact" if compact else "mcp-full"
    env = child_env(**({"HOROSA_MCP_COMPACT": "1"} if compact else {}))
    async with stdio_client(server_params(env)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = (await session.list_tools()).tools
            expected = COMPACT_SURFACE_TOOL_COUNT if compact else FACADE_TOOL_COUNT + len(TOOL_DEFINITIONS)
            report.check(area, "tools/list count", len(listed) == expected, f"{len(listed)} != {expected}")
            semaphore = asyncio.Semaphore(4)

            async def one(tool: str) -> None:
                definition = TOOL_DEFINITIONS[tool]
                async with semaphore:
                    try:
                        if compact:
                            result = await session.call_tool("horosa_tool_run", {"tool_name": definition.mcp_name, "request": example_payload(tool)})
                        else:
                            result = await session.call_tool(definition.mcp_name, example_payload(tool))
                        ok, detail = judge(envelope_of(result))
                    except Exception as exc:  # noqa: BLE001 - the audit reports, it does not crash
                        ok, detail = False, f"{type(exc).__name__}: {exc}"
                report.check(area, tool, ok, detail)

            await asyncio.gather(*(one(tool) for tool in tools))
            if not compact:
                await facades(report, session)


async def facades(report: Report, session: Any) -> None:
    area = "facades"

    async def call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return envelope_of(await session.call_tool(name, arguments))

    report.check(area, "agent_guidance", (await call("horosa_agent_guidance", {"tool_name": "horosa_cn_qimen"})).get("ok") is True)
    dispatched = await call("horosa_dispatch", {"request": {"query": "帮我排个八字", **BIRTH, **CONFIRM}})
    report.check(area, "dispatch with flat birth fields", dispatched.get("ok") is True, error_code(dispatched))
    run_id = (dispatched.get("memory_ref") or {}).get("run_id")
    hecan = await call("horosa_hecan", {"query": "今年事业如何", "birth": BIRTH, "tools": ["horosa_cn_bazi_birth", "ziwei_birth"], **CONFIRM})
    report.check(area, "hecan", hecan.get("ok") is True, error_code(hecan))
    report.check(area, "memory_query", (await call("horosa_memory_query", {"limit": 3})).get("ok") is not False)
    report.check(area, "dispatch stored a run", bool(run_id))
    if run_id:
        report.check(area, "memory_show", (await call("horosa_memory_show", {"run_id": run_id})).get("ok") is not False)
        report.check(area, "memory_record_answer", (await call("horosa_memory_record_answer", {"run_id": run_id, "ai_answer": "审计用解读。"})).get("ok") is not False)
        missing = await call("horosa_memory_record_answer", {"run_id": run_id})
        recovery = ((missing.get("error") or {}).get("details") or missing.get("details") or {}).get("agent_recovery") or {}
        report.check(area, "record_answer without ai_answer is agent-fixable", recovery.get("must_ask_user") is False, recovery)
        report.check(area, "report_template", (await call("horosa_report_template", {"run_id": run_id})).get("ok") is not False)
        rendered = await call("horosa_report_render", {"run_id": run_id, "format": "docx", "ai_report": {"title": "审计", "sections": [{"title": "结论", "content": "正文。"}]}})
        report.check(area, "report_render docx", rendered.get("ok") is not False and bool(rendered.get("artifact_path")), error_code(rendered))
        report.check(area, "technique_report", (await call("horosa_technique_report", {"run_id": run_id})).get("ok") is not False)
    from_tool = await call("horosa_report_from_tool", {"tool_name": "horosa_cn_nongli_time", "payload": {**BIRTH, **CONFIRM}, "format": "json"})
    report.check(area, "report_from_tool (MCP-style name)", from_tool.get("ok") is not False, error_code(from_tool))
    for uri in ("horosa://catalog/techniques", "horosa://catalog/export-registry", "horosa://runtime/status"):
        try:
            contents = (await session.read_resource(uri)).contents
            report.check(area, f"resource {uri}", bool(contents and getattr(contents[0], "text", "")))
        except Exception as exc:  # noqa: BLE001
            report.check(area, f"resource {uri}", False, exc)
    for prompt in (await session.list_prompts()).prompts:
        arguments = {a.name: "1995-06-03 05:30 上海" for a in (prompt.arguments or []) if a.required}
        try:
            report.check(area, f"prompt {prompt.name}", bool((await session.get_prompt(prompt.name, arguments)).messages))
        except Exception as exc:  # noqa: BLE001
            report.check(area, f"prompt {prompt.name}", False, exc)


def cli_surface(report: Report, tools: list[str]) -> None:
    env = child_env()
    work = Path(tempfile.mkdtemp(prefix="surface-audit-cli-"))
    command = [sys.executable, "-m", "horosa_skill.surfaces.cli"]

    def one(tool: str) -> tuple[str, bool, Any]:
        source, target = work / f"{tool}.in.json", work / f"{tool}.out.json"
        source.write_text(json.dumps(example_payload(tool), ensure_ascii=False), encoding="utf-8")
        proc = subprocess.run([*command, "tool", "run", tool, "--input", str(source), "--output", str(target)], capture_output=True,
                              text=True, encoding="utf-8", errors="replace", env=env, timeout=900)
        if proc.returncode != 0 or not target.is_file():
            return tool, False, f"exit {proc.returncode}: {proc.stderr[-300:]}"
        envelope = json.loads(target.read_text(encoding="utf-8"))
        ok, detail = judge(envelope)
        if ok and json.loads(proc.stdout) != envelope:
            return tool, False, "stdout differs from the --output file"
        if ok and not envelope.get("memory_ref"):
            return tool, False, "run was not stored"
        return tool, ok, detail

    with ThreadPoolExecutor(6) as pool:
        for tool, ok, detail in pool.map(one, tools):
            report.check("cli", tool, ok, detail)
    (work / "unknown.json").write_text("{}", encoding="utf-8")
    unknown = subprocess.run([*command, "tool", "run", "no_such_tool", "--input", str(work / "unknown.json")], capture_output=True,
                             text=True, encoding="utf-8", errors="replace", env=env, timeout=300)
    report.check("cli", "unknown tool: exit 2 + catalog", unknown.returncode == 2 and '"catalog"' in unknown.stderr, unknown.stderr[-200:])
    (work / "birth.json").write_text(json.dumps(BIRTH), encoding="utf-8")
    gated = subprocess.run([*command, "tool", "run", "horosa_astro_chart", "--input", str(work / "birth.json")], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", env=env, timeout=300)
    report.check("cli", "gate holds for the MCP-style name", gated.returncode == 2 and "agent_guidance.required" in gated.stderr, gated.stderr[-200:])


async def http_surface(report: Report) -> None:
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    token = "surface-audit-" + os.urandom(6).hex()
    proc = subprocess.Popen([sys.executable, "-m", "horosa_skill.surfaces.cli", "serve", "--transport", "streamable-http", "--port", str(port),
                             "--skip-runtime-start"], env=child_env(HOROSA_MCP_TOKEN=token), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}/mcp"
    try:
        for _ in range(240):
            try:
                httpx.get(f"http://127.0.0.1:{port}/", timeout=1)
                break
            except httpx.HTTPError:
                time.sleep(0.5)
        unauthorized = httpx.post(url, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
                                  headers={"Accept": "application/json, text/event-stream"}, timeout=10)
        report.check("http", "no token -> 401", unauthorized.status_code == 401, unauthorized.status_code)
        async with streamablehttp_client(url, headers={"Authorization": f"Bearer {token}"}) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = (await session.list_tools()).tools
                report.check("http", "tools/list with token", len(listed) == FACADE_TOOL_COUNT + len(TOOL_DEFINITIONS), len(listed))
                ok, detail = judge(envelope_of(await session.call_tool("horosa_cn_bazi_birth", {**BIRTH, **CONFIRM})))
                report.check("http", "tools/call", ok, detail)
                gated = envelope_of(await session.call_tool("horosa_astro_chart", {k: v for k, v in BIRTH.items() if k != "gender"}))
                report.check("http", "gate on an unconfirmed call", error_code(gated) == "agent_guidance.required", error_code(gated))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--only", help="Comma-separated technique names (registry keys) instead of all of them.")
    parser.add_argument("--skip-http", action="store_true", help="Skip the Streamable HTTP checks.")
    parser.add_argument("--json", type=Path, help="Write every check as JSON to this file.")
    args = parser.parse_args(argv)
    roots = [os.environ.get("HOROSA_SERVER_ROOT", ""), os.environ.get("HOROSA_CHART_SERVER_ROOT", "")]
    if not all(roots) or any(root.rstrip("/").endswith(port) for root in roots for port in DESKTOP_PORTS):
        print("set HOROSA_SERVER_ROOT / HOROSA_CHART_SERVER_ROOT to a vendored instance (start_vendored_instance.sh --with-java); "
              "never :8899 / :9999", file=sys.stderr)
        return 2
    tools = sorted(TOOL_DEFINITIONS) if not args.only else [t.strip() for t in args.only.split(",") if t.strip() in TOOL_DEFINITIONS]
    report = Report()
    asyncio.run(mcp_surface(report, tools, compact=False))
    asyncio.run(mcp_surface(report, tools, compact=True))
    cli_surface(report, tools)
    if not args.skip_http:
        asyncio.run(http_surface(report))
    print(report.summary())
    if args.json:
        args.json.write_text(json.dumps(report.rows, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if all(row["ok"] for row in report.rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
