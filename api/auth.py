import hmac

from fastapi import HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader

from api.config import settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(_api_key_header)) -> str:
    """Require a valid X-API-Key header for write operations.

    GET / analytics endpoints are intentionally public — attach this dependency
    only to POST, PATCH, and DELETE routes.
    """
    if not api_key or not hmac.compare_digest(api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing or invalid API key.",
        )
    return api_key
