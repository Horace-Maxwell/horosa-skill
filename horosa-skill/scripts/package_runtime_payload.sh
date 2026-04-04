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
ARCHIVE_PLATFORM="${ARCHIVE_PLATFORM:-darwin-arm64}"

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

require_path "${SOURCE_ROOT}/Horosa-Web/start_horosa_local.sh"
require_path "${SOURCE_ROOT}/Horosa-Web/stop_horosa_local.sh"
require_path "${SOURCE_ROOT}/Horosa-Web/scripts/repairEmbeddedPythonRuntime.py"
require_path "${SOURCE_ROOT}/Horosa-Web/astrostudyui/dist-file"
require_path "${SOURCE_ROOT}/Horosa-Web/astrostudyui/scripts/warmHorosaRuntime.js"
require_path "${SOURCE_ROOT}/Horosa-Web/astropy"
require_path "${SOURCE_ROOT}/Horosa-Web/flatlib-ctrad2"
require_path "${JAVA_SOURCE_DIR}"
require_path "${PYTHON_SOURCE_DIR}"
require_path "${BOOT_JAR_SOURCE}"

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
rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/Horosa-Web/flatlib-ctrad2/flatlib" "${STAGE_ROOT}/Horosa-Web/flatlib-ctrad2/"
if [ -f "${SOURCE_ROOT}/Horosa-Web/flatlib-ctrad2/LICENSE" ]; then
  rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/Horosa-Web/flatlib-ctrad2/LICENSE" "${STAGE_ROOT}/Horosa-Web/flatlib-ctrad2/"
fi
rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/Horosa-Web/astrostudyui/dist-file" "${STAGE_ROOT}/Horosa-Web/astrostudyui/"
rsync -a "${RSYNC_FILTERS[@]}" "${SOURCE_ROOT}/Horosa-Web/astrostudyui/scripts/warmHorosaRuntime.js" "${STAGE_ROOT}/Horosa-Web/astrostudyui/scripts/"
build_embedded_java_runtime "${JAVA_SOURCE_DIR}" "${STAGE_ROOT}/runtime/mac/java"
rsync -a "${RSYNC_FILTERS[@]}" "${PYTHON_SOURCE_DIR}" "${STAGE_ROOT}/runtime/mac/"
cp -f "${BOOT_JAR_SOURCE}" "${STAGE_ROOT}/runtime/mac/bundle/astrostudyboot.jar"

rm -rf \
  "${STAGE_ROOT}/runtime/mac/python/lib/python3.12/ensurepip" \
  "${STAGE_ROOT}/runtime/mac/python/include" \
  "${STAGE_ROOT}/runtime/mac/python/share" \
  "${STAGE_ROOT}/runtime/mac/python/Resources/English.lproj/Documentation" \
  "${STAGE_ROOT}/runtime/mac/python/lib/python3.12/config-3.12-darwin"
find "${STAGE_ROOT}/runtime/mac/python/lib" -type d \( -name 'test' -o -name 'tests' -o -name '__pycache__' -o -name 'idlelib' -o -name 'turtledemo' \) -prune -exec rm -rf {} + 2>/dev/null || true
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
    },
    "artifacts": {
        "horosa_web_root": "Horosa-Web",
        "astropy_root": "Horosa-Web/astropy",
        "flatlib_root": "Horosa-Web/flatlib-ctrad2/flatlib",
        "swefiles_root": "Horosa-Web/flatlib-ctrad2/flatlib/resources/swefiles",
        "boot_jar": "runtime/mac/bundle/astrostudyboot.jar",
    },
}
(stage_root / "runtime-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

(
  cd "${BUILD_ROOT}"
  tar -czf "${ARCHIVE_PATH}" runtime-payload
)

echo "runtime payload ready: ${ARCHIVE_PATH}"
