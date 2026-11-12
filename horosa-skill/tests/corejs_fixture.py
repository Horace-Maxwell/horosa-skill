"""A miniature `horosa-core-js-v<ver>.tar.gz` for tests of the JS engine asset (v0.50.0-dev, E-02).

Shaped like the real asset (`scripts/build_core_js_asset.py`): one `horosa-core-js/` root with the contract's required entries
and one `node_modules/<dep>/package.json` per dependency. Tests that need an engine that really runs build the real asset instead.
"""
from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path

NODE_FLOOR = ">=20.10.0"


def make_core_js_archive(
    path: Path,
    version: str,
    *,
    deps: dict[str, str] | None = None,
    omit: tuple[str, ...] = (),
    extra: dict[str, bytes] | None = None,
    root: str = "horosa-core-js",
    node_floor: str = NODE_FLOOR,
) -> dict:
    """Write the archive; return {path, sha256, size}. `omit` drops entries (relative to the root), `extra` adds raw members."""
    deps = {"lunar-javascript": "1.7.7"} if deps is None else deps
    files: dict[str, bytes] = {
        "package.json": json.dumps({"name": "horosa-core-js", "version": version, "engines": {"node": node_floor},
                                    "dependencies": deps}).encode("utf-8"),
        "bin/cli.mjs": b"console.log(JSON.stringify({ok: true}))\n",
        "src/tools/index.js": b"export {}\n",
        "dist/app-charts.cjs": b"module.exports = {}\n",
        **{f"node_modules/{dep}/package.json": json.dumps({"name": dep, "version": ver}).encode("utf-8") for dep, ver in deps.items()},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "w:gz") as tar:
        for rel, data in sorted(files.items()):
            if rel in omit:
                continue
            info = tarfile.TarInfo(f"{root}/{rel}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        for name, data in (extra or {}).items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    data = path.read_bytes()
    return {"path": path, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}


def core_js_manifest_entry(info: dict, url: str, version: str) -> dict:
    return {"url": url, "sha256": info["sha256"], "archive_type": "tar.gz", "size": info["size"], "version": version,
            "node_floor": NODE_FLOOR, "root": "horosa-core-js"}
