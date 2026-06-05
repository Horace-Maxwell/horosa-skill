#!/usr/bin/env bash
# Build Horosa runtime release archives for macOS (darwin-arm64), Windows (win32-x64),
# and optionally Linux (linux-x64).
#
# Prerequisites (macOS host):
#   1. vendor/runtime-source/ is populated (see sync_vendored_runtime_sources.sh)
#   2. npm, curl, python3 are on PATH
#
# Linux archives require additional setup; see build_runtime_release_linux.py.
#
# Environment:
#   HOROSA_RUNTIME_RELEASE_REPO   GitHub repo (default: Horace-Maxwell/horosa-skill)
#   HOROSA_RUNTIME_RELEASE_BASE_URL  Base URL for release download
#   HOROSA_SKIP_LINUX           Set to "1" to skip Linux archive building

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SKILL_ROOT="${ROOT}/horosa-skill"
DIST_ROOT="${SKILL_ROOT}/dist/runtime"
export HOROSA_SKILL_PYPROJECT="${SKILL_ROOT}/pyproject.toml"
VERSION="$(python3 - <<'PY'
import tomllib
from pathlib import Path
data = tomllib.loads(Path(__import__('os').environ['HOROSA_SKILL_PYPROJECT']).read_text(encoding='utf-8'))
print(data['project']['version'])
PY
)"
RELEASE_REPO="${HOROSA_RUNTIME_RELEASE_REPO:-Horace-Maxwell/horosa-skill}"
RELEASE_BASE_URL="${HOROSA_RUNTIME_RELEASE_BASE_URL:-https://github.com/${RELEASE_REPO}/releases/latest/download}"

# --- macOS ---
"${ROOT}/horosa-skill/scripts/package_runtime_payload.sh"

# --- Windows ---
python3 "${ROOT}/horosa-skill/scripts/build_runtime_release_windows.py"

mkdir -p "${DIST_ROOT}"

# --- Build manifest argument list ---
MANIFEST_ARGS=( --version "${VERSION}" --output "${DIST_ROOT}/runtime-manifest.json" )

DARWIN_ARCHIVE="${DIST_ROOT}/horosa-runtime-darwin-arm64-v${VERSION}.tar.gz"
WINDOWS_ARCHIVE="${DIST_ROOT}/horosa-runtime-win32-x64-v${VERSION}.zip"
LINUX_ARCHIVE="${DIST_ROOT}/horosa-runtime-linux-x64-v${VERSION}.tar.gz"

if [ -f "${DARWIN_ARCHIVE}" ]; then
    MANIFEST_ARGS+=( --darwin-archive "${DARWIN_ARCHIVE}" --darwin-url "${RELEASE_BASE_URL}/$(basename "${DARWIN_ARCHIVE}")" )
fi
if [ -f "${WINDOWS_ARCHIVE}" ]; then
    MANIFEST_ARGS+=( --windows-archive "${WINDOWS_ARCHIVE}" --windows-url "${RELEASE_BASE_URL}/$(basename "${WINDOWS_ARCHIVE}")" )
fi

# --- Linux (optional) ---
SKIP_LINUX="${HOROSA_SKIP_LINUX:-0}"
if [ "${SKIP_LINUX}" != "1" ] && [ -x "$(command -v python3)" ]; then
    if python3 -c "import tomllib; open('/dev/null')" 2>/dev/null; then
        echo "--- Building Linux runtime archive ---"
        python3 "${ROOT}/horosa-skill/scripts/build_runtime_release_linux.py" 2>&1 || echo "WARNING: Linux build skipped (see above)" >&2
    fi
fi
if [ -f "${LINUX_ARCHIVE}" ]; then
    MANIFEST_ARGS+=( --linux-archive "${LINUX_ARCHIVE}" --linux-url "${RELEASE_BASE_URL}/$(basename "${LINUX_ARCHIVE}")" )
fi

python3 "${ROOT}/horosa-skill/scripts/generate_release_manifest.py" "${MANIFEST_ARGS[@]}"

# --- Checksums ---
SHASUM_CMD=""
for cmd in sha256sum shasum; do
    if command -v "${cmd}" &>/dev/null; then
        SHASUM_CMD="${cmd}"
        break
    fi
done
if [ -n "${SHASUM_CMD}" ]; then
    (
        cd "${DIST_ROOT}"
        # Collect all runtime archives that actually exist
        ARCHIVES=()
        for f in horosa-runtime-*.tar.gz horosa-runtime-*.zip; do
            [ -f "${f}" ] && ARCHIVES+=("${f}")
        done
        if [ "${#ARCHIVES[@]}" -gt 0 ]; then
            "${SHASUM_CMD}" -a 256 "${ARCHIVES[@]}" > SHA256SUMS.txt
        fi
    )
fi

# --- Verification ---
VERIFY_ARGS=( --manifest "${DIST_ROOT}/runtime-manifest.json" )
[ -f "${DARWIN_ARCHIVE}" ] && VERIFY_ARGS+=( --darwin-archive "${DARWIN_ARCHIVE}" )
[ -f "${WINDOWS_ARCHIVE}" ] && VERIFY_ARGS+=( --windows-archive "${WINDOWS_ARCHIVE}" )
[ -f "${LINUX_ARCHIVE}" ] && VERIFY_ARGS+=( --linux-archive "${LINUX_ARCHIVE}" )
python3 "${ROOT}/horosa-skill/scripts/verify_runtime_release.py" "${VERIFY_ARGS[@]}"
