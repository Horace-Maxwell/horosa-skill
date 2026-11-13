"""后台子进程在 Windows 上不弹控制台窗口：每个 `subprocess.run` / `Popen` 都带 `creationflags=NO_WINDOW`。

为什么：控制台程序（node.exe、powershell.exe、netstat.exe……）被一个**没有控制台**的进程拉起时，Windows 会给它新开一个
可见的控制台窗口。MCP server 由 GUI 宿主以 DETACHED 方式起、或用 pythonw 起时就是这样——实测每次 `tool run` 闪两个窗口
（node 版本探针 + 引擎本身）。`CREATE_NO_WINDOW` 给子进程一个没有窗口的控制台：输出照样走管道，启动器（powershell -File）
照样能跑（不是 DETACHED_PROCESS，那会让它静默 exit 0，见 runtime/manager.py）。父进程本来就有控制台时，子进程原本继承它，
现在改成各自一个隐藏控制台——我们的调用都捕获输出、自己管超时，没有依赖共享控制台的地方。非 Windows 上是 0（不改变任何行为）。
"""

from __future__ import annotations

import os
import subprocess

NO_WINDOW: int = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
