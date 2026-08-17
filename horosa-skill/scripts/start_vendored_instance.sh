#!/usr/bin/env bash
# 起**本仓 vendored 引擎**的 live 验证实例（chart 必起，--with-java 可选）。
#
# 为什么必须用脚本而不是手打（两条都咬过人）：
#   1. chart 的 PYTHONPATH 是**三段**（flatlib-ctrad2 : astropy : Horosa-Web/vendor）+ 内嵌解释器。
#      少 vendor 那段 → ken/神数引擎全挂不上，taiyi/jinkou/sanshiunited/wangji 一起红，症状像
#      「这些技法坏了」——v0.26.0 整轮把真 bug 误判成环境问题正是栽在手打命令上（AGENTS §8）。
#   2. live 验证**永不**该打默认 :8899/:9999 上恰好在跑的东西：那个栈来源不可知，可能根本不是
#      本仓的树。本脚本只用非默认端口，结束后 stop_vendored_instance.sh 按 PID 精确回收
#      （pkill 法则：绝不按进程名杀——bundled 与别的实例都跑 webchartsrv.py）。
#
# 用法：
#   bash scripts/start_vendored_instance.sh                 # chart @ 8877
#   bash scripts/start_vendored_instance.sh --with-java     # + java @ 9977（无 Mongo 的机器上
#                                                           #   java 族技法会 500，脚本会提示）
#   CHART_PORT=8878 JAVA_PORT=9978 bash scripts/start_vendored_instance.sh --with-java
#
# 就绪判据（AGENTS §8）：启动日志 `kentang prewarm ready (loaded=N, failed=0)`——failed 非 0
# 就是没起对，本脚本直接失败并打日志尾，绝不留一个半死实例给你测。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VENDOR="${ROOT}/vendor/runtime-source"
RUNDIR="${ROOT}/horosa-skill/build/vendored-instance"
CHART_PORT="${CHART_PORT:-8877}"
JAVA_PORT="${JAVA_PORT:-9977}"
WITH_JAVA=0
[ "${1:-}" = "--with-java" ] && WITH_JAVA=1

PY="${VENDOR}/runtime/mac/python/bin/python3"
WEBSRV="${VENDOR}/Horosa-Web/astropy/websrv"
JAR="${VENDOR}/runtime/mac/bundle/astrostudyboot.jar"
JAVA_BIN="${VENDOR}/runtime/mac/java/bin/java"

for p in "${PY}" "${WEBSRV}/webchartsrv.py" "${VENDOR}/Horosa-Web/flatlib-ctrad2" "${VENDOR}/Horosa-Web/vendor"; do
  if [ ! -e "${p}" ]; then
    echo "missing: ${p}" >&2
    echo "先重灌 vendored 树：HOROSA_SOURCE_ROOT=<Horosa-Public> bash horosa-skill/scripts/sync_vendored_runtime_sources.sh" >&2
    exit 1
  fi
done

port_busy() { nc -z 127.0.0.1 "$1" >/dev/null 2>&1; }
pid_alive() { [ -f "$1" ] && kill -0 "$(cat "$1")" >/dev/null 2>&1; }

mkdir -p "${RUNDIR}"
CHART_PID="${RUNDIR}/chart.pid"; CHART_LOG="${RUNDIR}/chart.log"
JAVA_PID="${RUNDIR}/java.pid";  JAVA_LOG="${RUNDIR}/java.log"

if pid_alive "${CHART_PID}"; then
  echo "chart already running (pid $(cat "${CHART_PID}")) — stop first: bash horosa-skill/scripts/stop_vendored_instance.sh" >&2
  exit 1
fi
if port_busy "${CHART_PORT}"; then
  echo "port ${CHART_PORT} is busy and not ours — pick another: CHART_PORT=<n> $0" >&2
  exit 1
fi

# 三段 PYTHONPATH + 内嵌解释器 —— 唯一正确的起法，别改回手打。
(
  cd "${WEBSRV}"
  PYTHONPATH="${VENDOR}/Horosa-Web/flatlib-ctrad2:${VENDOR}/Horosa-Web/astropy:${VENDOR}/Horosa-Web/vendor" \
    HOROSA_CHART_PORT="${CHART_PORT}" nohup "${PY}" webchartsrv.py > "${CHART_LOG}" 2>&1 &
  echo $! > "${CHART_PID}"
)
echo "chart starting (pid $(cat "${CHART_PID}"), port ${CHART_PORT}) — waiting for kentang prewarm…"

deadline=$((SECONDS + 120))
ready=""
while [ ${SECONDS} -lt ${deadline} ]; do
  ready="$(grep -o 'kentang prewarm ready[^)]*)' "${CHART_LOG}" 2>/dev/null | tail -1 || true)"
  [ -n "${ready}" ] && break
  sleep 2
done
if [ -z "${ready}" ]; then
  echo "chart never reached 'kentang prewarm ready' within 120s — log tail:" >&2
  tail -15 "${CHART_LOG}" >&2
  bash "${ROOT}/horosa-skill/scripts/stop_vendored_instance.sh" || true
  exit 1
fi
if ! printf '%s' "${ready}" | grep -q "failed=0"; then
  echo "kentang prewarm has failures — ${ready}（AGENTS §8：failed 非 0 = 没按正确方式起）" >&2
  tail -15 "${CHART_LOG}" >&2
  bash "${ROOT}/horosa-skill/scripts/stop_vendored_instance.sh" || true
  exit 1
fi
echo "chart ready: ${ready}"

if [ "${WITH_JAVA}" = "1" ]; then
  if [ ! -f "${JAR}" ] || [ ! -x "${JAVA_BIN}" ]; then
    echo "java runtime not vendored (${JAR}) — re-run sync_vendored_runtime_sources.sh" >&2
    exit 1
  fi
  if port_busy "${JAVA_PORT}"; then
    echo "port ${JAVA_PORT} is busy — pick another: JAVA_PORT=<n> $0 --with-java" >&2
    exit 1
  fi
  (
    cd "${VENDOR}"
    nohup "${JAVA_BIN}" -Dfile.encoding=UTF-8 -Dsun.jnu.encoding=UTF-8 \
      -jar "${JAR}" --server.port="${JAVA_PORT}" --astrosrv="http://127.0.0.1:${CHART_PORT}" \
      > "${JAVA_LOG}" 2>&1 &
    echo $! > "${JAVA_PID}"
  )
  echo "java starting (pid $(cat "${JAVA_PID}"), port ${JAVA_PORT})… root 回 500 是正常（无 / 路由）"
  echo "⚠ 无 Mongo/Redis 的机器：java 族技法（nongli/bazi/ziwei/liureng）会 ResultCode 9999 —— 那是环境，"
  echo "  不是回归（AGENTS §8.5：9999 必须再读 Result 原文再定性）。"
fi

echo
echo "live 测试的 env（复制粘贴）："
echo "  export HOROSA_CHART_SERVER_ROOT=http://127.0.0.1:${CHART_PORT}"
if [ "${WITH_JAVA}" = "1" ]; then
  echo "  export HOROSA_SERVER_ROOT=http://127.0.0.1:${JAVA_PORT}"
else
  echo "  export HOROSA_SERVER_ROOT=http://127.0.0.1:9   # java 未起：显式指向不可达，别让门禁去探默认端口"
fi
echo "结束后：bash horosa-skill/scripts/stop_vendored_instance.sh"
