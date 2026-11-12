from __future__ import annotations

import argparse
import json
import sys
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path

from horosa_skill.benchmark import run_benchmark
from horosa_skill.benchmark.runner import exit_code
from horosa_skill.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Run HorosaBench benchmark cases.")
    parser.add_argument("--dataset", type=Path, default=None, help="Optional benchmark dataset JSON path.")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON report output path.")
    parser.add_argument("--skip-runtime", action="store_true", help="Skip runtime-backed cases and only execute local cases.")
    parser.add_argument("--save-result", action="store_true", help="Persist benchmark outputs into the local record layer.")
    parser.add_argument("--require-full", action="store_true",
                        help="Exit 2 unless every case ran (use on a lane that has the runtime; --skip-runtime runs 3 of ~120).")
    args = parser.parse_args()

    report = run_benchmark(
        settings=Settings.from_env(),
        dataset_path=args.dataset,
        skip_runtime=args.skip_runtime,
        save_result=args.save_result,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8", newline="\n")
    print(text)
    print(report["summary"], file=sys.stderr)
    sys.exit(exit_code(report, require_full=args.require_full))


if __name__ == "__main__":
    main()
