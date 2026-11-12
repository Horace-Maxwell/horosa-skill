from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _classify_archive_type(path: Path) -> str:
    """Return the archive type string (.tar.gz → 'tar.gz', .zip → 'zip', else the raw suffix)."""
    name = path.name
    if name.endswith(".tar.gz"):
        return "tar.gz"
    if name.endswith(".tar.xz"):
        return "tar.xz"
    return path.suffix.lstrip(".") or "tar.gz"


def core_js_entry(archive: Path, url: str, version: str, spec: dict[str, object]) -> dict[str, object]:
    """The manifest's top-level `core_js` entry (v0.50.0-dev, E-02), read from the archive itself.

    The node floor and the version come from the archive's own package.json — the bytes users install, not a value typed
    here — and must agree with the release version; the root directory must be the contract's.
    """
    root = str(spec.get("root") or "horosa-core-js")
    try:
        with tarfile.open(archive, "r:gz") as tar:
            handle = tar.extractfile(f"{root}/package.json")
            package = json.loads(handle.read().decode("utf-8")) if handle else None
    except (OSError, KeyError, tarfile.TarError, ValueError) as exc:
        raise SystemExit(f"{archive.name}: cannot read {root}/package.json ({type(exc).__name__}: {exc})") from exc
    if not isinstance(package, dict) or package.get("version") != version:
        raise SystemExit(f"{archive.name}: {root}/package.json version {(package or {}).get('version')!r} != release {version!r}")
    node_floor = (package.get("engines") or {}).get("node")
    if not isinstance(node_floor, str) or not node_floor.strip():
        raise SystemExit(f"{archive.name}: {root}/package.json has no engines.node")
    return {
        "url": url,
        "sha256": sha256_file(archive),
        "archive_type": _classify_archive_type(archive),
        "size": archive.stat().st_size,
        "version": version,
        "node_floor": node_floor.strip(),
        "root": root,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a runtime release manifest for horosa-skill.\n\n"
            "At least one platform archive must be provided. A release manifest that "
            "covers zero platforms is rejected."
        )
    )
    parser.add_argument("--version", required=True, help="Runtime version.")
    parser.add_argument("--darwin-archive", help="Path to the macOS (darwin-arm64) runtime archive.")
    parser.add_argument("--darwin-url", help="GitHub Releases URL for the macOS runtime archive.")
    parser.add_argument("--windows-archive", help="Path to the Windows (win32-x64) runtime archive.")
    parser.add_argument("--windows-url", help="GitHub Releases URL for the Windows runtime archive.")
    parser.add_argument("--linux-archive", help="Path to the Linux (linux-x64) runtime archive.")
    parser.add_argument("--linux-url", help="GitHub Releases URL for the Linux runtime archive.")
    parser.add_argument(
        "--url-base",
        help=(
            "Base URL for archives whose --*-url is not given, e.g. "
            "https://github.com/<repo>/releases/download/v0.38.0 — tag-pinned so pin-forward is visible "
            "from the manifest alone (v0.38.0 A3). `releases/latest/download` bases are accepted but not recommended."
        ),
    )
    parser.add_argument(
        "--core-js-archive",
        help=(
            "Path to the platform-independent JS engine asset (horosa-core-js-v<ver>.tar.gz, scripts/build_core_js_asset.py). "
            "Written under the top-level `core_js` key — never under `platforms` (v0.50.0-dev, E-02)."
        ),
    )
    parser.add_argument("--core-js-url", help="URL for the JS engine asset (default: --url-base/<archive name>).")
    parser.add_argument("--output", required=True, help="Output manifest JSON path.")
    parser.add_argument(
        "--platforms-contract",
        default=str(Path(__file__).resolve().parents[1] / "contracts" / "release_platforms.json"),
        help="release_platforms.json; each platform's `min_os` is copied into its manifest entry (v0.38.1 R16).",
    )
    args = parser.parse_args()

    contract_platforms: dict[str, dict[str, object]] = {}
    contract_core_js: dict[str, object] = {}
    contract_path = Path(args.platforms_contract).expanduser()
    if contract_path.is_file():
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract_platforms = contract.get("platforms") or {}
        contract_core_js = contract.get("core_js") or {}

    platforms: dict[str, dict[str, object]] = {}

    def entry(platform_key: str, archive_arg: str, url_arg: str | None) -> dict[str, object]:
        archive = Path(archive_arg).expanduser().resolve()
        url = url_arg or (f"{args.url_base.rstrip('/')}/{archive.name}" if args.url_base else None)
        if not url:
            parser.error(f"{archive.name}: give its --*-url or --url-base")
        # `size` (bytes) feeds the installer's disk precheck (manager._require_install_disk_space reads it;
        # without it the check falls back to a flat 3 GiB) and lets release-completeness compare with
        # Content-Length (v0.38.0 A3).
        result: dict[str, object] = {"url": url, "sha256": sha256_file(archive), "archive_type": _classify_archive_type(archive),
                                     "size": archive.stat().st_size}
        # `min_os` lets install refuse an old host before the download (manager._assert_min_os reads it).
        min_os = (contract_platforms.get(platform_key) or {}).get("min_os")
        if isinstance(min_os, str) and min_os.strip():
            result["min_os"] = min_os.strip()
        return result

    if args.darwin_archive and (args.darwin_url or args.url_base):
        platforms["darwin-arm64"] = entry("darwin-arm64", args.darwin_archive, args.darwin_url)
    if args.windows_archive and (args.windows_url or args.url_base):
        platforms["win32-x64"] = entry("win32-x64", args.windows_archive, args.windows_url)
    if args.linux_archive and (args.linux_url or args.url_base):
        platforms["linux-x64"] = entry("linux-x64", args.linux_archive, args.linux_url)

    if not platforms:
        parser.error("At least one platform archive (darwin, windows, or linux) must be provided.")

    manifest: dict[str, object] = {
        "version": args.version,
        "platforms": platforms,
    }
    if args.core_js_archive:
        core_js_archive = Path(args.core_js_archive).expanduser().resolve()
        core_js_url = args.core_js_url or (f"{args.url_base.rstrip('/')}/{core_js_archive.name}" if args.url_base else None)
        if not core_js_url:
            parser.error(f"{core_js_archive.name}: give --core-js-url or --url-base")
        manifest[str(contract_core_js.get("manifest_key") or "core_js")] = core_js_entry(
            core_js_archive, core_js_url, args.version, contract_core_js
        )
    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
