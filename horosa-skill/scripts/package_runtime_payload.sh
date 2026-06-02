#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SKILL_ROOT="${ROOT}/horosa-skill"
SOURCE_ROOT="${ROOT}/vendor/runtime-source"
BUILD_ROOT="${SKILL_ROOT}/build/runtime"
STAGE_ROOT="${BUILD_ROOT}/runtime-payload"
DIST_ROOT="${SKILL_ROOT}/dist/runtime"
JAVA_SOURCE_DIR="${SOURCE_ROOT}/runtime/mac/java"
PYTHON_SOURCE_DIR="${SOURCE_ROOT}/runtime/mac/python"
BOOT_JAR_SOURCE="${SOURCE_ROOT}/runtime/mac/bundle/astrostudyboot.jar"
CORE_JS_ROOT="${SKILL_ROOT}/horosa-core-js"
ARCHIVE_PLATFORM="${ARCHIVE_PLATFORM:-darwin-arm64}"
NODE_VERSION_LINE_URL="${NODE_VERSION_LINE_URL:-https://nodejs.org/dist/latest-v22.x/SHASUMS256.txt}"
DOWNLOAD_ROOT="${BUILD_ROOT}/downloads"

RSYNC_FILTERS=(
  "--exclude=.DS_Store"
  "--exclude=._*"
  "--exclude=_CodeSignature"
  "--exclude=*/_CodeSignature"
  '--exclude=${env:HOME}'
  '--exclude=*/${env:HOME}'
  "--exclude=.horosa-logs"
  "--exclude=*/.horosa-logs"
  "--exclude=.pytest_cache"
  "--exclude=*/.pytest_cache"
  "--exclude=.cache"
  "--exclude=*/.cache"
  "--exclude=__pycache__"
  "--exclude=*/__pycache__"
  "--exclude=*.pyc"
  "--exclude=*.pyo"
  "--exclude=*.map"
  "--exclude=*.tmp"
  "--exclude=*.temp"
  "--exclude=*.pid"
)

read -r VERSION ARCHIVE_NAME <<EOF
$(PYPROJECT_PATH="${SKILL_ROOT}/pyproject.toml" python3 - <<'PY'
import os, pathlib, tomllib
pyproject = pathlib.Path(os.environ["PYPROJECT_PATH"])
data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
version = data["project"]["version"]
print(version, f"horosa-runtime-darwin-arm64-v{version}.tar.gz")
PY
)
EOF

ARCHIVE_PATH="${DIST_ROOT}/${ARCHIVE_NAME}"

require_path() {
  local target="$1"
  if [ ! -e "${target}" ]; then
    echo "missing required vendored source path: ${target}" >&2
    exit 1
  fi
}

build_embedded_java_runtime() {
  local src_java="$1"
  local dest_java="$2"
  local jlink_bin="${src_java}/bin/jlink"
  local jmods_dir="${src_java}/jmods"
  local jlink_modules="java.base,java.desktop,java.instrument,java.logging,java.management,java.naming,java.net.http,java.prefs,java.scripting,java.security.jgss,java.sql,java.xml,jdk.charsets,jdk.crypto.ec,jdk.management,jdk.unsupported,jdk.zipfs"

  if [ -x "${jlink_bin}" ] && [ -d "${jmods_dir}" ]; then
    "${jlink_bin}" \
      --module-path "${jmods_dir}" \
      --add-modules "${jlink_modules}" \
      --strip-debug \
      --no-header-files \
      --no-man-pages \
      --output "${dest_java}"
    return 0
  fi

  rsync -a "${RSYNC_FILTERS[@]}" "${src_java}" "$(dirname "${dest_java}")/"
}

resolve_node_archive_name() {
  local arch_suffix="darwin-arm64"
  if [[ "${ARCHIVE_PLATFORM}" == *"x64"* ]]; then
    arch_suffix="darwin-x64"
  fi
  curl -fsSL "${NODE_VERSION_LINE_URL}" | awk "/node-v.*-${arch_suffix}\\.tar\\.gz/{print \$2; exit}"
}

ensure_node_runtime() {
  local dest_root="$1"
  local node_src="${SOURCE_ROOT}/runtime/mac/node"
  if [ -x "${node_src}/bin/node" ]; then
    rsync -a "${RSYNC_FILTERS[@]}" "${node_src}" "${STAGE_ROOT}/runtime/mac/"
    return 0
  fi

  mkdir -p "${DOWNLOAD_ROOT}"
  local archive_name
  archive_name="$(resolve_node_archive_name)"
  if [ -z "${archive_name}" ]; then
    echo "failed to resolve latest macOS Node.js archive name" >&2
    exit 1
  fi
  local archive_path="${DOWNLOAD_ROOT}/${archive_name}"
  if [ ! -f "${archive_path}" ]; then
    curl -fL "https://nodejs.org/dist/latest-v22.x/${archive_name}" -o "${archive_path}"
  fi
  rm -rf "${dest_root}"
  mkdir -p "${dest_root}"
  tar -xzf "${archive_path}" -C "${dest_root}" --strip-components=1
}

require_path "${SOURCE_ROOT}/Horosa-Web/start_horosa_local.sh"
require_path "${SOURCE_ROOT}/Horosa-Web/stop_horosa_local.sh"
require_path "${SOURCE_ROOT}/Horosa-Web/scripts/repairEmbeddedPythonRuntime.py"
require_path "${SOURCE_ROOT}/Horosa-Web/astrostudyui/dist-file"
require_path "${SOURCE_ROOT}/Horosa-Web/astrostudyui/scripts/warmHorosaRuntime.js"
require_path "${SOURCE_ROOT}/Horosa-Web/astropy"
require_path "${SOURCE_ROOT}/Horosa-Web/flatlib-ctrad2"
require_path "${SOURCE_ROOT}/Horosa-Web/vendor/kinqimen"
require_path "${SOURCE_ROOT}/Horosa-Web/vendor/kintaiyi"
require_path "${SOURCE_ROOT}/Horosa-Web/vendor/kinjinkou"
require_path "${JAVA_SOURCE_DIR}"
require_path "${PYTHON_SOURCE_DIR}"
require_path "${BOOT_JAR_SOURCE}"
require_path "${CORE_JS_ROOT}/bin/cli.mjs"

# 邵子参评数 (canping) / 河洛理数 (heluo) compute their four pillars in-process via the vendored bazi
# chain, which imports the `lunar-javascript` npm package. Install the production dep so the unfiltered
# rsync of horosa-core-js below bundles node_modules into the payload (RSYNC_FILTERS has no
# node_modules exclusion). Without this, a clean/CI build ships a runtime where canping/heluo throw
# "Cannot find package 'lunar-javascript'" at runtime.
echo "installing horosa-core-js production deps (lunar-javascript)…"
( cd "${CORE_JS_ROOT}" && npm install --omit=dev --no-audit --no-fund --loglevel=error )
require_path "${CORE_JS_ROOT}/node_modules/lunar-javascript/package.json"

rm -rf "${BUILD_ROOT}"
mkdir -p "${STAGE_ROOT}/Horosa-Web/astrostudyui/scripts"
mkdir -p "${STAGE_ROOT}/Horosa-Web/scripts"
mkdir -p "${STAGE_ROOT}/Horosa-Web/astropy"
mkdir -p "${STAGE_ROOT}/Horosa-Web/flatlib-ctrad2"
mkdir -p "${STAGE_ROOT}/runtime/mac"
mkdir -p "${STAGE_ROOT}/runtime/mac/bundle"
mkdir -p "${DIST_ROOT}"

rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/Horosa-Web/start_horosa_local.sh" "${STAGE_ROOT}/Horosa-Web/"
rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/Horosa-Web/stop_horosa_local.sh" "${STAGE_ROOT}/Horosa-Web/"
rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/Horosa-Web/scripts/repairEmbeddedPythonRuntime.py" "${STAGE_ROOT}/Horosa-Web/scripts/"
rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/Horosa-Web/astropy/__init__.py" "${STAGE_ROOT}/Horosa-Web/astropy/"
rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/Horosa-Web/astropy/astrostudy" "${STAGE_ROOT}/Horosa-Web/astropy/"
rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/Horosa-Web/astropy/websrv" "${STAGE_ROOT}/Horosa-Web/astropy/"
# ken engines for the chart-service qimen/taiyi/jinkou mounts + the 5 standalone 神数 engines
# (wangji/wuzhao/taixuan/jingjue/shenyishu). Embedded Python already carries their deps
# (bidict / numpy / kerykeion / ephem / pendulum).
mkdir -p "${STAGE_ROOT}/Horosa-Web/vendor"
for ken_engine in kinqimen kintaiyi kinjinkou kinwangji kinwuzhao taixuanshifa jingjue shenyishu; do
  rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/Horosa-Web/vendor/${ken_engine}" "${STAGE_ROOT}/Horosa-Web/vendor/"
done
# kinastro engine for the 9 kinastro-* 神数 (engine only; exclude tools/cities + streamlit ui/docs).
if [ -d "${SOURCE_ROOT}/Horosa-Web/vendor/kinastro" ]; then
  rsync -a "${RSYNC_FILTERS[@]}" \
    --exclude='tools' --exclude='ui' --exclude='frontend' --exclude='docs' --exclude='wiki' \
    --exclude='examples' --exclude='tests' --exclude='styles' --exclude='scripts' \
    --exclude='.streamlit' --exclude='.github' --exclude='.devcontainer' --exclude='.git' \
    "${SOURCE_ROOT}/Horosa-Web/vendor/kinastro" "${STAGE_ROOT}/Horosa-Web/vendor/"
fi
# The bundled chart service ships qimen/taiyi/jinkou + all 14 神数 (5 standalone + 9 kinastro-*).
# The graceful-mount patch is still applied (defensive): if any engine fails to import the staged
# mount skips it so the chart service still boots offline.
KENTANG_REGISTRY="${STAGE_ROOT}/Horosa-Web/astropy/websrv/kentang/registry.py"
if [ -f "${KENTANG_REGISTRY}" ]; then
  KENTANG_REGISTRY_PATH="${KENTANG_REGISTRY}" python3 - <<'PY'
import os, pathlib
p = pathlib.Path(os.environ["KENTANG_REGISTRY_PATH"])
text = p.read_text(encoding="utf-8")
needle = (
    "def mount_kentang_services(cherrypy):\n"
    "    for spec in KENTANG_SERVICE_SPECS:\n"
    "        cherrypy.tree.mount(_load_service(spec), spec[\"mount\"])\n"
)
replacement = (
    "def mount_kentang_services(cherrypy):\n"
    "    import sys as _sys\n"
    "    for spec in KENTANG_SERVICE_SPECS:\n"
    "        try:\n"
    "            cherrypy.tree.mount(_load_service(spec), spec[\"mount\"])\n"
    "        except Exception as _exc:  # offline payload may omit some ken engines\n"
    "            print(f\"[kentang] skipping {spec.get('mount')}: {_exc}\", file=_sys.stderr)\n"
)
if needle in text:
    p.write_text(text.replace(needle, replacement), encoding="utf-8")
    print("patched staged kentang mount to skip unavailable engines")
else:
    print("WARNING: kentang mount signature not found; staged registry left unpatched", flush=True)
PY
fi
rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/Horosa-Web/flatlib-ctrad2/flatlib" "${STAGE_ROOT}/Horosa-Web/flatlib-ctrad2/"
if [ -f "${SOURCE_ROOT}/Horosa-Web/flatlib-ctrad2/LICENSE" ]; then
  rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/Horosa-Web/flatlib-ctrad2/LICENSE" "${STAGE_ROOT}/Horosa-Web/flatlib-ctrad2/"
fi
rsync -a "${RSYNC_FILTERS[@]}" --exclude='fengshui' "${SOURCE_ROOT}/Horosa-Web/astrostudyui/dist-file" "${STAGE_ROOT}/Horosa-Web/astrostudyui/"
rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/Horosa-Web/astrostudyui/scripts/warmHorosaRuntime.js" "${STAGE_ROOT}/Horosa-Web/astrostudyui/scripts/"
build_embedded_java_runtime "${JAVA_SOURCE_DIR}" "${STAGE_ROOT}/runtime/mac/java"
rsync -a "${RSYNC_FILTERS[@]}" "${PYTHON_SOURCE_DIR}" "${STAGE_ROOT}/runtime/mac/"
ensure_node_runtime "${STAGE_ROOT}/runtime/mac/node"
cp -f "${BOOT_JAR_SOURCE}" "${STAGE_ROOT}/runtime/mac/bundle/astrostudyboot.jar"
rsync -a "${RSYNC_FILTERS[@]}" "${CORE_JS_ROOT}" "${STAGE_ROOT}/"

rm -rf \
  "${STAGE_ROOT}/runtime/mac/python/lib/python3.12/ensurepip" \
  "${STAGE_ROOT}/runtime/mac/python/include" \
  "${STAGE_ROOT}/runtime/mac/python/share" \
  "${STAGE_ROOT}/runtime/mac/python/Resources/English.lproj/Documentation" \
  "${STAGE_ROOT}/runtime/mac/python/lib/python3.12/config-3.12-darwin"
# Drop __pycache__ everywhere, but only strip STDLIB test/idlelib/turtledemo dirs — never
# descend into site-packages, whose package tests (e.g. astropy/tests, required by kintaiyi's
# `import astropy`) must be kept or the bundled chart service can't mount the taiyi ken engine.
find "${STAGE_ROOT}/runtime/mac/python/lib" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
find "${STAGE_ROOT}/runtime/mac/python/lib" -type d -name 'site-packages' -prune -o -type d \( -name 'test' -o -name 'tests' -o -name 'idlelib' -o -name 'turtledemo' \) -prune -exec rm -rf {} + 2>/dev/null || true
find "${STAGE_ROOT}" -type d \( -name '.horosa-logs' -o -name '.pytest_cache' -o -name '.cache' -o -name '__pycache__' \) -prune -exec rm -rf {} + 2>/dev/null || true
find "${STAGE_ROOT}" -type d -name '_CodeSignature' -prune -exec rm -rf {} + 2>/dev/null || true
find "${STAGE_ROOT}" \( -name '._*' -o -name '.DS_Store' \) -exec rm -rf {} + 2>/dev/null || true
find "${STAGE_ROOT}" \( -name '*.pyc' -o -name '*.pyo' -o -name '*.map' -o -name '*.tmp' -o -name '*.temp' -o -name '*.pid' \) -delete 2>/dev/null || true
find "${STAGE_ROOT}/runtime/mac/python/lib" -type f \( -name '*.a' -o -name '*.o' \) -delete 2>/dev/null || true
/usr/bin/python3 "${STAGE_ROOT}/Horosa-Web/scripts/repairEmbeddedPythonRuntime.py" --repair "${STAGE_ROOT}/runtime/mac/python"

STAGE_ROOT_ENV="${STAGE_ROOT}" VERSION_ENV="${VERSION}" PLATFORM_ENV="${ARCHIVE_PLATFORM}" python3 - <<'PY'
import json, os, pathlib

stage_root = pathlib.Path(os.environ["STAGE_ROOT_ENV"])
manifest = {
    "schema_version": 1,
    "version": os.environ["VERSION_ENV"],
    "platform": os.environ["PLATFORM_ENV"],
    "runtime_layout_version": 1,
    "runtime_payload_version": os.environ["VERSION_ENV"],
    "export_registry_version": 6,
    "services": {
        "backend_url": "http://127.0.0.1:9999",
        "chart_url": "http://127.0.0.1:8899",
        "start_script": "Horosa-Web/start_horosa_local.sh",
        "stop_script": "Horosa-Web/stop_horosa_local.sh",
    },
    "runtimes": {
        "python": "runtime/mac/python/bin/python3",
        "java": "runtime/mac/java/bin/java",
        "node": "runtime/mac/node/bin/node",
    },
    "artifacts": {
        "horosa_web_root": "Horosa-Web",
        "astropy_root": "Horosa-Web/astropy",
        "flatlib_root": "Horosa-Web/flatlib-ctrad2/flatlib",
        "swefiles_root": "Horosa-Web/flatlib-ctrad2/flatlib/resources/swefiles",
        "boot_jar": "runtime/mac/bundle/astrostudyboot.jar",
        "horosa_core_js_root": "horosa-core-js",
    },
}
(stage_root / "runtime-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

(
  cd "${BUILD_ROOT}"
  tar -czf "${ARCHIVE_PATH}" runtime-payload
)

echo "runtime payload ready: ${ARCHIVE_PATH}"
