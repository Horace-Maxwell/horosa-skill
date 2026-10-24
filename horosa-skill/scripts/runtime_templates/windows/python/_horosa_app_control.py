"""Windows 应用控制（Smart App Control）拒绝加载某些原生扩展时，给有纯 Python 等价路径的模块换上替身。

由 horosa-skill 的 runtime manager 在每次 start 时拷进随包 Python 的 site-packages（同目录的 horosa_app_control.pth 引入它），
与 start_horosa_local.ps1 走同一条「每次 start 重拷」的路，所以已装的 runtime 升级 skill 即生效。

为什么需要：Smart App Control 按云端信誉放行，没签名、流行度不够的小 DLL 会被拒（`DLL load failed … An Application Control
policy has blocked this file`，即 os error 4551）。2026-10-23 维护机实测：新装 v0.43.0 载荷的 258 个原生文件里拦了 2 个——
`astropy/time/_parse_times.pyd`（官方 astropy 7.2.0 abi3 wheel 原件）与 `pendulum/_pendulum.*.pyd`；同一哈希在早先装的根里放行。
pendulum 自带纯 Python 回退；astropy 没有：`astropy.time.formats` 顶层 `from . import _parse_times`，一拦整个 astropy.time
起不来 → kintaiyi（`from astropy.coordinates import SkyCoord`）挂 → 太乙 / 三式合一不可用。

替身只做一件事：让 astropy 的「快速 C 解析器」每次都失败。astropy 自己的 `TimeString.set_jds` 在快速解析抛任何异常时落回
`get_jds_python`（它的参照实现），所以结果不变、只是慢一点。真扩展能加载时什么都不发生。
"""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import importlib.util
import sys

_BLOCKED_MARKERS = ("Application Control", "4551")


def _is_app_control_block(exc: BaseException) -> bool:
    text = str(exc)
    return getattr(exc, "winerror", None) == 4551 or any(marker in text for marker in _BLOCKED_MARKERS)


def _fill_parse_times(module: object) -> None:
    import numpy as np

    # 与真扩展导出的 dtype 逐字段相同（2026-10-23 从能加载的根里读出：align=True）。
    module.dt_pars = np.dtype(  # type: ignore[attr-defined]
        [("delim", "S1"), ("start", "<i4"), ("stop", "<i4"), ("break_allowed", "?")], align=True
    )
    module.dt_u1 = np.dtype([("byte", "u1")], align=True)  # type: ignore[attr-defined]
    module.dt_ymdhms = np.dtype(  # type: ignore[attr-defined]
        [("year", "<i4"), ("month", "<i4"), ("day", "<i4"), ("hour", "<i4"), ("minute", "<i4"), ("second", "<f8")],
        align=True,
    )

    def create_parser(pars: object):  # noqa: ARG001 - 签名与真扩展相同
        def _parser(chars: object):  # noqa: ARG001
            raise ValueError("astropy fast time parser unavailable (native extension blocked by Windows Application Control)")

        return _parser

    module.create_parser = create_parser  # type: ignore[attr-defined]
    module.HOROSA_APP_CONTROL_STUB = True  # type: ignore[attr-defined]


_STUBS = {"astropy.time._parse_times": _fill_parse_times}


class _GuardedLoader(importlib.abc.Loader):
    """先试真扩展；被应用控制拒绝时换成替身，并在 stderr 留一行（进 chart 服务日志）。"""

    def __init__(self, name: str, real: importlib.abc.Loader, origin: str | None) -> None:
        self._name, self._real, self._origin = name, real, origin
        self._stubbed = False

    def create_module(self, spec):  # noqa: ANN001
        try:
            return self._real.create_module(spec)
        except ImportError as exc:
            if not _is_app_control_block(exc):
                raise
            self._stubbed = True
            sys.stderr.write(
                f"horosa: Windows Application Control blocked {self._origin or self._name}; "
                "using the pure-Python fallback (results unchanged)\n"
            )
            return None  # 交回默认的空模块，下面 exec_module 填替身

    def exec_module(self, module) -> None:  # noqa: ANN001
        if self._stubbed:
            _STUBS[self._name](module)
            return
        self._real.exec_module(module)


class _Finder(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):  # noqa: ANN001
        if name not in _STUBS:
            return None
        spec = importlib.machinery.PathFinder.find_spec(name, path, target)
        if spec is None or spec.loader is None:
            return spec
        spec.loader = _GuardedLoader(name, spec.loader, spec.origin)
        return spec


if sys.platform == "win32" and not any(isinstance(f, _Finder) for f in sys.meta_path):
    sys.meta_path.insert(0, _Finder())
