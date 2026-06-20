"""API key authentication for Terra OBIA REST endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from terra_api.config import settings

_api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description=(
        "API key issued by your Terra OBIA administrator. "
        "Enterprise deployments will upgrade to OAuth2/SSO."
    ),
)


def require_api_key(api_key: Annotated[str | None, Security(_api_key_header)] = None) -> str:
    """Validate the request API key when authentication is enabled.

    When ``TERRA_API_KEY`` is unset (development mode), authentication is skipped.
    Production and government deployments should set ``TERRA_API_KEY`` and later
    migrate to OAuth2/OpenID Connect single sign-on.

    Args:
        api_key: Value from the ``X-API-Key`` request header.

    Returns:
        Validated API key string.

    Raises:
        HTTPException: When authentication is required and the key is missing/invalid.
    """
    configured = settings.api_key
    if configured is None:
        return "development"
    if api_key is None or api_key != configured:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )
    return api_key


AuthenticatedKey = Annotated[str, Depends(require_api_key)]
