"""Windows 路径里「看着像文件名、其实不是」的形状。纯字符串判断，绝不碰文件系统（`ntpath` 在任何平台都按 Windows 规则解析）。

为什么不能先 resolve 再判：`Path(r"\\\\host\\share\\x").resolve()` 会真的打开这个路径——Windows 为此向 host 发起 SMB 连接并自动带上当前用户的
NTLM 凭据，被拒绝之前凭据已经送出去了（实测对不可路由地址卡 21 秒才返回）。MCP 工具可被提示注入调用，所以 output_path 必须先按字符串拦。
"""

from __future__ import annotations

import ntpath

# 无论带什么扩展名都指向设备（`NUL.pdf`）：Windows 10 上是设备，Windows 11 上能建出资源管理器删不掉的文件。
# 上标数字同样是保留名（learn.microsoft.com「Naming Files, Paths, and Namespaces」）；CONIN$ / CONOUT$ 是 CreateFile 的控制台特殊名。
RESERVED_STEMS = frozenset(
    {"con", "prn", "aux", "nul", "conin$", "conout$"}
    | {f"{device}{digit}" for device in ("com", "lpt") for digit in "123456789¹²³"}
)
_ILLEGAL_CHARS = frozenset('<>"|?*') | {chr(code) for code in range(32)}


def is_reserved_name(segment: str) -> bool:
    """这一级名字（可带扩展名）是不是 Windows 保留设备名。"""
    return segment.split(".")[0].rstrip(" ").casefold() in RESERVED_STEMS


def is_network_or_device_path(text: str) -> bool:
    r"""`\\host\share`、`//host/share`、`\\?\…`、`\\.\…`、`/\host`：两个分隔符开头的都不是普通本地路径。"""
    return text.replace("/", "\\").startswith("\\\\")


def is_under_network_root(text: str, roots: list[str]) -> bool:
    """规范化后（纯字符串，`..` 已折叠）是否落在某个用户配置的网络根之内——只有用户自己配过的共享才放行。"""
    normalized = ntpath.normcase(ntpath.normpath(text))
    for root in roots:
        if is_network_or_device_path(root):
            prefix = ntpath.normcase(ntpath.normpath(root)).rstrip("\\") + "\\"
            if normalized.startswith(prefix):
                return True
    return False


def path_problem(text: str) -> tuple[str, str] | None:
    """有问题返回 (中文原因, English reason)，否则 None。网络路径是否放行由调用方按白名单决定，这里只看字符与设备名。"""
    if any(ch in _ILLEGAL_CHARS for ch in text):
        return ('含 Windows 文件名不允许的字符（< > " | ? * 或控制字符）', 'contains characters Windows does not allow in file names (< > " | ? * or control characters)')
    _, rest = ntpath.splitdrive(text.replace("/", "\\"))
    if ":" in rest:
        return ("含「:」——这是 NTFS 备用数据流，文件看起来不存在", "contains ':' — that is an NTFS alternate data stream, the file would look like it does not exist")
    for segment in rest.split("\\"):
        if segment and is_reserved_name(segment):
            return (f"「{segment}」是 Windows 保留设备名（NUL / CON / COM1…），内容不会进文件", f"'{segment}' is a reserved Windows device name (NUL / CON / COM1…), the content would not reach a file")
    return None
