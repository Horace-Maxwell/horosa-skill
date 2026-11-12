"""生成 src/horosa_skill/data/zeri_condition_meanings.json（择日十技法的条件说明，深审 F5）。

跑 horosa-core-js 的 `zeri_conditions` catalog（只读上游十张条件注册表），按 horosa_skill.zeri_conditions.build_meanings 写每类一行中英说明。
用法：uv run python scripts/gen_zeri_condition_meanings.py [--check]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG / "src"))

from horosa_skill.zeri_conditions import DATA_PATH, build_meanings  # noqa: E402


def catalog() -> dict:
    out = subprocess.run(
        ["node", str(PKG / "horosa-core-js" / "bin" / "cli.mjs"), "run", "zeri_conditions"],
        input=json.dumps({"action": "catalog"}), capture_output=True, text=True, check=True, encoding="utf-8",
    )
    return json.loads(out.stdout)["data"]["catalog"]


def render() -> str:
    return json.dumps(build_meanings(catalog()), ensure_ascii=False, indent=1) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = render()
    if args.check:
        if DATA_PATH.read_text(encoding="utf-8") != text:
            print(f"{DATA_PATH} is stale: run scripts/gen_zeri_condition_meanings.py", file=sys.stderr)
            return 1
        print("zeri condition meanings up to date")
        return 0
    DATA_PATH.write_text(text, encoding="utf-8")
    print(f"wrote {DATA_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
