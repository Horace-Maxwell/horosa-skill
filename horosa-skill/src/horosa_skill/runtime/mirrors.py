"""GitHub download URLs through user-configured mirror prefixes (v0.38.0 B3, extracted from the manager).

`HOROSA_RUNTIME_MIRROR` is a comma-separated list of prefixes that replace `https://github.com` — the
same rewrite serves the runtime manifest, the runtime archives and the wheel release asset, so a machine
that cannot reach github.com:443 (issue #14) has ONE knob. The original URL is always the last candidate.
"""

from __future__ import annotations

import os

GITHUB = "https://github.com"


def _insecure(prefix: str) -> bool:
    """明文 http 且不是回环（审计 PF-01 第 2 层）：中间人能换掉清单与归档。HOROSA_RUNTIME_MIRROR_ALLOW_HTTP=1 才放。"""
    from urllib.parse import urlparse

    parsed = urlparse(prefix)
    if parsed.scheme != "http":
        return False
    host = (parsed.hostname or "").lower()
    return host not in {"127.0.0.1", "localhost", "::1"}


def _allow_http() -> bool:
    return os.environ.get("HOROSA_RUNTIME_MIRROR_ALLOW_HTTP", "").strip().lower() in {"1", "true", "yes", "on"}


def mirror_prefixes(mirrors: str | None = None) -> tuple[list[str], list[str]]:
    """(用得上的镜像前缀, 因明文 http 被拒的前缀)。"""
    raw = os.environ.get("HOROSA_RUNTIME_MIRROR", "") if mirrors is None else mirrors
    prefixes = [m.strip().rstrip("/") for m in raw.split(",") if m.strip()]
    if _allow_http():
        return prefixes, []
    return [p for p in prefixes if not _insecure(p)], [p for p in prefixes if _insecure(p)]


def mirror_candidates(url: str, mirrors: str | None = None) -> list[str]:
    """Mirror-prefixed variants of a github.com URL first, the original URL last.

    Non-GitHub URLs (a corporate proxy, a `file://` archive) are returned untouched. Plain-http mirrors that are not
    loopback are dropped unless HOROSA_RUNTIME_MIRROR_ALLOW_HTTP=1 (audit PF-01).
    """
    prefixes, _rejected = mirror_prefixes(mirrors)
    if not prefixes or not url.startswith(GITHUB + "/"):
        return [url]
    suffix = url[len(GITHUB):]
    return [f"{prefix}{suffix}" for prefix in prefixes] + [url]


def preferred_mirror_url(url: str) -> str:
    """First mirror if any, else the original — for one-off commands a user runs by hand (hints).

    Generated client configs must NOT use this (audit PF-02): the client would fetch and execute the wheel from the
    mirror on every cold start. They carry the original https URL or a locally cached, digest-checked wheel."""
    return mirror_candidates(url)[0]
