"""这个端口上的服务，是**我们起的**那一个吗。

🔴 为什么必须问：旧实现只做「HTTP 响应码 < 500 就算可达」，于是 8899/9999 上任何一个应答的
进程都会被静默采用为后端 —— 用户的星阙桌面端、另一个项目的开发服务器、一个 `python -m
http.server`，全都算「runtime 已在运行」。症状不是「连不上」，而是**排盘失败但 statusCode 200**，
或者更糟：把请求发给一个完全无关的服务。上游为此在 chart/Java 两侧都加了 `/horosaIdentity`
握手端点（明文、免签名，带壳注入的每次启动 nonce）；这里是它的消费方。

三级证据，逐级退让，**永远不把「查不到」当成「是我们的」**：
  1. `/horosaIdentity` 的 app 标记（+ nonce 相等）—— 最强，但只在新载荷上存在（已装的 v0.3.0
     载荷没有这个端点，会 404，必须优雅落到第 2 级，而不是判成 foreign）。
  2. 监听该端口的进程命令行里含我方 runtime 实路径或 `-Dhorosa.runtime.root=<我方根>`。
  3. 我方注册表里记下的服务 PID 仍存活。
都答不上来就是 `unknown` —— 由调用方决定是拒绝还是在用户明示下采用，而不是这里替它决定。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal
from urllib.parse import urlsplit

from horosa_skill.engine.client import loopback_httpx_client
from horosa_skill.runtime.ports import listener_pids
from horosa_skill.runtime.procs import pid_alive, process_command, process_image_path

Verdict = Literal["ours", "foreign", "unknown"]

# 上游两侧 /horosaIdentity 会自报的 app 标记。
_APP_MARKERS = frozenset({"horosa-chart", "horosa-backend", "horosa-web", "horosa"})
_IDENTITY_PATH = "/horosaIdentity"
_IDENTITY_TIMEOUT = 1.5


@dataclass
class EndpointIdentity:
    verdict: Verdict
    evidence: str
    url: str
    port: int | None = None
    app: str | None = None
    nonce_match: bool | None = None
    holders: list[dict[str, Any]] = field(default_factory=list)

    # 「能当后端用」与「能对它执行停/重启」是**两件事**。前者只要确认它说的是星阙的协议
    # （app 标记就够）；后者必须确认**是我们把它起起来的**——否则一次 `runtime restart` 就会
    # 把用户自己开着的星阙桌面端停掉。下面三条是「我们起的」这一档的证据。
    _STRONG_EVIDENCE = frozenset({
        "identity.nonce_match",
        "process.image_under_runtime_root",
        "process.command_matches_runtime_root",
        "registry.service_pid_alive",
    })

    @property
    def started_by_us(self) -> bool:
        """能否对它执行停止/重启。app 标记只证明「是星阙」，不证明「是我们这一份」。"""
        return self.verdict == "ours" and self.evidence in self._STRONG_EVIDENCE

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "evidence": self.evidence,
            "url": self.url,
            "port": self.port,
            "app": self.app,
            "nonce_match": self.nonce_match,
            "holders": self.holders,
            "started_by_us": self.started_by_us,
        }


def _port_of(url: str) -> int | None:
    try:
        parsed = urlsplit(url if "//" in url else f"//{url}")
        if parsed.port:
            return int(parsed.port)
        if parsed.scheme == "https":
            return 443
        if parsed.scheme == "http":
            return 80
    except ValueError:
        return None
    return None


def probe_identity(url: str) -> dict[str, Any] | None:
    """GET /horosaIdentity。端点不存在 / 不是 JSON / 连不上都返回 None（**不是** foreign）。"""
    base = url.rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme and parsed.netloc:
        base = f"{parsed.scheme}://{parsed.netloc}"
    try:
        with loopback_httpx_client(base, timeout=_IDENTITY_TIMEOUT, follow_redirects=True) as client:
            response = client.get(base + _IDENTITY_PATH)
    except Exception:  # noqa: BLE001 - 连不上 = 没有证据，不是反面证据
        return None
    if response.status_code >= 400:
        return None
    try:
        payload = json.loads(response.text)
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _command_says_ours(command: str | None, runtime_root: Path | str) -> bool:
    if not command:
        return False
    root = str(runtime_root).rstrip("/\\")
    if not root:
        return False
    if root in command:
        return True
    # exploded 启动模式下 argv 里没有 ROOT，靠启动器补上的这个系统属性（见 _patch_mac_launcher）。
    return f'-Dhorosa.runtime.root={root}' in command or f'-Dhorosa.runtime.root="{root}"' in command


def _normalized(path: str) -> str:
    """跨平台等价比较：分隔符统一、Windows 不分大小写、去尾分隔符。"""
    text = os.path.normpath(str(path)).replace("\\", "/").rstrip("/")
    return text.lower() if os.name == "nt" else text


def _image_says_ours(image_path: str | None, runtime_root: Path | str) -> bool:
    """可执行文件的映像路径是否在我方 runtime 根下。

    载荷的 python.exe / java.exe 就住在 `<root>/current/runtime/<os>/…`，这条不经任何代码页
    （ctypes 直接拿 Unicode），是 Windows 上最可靠的一级证据。
    """
    if not image_path:
        return False
    root = _normalized(runtime_root)
    if not root:
        return False
    return _normalized(image_path).startswith(root + "/")


def _holder_evidence(pid: int, runtime_root: Path | str, *, need_name: bool) -> tuple[str | None, str | None, str | None]:
    """一个监听进程的归属证据：`(evidence, image, command)`。

    先问映像路径（免费、免编码），命中就不再起 PowerShell；只有在**需要点名**一个不属于我们的
    持有者时（`need_name`）才去取完整命令行 —— 那一步在 Windows 上要起 PowerShell（≤ 8 s）。
    这既是 A1 的编码修复，也是 A2 的 doctor 提速：健康机器上 doctor 一次 PowerShell 都不起。
    """
    image = process_image_path(pid)
    if _image_says_ours(image, runtime_root):
        return "process.image_under_runtime_root", image, None
    command = process_command(pid) if (image is None or need_name) else None
    if _command_says_ours(command, runtime_root):
        return "process.command_matches_runtime_root", image, command
    return None, image, command


def holders_outside_runtime_root(port: int | None, runtime_root: Path | str) -> list[dict[str, Any]] | None:
    """监听 `port` 的进程若**全部**可证明跑在 `runtime_root` 之外，返回它们的 `{pid, image, command}`；否则 None。

    给 install/upgrade 的换目录闸用：一份从别的根跑的星阙（用户的桌面端、另一个 runtime root）文件不在这里，
    换本根的 current/ 动不到它 —— 它只是「端口被占」，不是「正在被替换的 runtime 有人在用」。
    None 表示**证明不了**（查不到监听者 / 有持有者住在本根下 / 拿不到映像也拿不到命令行），调用方按拒绝处理：
    永远不把「查不到」当成「在别处」。绝不终止任何进程。
    """
    if port is None:
        return None
    pids = listener_pids(port)
    if not pids:
        return None
    holders: list[dict[str, Any]] = []
    for pid in pids:
        evidence, image, command = _holder_evidence(pid, runtime_root, need_name=True)
        if evidence:
            return None  # 住在本根下 → 换目录会伤到它 → 交给调用方拒绝
        if not (image or command):
            return None  # 点不出名 → 证明不了在别处
        holders.append({"pid": pid, "image": image, "command": command or image})
    return holders


def classify_endpoint(
    url: str,
    *,
    runtime_root: Path | str,
    launch_nonce: str | None = None,
    service_pids: Iterable[Any] = (),
) -> EndpointIdentity:
    """判定 `url` 背后的服务归属。绝不终止任何进程，绝不修改任何状态。"""
    port = _port_of(url)
    holders: list[dict[str, Any]] = []

    # 1) 身份握手（新载荷才有）
    payload = probe_identity(url)
    if payload is not None:
        app = str(payload.get("app") or "") or None
        if app and app in _APP_MARKERS:
            reported = str(payload.get("nonce") or "")
            if launch_nonce:
                if reported and reported == launch_nonce:
                    return EndpointIdentity("ours", "identity.nonce_match", url, port, app, True)
                if reported and reported != launch_nonce:
                    # 是星阙，但**不是这次启动的那一份**（用户的桌面端 / 另一个实例）。
                    return EndpointIdentity("foreign", "identity.nonce_mismatch", url, port, app, False)
            # app 标记只够「能当后端用」，不够「是我们起的」（`started_by_us` 要强证据）——两者的
            # /horosaIdentity 一模一样，分不清我方托管的 runtime 与用户自己开的桌面端。
            # 🔴 但**不能在这里 return**：那样监听进程的命令行（第 2 级强证据）永远没机会说话，
            # 于是 `stop` 连**跑在我们 runtime 根下的**进程都报 runtime.stop_refused_foreign，
            # 用户只能按 PID 手杀（或 --force —— 那把锤子连用户的桌面端一起砸）。
            # 触发条件 = 对面**没报 nonce**：托管启动会把 HOROSA_LAUNCH_NONCE 传下去（实测 doctor
            # 拿到 identity.nonce_match），但直接跑 payload 自带的 start_horosa_local.ps1（AGENTS §8
            # 记录的 vendored 实例起法）、或状态里的 nonce 已被后一次启动覆盖时，报的就是 nonce=""。
            # 本轮在 Windows 构建机上就是这么复现出 stop_refused_foreign 的。
            # 只允许**升级**（弱 ours → 强 ours），绝不降级为 foreign：app 标记已经证明对面说的是
            # 星阙协议，把它判成 foreign 会连「外部模式下用用户的桌面端当后端」一起打掉。
            for pid in listener_pids(port) if port is not None else []:
                # 只求升级为强证据，不为点名 → need_name=False：映像路径命中就不起 PowerShell。
                evidence, _image, _command = _holder_evidence(pid, runtime_root, need_name=False)
                if evidence:
                    return EndpointIdentity("ours", evidence, url, port, app, None)
            for pid in service_pids:
                if pid_alive(pid) == "alive":
                    return EndpointIdentity("ours", "registry.service_pid_alive", url, port, app, None)
            return EndpointIdentity("ours", "identity.app_marker", url, port, app, None)
        if app:
            return EndpointIdentity("foreign", "identity.other_app", url, port, app, None)

    # 2) 监听进程：先看映像路径（免编码），再看命令行
    if port is not None:
        pids = listener_pids(port)
        for pid in pids:
            # 这里要能点名陌生持有者 → need_name=True（映像命中时仍然不起 PowerShell）。
            evidence, image, command = _holder_evidence(pid, runtime_root, need_name=True)
            holders.append({"pid": pid, "image": image, "command": command or image})
            if evidence:
                return EndpointIdentity("ours", evidence, url, port, holders=holders)
        if holders and any(h.get("command") for h in holders):
            return EndpointIdentity("foreign", "process.command_is_not_ours", url, port, holders=holders)

    # 3) 我方注册表里记的服务 PID
    for pid in service_pids:
        if pid_alive(pid) == "alive":
            return EndpointIdentity("ours", "registry.service_pid_alive", url, port, holders=holders)

    return EndpointIdentity("unknown", "no_evidence", url, port, holders=holders)


def trust_unknown_ports() -> bool:
    """`HOROSA_RUNTIME_TRUST_PORTS=1`：用户明示「就采用这个查不出身份的服务」。"""
    return os.environ.get("HOROSA_RUNTIME_TRUST_PORTS", "").strip().lower() in {"1", "true", "yes", "on"}
