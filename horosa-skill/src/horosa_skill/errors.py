from __future__ import annotations


class HorosaSkillError(Exception):
    def __init__(self, message: str, *, code: str = "horosa_skill_error", details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


class ToolTransportError(HorosaSkillError):
    pass


class ToolValidationError(HorosaSkillError):
    pass


class DispatchResolutionError(HorosaSkillError):
    pass


class RuntimeError(HorosaSkillError):
    pass


class RuntimeInstallError(RuntimeError):
    pass


class RuntimeValidationError(RuntimeError):
    pass
