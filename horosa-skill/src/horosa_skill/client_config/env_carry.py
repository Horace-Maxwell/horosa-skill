"""跑 `setup` / `client config` 的终端里设着的 `HOROSA_*`，哪些要写进客户端配置的 env 表。

🔴 为什么要有这张表：客户端起 MCP server 时给它的环境**不是**你终端里的环境——GUI 客户端（Claude Desktop、Cursor、
VS Code…）不读 shell 配置，Codex 只转发十几个系统变量。终端里 `HOROSA_RUNTIME_ROOT=/data/horosa horosa-skill setup`
装得好好的，客户端起的 server 却去默认目录找 runtime：每个技法都回 `runtime.not_installed`，而 setup 报的是全绿
（旧探针继承了终端的环境，所以它自己是通的）。

规则只有一条：**决定「用哪套引擎、哪份数据」的变量，显式设了且不等于缺省值，就写进条目的 env**；其余一律不写。
- 写（`CARRIED`）：runtime 根、数据目录及其派生路径、两个引擎地址与端口、JS 引擎与 node 的位置、自备知识库位置。路径写成解析后的
  绝对路径（客户端的 cwd 不是你的 cwd）。
- 不写、但 setup 会点名（`behaviour` 组）：改变 server 行为的开关（`HOROSA_TOOLSETS`、`HOROSA_CLARIFY`…）。它们是
  「这个终端里临时试一下」的常客，悄悄固化进客户端配置比不带更糟；要它生效，自己写进 env 表。
- 永不写：密钥与令牌（按名字判，见 `is_secret_env_name`）、只对 `serve` 的 HTTP 传输 / 安装下载 / 诊断有意义的、内部的。
- 由 setup 自己的参数决定（`FLAG_OWNED`）：`--surface` / `--output-script` / `--vectors`。

`config.ENV_FLAG_REGISTRY` 里的每个变量都必须落在这三张表之一（tests/test_client_env_carry.py 锁）：新增一个环境变量时
必须回答「客户端需不需要它」，不会再默默漏掉。
"""
from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path

from horosa_skill import config

# 名字里带这些词的变量当密钥：值永不写进配置、永不回显。登记表（config.ENV_FLAG_REGISTRY）目前没有「是不是密钥」这一列，
# 判据先住在这里；哪天登记表有了，这个函数改成读它。
# 按下划线分段匹配：`HOROSA_MCP_TOKEN` 是密钥，`HOROSA_MCP_RESULT_MAX_TOKENS`（阅读视图的预算）不是——子串匹配曾把后者当成密钥。
_SECRET_NAME = re.compile(r"(?:^|_)(TOKEN|SECRET|PASSWORD|PASSWD|API_?KEY|CREDENTIALS?|PRIVATE_?KEY|BEARER|COOKIE)(?:_|$)", re.IGNORECASE)


def is_secret_env_name(name: str) -> bool:
    """这个环境变量名看起来装的是密钥 / 令牌吗（`HOROSA_MCP_TOKEN`、`HOROSA_JEV_API_KEY`、别家的 `*_API_KEY`…）。"""
    return bool(_SECRET_NAME.search(name or ""))


# name -> 写法：path = 解析成绝对路径；pathlist = os.pathsep 分隔的一串路径；program = 带目录才解析（裸命令名原样）；
# value = 原样。
CARRIED: dict[str, str] = {
    "HOROSA_RUNTIME_ROOT": "path",
    "HOROSA_SKILL_DATA_DIR": "path",
    "HOROSA_SKILL_DB_PATH": "path",
    "HOROSA_SKILL_OUTPUT_DIR": "path",
    "HOROSA_REPORT_OUTPUT_ROOTS": "pathlist",
    "HOROSA_USER_KNOWLEDGE_DIR": "path",
    "HOROSA_USER_KNOWLEDGE_MAX_CHARS": "value",
    "HOROSA_EMBED_MODEL_DIR": "path",
    "HOROSA_ASTRODATA_DB": "path",
    "HOROSA_NODE_BIN": "program",
    "HOROSA_CORE_JS_ROOT": "path",  # 没有离线 runtime 的机器（网关模式）靠它找 JS 引擎：八字 / 紫微 / 奇门等都算在那里
    "HOROSA_SERVER_ROOT": "value",
    "HOROSA_CHART_SERVER_ROOT": "value",
    "HOROSA_LOCAL_BACKEND_PORT": "value",
    "HOROSA_LOCAL_CHART_PORT": "value",
    "HOROSA_PORTS": "value",
}

# setup / client config 自己的参数说了算（--surface / --output-script / --vectors）。
FLAG_OWNED: frozenset[str] = frozenset({"HOROSA_MCP_COMPACT", "HOROSA_OUTPUT_SCRIPT", "HOROSA_KNOWLEDGE_VECTORS"})

# 不写进配置的，按原因分组。`behaviour` 组设了会被 setup 点名（其余组与 stdio 客户端无关，点名只是噪声）。
NOT_CARRIED: dict[str, str] = {
    # 改变 server 行为的开关
    "HOROSA_TOOLSETS": "behaviour",
    "HOROSA_CLARIFY": "behaviour",
    "HOROSA_TECHNIQUE_CARD": "behaviour",
    "HOROSA_OUTPUT_SCHEMA": "behaviour",
    "HOROSA_MCP_ELICIT": "behaviour",
    "HOROSA_MCP_ELICIT_TIMEOUT_SECONDS": "behaviour",
    "HOROSA_MCP_RESULT_VIEW": "behaviour",
    "HOROSA_MCP_RESULT_MAX_TOKENS": "behaviour",
    "HOROSA_MCP_RESULT_MAX_CHARS": "behaviour",
    "HOROSA_MCP_MAX_CONCURRENT_TOOLS": "behaviour",
    "HOROSA_STRICT_CONFIG": "behaviour",
    "HOROSA_RUNTIME_START_TIMEOUT_SECONDS": "behaviour",
    "HOROSA_RUNTIME_CALL_WAIT_SECONDS": "behaviour",
    "HOROSA_RUNTIME_JAVA_RETRY_COOLDOWN_SECONDS": "behaviour",
    "HOROSA_RUNTIME_TRUST_PORTS": "behaviour",
    "HOROSA_JS_ENGINE_TIMEOUT_SECONDS": "behaviour",
    "HOROSA_JEV": "behaviour",
    "HOROSA_JEV_SCOPE": "behaviour",
    "HOROSA_JEV_SURFACES": "behaviour",
    "HOROSA_JEV_MODEL": "behaviour",
    "HOROSA_JEV_BASE_URL": "behaviour",
    "HOROSA_JEV_TIMEOUT_MS": "behaviour",
    "HOROSA_JEV_LEDGER": "behaviour",
    # 密钥 / 令牌：永不写
    "HOROSA_MCP_TOKEN": "secret",
    "HOROSA_JEV_API_KEY": "secret",
    # 只对 `serve` 的 HTTP 传输有意义（stdio 客户端用不到）
    "HOROSA_MCP_ALLOWED_HOSTS": "serve",
    "HOROSA_SKILL_HOST": "serve",
    "HOROSA_SKILL_PORT": "serve",
    # 只在安装 / 下载 runtime 时读
    "HOROSA_RUNTIME_MANIFEST_URL": "install",
    "HOROSA_RUNTIME_RELEASE_REPO": "install",
    "HOROSA_RUNTIME_MIRROR": "install",
    "HOROSA_RUNTIME_DOWNLOAD_TIMEOUT_SECONDS": "install",
    "HOROSA_RUNTIME_DOWNLOAD_ATTEMPTS": "install",
    "HOROSA_RUNTIME_RELEASE_BASE_URL": "install",
    "HOROSA_RUNTIME_LAUNCHER_PATCH": "install",
    "HOROSA_RUNTIME_PLATFORM": "install",
    # 日志与追踪
    "HOROSA_SKILL_LOG_LEVEL": "diagnostics",
    "HOROSA_TRACE_ENABLED": "diagnostics",
    "HOROSA_TRACE_DIR": "diagnostics",
    "HOROSA_TRACE_CAPTURE_PAYLOADS": "diagnostics",
    "HOROSA_TRACE_CAPTURE_AI_ANSWERS": "diagnostics",
    "HOROSA_TRACE_OTLP_ENDPOINT": "diagnostics",
    # 宿主 / 启动器 / 构建脚本之间传的，或星阙桌面版自己的
    "HOROSA_INSTALL_CONTEXT": "internal",
    "HOROSA_PLUGIN_ROOT": "internal",
    "HOROSA_CDS_TRAIN_PORT": "internal",
    "HOROSA_UV_BIN": "internal",
    "HOROSA_UVX_BIN": "internal",
    "HOROSA_MCPORTER_BIN": "internal",
    "HOROSA_SERVER_PORT": "internal",
    "HOROSA_CHART_PORT": "internal",
    "HOROSA_BACKEND_PORT": "internal",
    "HOROSA_ROOT": "internal",
    "HOROSA_LOG_ROOT": "internal",
    "HOROSA_SOURCE_ROOT": "internal",
    "HOROSA_WINDOWS_SOURCE_ROOT": "internal",
    "HOROSA_LINUX_JAVA_HOME": "internal",
    "HOROSA_LINUX_PYTHON_HOME": "internal",
    "HOROSA_LINUX_SKIP_DOWNLOAD": "internal",
    "HOROSA_SKILL_PYPROJECT": "internal",
    "HOROSA_LAUNCH_NONCE": "internal",
    "HOROSA_JEV_LIVE": "internal",
    "HOROSA_VERAPDF": "internal",
    "HOROSA_EPHE_PATH_FASTPATH": "internal",
    "HOROSA_DESKTOP_MONGO_OPTIONAL": "internal",
    "HOROSA_DESKTOP_MONGO_SKIP_PING": "internal",
    "HOROSA_MONGO_FALLBACK_DIR": "internal",
    "HOROSA_ENABLE_STARTUP_CRON": "internal",
    "HOROSA_ENABLE_STARTUP_TRANSGROUP_INIT": "internal",
    "HOROSA_JAVA_HOME": "internal",
    "HOROSA_APP_CHARTS": "internal",
    "HOROSA_APP_CHARTS_DEBUG": "internal",
}


def _read(environ: Mapping[str, str], name: str) -> str | None:
    """与 `config._env_text` 同一口径：空白、宿主没展开的 `${…}` 占位符都当没设。"""
    value = (environ.get(name) or "").strip()
    if not value or config._UNEXPANDED_TEMPLATE.search(value):
        return None
    return value


def _absolute(value: str) -> str:
    try:
        return str(Path(value).expanduser().resolve())
    except (OSError, RuntimeError):
        return str(Path(value).expanduser())


def _defaults() -> dict[str, str]:
    """有固定缺省值的那几个：设成缺省值等于没设，不写（配置保持最小、与没设时逐字节相同）。"""
    return {
        "HOROSA_RUNTIME_ROOT": _absolute(str(config._default_runtime_root())),
        "HOROSA_SKILL_DATA_DIR": _absolute(str(config._default_home_dir())),
        "HOROSA_SERVER_ROOT": "http://127.0.0.1:9999",
        "HOROSA_CHART_SERVER_ROOT": "http://127.0.0.1:8899",
        "HOROSA_LOCAL_BACKEND_PORT": "9999",
        "HOROSA_LOCAL_CHART_PORT": "8899",
        "HOROSA_USER_KNOWLEDGE_MAX_CHARS": "12000",
    }


def _rendered(kind: str, value: str) -> str:
    if kind == "path":
        return _absolute(value)
    if kind == "pathlist":
        return os.pathsep.join(_absolute(part) for part in value.split(os.pathsep) if part.strip())
    if kind == "program":
        # 裸命令名（`node`）靠 PATH 找，原样写；带目录的才是一个位置。
        return _absolute(value) if any(sep and sep in value for sep in (os.sep, os.altsep)) else value
    return value.rstrip("/") if value.startswith(("http://", "https://")) else value


def carried_env(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """要写进客户端条目 env 的变量：显式设了、不是密钥、且不等于缺省值的 `CARRIED` 成员（按表的顺序）。"""
    environ = os.environ if environ is None else environ
    defaults = _defaults()
    out: dict[str, str] = {}
    for name, kind in CARRIED.items():
        raw = _read(environ, name)
        if raw is None or is_secret_env_name(name):
            continue
        value = _rendered(kind, raw)
        if value and value != defaults.get(name):
            out[name] = value
    return out


def shell_only(environ: Mapping[str, str] | None = None) -> list[str]:
    """终端里设着、会改变 server 行为、但**不会**写进配置的变量名（只给名字，不给值）。"""
    environ = os.environ if environ is None else environ
    return [name for name, group in NOT_CARRIED.items() if group == "behaviour" and _read(environ, name) is not None]


# 任何客户端都会给子进程的系统变量（Codex 的转发表就是这个量级；Windows 上缺 SYSTEMROOT / APPDATA 连 Python 都起不来）。
_SYSTEM_ENV = (
    "PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "SystemRoot", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP", "TMPDIR",
    "LANG", "LC_ALL", "LC_CTYPE", "COMSPEC", "PATHEXT", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "PROGRAMFILES",
    "HOMEDRIVE", "HOMEPATH", "USERNAME", "USER", "LOGNAME", "SHELL", "TERM", "TZ",
)
# 装依赖要走的网络配置（代理、证书、uv 的索引 / 缓存位置）：探针顺带把 uv / uvx 的环境装好，客户端之后从缓存起。
# 这些不改变 server 算出什么，只决定依赖下不下得来——留着，免得镜像 / 代理后面的机器在探针这一步白白失败。
_PLUMBING_NAMES = frozenset({
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE", "NODE_EXTRA_CA_CERTS",
})
_PLUMBING_PREFIXES = ("UV_", "XDG_")


def minimal_client_env(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """「客户端什么都不替你带」时 server 拿到的环境：系统变量 + 装依赖的网络配置，**没有**终端里的 `HOROSA_*` / `PYTHON*`。

    setup 的 stdio 探针用它（再并上条目自己的 env）起 server：只因为终端里设着某个变量才通的配置，在这里通不了。
    """
    environ = os.environ if environ is None else environ
    system = {name.upper() for name in _SYSTEM_ENV}
    return {
        name: value for name, value in environ.items()
        if name.upper() in system or name.upper() in _PLUMBING_NAMES or name.upper().startswith(_PLUMBING_PREFIXES)
    }
