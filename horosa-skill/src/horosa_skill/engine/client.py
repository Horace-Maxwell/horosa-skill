from __future__ import annotations

from typing import Any

import httpx

from horosa_skill.errors import ToolTransportError


class HorosaApiClient:
    def __init__(self, server_root: str, timeout: float = 60.0) -> None:
        self.server_root = server_root.rstrip("/")
        self.timeout = timeout

    def call(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.server_root}{endpoint}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise ToolTransportError(
                        "Horosa server returned a non-object JSON response.",
                        code="transport.invalid_response_shape",
                        details={"endpoint": endpoint},
                    )
                return data
        except httpx.HTTPStatusError as exc:
            raise ToolTransportError(
                f"Horosa server returned HTTP {exc.response.status_code}.",
                code="transport.http_error",
                details={"endpoint": endpoint, "status_code": exc.response.status_code, "body": exc.response.text[:1000]},
            ) from exc
        except httpx.HTTPError as exc:
            raise ToolTransportError(
                "Could not reach the Horosa server.",
                code="transport.connection_error",
                details={"endpoint": endpoint, "message": str(exc)},
            ) from exc
        except ValueError as exc:
            raise ToolTransportError(
                "Horosa server returned invalid JSON.",
                code="transport.invalid_json",
                details={"endpoint": endpoint, "message": str(exc)},
            ) from exc

