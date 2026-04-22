from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from app.config import get_settings

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """
    Simple API key auth. To upgrade to JWT later:
    1. Replace this function body with JWT decode logic
    2. Update the Security() dependency in routes
    3. Nothing else in the codebase needs to change
    """
    settings = get_settings()

    if settings.environment == "development" and not api_key:
        return "dev-bypass"

    if not api_key or api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Pass X-API-Key header.",
        )
    return api_key
