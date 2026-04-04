from __future__ import annotations

import argparse
import json
import tarfile
import zipfile
from pathlib import Path


REQUIRED_ENTRIES = {
    "darwin-arm64": [
        "runtime-payload/runtime-manifest.json",
        "runtime-payload/Horosa-Web/start_horosa_local.sh",
        "runtime-payload/Horosa-Web/stop_horosa_local.sh",
        "runtime-payload/Horosa-Web/astropy/",
        "runtime-payload/Horosa-Web/flatlib-ctrad2/flatlib/resources/swefiles/",
        "runtime-payload/runtime/mac/python/bin/python3",
        "runtime-payload/runtime/mac/java/bin/java",
        "runtime-payload/runtime/mac/node/bin/node",
        "runtime-payload/runtime/mac/bundle/astrostudyboot.jar",
        "runtime-payload/horosa-core-js/bin/cli.mjs",
    ],
    "win32-x64": [
        "runtime-payload/runtime-manifest.json",
        "runtime-payload/Horosa-Web/start_horosa_local.ps1",
        "runtime-payload/Horosa-Web/stop_horosa_local.ps1",
        "runtime-payload/Horosa-Web/astropy/",
        "runtime-payload/Horosa-Web/flatlib-ctrad2/flatlib/resources/swefiles/",
        "runtime-payload/runtime/windows/python/python.exe",
        "runtime-payload/runtime/windows/java/bin/java.exe",
        "runtime-payload/runtime/windows/node/node.exe",
        "runtime-payload/runtime/windows/bundle/astrostudyboot.jar",
        "runtime-payload/horosa-core-js/bin/cli.mjs",
    ],
}


def _archive_entries(path: Path) -> set[str]:
    if path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as archive:
            return {member.name if member.isdir() else member.name for member in archive.getmembers()}
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            return set(archive.namelist())
    raise SystemExit(f"unsupported archive type: {path}")


def _assert_entries(path: Path, platform_key: str) -> None:
    entries = _archive_entries(path)
    missing: list[str] = []
    for required in REQUIRED_ENTRIES[platform_key]:
        if required.endswith("/"):
            if not any(entry.startswith(required) for entry in entries):
                missing.append(required)
        elif required not in entries:
            missing.append(required)
    if missing:
        raise SystemExit(f"{path.name} is missing required entries:\n- " + "\n- ".join(missing))


def _validate_manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    platforms = data.get("platforms")
    if not isinstance(platforms, dict):
        raise SystemExit(f"manifest missing platforms object: {path}")
    for key in ("darwin-arm64", "win32-x64"):
        if key not in platforms:
            raise SystemExit(f"manifest missing platform entry: {key}")
        item = platforms[key]
        for field in ("url", "sha256", "archive_type"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise SystemExit(f"manifest {key}.{field} is missing or empty")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify Horosa runtime release archives and manifest.")
    parser.add_argument("--darwin-archive", required=True)
    parser.add_argument("--windows-archive", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()

    darwin_archive = Path(args.darwin_archive).expanduser().resolve()
    windows_archive = Path(args.windows_archive).expanduser().resolve()
    manifest_path = Path(args.manifest).expanduser().resolve()

    _assert_entries(darwin_archive, "darwin-arm64")
    _assert_entries(windows_archive, "win32-x64")
    manifest = _validate_manifest(manifest_path)

    print(
        json.dumps(
            {
                "ok": True,
                "version": manifest.get("version"),
                "darwin_archive": str(darwin_archive),
                "windows_archive": str(windows_archive),
                "manifest": str(manifest_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
