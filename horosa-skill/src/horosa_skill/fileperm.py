"""本机数据的权限缺省（审计 O-05 / PF-11，维护者 2026-11-14 按推荐定）。

存档里是姓名、出生时刻地点、问题与 AI 解读。以前数据目录随 umask（0755）、库与存档 0644，同机别的账户都读得到，而报告是 0600——两边不一致不是设计。
现在（POSIX）：**新建**的数据目录 0700、新建的存档 / trace / 记忆库 0600；已有目录与文件的权限不动（那是用户的，doctor 的 privacy 字段只报不改）。
容器卷上要让别的进程读的部署：`HOROSA_DATA_PRIVATE=0` 回到按 umask 建。Windows 走用户 profile 的 ACL 继承，不改。
"""
from __future__ import annotations

import os
from pathlib import Path

_OFF = {"0", "false", "no", "off"}


def data_private() -> bool:
    return os.name != "nt" and str(os.environ.get("HOROSA_DATA_PRIVATE", "1")).strip().lower() not in _OFF


def new_file_mode(shared: int = 0o666) -> int:
    """os.open 建新文件的 mode：私有时 0600，否则沿用调用方原来的值（再经 umask）。"""
    return 0o600 if data_private() else shared


def make_private_dir(path: Path) -> None:
    """建目录；**这次新建的**才收紧到 0700（已有目录不动）。"""
    existed = path.exists()
    path.mkdir(parents=True, exist_ok=True)
    if not existed and data_private():
        try:
            path.chmod(0o700)
        except OSError:
            pass  # 只读挂载 / 非属主：建得出来就够用，权限是附加的保护（doctor 照报）


def make_private_file(path: Path) -> None:
    """文件刚由别人（如 sqlite）按 umask 建出来：私有时收紧到 0600。"""
    if data_private():
        try:
            path.chmod(0o600)
        except OSError:
            pass
