#!/usr/bin/env bash
# 发布的维护机半边（v0.38.0 A5 起）：seed（darwin-arm64 payload）→ darwin manifest（本地校验用）→ SBOM → MCPB → wheel →
# SHA256SUMS → verify → `--draft` 把 seed / .mcpb / wheel / SBOM 放上一个 **draft** release → `--dispatch` 触发
# `release-runtime.yml`（托管 runner 从 seed 派生 Windows 半、装双平台清单、三台真机矩阵；`publish=true` 才转公开）。
#
# 为什么要有它：v0.27.0 首发时这串是手打的，SBOM（OPERATIONS.md 明列的必要资产、生成器一直躺在
# scripts/generate_sbom.py）被整个漏掉——手打清单必漏，漏的永远是最不显眼那件。发布步骤只允许
# 以脚本形态存在；release-completeness.yml 现在也断言 SBOM 资产在场，双保险。
#
# 🔴 本脚本**从不**创建公开 release、**从不**上传清单：清单只在两平台齐了才由 release-runtime.yml 的 assemble 上到
# draft；转公开由 publish job 在 `sync_windows_release.py --check --tag vX --draft` 报 [OK] 之后做。这就是「缺半」
# 窗口的终结（此前 `--publish` 会先发一个 darwin-only 清单的公开 release，Windows 用户在构建机补传前 install 全 404）。
#
# 用法：
#   bash horosa-skill/scripts/publish_release.sh                       # 构建 + 校验，不上传（安全默认）
#   bash horosa-skill/scripts/publish_release.sh --draft               # 另建/复用 draft release，上传 seed / .mcpb / wheel / SBOM
#   bash horosa-skill/scripts/publish_release.sh --draft --dispatch    # 再触发 release-runtime.yml（publish=false）并 gh run watch
#   之后：python horosa-skill/scripts/sync_windows_release.py --check --tag vX.Y.Z --draft   # 期望 [OK]
#         gh workflow run release-runtime.yml -f version=X.Y.Z -f publish=true               # 转公开 latest
#
# 前置（脚本会拦）：preflight_release.py 已在本机全绿；tag vX.Y.Z 已推送。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SKILL="${ROOT}/horosa-skill"
DIST="${SKILL}/dist/runtime"
REPO="${HOROSA_RUNTIME_RELEASE_REPO:-Horace-Maxwell/horosa-skill}"
DRAFT=0
DISPATCH=0
for arg in "$@"; do
  case "${arg}" in
    --draft) DRAFT=1 ;;
    --dispatch) DISPATCH=1 ;;
    --publish)
      echo "--publish 已移除（v0.38.0 A5）：它会先发一个 darwin-only 清单的公开 release。改用 --draft [--dispatch]，" >&2
      echo "转公开由 release-runtime.yml 的 publish job 在双平台 [OK] 之后做。" >&2
      exit 2 ;;
    *) echo "未知参数 ${arg}（可用：--draft --dispatch）" >&2; exit 2 ;;
  esac
done
[ "${DISPATCH}" = "1" ] && [ "${DRAFT}" != "1" ] && { echo "--dispatch 需要 --draft（流水线的 seed 来自 draft release）" >&2; exit 2; }

VERSION="$(python3 - <<PY
import tomllib, pathlib
print(tomllib.loads(pathlib.Path("${SKILL}/pyproject.toml").read_text(encoding="utf-8"))["project"]["version"])
PY
)"
TAG="v${VERSION}"
TAR="horosa-runtime-darwin-arm64-${TAG}.tar.gz"
# 资产 URL 钉 tag（v0.38.0 A3）：`releases/latest/download/...` 的 URL 让 pin-forward（清单指着上一版的包）从清单本身
# 看不出来；钉了 tag，release-completeness / sync_windows_release --check 只读清单就能判。安装器仍从 latest 取清单。
BASE_URL="https://github.com/${REPO}/releases/download/${TAG}"

if [ "${DRAFT}" = "1" ]; then
  # tag 必须已存在且指向远端——发布资产挂在 tag 上，没 tag 的「发布」是走不完的半程。
  if ! git -C "${ROOT}" rev-parse -q --verify "refs/tags/${TAG}" >/dev/null; then
    echo "tag ${TAG} 不存在 —— 先跑 preflight_release.py（全绿）再打 tag，再回来发布。" >&2
    exit 1
  fi
fi

echo "=== [1/8] darwin runtime payload（705MB 级，缓存命中时数分钟）==="
bash "${SKILL}/scripts/package_runtime_payload.sh"

echo "=== [2/8] darwin-only runtime-manifest.json ==="
python3 "${SKILL}/scripts/generate_release_manifest.py" \
  --version "${VERSION}" \
  --darwin-archive "${DIST}/${TAR}" \
  --darwin-url "${BASE_URL}/${TAR}" \
  --output "${DIST}/runtime-manifest.json"

echo "=== [3/8] SBOM（v0.27.0 漏过的那件）==="
python3 "${SKILL}/scripts/generate_sbom.py" \
  --project-root "${SKILL}" \
  --runtime-manifest "${DIST}/runtime-manifest.json" \
  --output "${DIST}/horosa-skill-sbom.json"

echo "=== [4/8] MCPB bundle（Claude Desktop 一键安装；server.json 的 mcpb package 直指它）==="
bash "${SKILL}/scripts/build_mcpb.sh" "${DIST}"
MCPB="horosa-skill-${VERSION}.mcpb"
[ -f "${DIST}/${MCPB}" ] || { echo "build_mcpb.sh 没产出 ${MCPB}" >&2; exit 1; }

echo "=== [5/8] wheel（零安装资产：uvx --from <wheel URL>，免 git、免 PyPI；v0.38.0 B3）==="
# 纯 Python wheel，与 PyPI 通道用的是同一个 `uv build`；README/SKILL/server.json 里钉版本的 URL 直指它，
# release-completeness.yml 断言它在场并真跑一次 `uvx --from <URL> horosa-skill --version`。
WHEEL="horosa_skill-${VERSION}-py3-none-any.whl"
rm -f "${DIST}/${WHEEL}"
( cd "${SKILL}" && uv build --wheel --out-dir "${DIST}" )
[ -f "${DIST}/${WHEEL}" ] || { echo "uv build 没产出 ${WHEEL}（hatchling 会把 horosa-skill 归一成 horosa_skill）" >&2; exit 1; }

echo "=== [6/8] SHA256SUMS.txt ==="
( cd "${DIST}" && shasum -a 256 "${TAR}" "${MCPB}" "${WHEEL}" > SHA256SUMS.txt && cat SHA256SUMS.txt )
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

echo "=== [7/8] verify_runtime_release.py ==="
python3 "${SKILL}/scripts/verify_runtime_release.py" \
  --darwin-archive "${DIST}/${TAR}" \
  --manifest "${DIST}/runtime-manifest.json"

if [ "${DRAFT}" != "1" ]; then
  echo "=== [8/8] 未上传（安全默认）。要进流水线：$0 --draft [--dispatch] ==="
  exit 0
fi

echo "=== [8/8] draft release ${TAG}：seed / .mcpb / wheel / SBOM（清单与 Windows 半由 release-runtime.yml 补齐）==="
# 🔴 只上 draft、绝不上清单：清单只在两平台齐了才由流水线放上去，公开由 publish job 在 [OK] 之后做。
DRAFT_ASSETS=("${DIST}/${TAR}" "${DIST}/${MCPB}" "${DIST}/${WHEEL}" "${DIST}/horosa-skill-sbom.json")
if gh release view "${TAG}" --repo "${REPO}" >/dev/null 2>&1; then
  IS_DRAFT="$(gh release view "${TAG}" --repo "${REPO}" --json isDraft -q .isDraft)"
  if [ "${IS_DRAFT}" != "true" ]; then
    echo "release ${TAG} 已是公开状态——本脚本只往 draft 放资产。已公开的版本走 sync_windows_release.py --check 判缺口。" >&2
    exit 1
  fi
  gh release upload "${TAG}" "${DRAFT_ASSETS[@]}" --repo "${REPO}" --clobber
else
  gh release create "${TAG}" "${DRAFT_ASSETS[@]}" --repo "${REPO}" --draft \
    --title "${TAG}" \
    --notes "Draft：seed / .mcpb / wheel / SBOM 已上传；Windows 半、双平台清单、SHA256SUMS 由 release-runtime.yml 补齐后转公开。发布说明请随后编辑补全。"
fi
echo "draft ${TAG} 就绪。"

if [ "${DISPATCH}" != "1" ]; then
  echo "下一步：gh workflow run release-runtime.yml -f version=${VERSION}（或本脚本加 --dispatch）；"
  echo "  再 python horosa-skill/scripts/sync_windows_release.py --check --tag ${TAG} --draft 期望 [OK]，"
  echo "  最后 gh workflow run release-runtime.yml -f version=${VERSION} -f publish=true 转公开。"
  exit 0
fi

echo "=== dispatch release-runtime.yml（version=${VERSION} publish=false run_matrix=true）==="
gh workflow run release-runtime.yml --repo "${REPO}" -f "version=${VERSION}" -f publish=false -f run_matrix=true -f arm_nonblocking=true -f dry_run=false
sleep 8
RUN_ID="$(gh run list --repo "${REPO}" --workflow release-runtime.yml --limit 1 --json databaseId -q '.[0].databaseId')"
echo "run ${RUN_ID}：gh run watch ${RUN_ID} --repo ${REPO} --exit-status"
gh run watch "${RUN_ID}" --repo "${REPO}" --exit-status
echo
echo "流水线绿了。判据仍是：python horosa-skill/scripts/sync_windows_release.py --check --tag ${TAG} --draft → [OK]；"
echo "然后 gh workflow run release-runtime.yml -f version=${VERSION} -f publish=true 转公开，再 --check 公开 latest。"
