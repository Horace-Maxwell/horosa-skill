from __future__ import annotations

import argparse
import hashlib
import json
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
    parser.add_argument("--output", required=True, help="Output manifest JSON path.")
    args = parser.parse_args()

    platforms: dict[str, dict[str, str]] = {}

    if args.darwin_archive and args.darwin_url:
        archive = Path(args.darwin_archive).expanduser().resolve()
        platforms["darwin-arm64"] = {
            "url": args.darwin_url,
            "sha256": sha256_file(archive),
            "archive_type": _classify_archive_type(archive),
        }
    if args.windows_archive and args.windows_url:
        archive = Path(args.windows_archive).expanduser().resolve()
        platforms["win32-x64"] = {
            "url": args.windows_url,
            "sha256": sha256_file(archive),
            "archive_type": _classify_archive_type(archive),
        }
    if args.linux_archive and args.linux_url:
        archive = Path(args.linux_archive).expanduser().resolve()
        platforms["linux-x64"] = {
            "url": args.linux_url,
            "sha256": sha256_file(archive),
            "archive_type": _classify_archive_type(archive),
        }

    if not platforms:
        parser.error("At least one platform archive (darwin, windows, or linux) must be provided.")

    manifest = {
        "version": args.version,
        "platforms": platforms,
    }
    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
