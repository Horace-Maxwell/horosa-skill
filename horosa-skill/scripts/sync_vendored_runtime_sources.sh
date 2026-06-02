#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SOURCE_ROOT="${HOROSA_SOURCE_ROOT:-$(cd "${ROOT}/.." && pwd)}"
WINDOWS_SOURCE_ROOT="${HOROSA_WINDOWS_SOURCE_ROOT:-}"
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
# ken engines backing the chart-service qimen/taiyi/jinkou endpoints + the 5 standalone 神数 engines
# (wangji/wuzhao/taixuan/jingjue/shenyishu). The 9 kinastro-* 神数 share the ~61 MB kinastro engine and
# are intentionally NOT vendored (out of skill scope — see AGENTS.md 神数 tier table).
require_path "${SOURCE_ROOT}/Horosa-Web/vendor/kinqimen"
require_path "${SOURCE_ROOT}/Horosa-Web/vendor/kintaiyi"
require_path "${SOURCE_ROOT}/Horosa-Web/vendor/kinjinkou"
require_path "${SOURCE_ROOT}/Horosa-Web/vendor/kinwangji"
require_path "${SOURCE_ROOT}/Horosa-Web/vendor/kinwuzhao"
require_path "${SOURCE_ROOT}/Horosa-Web/vendor/taixuanshifa"
require_path "${SOURCE_ROOT}/Horosa-Web/vendor/jingjue"
require_path "${SOURCE_ROOT}/Horosa-Web/vendor/shenyishu"
require_path "${SOURCE_ROOT}/Horosa-Web/vendor/kinastro/astro"
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
mkdir -p "${VENDOR_ROOT}/Horosa-Web/vendor"
for ken_engine in kinqimen kintaiyi kinjinkou kinwangji kinwuzhao taixuanshifa jingjue shenyishu; do
  rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/Horosa-Web/vendor/${ken_engine}" "${VENDOR_ROOT}/Horosa-Web/vendor/"
done
# kinastro engine backs the 9 kinastro-* 神数 (shaozi/tieban/fendjing/beiji/nanji/chunzi/xianqin/
# cetian/qizhengkin). Vendor only the engine (`astro/` + root .py + interpretations + LICENSE); the
# ~26 MB tools/cities geocoding DB + the streamlit ui/frontend/docs are not needed for ganzhi 神数.
rsync -a "${RSYNC_FILTERS[@]}" \
  --exclude='tools' --exclude='ui' --exclude='frontend' --exclude='docs' --exclude='wiki' \
  --exclude='examples' --exclude='tests' --exclude='styles' --exclude='scripts' \
  --exclude='.streamlit' --exclude='.github' --exclude='.devcontainer' --exclude='.git' \
  "${SOURCE_ROOT}/Horosa-Web/vendor/kinastro" "${VENDOR_ROOT}/Horosa-Web/vendor/"
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

if [ -n "${WINDOWS_SOURCE_ROOT}" ]; then
  WINDOWS_SOURCE_ROOT="$(cd "${WINDOWS_SOURCE_ROOT}" && pwd)"
  WINDOWS_RUNTIME_ROOT="${WINDOWS_SOURCE_ROOT}/local/workspace/runtime/windows"
  WINDOWS_PREP_ROOT="${WINDOWS_SOURCE_ROOT}/prepareruntime"

  require_path "${WINDOWS_RUNTIME_ROOT}"
  require_path "${WINDOWS_PREP_ROOT}/Prepare_Runtime_Windows.ps1"
  require_path "${WINDOWS_PREP_ROOT}/Prepare_Runtime_Windows.bat"

  mkdir -p "${VENDOR_ROOT}/runtime"
  rm -rf "${VENDOR_ROOT}/runtime/windows"
  rm -rf "${VENDOR_ROOT}/prepareruntime"

  rsync -a "${RSYNC_FILTERS[@]}" "${WINDOWS_RUNTIME_ROOT}/" "${VENDOR_ROOT}/runtime/windows/"
  rsync -a "${RSYNC_FILTERS[@]}" "${WINDOWS_PREP_ROOT}/" "${VENDOR_ROOT}/prepareruntime/"
fi

echo "vendored runtime sources ready at ${VENDOR_ROOT}"
