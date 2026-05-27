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
        # ken engines back /qimen/pan · /taiyi/pan · /jinkou/pan — without these the chart
        # service mounts no ken endpoints and qimen/taiyi/jinkou fail at runtime.
        "runtime-payload/Horosa-Web/vendor/kinqimen/",
        "runtime-payload/Horosa-Web/vendor/kintaiyi/",
        "runtime-payload/Horosa-Web/vendor/kinjinkou/",
        "runtime-payload/runtime/mac/python/bin/python3",
        "runtime-payload/runtime/mac/java/bin/java",
        "runtime-payload/runtime/mac/node/bin/node",
        "runtime-payload/runtime/mac/bundle/astrostudyboot.jar",
        "runtime-payload/horosa-core-js/bin/cli.mjs",
        # canping/heluo compute pillars via the vendored bazi chain → lunar-javascript; without the
        # bundled npm package those tools throw "Cannot find package 'lunar-javascript'" at runtime.
        "runtime-payload/horosa-core-js/node_modules/lunar-javascript/package.json",
    ],
    "win32-x64": [
        "runtime-payload/runtime-manifest.json",
        "runtime-payload/Horosa-Web/start_horosa_local.ps1",
        "runtime-payload/Horosa-Web/stop_horosa_local.ps1",
        "runtime-payload/Horosa-Web/astropy/",
        "runtime-payload/Horosa-Web/flatlib-ctrad2/flatlib/resources/swefiles/",
        # ken engines back /qimen/pan · /taiyi/pan · /jinkou/pan (see darwin note).
        "runtime-payload/Horosa-Web/vendor/kinqimen/",
        "runtime-payload/Horosa-Web/vendor/kintaiyi/",
        "runtime-payload/Horosa-Web/vendor/kinjinkou/",
        "runtime-payload/runtime/windows/python/python.exe",
        "runtime-payload/runtime/windows/java/bin/java.exe",
        "runtime-payload/runtime/windows/node/node.exe",
        "runtime-payload/runtime/windows/bundle/astrostudyboot.jar",
        "runtime-payload/horosa-core-js/bin/cli.mjs",
        # canping/heluo need the bundled lunar-javascript (see darwin note).
        "runtime-payload/horosa-core-js/node_modules/lunar-javascript/package.json",
    ],
}


def _archive_entries(path: Path) -> set[str]:
    if path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as archive:
            return {member.name for member in archive.getmembers()}
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            return set(archive.namelist())
    raise SystemExit(f"unsupported archive type: {path}")


def _read_archive_text(path: Path, entry_name: str) -> str:
    if path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as archive:
            member = archive.getmember(entry_name)
            file_obj = archive.extractfile(member)
            if file_obj is None:
                raise SystemExit(f"{path.name} has unreadable entry: {entry_name}")
            return file_obj.read().decode("utf-8")
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            return archive.read(entry_name).decode("utf-8")
    raise SystemExit(f"unsupported archive type: {path}")


def _assert_entries(path: Path, platform_key: str) -> None:
    entries = _archive_entries(path)
    missing: list[str] = []
    for required in REQUIRED_ENTRIES[platform_key]:
        if required.endswith("/"):
            # Require a real file strictly INSIDE the directory, not merely a directory-marker entry.
            # A zip can carry an empty required dir as a bare `…/swefiles/` marker; the old
            # `startswith(required)` matched that marker against itself and greenlit an archive whose
            # ephemeris / astropy / ken-engine dir was empty (broken at runtime). tar stores dir
            # members without a trailing slash, so this also makes tar and zip validate identically.
            if not any(
                entry.startswith(required) and len(entry) > len(required) and not entry.endswith("/")
                for entry in entries
            ):
                missing.append(required)
        elif required not in entries:
            missing.append(required)
    if missing:
        raise SystemExit(f"{path.name} is missing required entries:\n- " + "\n- ".join(missing))


def _assert_payload_manifest(path: Path, platform_key: str, expected_version: str) -> None:
    raw = _read_archive_text(path, "runtime-payload/runtime-manifest.json")
    try:
        payload_manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path.name} contains invalid runtime-payload/runtime-manifest.json: {exc}") from exc
    version = payload_manifest.get("version")
    payload_version = payload_manifest.get("runtime_payload_version", version)
    platform = payload_manifest.get("platform")
    errors: list[str] = []
    if version != expected_version:
        errors.append(f"version={version!r} expected {expected_version!r}")
    if payload_version != expected_version:
        errors.append(f"runtime_payload_version={payload_version!r} expected {expected_version!r}")
    if platform != platform_key:
        errors.append(f"platform={platform!r} expected {platform_key!r}")
    if errors:
        raise SystemExit(f"{path.name} has stale or mismatched embedded runtime manifest: " + "; ".join(errors))


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
    expected_version = str(manifest.get("version") or "")
    if not expected_version:
        raise SystemExit(f"manifest version is missing: {manifest_path}")
    _assert_payload_manifest(darwin_archive, "darwin-arm64", expected_version)
    _assert_payload_manifest(windows_archive, "win32-x64", expected_version)

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
