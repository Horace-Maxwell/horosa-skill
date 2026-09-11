"""GitHub download URLs through user-configured mirror prefixes (v0.38.0 B3, extracted from the manager).

`HOROSA_RUNTIME_MIRROR` is a comma-separated list of prefixes that replace `https://github.com` — the
same rewrite serves the runtime manifest, the runtime archives and the wheel release asset, so a machine
that cannot reach github.com:443 (issue #14) has ONE knob. The original URL is always the last candidate.
"""

from __future__ import annotations

import os

GITHUB = "https://github.com"


def mirror_candidates(url: str, mirrors: str | None = None) -> list[str]:
    """Mirror-prefixed variants of a github.com URL first, the original URL last.

    Non-GitHub URLs (a corporate proxy, a `file://` archive) are returned untouched.
    """
    raw = os.environ.get("HOROSA_RUNTIME_MIRROR", "") if mirrors is None else mirrors
    prefixes = [m.strip().rstrip("/") for m in raw.split(",") if m.strip()]
    if not prefixes or not url.startswith(GITHUB + "/"):
        return [url]
    suffix = url[len(GITHUB):]
    return [f"{prefix}{suffix}" for prefix in prefixes] + [url]


def preferred_mirror_url(url: str) -> str:
    """The URL a generated client config should carry: first mirror if any, else the original."""
    return mirror_candidates(url)[0]
