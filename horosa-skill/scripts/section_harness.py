#!/usr/bin/env python3
"""Section harness: run every tool's sample payload against a LIVE vendored instance and report export-section debt.

Promoted into scripts/ in v0.40.0 (it lived in a gitignored notes folder while LESSONS/AGENTS cited "harness 110/110" —
a claim no tracked script could back). It is the third layer of live verification after the lane and the live pytest:
for each technique it runs `HorosaSkillService.run_tool(tool, sample_payload)` and prints the tools whose export contract
is not clean (missing selected sections / unknown detected sections / errors).

    export HOROSA_CHART_SERVER_ROOT=http://127.0.0.1:8877 HOROSA_SERVER_ROOT=http://127.0.0.1:9977   # start_vendored_instance.sh --with-java
    HOROSA_RUNTIME_ROOT=$(mktemp -d) HOROSA_SKILL_DATA_DIR=$(mktemp -d) uv run python scripts/section_harness.py [tool ...] [--json out.json]

Acceptance for a release: `N tools run; clean=N`. HOROSA_RUNTIME_ROOT must be an EMPTY directory (an installed older
payload would otherwise supply the JS engine, see LESSONS v0.40.0 "live 复验跑的是已装 runtime 的旧 JS 引擎").
Never point it at :8899/:9999 — those may be the maintainer's desktop app.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")

PKG_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG_ROOT / "src"))

from horosa_skill.config import Settings  # noqa: E402
from horosa_skill.engine.registry import TOOL_DEFINITIONS  # noqa: E402
from horosa_skill.service import HorosaSkillService  # noqa: E402
from horosa_skill.testing_payloads import build_sample_payloads  # noqa: E402


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    out_json = None
    if "--json" in argv:
        out_json = argv[argv.index("--json") + 1]
        args = [a for a in args if a != out_json]
    tmp = Path(tempfile.mkdtemp(prefix="harness-"))
    settings = Settings.from_env().model_copy(update={"data_dir": tmp})
    service = HorosaSkillService(settings=settings)
    payloads = build_sample_payloads()
    tools = args or sorted(payloads)
    report: dict[str, dict] = {}
    for tool in tools:
        if tool not in TOOL_DEFINITIONS:
            continue
        payload = dict(payloads.get(tool) or {})
        payload.setdefault("agent_confirmed_settings", True)
        try:
            env = service.run_tool(tool, payload, save_result=False)
        except Exception as exc:  # noqa: BLE001 - the harness must report, not crash
            report[tool] = {"ok": False, "error": f"EXC {type(exc).__name__}: {exc}"[:300]}
            continue
        data = env.data or {}
        exp = data.get("export_snapshot") or {}
        rec: dict = {"ok": env.ok}
        if not env.ok:
            error = env.error or {}
            rec["error"] = error.get("code") if isinstance(error, dict) else str(error)
        rec["technique"] = exp.get("technique")
        rec["detected"] = list(exp.get("section_titles_detected") or [])
        rec["missing"] = exp.get("missing_selected_sections") or []
        rec["unknown"] = exp.get("unknown_detected_sections") or []
        report[tool] = rec
    for tool, rec in report.items():
        flag = "" if rec.get("ok") else "  !! " + str(rec.get("error"))
        if rec.get("missing") or rec.get("unknown") or not rec.get("ok"):
            print(f"{tool:22s} tech={rec.get('technique')}{flag}\n    missing={rec.get('missing')}\n    unknown={rec.get('unknown')}")
    clean = sum(1 for r in report.values() if r.get("ok") and not r.get("missing") and not r.get("unknown"))
    print(f"\n{len(report)} tools run; clean={clean}")
    if out_json:
        Path(out_json).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if clean == len(report) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
