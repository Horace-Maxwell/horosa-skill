#!/usr/bin/env bash
# 停掉 start_vendored_instance.sh 起的实例 —— **只按 pidfile 里的 PID 杀**。
# pkill 法则（AGENTS §8.6）：bundled 与任何别的实例都跑 webchartsrv.py，按进程名杀会连
# 不相干的服务一起带走；按端口杀也会误伤「恰好占了这个端口的别人」。PID 是唯一安全的作用域。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RUNDIR="${ROOT}/horosa-skill/build/vendored-instance"

stopped=0
for name in chart java; do
  pidfile="${RUNDIR}/${name}.pid"
  [ -f "${pidfile}" ] || continue
  pid="$(cat "${pidfile}")"
  if kill -0 "${pid}" >/dev/null 2>&1; then
    kill "${pid}" && echo "stopped ${name} (pid ${pid})"
    stopped=1
  else
    echo "${name} pid ${pid} already gone (stale pidfile)"
  fi
  rm -f "${pidfile}"
done
[ "${stopped}" = "1" ] || echo "nothing to stop（没有本脚本起的实例在跑）"
