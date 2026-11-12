"""跨进程互斥锁：O_EXCL 创建 + PID 存活回收 + 过期兜底。

🔴 为什么需要它：`start_local_services` 只有一把**进程内**的 `threading.Lock`。两个 MCP
客户端（Claude Desktop 与 Cursor，或者一个 serve 与一次 `doctor`）同时冷启动时，两边各起一次
启动器：抢同一个端口、互相覆盖 pid 文件、后到的那个看见「pid files already exist」于是先
stop 再 start —— 把先到的那个刚起好的服务停掉。这把锁让**恰好一个**进程去启动，其余的只轮询
就绪状态。

从 `evaluation_lock.py` 泛化而来（那边保留为薄包装，四个旧测试不动），两处升级：
  · 存活判定走 `runtime.procs.pid_alive`，Windows 也能立刻回收崩溃留下的锁（旧实现在 Windows
    上一律 unknown，只能等满 stale 时长）；
  · 锁文件里多记 `owner` 与 `created_at`，`describe_lock()` 让 `runtime status` 能说出「谁在启动」。

🔴 两条判定纪律（v0.50.0-dev，E-08）：
  · **「有人持锁」只有一个证据：锁文件已经存在。** 建不了锁文件的其它原因（目录只读、磁盘满、父目录建不出来）
    是 `LockDirNotWritableError`，不是 False —— 旧实现把任何 OSError 都答成 False，只读的 runtime 根于是让
    `runtime start` 回「别的进程正在启动」，用户去等一个不存在的启动者。
  · **pid 活着 ≠ 持有者还在。** 锁里多记一份进程启动口令（`procs.process_start_token`）；回收时 pid 活着但口令
    对不上 = 这个 pid 已经发给了别的进程，按死持有者回收。口令取不到 / 旧格式的锁里没有 / 两边取法不同，一律按
    「不知道」走原来的规则 —— 宁可多等，也不抢一个真在启动的进程的锁。
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from horosa_skill import fsretry
from horosa_skill.runtime.procs import pid_alive, process_start_token

# 锁交给启动器之后，里面记的 pid 是别的进程：我们不知道它还是不是启动器（Windows 回收 PID 很快）。install 换目录只持锁几分钟，
# 崩溃后留下的 pid 同样会被回收。这两类按时长封顶，上限内才相信「活着」；别的锁（长命的持锁进程本身）不受影响。
LAUNCHER_OWNER = "runtime-launcher"
INSTALL_OWNER = "runtime-install"
_AGE_CAPPED_OWNERS = frozenset({LAUNCHER_OWNER, INSTALL_OWNER})


class LockDirNotWritableError(OSError):
    """锁文件所在目录建不出来或写不进去。是 OSError 的子类：只认 OSError 的旧调用方照常接得住。"""

    def __init__(self, directory: Path, cause: BaseException) -> None:
        super().__init__(getattr(cause, "errno", None), f"Cannot create a lock file in {directory}: {cause}")
        self.directory = directory
        self.cause = cause


@contextmanager
def pid_lock(
    lock_path: Path,
    *,
    timeout_seconds: float = 60.0,
    stale_after_seconds: float = 3600.0,
    owner: str = "",
) -> Iterator[Path]:
    """持有 `lock_path` 直到退出。拿不到就等，超时抛 TimeoutError；目录写不了抛 LockDirNotWritableError（不等）。"""
    _ensure_dir(lock_path.parent)
    started = time.monotonic()
    while True:
        if _try_create(lock_path, owner=owner):
            break
        if reclaim_if_stale(lock_path, stale_after_seconds=stale_after_seconds):
            continue
        if time.monotonic() - started >= timeout_seconds:
            holder = describe_lock(lock_path)
            raise TimeoutError(
                f"Timed out waiting for lock {lock_path} (holder={holder})"
            )
        time.sleep(0.2)
    try:
        yield lock_path
    finally:
        release(lock_path)


def try_pid_lock(lock_path: Path, *, stale_after_seconds: float = 3600.0, owner: str = "") -> bool:
    """非阻塞地试一次。True = 拿到了（调用方负责 `release`）；False = 有人持锁。目录写不了抛 LockDirNotWritableError。"""
    _ensure_dir(lock_path.parent)
    if _try_create(lock_path, owner=owner):
        return True
    if reclaim_if_stale(lock_path, stale_after_seconds=stale_after_seconds):
        return _try_create(lock_path, owner=owner)
    return False


def release(lock_path: Path) -> None:
    """放锁。Windows 上别的进程正读着锁文件时 unlink 会 PermissionError：短暂重试——旧实现的 pid_lock 让它从 finally 冒出去，
    锁还留在盘上（持有者活着不可回收），其他进程只能等满超时。放锁绝不抛：真删不掉也比盖掉调用方的结果好。"""
    try:
        fsretry.unlink(lock_path)
    except OSError:
        pass


def release_launcher(lock_path: Path) -> None:
    """启动已有结果（服务都起来了 / 刚被停掉）时收回交给启动器的锁。别的持有者（正拿着锁的进程）一律不动。"""
    info = _read_lock(lock_path)
    if info is not None and info.get("owner") == LAUNCHER_OWNER:
        release(lock_path)


def _ensure_dir(directory: Path) -> None:
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise LockDirNotWritableError(directory, exc) from exc


def _dir_accepts_new_files(directory: Path) -> bool:
    """在目录里真建一个文件再删掉。`os.access` 在 Windows（ACL）和网络盘上不可信。"""
    try:
        fd, name = tempfile.mkstemp(prefix=".lock-probe-", dir=str(directory))
    except OSError:
        return False
    os.close(fd)
    try:
        fsretry.unlink(Path(name))
    except OSError:
        pass
    return True


def _try_create(lock_path: Path, *, owner: str) -> bool:
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    except OSError as exc:
        # Windows 上锁文件处于 delete-pending / 被杀毒软件扫着时，O_EXCL 创建报 PermissionError 而不是 FileExistsError：
        # 目录本身能建文件 → 这是「稍后再试」，仍按「有人持锁」答。目录建不了文件 → 不是锁的问题，如实抛。
        if _dir_accepts_new_files(lock_path.parent):
            return False
        raise LockDirNotWritableError(lock_path.parent, exc) from exc
    payload: dict[str, Any] = {
        "pid": os.getpid(),
        "owner": owner,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    token = process_start_token(os.getpid())
    if token:
        payload["start_token"] = token
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
    return True


def holder_was_replaced(info: dict[str, Any]) -> bool:
    """锁里记的 pid 现在是不是**另一个**进程。只有两边口令都取得到、取法相同、值不同才答 True；其余都是「不知道」。"""
    recorded = info.get("start_token")
    if not isinstance(recorded, str) or ":" not in recorded:
        return False
    current = process_start_token(info.get("pid"))
    if not current or ":" not in current:
        return False
    if recorded.split(":", 1)[0] != current.split(":", 1)[0]:
        return False
    return recorded != current


def describe_lock(lock_path: Path) -> dict[str, Any] | None:
    """锁当前持有者（供 `runtime status` 显示）。锁不存在返回 None。"""
    info = _read_lock(lock_path)
    if info is None:
        return None
    pid = info.get("pid")
    liveness = pid_alive(pid)
    if liveness == "alive" and holder_was_replaced(info):
        liveness = "dead"  # 这个 pid 现在是别的进程：当初的持有者已经不在了
    return {
        "pid": pid,
        "owner": info.get("owner") or None,
        "created_at": info.get("created_at"),
        "liveness": liveness,
        "age_seconds": _age_seconds(info.get("created_at"), lock_path),
    }


def reclaim_if_stale(lock_path: Path, *, stale_after_seconds: float) -> bool:
    """持有者已死或锁太老就删掉它。True = 已删/本就不存在，调用方可以重试创建。

    **活着的持有者不回收**，不论多老 —— 一次合法的长启动（首次 CDS 训练可达 15 分钟）必须被尊重。
    两个例外，都是「pid 活着但已经不是它」：
      · 锁里的启动口令与这个 pid 现在的口令对不上（`holder_was_replaced`）—— 立刻回收，不看时长；
      · 交给启动器 / install 的锁（`_AGE_CAPPED_OWNERS`）超过 `stale_after_seconds`：该值已大于一次启动的上限，
        超过它还「活着」只可能是 pid 被回收给了无关进程（口令取不到的平台 / 旧格式的锁靠这条兜底）。
    """
    info = _read_lock(lock_path)
    if info is None:
        return not lock_path.exists()
    liveness = pid_alive(info.get("pid"))
    if liveness == "alive" and holder_was_replaced(info):
        liveness = "dead"
    if liveness == "alive" and info.get("owner") not in _AGE_CAPPED_OWNERS:
        return False
    if liveness == "dead":
        stale = True
    else:  # unknown，或启动器的 pid：无法断言存活 → 退回按时长
        age = _age_seconds(info.get("created_at"), lock_path)
        stale = age is not None and age >= stale_after_seconds
    if not stale:
        return False
    try:
        lock_path.unlink()
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False


def _read_lock(lock_path: Path) -> dict[str, Any] | None:
    try:
        raw = lock_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError:
        return {}
    try:
        info = json.loads(raw)
    except ValueError:
        return {}  # 写到一半就崩了 → 无 pid，按时长回收
    return info if isinstance(info, dict) else {}


def _age_seconds(created_at: Any, lock_path: Path) -> float | None:
    if isinstance(created_at, str):
        try:
            ts = datetime.fromisoformat(created_at)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return max(0.0, (datetime.now(timezone.utc) - ts).total_seconds())
        except ValueError:
            pass
    try:
        return max(0.0, time.time() - lock_path.stat().st_mtime)
    except OSError:
        return None
