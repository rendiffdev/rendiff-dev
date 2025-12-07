"""
FastAPI dependencies for authentication, database, and common utilities.

This module uses modern FastAPI 0.124+ patterns including:
- Annotated type hints with Doc for better documentation
- Dependency scopes for proper resource management
- Enhanced type safety with Pydantic 2.10+
"""
from typing import Optional, Annotated, AsyncGenerator

from annotated_doc import Doc
from fastapi import Depends, HTTPException, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from api.config import settings
from api.models.database import get_session

logger = structlog.get_logger()


# Type aliases for cleaner code
APIKey = Annotated[str, Doc("Valid API key for authentication")]
OptionalAPIKey = Annotated[Optional[str], Doc("Optional API key from headers")]


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session dependency.

    Uses FastAPI's dependency injection to provide database sessions
    that are automatically closed after the request completes.
    """
    async for session in get_session():
        yield session


# Create typed dependency for database session
DatabaseSession = Annotated[
    AsyncSession,
    Depends(get_db),
    Doc("Async database session for database operations")
]


async def get_api_key(
    x_api_key: Annotated[
        Optional[str],
        Header(
            alias="X-API-Key",
            description="API key for authentication",
            example="rnd_live_abcdef123456789"
        )
    ] = None,
    authorization: Annotated[
        Optional[str],
        Header(
            description="Bearer token authorization",
            example="Bearer rnd_live_abcdef123456789"
        )
    ] = None,
) -> Optional[str]:
    """
    Extract API key from request headers.

    Supports two authentication methods:
    1. X-API-Key header: Direct API key
    2. Authorization header: Bearer token format
    """
    if x_api_key:
        return x_api_key

    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]

    return None


async def require_api_key(
    request: Request,
    api_key: Annotated[
        Optional[str],
        Depends(get_api_key),
        Doc("API key extracted from request headers")
    ] = None,
    db: DatabaseSession = None,
) -> str:
    """
    Require valid API key for endpoint access.

    This dependency:
    - Validates API key format and existence
    - Uses timing attack protection
    - Supports IP whitelist validation
    - Updates API key usage statistics

    Returns:
        str: Validated API key

    Raises:
        HTTPException: 401 if API key is missing or invalid
        HTTPException: 403 if IP is not in whitelist
    """
    if not settings.ENABLE_API_KEYS:
        return "anonymous"

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "authentication_required",
                "message": "API key required",
                "help": "Include X-API-Key header or Authorization: Bearer <key>"
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate API key against database with timing attack protection
    import asyncio
    from api.services.api_key import APIKeyService

    # Always take the same amount of time regardless of key validity
    start_time = asyncio.get_event_loop().time()

    api_key_model = await APIKeyService.validate_api_key(
        db, api_key, update_usage=True
    )

    # Ensure constant time execution (minimum 100ms)
    elapsed = asyncio.get_event_loop().time() - start_time
    min_time = 0.1  # 100ms
    if elapsed < min_time:
        await asyncio.sleep(min_time - elapsed)

    if not api_key_model:
        logger.warning(
            "Invalid API key attempted",
            api_key_prefix=api_key[:8] + "..." if len(api_key) > 8 else api_key,
            client_ip=request.client.host if request.client else "unknown",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "invalid_api_key",
                "message": "Invalid API key"
            },
        )

    # Check IP whitelist if enabled
    if settings.ENABLE_IP_WHITELIST:
        import ipaddress
        client_ip = request.client.host if request.client else "unknown"

        # Validate client IP against CIDR ranges
        try:
            client_ip_obj = ipaddress.ip_address(client_ip)
            allowed = False

            for allowed_range in settings.ip_whitelist_parsed:
                try:
                    if client_ip_obj in ipaddress.ip_network(allowed_range, strict=False):
                        allowed = True
                        break
                except (ipaddress.AddressValueError, ipaddress.NetmaskValueError):
                    # Fallback to string comparison for invalid CIDR
                    if client_ip.startswith(allowed_range):
                        allowed = True
                        break

            if not allowed:
                logger.warning(
                    "IP not in whitelist",
                    client_ip=client_ip,
                    api_key_id=str(api_key_model.id),
                    user_id=api_key_model.user_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "ip_not_authorized",
                        "message": "IP address not authorized"
                    },
                )
        except ValueError:
            # Invalid IP address format
            pass

    # Store API key model in request state for other endpoints
    request.state.api_key_model = api_key_model

    return api_key


# Create typed dependency for API key requirement
RequiredAPIKey = Annotated[
    str,
    Depends(require_api_key),
    Doc("Validated API key from request")
]


async def get_current_user(
    request: Request,
    api_key: RequiredAPIKey,
) -> dict:
    """
    Get current user information from validated API key.

    Returns a dictionary containing user details, quotas, and usage statistics.
    """
    # Get API key model from request state (set by require_api_key)
    api_key_model = getattr(request.state, 'api_key_model', None)

    if not api_key_model:
        # Fallback for anonymous access
        return {
            "id": "anonymous",
            "api_key": api_key,
            "role": "anonymous",
            "quota": {
                "concurrent_jobs": 1,
                "monthly_minutes": 100,
            },
        }

    return {
        "id": api_key_model.user_id or f"api_key_{api_key_model.id}",
        "api_key_id": str(api_key_model.id),
        "api_key": api_key,
        "name": api_key_model.name,
        "organization": api_key_model.organization,
        "role": "admin" if api_key_model.is_admin else "user",
        "quota": {
            "concurrent_jobs": api_key_model.max_concurrent_jobs,
            "monthly_minutes": api_key_model.monthly_limit_minutes,
        },
        "usage": {
            "total_requests": api_key_model.total_requests,
            "last_used_at": api_key_model.last_used_at.isoformat() if api_key_model.last_used_at else None,
        },
        "expires_at": api_key_model.expires_at.isoformat() if api_key_model.expires_at else None,
        "is_admin": api_key_model.is_admin,
    }


# Create typed dependency for current user
CurrentUser = Annotated[
    dict,
    Depends(get_current_user),
    Doc("Current authenticated user information")
]


# Optional API key dependency (doesn't require authentication)
async def get_optional_api_key(
    api_key: Annotated[Optional[str], Depends(get_api_key)] = None,
) -> Optional[str]:
    """Get API key if provided, without requiring it."""
    return api_key


OptionalAuth = Annotated[
    Optional[str],
    Depends(get_optional_api_key),
    Doc("Optional API key for endpoints that support anonymous access")
]
