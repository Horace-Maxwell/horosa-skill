"""mac 启动器补丁器的孪生测试。

要防的 bug：上游 `reclaim_stale_port` 按**命令行子串**（`webchartsrv` / `astrostudyboot`）
`kill -9` 端口持有者——星阙桌面端跑的正是这两个镜像。上游注释写着「绝不误杀第三方」，
但那句话只有在「只有我们用这两个名字」时才成立，而事实不是。

注意时序：v0.36.0 随包出货的那版启动器（606 行）用 lsof 探测后**拒绝**，没有 kill 路径；
误杀代码在更新的上游版本里，**下次重建 runtime 载荷时才会随包出货**。补丁器因此必须
「有危险构造才打、没有就一字不改」——否则会把当前安全的老版本改坏。
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from horosa_skill.config import Settings
from horosa_skill.errors import RuntimeInstallError
from horosa_skill.runtime.manager import HorosaRuntimeManager

PKG_ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = PKG_ROOT.parent / "vendor/runtime-source/Horosa-Web/start_horosa_local.sh"

pytestmark = pytest.mark.skipif(
    not UPSTREAM.is_file(),
    reason="vendor/runtime-source 是 gitignored 的本地构建输入；CI 上没有它（preflight 会跑这条）",
)


@pytest.fixture()
def manager(tmp_path: Path) -> HorosaRuntimeManager:
    return HorosaRuntimeManager(Settings(runtime_root=tmp_path / "runtime"))


@pytest.fixture()
def patched(manager: HorosaRuntimeManager, tmp_path: Path) -> str:
    script = tmp_path / "start_horosa_local.sh"
    shutil.copy2(UPSTREAM, script)
    assert manager._patch_mac_launcher(script) is True
    return script.read_text(encoding="utf-8")


def test_every_kill_is_guarded_by_ownership(patched: str) -> None:
    """reclaim_stale_port 里的 kill -9 之前必须先确认这个 pid 是我们这套安装的。"""
    body_start = patched.index("reclaim_stale_port() {")
    body = patched[body_start : patched.index("\n}\n", body_start)]
    assert "horosa_owns_pid" in body
    assert body.index("horosa_owns_pid") < body.index("kill -9"), "守卫必须在 kill 之前"


def test_root_marker_covers_every_jvm_launch(patched: str) -> None:
    """exploded 模式下 java 的 argv 是 `java -cp . JarLauncher`，不含 ROOT。

    少标一处 = 有一条启动路径判不出归属 → 那条路径上的进程会被当成外来者（或反过来）。
    """
    owners = patched.count("-Dhorosa.runtime.owner=")
    roots = patched.count('-Dhorosa.runtime.root="${ROOT}"')
    assert owners > 0 and roots == owners, f"root {roots} 个 ≠ owner {owners} 个"


def test_patched_script_is_valid_bash(patched: str, tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    probe.write_text(patched, encoding="utf-8")
    result = subprocess.run(["bash", "-n", str(probe)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_patch_is_idempotent(manager: HorosaRuntimeManager, tmp_path: Path) -> None:
    script = tmp_path / "s.sh"
    shutil.copy2(UPSTREAM, script)
    manager._patch_mac_launcher(script)
    once = script.read_text(encoding="utf-8")
    manager._patch_mac_launcher(script)
    assert script.read_text(encoding="utf-8") == once, "第二次打补丁改动了文件（每次 start 都会跑）"


def test_a_launcher_without_the_danger_is_left_untouched(manager: HorosaRuntimeManager, tmp_path: Path) -> None:
    """v0.36.0 随包那版没有 kill 路径 —— 一字都不该改。"""
    script = tmp_path / "old.sh"
    script.write_text(
        '#!/usr/bin/env bash\nset -euo pipefail\n\nROOT="$(cd "$(dirname "$0")" && pwd)"\n'
        'echo "port ${CHART_PORT} is already in use."\nexit 1\n',
        encoding="utf-8",
    )
    before = script.read_bytes()
    assert manager._patch_mac_launcher(script) is False
    assert script.read_bytes() == before


def test_anchor_drift_fails_loudly(manager: HorosaRuntimeManager, tmp_path: Path) -> None:
    """上游改了 kill 那一行的写法时必须报错。

    静默跳过等于回到误杀路径，而「补丁没打上」在日志里是看不见的 —— 这正是本仓
    「不许静默降级」那条纪律的运行时版本。
    """
    script = tmp_path / "drift.sh"
    script.write_text(
        UPSTREAM.read_text(encoding="utf-8").replace(
            'kill -9 "${pid}" >/dev/null 2>&1 && killed=1 ;;', 'kill -TERM "${pid}" ;;'
        ),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeInstallError) as excinfo:
        manager._patch_mac_launcher(script)
    assert excinfo.value.code == "runtime.launcher_patch_anchor_missing"
    assert "next_action" in excinfo.value.details


def test_the_upstream_comment_claim_is_the_bug(tmp_path: Path) -> None:
    """把上游那句「绝不误杀第三方」钉成可证伪的断言。

    它只在「只有我们用 webchartsrv/astrostudyboot 这两个名字」时成立；星阙桌面端跑的
    正是这两个镜像，所以未打补丁的脚本对桌面端的 pid 会判「该杀」。
    """
    raw = UPSTREAM.read_text(encoding="utf-8")
    body_start = raw.index("reclaim_stale_port() {")
    body = raw[body_start : raw.index("\n}\n", body_start)]
    assert "kill -9" in body
    assert "${ROOT}" not in body, (
        "上游已经自己加了 ROOT 守卫 —— 补丁器可以退休了，请同步删除并更新 LESSONS"
    )
