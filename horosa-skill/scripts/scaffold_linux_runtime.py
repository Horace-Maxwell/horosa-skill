"""Scaffold a Linux (linux-x64) runtime payload directory skeleton.

This script creates the directory structure and placeholder files expected by
``verify_runtime_release.py`` for the ``linux-x64`` platform.  It is the Linux
counterpart of ``scaffold_windows_runtime.py``.

Usage::

    python scripts/scaffold_linux_runtime.py \\
        --output /tmp/linux-payload \\
        --version 0.9.2

The output directory will contain a ``runtime-payload/`` tree that maintainers
can then populate with real Linux binaries (Python, Java, Node, etc.) before
running ``package_runtime_payload.sh`` (or a platform-specific tar command).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_manifest(version: str) -> dict:
    """Return a minimal runtime-manifest.json for the linux-x64 platform."""
    return {
        "schema_version": 1,
        "version": version,
        "platform": "linux-x64",
        "runtime_layout_version": 1,
        "export_registry_version": 6,
        "services": {
            "backend_url": "http://127.0.0.1:9999",
            "chart_url": "http://127.0.0.1:8899",
            "start_script": "Horosa-Web/start_horosa_local.sh",
            "stop_script": "Horosa-Web/stop_horosa_local.sh",
        },
        "runtimes": {
            "python": "runtime/linux/python/bin/python3",
            "java": "runtime/linux/java/bin/java",
            "node": "runtime/linux/node/bin/node",
        },
        "artifacts": {
            "horosa_web_root": "Horosa-Web",
            "astropy_root": "Horosa-Web/astropy",
            "flatlib_root": "Horosa-Web/flatlib-ctrad2/flatlib",
            "swefiles_root": "Horosa-Web/flatlib-ctrad2/flatlib/resources/swefiles",
            "boot_jar": "runtime/linux/bundle/astrostudyboot.jar",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a lightweight Linux runtime payload scaffold for horosa-skill."
    )
    parser.add_argument("--output", required=True, help="Output directory for the runtime scaffold.")
    parser.add_argument("--version", required=True, help="Runtime version to stamp into runtime-manifest.json.")
    args = parser.parse_args()

    payload_root = Path(args.output).expanduser().resolve() / "runtime-payload"

    # -- Start / stop scripts (POSIX shell, same as macOS but with Linux-appropriate paths) --
    write_text(
        payload_root / "Horosa-Web/start_horosa_local.sh",
        _LINUX_START_SCRIPT,
    )
    write_text(
        payload_root / "Horosa-Web/stop_horosa_local.sh",
        _LINUX_STOP_SCRIPT,
    )

    # -- Runtime manifest --
    write_text(
        payload_root / "runtime-manifest.json",
        json.dumps(build_manifest(args.version), ensure_ascii=False, indent=2) + "\n",
    )

    # -- Placeholder directories / files for binaries that must be provided by the maintainer --
    write_text(payload_root / "runtime/linux/README.txt",
        "Place packaged Java, Python, Node runtimes and astrostudyboot.jar here before creating the release archive.\n"
    )
    write_text(payload_root / "runtime/linux/java/bin/java.placeholder", "")
    write_text(payload_root / "runtime/linux/python/bin/python3.placeholder", "")
    write_text(payload_root / "runtime/linux/node/bin/node.placeholder", "")
    write_text(payload_root / "runtime/linux/bundle/astrostudyboot.jar.placeholder", "")

    # -- Shared data directories (identical structure across all platforms) --
    write_text(payload_root / "Horosa-Web/astropy/.keep", "")
    write_text(payload_root / "Horosa-Web/flatlib-ctrad2/flatlib/resources/swefiles/.keep", "")

    # -- Ken engines (identical Python code across all platforms) --
    for ken_engine in ("kinqimen", "kintaiyi", "kinjinkou",
                       "kinwangji", "kinwuzhao",
                       "taixuanshifa", "jingjue", "shenyishu",
                       "kinastro"):
        (payload_root / "Horosa-Web/vendor" / ken_engine / ".keep").parent.mkdir(parents=True, exist_ok=True)
        (payload_root / "Horosa-Web/vendor" / ken_engine / ".keep").write_text("", encoding="utf-8")

    # -- horosa-core-js with npm dependencies --
    (payload_root / "horosa-core-js/bin/cli.mjs.placeholder").parent.mkdir(parents=True, exist_ok=True)
    (payload_root / "horosa-core-js/bin/cli.mjs.placeholder").write_text("", encoding="utf-8")
    # The full node_modules/ must be populated via `cd horosa-core-js && npm install` at package time.

    print(
        json.dumps(
            {"ok": True, "payload_root": str(payload_root), "version": args.version},
            ensure_ascii=False,
            indent=2,
        )
    )


_LINUX_START_SCRIPT = """\
#!/usr/bin/env bash
# Horosa Linux runtime startup script.
# This script starts the Java backend (astrostudyboot) and the Python chart service.
set -euo pipefail

HOROSA_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${HOROSA_ROOT}/.horosa-logs"
BACKEND_JAR="${HOROSA_ROOT}/runtime/linux/bundle/astrostudyboot.jar"
PYTHON_BIN="${HOROSA_ROOT}/runtime/linux/python/bin/python3"
JAVA_BIN="${HOROSA_ROOT}/runtime/linux/java/bin/java"
NODE_BIN="${HOROSA_ROOT}/runtime/linux/node/bin/node"
BACKEND_PORT="${HOROSA_BACKEND_PORT:-9999}"
CHART_PORT="${HOROSA_CHART_PORT:-8899}"

mkdir -p "${LOG_DIR}"

# Start the Python chart service (astropy, flatlib, ken engines).
export PYTHONPATH="${HOROSA_ROOT}/Horosa-Web:${HOROSA_ROOT}/Horosa-Web/vendor/kinqimen:${HOROSA_ROOT}/Horosa-Web/vendor/kintaiyi:${HOROSA_ROOT}/Horosa-Web/vendor/kinjinkou:${HOROSA_ROOT}/Horosa-Web/vendor/kinwangji:${HOROSA_ROOT}/Horosa-Web/vendor/kinwuzhao:${HOROSA_ROOT}/Horosa-Web/vendor/taixuanshifa:${HOROSA_ROOT}/Horosa-Web/vendor/jingjue:${HOROSA_ROOT}/Horosa-Web/vendor/shenyishu:${HOROSA_ROOT}/Horosa-Web/vendor/kinastro"
if [ -f "${PYTHON_BIN}" ]; then
    "${PYTHON_BIN}" -m horosa_chart_service --port "${CHART_PORT}" \
        >> "${LOG_DIR}/chart-service.log" 2>&1 &
    echo $! > "${LOG_DIR}/chart-service.pid"
    echo "Python chart service started on port ${CHART_PORT} (pid $(cat "${LOG_DIR}/chart-service.pid"))"
else
    echo "WARNING: Python runtime not found at ${PYTHON_BIN}" >&2
fi

# Start the Java backend.
if [ -f "${JAVA_BIN}" ] && [ -f "${BACKEND_JAR}" ]; then
    "${JAVA_BIN}" -jar "${BACKEND_JAR}" --server.port="${BACKEND_PORT}" \
        >> "${LOG_DIR}/backend.log" 2>&1 &
    echo $! > "${LOG_DIR}/backend.pid"
    echo "Java backend started on port ${BACKEND_PORT} (pid $(cat "${LOG_DIR}/backend.pid"))"
else
    echo "WARNING: Java runtime or backend JAR not found" >&2
fi

echo "Horosa runtime startup initiated. Check logs under ${LOG_DIR} for status."
"""

_LINUX_STOP_SCRIPT = """\
#!/usr/bin/env bash
# Horosa Linux runtime shutdown script.
set -euo pipefail

HOROSA_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${HOROSA_ROOT}/.horosa-logs"

for service in chart-service backend; do
    pid_file="${LOG_DIR}/${service}.pid"
    if [ -f "${pid_file}" ]; then
        pid="$(cat "${pid_file}")"
        if kill "${pid}" 2>/dev/null; then
            echo "Stopped ${service} (pid ${pid})"
        else
            echo "${service} (pid ${pid}) was not running"
        fi
        rm -f "${pid_file}"
    fi
done

echo "Horosa runtime shut down."
"""


if __name__ == "__main__":
    main()
