#!/usr/bin/env python3
"""Ratchet the byte size of the MCP `tools/list` response (full and compact surfaces).

v0.35.0 shipped a 1186 KB `tools/list` (≈318k tokens) for the default surface: 57 tools inherited all
95 BirthInput fields, dispatch/hecan inlined a 5-way union twice (24 KB each), and every tool repeated
a 322-byte clarification-gate paragraph. An agent paid that on every session before saying a word.

v0.36.0 B1 split the schema into an advertised layer (domain core + tool-own fields + `request` escape
hatch; `surfaces/mcp_schema.py`) and a validation layer (the full model — undeclared top-level keys
still reach `run_tool`). This guard measures both surfaces **in-process** (no runtime needed) and
enforces hard caps plus a ratchet: the recorded baseline may only go down, and any regression above
2% of the baseline fails CI.

Baseline lives in `contracts/mcp_list_budget.json`. Refresh with `--update-baseline` after paying
size down. Stdlib + the package itself. Wired into CI.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

# Windows 控制台默认 cp1252/cp936：脚本自己 print 的中文会抛 UnicodeEncodeError 并让脚本 exit 1
# （v0.38.0 的 repack 脚本在「打印成功信息」那一步失败过）。统一在入口把两条流改成 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
PKG_ROOT = SCRIPTS.parent
BASELINE = PKG_ROOT / "contracts" / "mcp_list_budget.json"
sys.path.insert(0, str(PKG_ROOT / "src"))

# instructions_bytes（v0.38.1 C20）：_SERVER_INSTRUCTIONS 发给每个客户端，2048 是自设预算（已 2035/2048）——
# 棘轮 + 硬顶，防一字破限而无人知。
HARD_CAPS = {"full_bytes": 256 * 1024, "compact_bytes": 30 * 1024, "instructions_bytes": 2048}
TOLERANCE = 0.02


def measure() -> dict[str, int]:
    from horosa_skill.config import Settings
    from horosa_skill.memory.store import MemoryStore
    from horosa_skill.service import HorosaSkillService
    from horosa_skill.surfaces.mcp_server import create_mcp_server

    from horosa_skill.surfaces.mcp_server import _SERVER_INSTRUCTIONS

    sizes: dict[str, int] = {"instructions_bytes": len(_SERVER_INSTRUCTIONS.encode("utf-8"))}
    with tempfile.TemporaryDirectory() as tmp:
        for key, compact in (("full_bytes", False), ("compact_bytes", True)):
            settings = Settings(db_path=Path(tmp) / f"{key}.db", output_dir=Path(tmp) / "runs", mcp_compact=compact)
            mcp = create_mcp_server(HorosaSkillService(settings, store=MemoryStore(settings)), settings)
            tools = [tool.model_dump(mode="json") for tool in asyncio.run(mcp.list_tools())]
            sizes[key] = len(json.dumps(tools, ensure_ascii=False).encode("utf-8"))
            sizes[key.replace("_bytes", "_tools")] = len(tools)
    return sizes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--update-baseline", action="store_true", help="rewrite the baseline after paying size down")
    args = ap.parse_args()
    sizes = measure()

    if args.update_baseline:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(
            json.dumps(
                {
                    "_comment": (
                        "Ratchet baseline for the MCP tools/list byte size (full + compact surfaces, measured "
                        "in-process). Hard caps: full ≤ 256 KB, compact ≤ 30 KB; regressions above 2% of the "
                        "baseline fail CI. Refresh with `uv run python scripts/verify_mcp_list_budget.py --update-baseline`."
                    ),
                    "hard_caps": HARD_CAPS,
                    **sizes,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"baseline updated: full {sizes['full_bytes']} B ({sizes['full_tools']} tools), compact {sizes['compact_bytes']} B ({sizes['compact_tools']} tools), instructions {sizes['instructions_bytes']} B")
        return 0

    if not BASELINE.is_file():
        print(f"missing {BASELINE.relative_to(PKG_ROOT)} — run with --update-baseline once to seed it", file=sys.stderr)
        return 1
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    errors: list[str] = []
    for key, cap in HARD_CAPS.items():
        if sizes[key] > cap:
            errors.append(f"{key}: {sizes[key]} B exceeds the hard cap {cap} B")
        allowed = int(base.get(key, cap) * (1 + TOLERANCE))
        if sizes[key] > allowed:
            errors.append(f"{key}: {sizes[key]} B > baseline {base.get(key)} B (+{TOLERANCE:.0%}) — a schema/description grew; slim it or justify a new baseline")
    if errors:
        print("mcp tools/list budget FAILED:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    shrunk = [key for key in HARD_CAPS if sizes[key] < int(base.get(key, 0) * (1 - TOLERANCE))]
    if shrunk:
        print(
            f"mcp tools/list shrank ({', '.join(f'{k} {base.get(k)}→{sizes[k]}' for k in shrunk)}); run "
            "`uv run python scripts/verify_mcp_list_budget.py --update-baseline` to lock the gain in.",
            file=sys.stderr,
        )
        return 1
    print(
        f"mcp tools/list budget OK: full {sizes['full_bytes']} B / {HARD_CAPS['full_bytes']} B "
        f"({sizes['full_tools']} tools), compact {sizes['compact_bytes']} B / {HARD_CAPS['compact_bytes']} B "
        f"({sizes['compact_tools']} tools), instructions {sizes['instructions_bytes']} B / {HARD_CAPS['instructions_bytes']} B"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
