#!/usr/bin/env bash
# mac 半边发布一条龙：payload → darwin manifest → SBOM → MCPB → SHA256SUMS → verify → gh release 上传。
#
# 为什么要有它：v0.27.0 首发时这串是手打的，SBOM（OPERATIONS.md 明列的必要资产、生成器一直躺在
# scripts/generate_sbom.py）被整个漏掉——手打清单必漏，漏的永远是最不显眼那件。发布步骤只允许
# 以脚本形态存在；release-completeness.yml 现在也断言 SBOM 资产在场，双保险。
#
# 分工（AGENTS §7）：本脚本只管 darwin 半边 + 单平台 manifest。Windows 半边**必须**由构建机跑
# `sync_windows_release.py --upload` 补传（它会重生成双平台 manifest + SHA256SUMS）；
# 完整性判据始终是它 `--check` 的 [GAP]/[OK]，不是本脚本的退出码。
#
# 用法：
#   bash horosa-skill/scripts/publish_darwin_release.sh            # 构建+校验，不上传（安全默认）
#   bash horosa-skill/scripts/publish_darwin_release.sh --publish  # 另创建 release 并上传资产
#
# 前置（脚本会拦）：preflight_release.py 已在本机全绿；tag vX.Y.Z 已推送。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SKILL="${ROOT}/horosa-skill"
DIST="${SKILL}/dist/runtime"
REPO="${HOROSA_RUNTIME_RELEASE_REPO:-Horace-Maxwell/horosa-skill}"
PUBLISH=0
[ "${1:-}" = "--publish" ] && PUBLISH=1

VERSION="$(python3 - <<PY
import tomllib, pathlib
print(tomllib.loads(pathlib.Path("${SKILL}/pyproject.toml").read_text(encoding="utf-8"))["project"]["version"])
PY
)"
TAG="v${VERSION}"
TAR="horosa-runtime-darwin-arm64-${TAG}.tar.gz"
BASE_URL="https://github.com/${REPO}/releases/latest/download"

if [ "${PUBLISH}" = "1" ]; then
  # tag 必须已存在且指向远端——发布资产挂在 tag 上，没 tag 的「发布」是走不完的半程。
  if ! git -C "${ROOT}" rev-parse -q --verify "refs/tags/${TAG}" >/dev/null; then
    echo "tag ${TAG} 不存在 —— 先跑 preflight_release.py（全绿）再打 tag，再回来发布。" >&2
    exit 1
  fi
fi

echo "=== [1/7] darwin runtime payload（705MB 级，缓存命中时数分钟）==="
bash "${SKILL}/scripts/package_runtime_payload.sh"

echo "=== [2/7] darwin-only runtime-manifest.json ==="
python3 "${SKILL}/scripts/generate_release_manifest.py" \
  --version "${VERSION}" \
  --darwin-archive "${DIST}/${TAR}" \
  --darwin-url "${BASE_URL}/${TAR}" \
  --output "${DIST}/runtime-manifest.json"

echo "=== [3/7] SBOM（v0.27.0 漏过的那件）==="
python3 "${SKILL}/scripts/generate_sbom.py" \
  --project-root "${SKILL}" \
  --runtime-manifest "${DIST}/runtime-manifest.json" \
  --output "${DIST}/horosa-skill-sbom.json"

echo "=== [4/7] MCPB bundle（Claude Desktop 一键安装；server.json 的 mcpb package 直指它）==="
bash "${SKILL}/scripts/build_mcpb.sh" "${DIST}"
MCPB="horosa-skill-${VERSION}.mcpb"
[ -f "${DIST}/${MCPB}" ] || { echo "build_mcpb.sh 没产出 ${MCPB}" >&2; exit 1; }

echo "=== [5/7] SHA256SUMS.txt ==="
( cd "${DIST}" && shasum -a 256 "${TAR}" "${MCPB}" > SHA256SUMS.txt && cat SHA256SUMS.txt )
# server.json 的 mcpb package 带 fileSha256，客户端安装前会校验它 —— 这里回填，别让它留空发出去。
python3 - "${SKILL}/../server.json" "${DIST}/${MCPB}" <<'BACKFILL'
import hashlib, json, sys
server_json, bundle = sys.argv[1], sys.argv[2]
digest = hashlib.sha256(open(bundle, "rb").read()).hexdigest()
data = json.load(open(server_json, encoding="utf-8"))
changed = False
for package in data.get("packages", []):
    if package.get("registryType") == "mcpb" and package.get("fileSha256") != digest:
        package["fileSha256"] = digest
        changed = True
if changed:
    with open(server_json, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"server.json: mcpb fileSha256 -> {digest}")
    print("   ↳ 记得随发布提交它：git commit -m 'chore(release): pin mcpb sha'")
else:
    print("server.json: mcpb fileSha256 已是最新")
BACKFILL

echo "=== [6/7] verify_runtime_release.py ==="
python3 "${SKILL}/scripts/verify_runtime_release.py" \
  --darwin-archive "${DIST}/${TAR}" \
  --manifest "${DIST}/runtime-manifest.json"

if [ "${PUBLISH}" != "1" ]; then
  echo "=== [7/7] 未上传（安全默认）。要发布：$0 --publish ==="
  exit 0
fi

echo "=== [7/7] gh release ${TAG} ==="
ASSETS=("${DIST}/${TAR}" "${DIST}/runtime-manifest.json" "${DIST}/SHA256SUMS.txt" "${DIST}/horosa-skill-sbom.json" "${DIST}/${MCPB}")
if gh release view "${TAG}" --repo "${REPO}" >/dev/null 2>&1; then
  gh release upload "${TAG}" "${ASSETS[@]}" --repo "${REPO}" --clobber
else
  gh release create "${TAG}" "${ASSETS[@]}" --repo "${REPO}" \
    --title "${TAG}" \
    --notes "darwin 半边已上传。⚠️ Windows 半边待构建机 sync_windows_release.py --upload 补传（判据：--check 的 [GAP]/[OK]）。发布说明请随后编辑补全。"
fi
echo
echo "darwin 半边发布完成。下一步（Windows 构建机）："
echo "  git pull 到本发布 commit → python horosa-skill/scripts/sync_windows_release.py --upload"
echo "最终判据：python horosa-skill/scripts/sync_windows_release.py --check 无 [GAP]。"
