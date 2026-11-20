#!/usr/bin/env python3
"""从双平台发布清单生成包内钉值 `src/horosa_skill/data/runtime_pins.json`（审计 PF-01 第 3 层）。

release-runtime.yml 的 assemble 在 Windows 半派生完、清单生成之后跑它，再用 tag 的源码 `uv build --wheel` 换掉草稿里的 wheel。
  uv run python scripts/write_runtime_pins.py --manifest dist/runtime/runtime-manifest.json --output <tag 树>/horosa-skill/src/horosa_skill/data/runtime_pins.json
本仓不提交这个文件（源码 checkout 不钉）。Stdlib + 本包。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    from horosa_skill.runtime.pins import pins_from_manifest

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expect-platforms", default="darwin-arm64,win32-x64", help="comma-separated platforms that must be pinned")
    args = parser.parse_args(argv)
    pins = pins_from_manifest(json.loads(args.manifest.read_text(encoding="utf-8")))
    missing = [p for p in args.expect_platforms.split(",") if p and p not in pins["platforms"]]
    if not pins["version"] or missing or "core_js" not in pins:
        print(f"runtime-pins: refusing — version={pins['version']!r}, missing platforms={missing}, core_js={'core_js' in pins}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(pins, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"runtime-pins: wrote {args.output} (version {pins['version']}, platforms {sorted(pins['platforms'])}, core_js)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
