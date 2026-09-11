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
    parser.add_argument(
        "--url-base",
        help=(
            "Base URL for archives whose --*-url is not given, e.g. "
            "https://github.com/<repo>/releases/download/v0.38.0 — tag-pinned so pin-forward is visible "
            "from the manifest alone (v0.38.0 A3). `releases/latest/download` bases are accepted but not recommended."
        ),
    )
    parser.add_argument("--output", required=True, help="Output manifest JSON path.")
    args = parser.parse_args()

    platforms: dict[str, dict[str, object]] = {}

    def entry(archive_arg: str, url_arg: str | None) -> dict[str, object]:
        archive = Path(archive_arg).expanduser().resolve()
        url = url_arg or (f"{args.url_base.rstrip('/')}/{archive.name}" if args.url_base else None)
        if not url:
            parser.error(f"{archive.name}: give its --*-url or --url-base")
        # `size` (bytes) feeds the installer's disk precheck (manager._require_install_disk_space reads it;
        # without it the check falls back to a flat 3 GiB) and lets release-completeness compare with
        # Content-Length (v0.38.0 A3).
        return {"url": url, "sha256": sha256_file(archive), "archive_type": _classify_archive_type(archive),
                "size": archive.stat().st_size}

    if args.darwin_archive and (args.darwin_url or args.url_base):
        platforms["darwin-arm64"] = entry(args.darwin_archive, args.darwin_url)
    if args.windows_archive and (args.windows_url or args.url_base):
        platforms["win32-x64"] = entry(args.windows_archive, args.windows_url)
    if args.linux_archive and (args.linux_url or args.url_base):
        platforms["linux-x64"] = entry(args.linux_archive, args.linux_url)

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
