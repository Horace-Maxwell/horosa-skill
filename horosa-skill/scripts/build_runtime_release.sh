#!/usr/bin/env bash
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

"${ROOT}/horosa-skill/scripts/package_runtime_payload.sh"
python3 "${ROOT}/horosa-skill/scripts/build_runtime_release_windows.py"
mkdir -p "${DIST_ROOT}"
python3 "${ROOT}/horosa-skill/scripts/generate_release_manifest.py" \
  --version "${VERSION}" \
  --darwin-archive "${DIST_ROOT}/horosa-runtime-darwin-arm64-v${VERSION}.tar.gz" \
  --darwin-url "${RELEASE_BASE_URL}/horosa-runtime-darwin-arm64-v${VERSION}.tar.gz" \
  --windows-archive "${DIST_ROOT}/horosa-runtime-win32-x64-v${VERSION}.zip" \
  --windows-url "${RELEASE_BASE_URL}/horosa-runtime-win32-x64-v${VERSION}.zip" \
  --output "${DIST_ROOT}/runtime-manifest.json"

(
  cd "${DIST_ROOT}"
  shasum -a 256 "horosa-runtime-darwin-arm64-v${VERSION}.tar.gz" "horosa-runtime-win32-x64-v${VERSION}.zip" > SHA256SUMS.txt
)

python3 "${ROOT}/horosa-skill/scripts/verify_runtime_release.py" \
  --darwin-archive "${DIST_ROOT}/horosa-runtime-darwin-arm64-v${VERSION}.tar.gz" \
  --windows-archive "${DIST_ROOT}/horosa-runtime-win32-x64-v${VERSION}.zip" \
  --manifest "${DIST_ROOT}/runtime-manifest.json"
