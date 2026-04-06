from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_PATHS = [
    "vendor/runtime-source/runtime/mac",
    "vendor/runtime-source/runtime/windows",
    "vendor/runtime-source/prepareruntime",
    "horosa-skill/scripts/build_runtime_release.sh",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify vendored runtime source prerequisites for release builds.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    root = args.root.resolve()
    results = []
    missing = []
    for rel in REQUIRED_PATHS:
        target = root / rel
        exists = target.exists()
        results.append({"path": str(target), "exists": exists})
        if not exists:
            missing.append(str(target))
    if missing:
        raise SystemExit("Missing vendored runtime sources:\n" + "\n".join(missing))
    print(json.dumps({"ok": True, "checked": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
