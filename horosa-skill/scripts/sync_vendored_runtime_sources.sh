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
  '--exclude=${env:*'
  '--exclude=*/${env:*'
  "--exclude=.horosa-logs"
  "--exclude=*/.horosa-logs"
  # SQLite 日志侧车（WAL/SHM/journal）：上游进程打开过库就会留在磁盘上、git 不跟踪。拷进镜像等于
  # 让打包出去的 runtime 在打开库时回放一段上游未 checkpoint 的写入——库内容偏离 git 里的那份 .sqlite。
  "--exclude=*.sqlite-wal"
  "--exclude=*.sqlite-shm"
  "--exclude=*.sqlite-journal"
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
# (wangji/wuzhao/taixuan/jingjue/shenyishu). The 9 kinastro-* 神数 share the kinastro engine, which IS
# vendored below (engine-only: `astro/` + root .py + interpretations + LICENSE; the ~26 MB tools/cities
# geocoding DB + streamlit ui/frontend/docs are excluded — see AGENTS.md 神数 tier table).
require_path "${SOURCE_ROOT}/Horosa-Web/vendor/kin_year_domain.py"
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
# Shared top-level module (upstream v3.5.0 全年份域): 16 engine files lazily `from kin_year_domain import
# solar_term_name/extreme_pillars`. Missing it → every ken/神数 engine 500s on first request (BC/远期
# year fallback path). Its sibling月柱边界回归测试随行(小体积,自检有用). Both live at vendor root, not
# inside an engine dir, so they are copied explicitly here rather than by the loop above.
rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/Horosa-Web/vendor/kin_year_domain.py" "${VENDOR_ROOT}/Horosa-Web/vendor/"
if [ -f "${SOURCE_ROOT}/Horosa-Web/vendor/test_month_pillar_boundary.py" ]; then
  rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/Horosa-Web/vendor/test_month_pillar_boundary.py" "${VENDOR_ROOT}/Horosa-Web/vendor/"
fi
# vendor 根级的第三方引擎清单 README（纯文档）：随镜像走，省得守卫每轮报「根级新增」notice。
if [ -f "${SOURCE_ROOT}/Horosa-Web/vendor/README.md" ]; then
  rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/Horosa-Web/vendor/README.md" "${VENDOR_ROOT}/Horosa-Web/vendor/"
fi
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

# core-js 的 vendored JS 树受 git 跟踪、却**不**由本脚本拷贝（逐文件按需移植 + 少量 shim）。
# 它长期零守卫：上游改了 JS，这里毫无信号。同步完顺手核一遍同源性并把上游状态写进 contracts/，
# 让每次同步在 git 里留痕（漂移则报告，不阻断——bespoke shim 本就允许存在）。
echo "checking core-js vendored tree + upstream contract currency ..."
HOROSA_SOURCE_ROOT="${SOURCE_ROOT}" python3 "${ROOT}/horosa-skill/scripts/verify_upstream_sync.py" --write-state || {
  echo "  ^ 上游同源检查未通过：若刚重同步到新版上游，这是预期的红——去回填新增段并推进"
  echo "    MIRRORED_UPSTREAM_AIEXPORT_VERSION，再跑 verify_export_section_baseline.py --update-baseline。"
}
