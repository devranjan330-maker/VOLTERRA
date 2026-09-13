from fastapi import Header, HTTPException, Depends
from starlette.status import HTTP_401_UNAUTHORIZED
from .config import settings

def validate_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """Simple API‑key validation dependency.
    Raises HTTP_401_UNAUTHORIZED if the provided key does not match the secret
    defined in the environment (settings.API_KEY)."""
    if x_api_key != settings.API_KEY:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_api_key", "message": "Invalid API key"},
        )
    return True

# Export a FastAPI dependency that can be added globally
api_key_dependency = Depends(validate_api_key)
