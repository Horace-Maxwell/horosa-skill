"""macOS 启动器补丁（安装后由 manager._apply_runtime_overrides 调）：上游启动脚本的 reclaim_stale_port 会按端口杀进程，补一段「只杀自己起的 pid」的归属判断；带版本标记，打过即幂等。"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from horosa_skill.errors import RuntimeInstallError

logger = logging.getLogger("horosa_skill.runtime.manager")  # 搬出前的日志名，不变


class MacLauncherPatchMixin:
    # macOS 启动器补丁：标记 + 五处锚点。上游脚本住在只读的 vendor 树，所以修复走**安装/启动时
    # 打补丁**（与 _patch_windows_boot_jar 同一模式），已装的 runtime 下次 serve/doctor 即打上。
    _MAC_LAUNCHER_PATCH_MARK = "# horosa-skill-launcher-patch v1"
    # 只有出现这个构造才需要打补丁：v0.36.0 随包出货的那版（606 行）用 lsof 探测后直接拒绝，
    # 没有任何 kill 路径；误杀代码在更新的上游版本里，下次重建 runtime 载荷时才会随包出货。
    _MAC_LAUNCHER_DANGER = "reclaim_stale_port"

    _MAC_OWNS_PID_HELPER = """
%(mark)s
# 🔴 上游 reclaim_stale_port 按**命令行子串**（webchartsrv / astrostudyboot）kill -9 端口持有者，
# 注释里写着「绝不误杀第三方」——但星阙桌面端跑的正是这两个镜像，所以那句判断不成立：
# 用户同时开着桌面端时，本 skill 起服务会把桌面端 kill 掉（数据丢失风险）。
# stop_horosa_local.sh 有 `grep -Fq "${ROOT}"` 守卫、Windows 启动器是拒绝而非 kill——
# 唯独 mac 的 start 没跟上。这个 helper 把「是不是我们这套安装」变成可判定的：
#   ① 命令行里出现本安装根目录；或 ② 带 -Dhorosa.runtime.root=<本安装根>（exploded 模式下
#      java 的 argv 是 `java -cp . JarLauncher`，不含 ROOT，只能靠这个显式标记）。
horosa_owns_pid() {
  local _pid="$1" _cmd
  _cmd="$(ps -p "${_pid}" -o command= 2>/dev/null || true)"
  case "${_cmd}" in
    *"${ROOT}"*) return 0 ;;
  esac
  case "${_cmd}" in
    *"-Dhorosa.runtime.root=${ROOT}"*) return 0 ;;
  esac
  return 1
}
""" % {"mark": _MAC_LAUNCHER_PATCH_MARK}

    def _patch_mac_launcher(self, script_path: Path) -> bool:
        """给 macOS 启动器加「只杀自己人」守卫 + 可判定的 root 标记。幂等；锚点不符即拒。

        返回 True 表示打了补丁（或已打过），False 表示这版启动器没有危险构造、无需补丁。
        锚点数不符时抛 RuntimeInstallError 而不是静默跳过 —— 静默跳过等于回到误杀路径，
        而「补丁没打上」在日志里是看不见的。
        """
        try:
            text = script_path.read_text(encoding="utf-8")
        except OSError:
            return False
        if self._MAC_LAUNCHER_PATCH_MARK in text:
            return True
        if self._MAC_LAUNCHER_DANGER not in text:
            return False  # 老版启动器：无 kill 路径，本来就安全

        root_anchor = 'ROOT="$(cd "$(dirname "$0")" && pwd)"\n'
        if text.count(root_anchor) != 1:
            raise RuntimeInstallError(
                "macOS 启动器补丁失败：找不到 ROOT 定义锚点。",
                code="runtime.launcher_patch_anchor_missing",
                details={
                    "script": str(script_path), "anchor": "ROOT=",
                    "next_action": "升级 horosa-skill（uv sync 或 uvx --refresh）后重试；"
                                   "临时跳过设 HOROSA_RUNTIME_LAUNCHER_PATCH=0（会失去误杀保护）。",
                },
            )
        patched = text.replace(root_anchor, root_anchor + self._MAC_OWNS_PID_HELPER, 1)

        kill_anchor = '        kill -9 "${pid}" >/dev/null 2>&1 && killed=1 ;;\n'
        if patched.count(kill_anchor) != 1:
            raise RuntimeInstallError(
                "macOS 启动器补丁失败：reclaim_stale_port 的 kill 锚点不唯一。",
                code="runtime.launcher_patch_anchor_missing",
                details={
                    "script": str(script_path), "anchor": "reclaim_stale_port kill -9",
                    "found": patched.count(kill_anchor),
                    "next_action": "升级 horosa-skill 后重试；临时跳过设 HOROSA_RUNTIME_LAUNCHER_PATCH=0。",
                },
            )
        patched = patched.replace(
            kill_anchor,
            '        horosa_owns_pid "${pid}" || { diag_log "port ${port}: ${tag} pid=${pid} '
            'is NOT ours; refusing to kill"; continue; }\n' + kill_anchor,
            1,
        )

        owner_anchor = "-Dhorosa.runtime.owner="
        owner_count = patched.count(owner_anchor)
        if owner_count == 0:
            raise RuntimeInstallError(
                "macOS 启动器补丁失败：找不到 -Dhorosa.runtime.owner 锚点。",
                code="runtime.launcher_patch_anchor_missing",
                details={"script": str(script_path), "anchor": owner_anchor,
                         "next_action": "升级 horosa-skill 后重试。"},
            )
        # 每个 JVM 启动点都带上本安装根，exploded 模式下才判得出归属。
        patched = re.sub(
            r"(-Dhorosa\.runtime\.owner=[A-Za-z0-9._-]+)",
            r'\1 -Dhorosa.runtime.root="${ROOT}"',
            patched,
        )
        # AppCDS 训练 JVM 的硬编码端口改为可配（39997 与别的程序撞车时目前是静默降级）。
        patched = patched.replace("local train_port=39997", 'local train_port="${HOROSA_CDS_TRAIN_PORT:-39997}"')

        try:
            script_path.write_text(patched, encoding="utf-8")
            script_path.chmod(script_path.stat().st_mode | 0o111)
        except OSError as exc:
            raise RuntimeInstallError(
                "写入 mac 启动器补丁失败（runtime 目录只读或属于别的用户）。",
                code="runtime.launcher_patch_write_failed",
                details={
                    "path": str(script_path), "error": f"{type(exc).__name__}: {exc}",
                    "next_action": "检查 runtime 目录权限；确需临时跳过设 HOROSA_RUNTIME_LAUNCHER_PATCH=0（会失去误杀保护）。",
                },
            ) from exc
        logger.info("patched macOS launcher with foreign-process kill guard: %s", script_path)
        return True
