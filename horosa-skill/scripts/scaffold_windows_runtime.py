from __future__ import annotations

import argparse
import json
from pathlib import Path


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_manifest(version: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "version": version,
        "platform": "win32-x64",
        "runtime_layout_version": 1,
        "export_registry_version": 6,
        "services": {
            "backend_url": "http://127.0.0.1:9999",
            "chart_url": "http://127.0.0.1:8899",
            "start_script": "Horosa-Web/start_horosa_local.ps1",
            "stop_script": "Horosa-Web/stop_horosa_local.ps1",
        },
        "runtimes": {
            "python": "runtime/windows/python/python.exe",
            "java": "runtime/windows/java/bin/java.exe",
            "node": "runtime/windows/node/node.exe",
        },
        "artifacts": {
            "horosa_web_root": "Horosa-Web",
            "astropy_root": "Horosa-Web/astropy",
            "flatlib_root": "Horosa-Web/flatlib-ctrad2/flatlib",
            "swefiles_root": "Horosa-Web/flatlib-ctrad2/flatlib/resources/swefiles",
            "boot_jar": "runtime/windows/bundle/astrostudyboot.jar",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a lightweight Windows runtime payload scaffold.")
    parser.add_argument("--output", required=True, help="Output directory for the runtime scaffold.")
    parser.add_argument("--version", required=True, help="Runtime version to stamp into runtime-manifest.json.")
    args = parser.parse_args()

    payload_root = Path(args.output).expanduser().resolve() / "runtime-payload"

    write_text(
        payload_root / "Horosa-Web/start_horosa_local.ps1",
        "$ErrorActionPreference = 'Stop'\nWrite-Host 'TODO: wire Windows runtime startup here.'\nexit 0\n",
    )
    write_text(
        payload_root / "Horosa-Web/stop_horosa_local.ps1",
        "$ErrorActionPreference = 'Stop'\nWrite-Host 'TODO: wire Windows runtime shutdown here.'\nexit 0\n",
    )
    write_text(
        payload_root / "runtime/windows/README.txt",
        "Place packaged Java, Python, Node, and astrostudyboot.jar assets here before creating the release zip.\n",
    )
    write_text(payload_root / "runtime/windows/java/bin/java.exe.placeholder", "")
    write_text(payload_root / "runtime/windows/python/python.exe.placeholder", "")
    write_text(payload_root / "runtime/windows/node/node.exe.placeholder", "")
    write_text(payload_root / "runtime/windows/bundle/astrostudyboot.jar.placeholder", "")
    write_text(payload_root / "Horosa-Web/astropy/.keep", "")
    write_text(payload_root / "Horosa-Web/flatlib-ctrad2/flatlib/resources/swefiles/.keep", "")
    write_text(
        payload_root / "runtime-manifest.json",
        json.dumps(build_manifest(args.version), ensure_ascii=False, indent=2) + "\n",
    )


if __name__ == "__main__":
    main()
