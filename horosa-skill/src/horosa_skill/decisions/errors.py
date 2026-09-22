"""决策层错误族。所有消息都不得含 API key（传输层在构造消息前先 `_scrub`）。"""

from __future__ import annotations

from horosa_skill.errors import HorosaSkillError


class JevError(HorosaSkillError):
    """决策层任何失败的基类；调用方按它整体关闭式降级。"""

    def __init__(self, message: str, *, code: str = "jev.error", details: dict | None = None) -> None:
        super().__init__(message, code=code, details=details)


class JevConfigError(JevError):
    """配置不合法（非 https、key 缺失、问题规格越界）。"""

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message, code="jev.config", details=details)


class JevUnavailable(JevError):
    """本次不可用（面未开 / 熔断中 / 回放缺记录）——不是故障，是策略。"""

    def __init__(self, message: str, *, code: str = "jev.unavailable", details: dict | None = None) -> None:
        super().__init__(message, code=code, details=details)


class JevRequestError(JevError):
    """4xx 且不可重试（400/404/422）。"""

    def __init__(self, message: str, *, code: str = "jev.request", details: dict | None = None) -> None:
        super().__init__(message, code=code, details=details)


class JevAuthError(JevRequestError):
    """401/403：key 无效或无权限。"""

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message, code="jev.auth", details=details)


class JevRateLimited(JevError):
    """429 / 529：限流或过载，重试预算用尽后抛出。"""

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message, code="jev.rate_limited", details=details)


class JevServerError(JevError):
    """5xx。"""

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message, code="jev.server", details=details)


class JevConnectionError(JevError):
    """连接层失败（DNS / TLS / 连接被拒）。"""

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message, code="jev.connection", details=details)


class JevTimeout(JevError):
    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message, code="jev.timeout", details=details)


class JevResponseInvalid(JevError):
    """HTTP 2xx 但响应体不合官方 schema（缺问题 / 概率越界 / 选项不在集合里）。"""

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message, code="jev.response_invalid", details=details)
