"""Shared request-header helpers."""

from typing import Mapping, Optional


APP_ID_HEADER = "X-FangcunGuard-Application-ID"
APP_ID_HEADER_ALIASES = (
    APP_ID_HEADER,
    "X-FG-Application-ID",
    "X-OG-Application-ID",
)


def read_external_app_id(headers: Mapping[str, str]) -> Optional[str]:
    """Return the external application id from the supported header aliases."""
    for name in APP_ID_HEADER_ALIASES:
        value = headers.get(name)
        if value:
            return value
    return None
