"""测试里起 node 跑 ESM 片段的唯一入口（v0.40.0 首推 windows-smoke 红：ERR_UNSUPPORTED_ESM_URL_SCHEME ×18）。

`node --input-type=module -e "import(process.argv[1])"` 在 Windows 上不接受裸盘符绝对路径（`D:\\a\\…\\x.js`），
只认 `file://` URL；macOS / Linux 的 `/abs/x.js` 恰好能过，所以本机全绿、Windows job 才红。这里把 Path 参数统一转成
`Path.resolve().as_uri()`，并拒绝以字符串形式传进来的绝对 `.js` 路径（那正是会在 Windows 上炸的形状）。
守卫：tests/ 里 `--input-type=module` 字面量只许出现在本文件（tests/test_subprocess_encoding.py）。
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path, PurePath

_ABS_MODULE_PATH = re.compile(r"^(?:/|[A-Za-z]:[\\/]).*\.(?:m?js)$")


def module_url(path: PurePath | str) -> str:
    """模块文件 → node ESM loader 三平台都认的 file:// URL。"""
    return Path(path).resolve().as_uri()


def esm_argv(script: str, *args: PurePath | str) -> list[str]:
    argv = ["node", "--input-type=module", "-e", script]
    for arg in args:
        if isinstance(arg, PurePath):
            argv.append(module_url(arg))
            continue
        text = f"{arg}"
        if _ABS_MODULE_PATH.match(text):
            raise ValueError(f"pass module paths as Path objects, not strings ({text!r}): Windows ESM needs file:// URLs")
        argv.append(text)
    return argv


def node_esm_process(
    script: str, *args: PurePath | str, cwd: PurePath | str | None = None, timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """跑 ESM 片段，回 CompletedProcess（不 check；调用方自己看 returncode / stderr）。"""
    return subprocess.run(
        esm_argv(script, *args), capture_output=True, text=True, encoding="utf-8", cwd=cwd, timeout=timeout,
    )


def run_node_esm(script: str, *args: PurePath | str, cwd: PurePath | str | None = None, timeout: float | None = None) -> str:
    """跑 ESM 片段，返回 stdout（UTF-8 解码；非零退出 → CalledProcessError 带 stderr）。"""
    completed = node_esm_process(script, *args, cwd=cwd, timeout=timeout)
    completed.check_returncode()
    return completed.stdout
