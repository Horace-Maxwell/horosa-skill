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


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a runtime release manifest for horosa-skill.")
    parser.add_argument("--version", required=True, help="Runtime version.")
    parser.add_argument("--darwin-archive", help="Path to the macOS runtime archive.")
    parser.add_argument("--darwin-url", help="GitHub Releases URL for the macOS runtime archive.")
    parser.add_argument("--windows-archive", help="Path to the Windows runtime archive.")
    parser.add_argument("--windows-url", help="GitHub Releases URL for the Windows runtime archive.")
    parser.add_argument("--output", required=True, help="Output manifest JSON path.")
    args = parser.parse_args()

    platforms: dict[str, dict[str, str]] = {}

    if args.darwin_archive and args.darwin_url:
        archive = Path(args.darwin_archive).expanduser().resolve()
        platforms["darwin-arm64"] = {
            "url": args.darwin_url,
            "sha256": sha256_file(archive),
            "archive_type": "tar.gz" if archive.name.endswith(".tar.gz") else archive.suffix.lstrip("."),
        }
    if args.windows_archive and args.windows_url:
        archive = Path(args.windows_archive).expanduser().resolve()
        platforms["win32-x64"] = {
            "url": args.windows_url,
            "sha256": sha256_file(archive),
            "archive_type": "zip" if archive.name.endswith(".zip") else archive.suffix.lstrip("."),
        }

    manifest = {
        "version": args.version,
        "platforms": platforms,
    }
    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
