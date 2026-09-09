#!/usr/bin/env bash
# 打一个 .mcpb 包（Claude Desktop 的一键安装格式）。
#
# bundle 根 = horosa-skill/：MCPB 的 `server.type: "uv"` 会在包根跑 `uv run --directory ${__dirname}`，
# 所以那一层必须持有 pyproject.toml。排除项见 .mcpbignore。
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${1:-${HERE}/dist}"
cd "${HERE}"

VERSION="$(python3 -c "import re,pathlib;print(re.search(r'^version = \"([^\"]+)\"', pathlib.Path('pyproject.toml').read_text(), re.M).group(1))")"
BUNDLE="${OUT_DIR}/horosa-skill-${VERSION}.mcpb"
mkdir -p "${OUT_DIR}"

echo "[1/3] validate manifest"
npx -y @anthropic-ai/mcpb@2 validate manifest.json

echo "[2/3] pack -> ${BUNDLE}"
npx -y @anthropic-ai/mcpb@2 pack . "${BUNDLE}"

echo "[3/3] sha256"
if command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "${BUNDLE}"
else
  sha256sum "${BUNDLE}"
fi
