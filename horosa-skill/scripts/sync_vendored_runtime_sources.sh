#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SOURCE_ROOT="${HOROSA_SOURCE_ROOT:-$(cd "${ROOT}/.." && pwd)}"
VENDOR_ROOT="${ROOT}/vendor/runtime-source"

RSYNC_FILTERS=(
  "--exclude=.DS_Store"
  "--exclude=._*"
  "--exclude=.pytest_cache"
  "--exclude=.cache"
  "--exclude=__pycache__"
  "--exclude=*.pyc"
  "--exclude=*.pyo"
  "--exclude=*.map"
  "--exclude=*.tmp"
  "--exclude=*.temp"
  "--exclude=*.pid"
  "--exclude=_CodeSignature"
  "--exclude=*/_CodeSignature"
  '--exclude=${env:HOME}'
  '--exclude=*/${env:HOME}'
  "--exclude=.horosa-logs"
  "--exclude=*/.horosa-logs"
)

require_path() {
  local target="$1"
  if [ ! -e "${target}" ]; then
    echo "missing required source path: ${target}" >&2
    exit 1
  fi
}

require_path "${SOURCE_ROOT}/Horosa-Web/start_horosa_local.sh"
require_path "${SOURCE_ROOT}/Horosa-Web/stop_horosa_local.sh"
require_path "${SOURCE_ROOT}/Horosa-Web/astropy"
require_path "${SOURCE_ROOT}/Horosa-Web/flatlib-ctrad2"
require_path "${SOURCE_ROOT}/Horosa-Web/astrostudyui/dist-file"
require_path "${SOURCE_ROOT}/runtime/mac/python"
require_path "${SOURCE_ROOT}/runtime/mac/java"

rm -rf "${VENDOR_ROOT}"
mkdir -p "${VENDOR_ROOT}/Horosa-Web/astrostudyui/scripts"
mkdir -p "${VENDOR_ROOT}/Horosa-Web/astrostudyui/src/utils"
mkdir -p "${VENDOR_ROOT}/Horosa-Web/scripts"
mkdir -p "${VENDOR_ROOT}/runtime/mac/bundle"

rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/Horosa-Web/start_horosa_local.sh" "${VENDOR_ROOT}/Horosa-Web/"
rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/Horosa-Web/stop_horosa_local.sh" "${VENDOR_ROOT}/Horosa-Web/"
rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/Horosa-Web/scripts/repairEmbeddedPythonRuntime.py" "${VENDOR_ROOT}/Horosa-Web/scripts/"
rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/Horosa-Web/astrostudyui/dist-file" "${VENDOR_ROOT}/Horosa-Web/astrostudyui/"
rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/Horosa-Web/astrostudyui/scripts/warmHorosaRuntime.js" "${VENDOR_ROOT}/Horosa-Web/astrostudyui/scripts/"
rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/Horosa-Web/astrostudyui/src/utils/aiExport.js" "${VENDOR_ROOT}/Horosa-Web/astrostudyui/src/utils/"
rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/Horosa-Web/astropy" "${VENDOR_ROOT}/Horosa-Web/"
rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/Horosa-Web/flatlib-ctrad2" "${VENDOR_ROOT}/Horosa-Web/"
rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/runtime/mac/python" "${VENDOR_ROOT}/runtime/mac/"
rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/runtime/mac/java" "${VENDOR_ROOT}/runtime/mac/"

if [ -f "${SOURCE_ROOT}/Horosa-Web/astrostudysrv/astrostudyboot/target/astrostudyboot.jar" ]; then
  rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/Horosa-Web/astrostudysrv/astrostudyboot/target/astrostudyboot.jar" "${VENDOR_ROOT}/runtime/mac/bundle/"
elif [ -f "${SOURCE_ROOT}/runtime/mac/bundle/astrostudyboot.jar" ]; then
  rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/runtime/mac/bundle/astrostudyboot.jar" "${VENDOR_ROOT}/runtime/mac/bundle/"
else
  echo "missing astrostudyboot.jar in both build output and runtime fallback" >&2
  exit 1
fi

find "${VENDOR_ROOT}" -type d \( -name '.pytest_cache' -o -name '.cache' -o -name '__pycache__' -o -name '.horosa-logs' \) -prune -exec rm -rf {} + 2>/dev/null || true
find "${VENDOR_ROOT}" \( -name '.DS_Store' -o -name '._*' -o -name '*.pyc' -o -name '*.pyo' -o -name '*.map' -o -name '*.tmp' -o -name '*.temp' -o -name '*.pid' \) -delete 2>/dev/null || true

echo "vendored runtime sources ready at ${VENDOR_ROOT}"
