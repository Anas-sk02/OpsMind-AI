import uuid
from typing import AsyncGenerator, Callable, List, Optional
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AuthenticationException, ForbiddenException
from app.core.security import decode_token, extract_user_claims
from app.models.user import User
from app.services.auth_service import AuthService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user_claims(
    token: Optional[str] = Depends(oauth2_scheme)
) -> dict:
    """
    Validates Bearer token from incoming request headers (supports Supabase Auth & custom JWTs).
    Returns normalized claims dict {user_id, email, role, raw_payload}.
    """
    if not token:
        raise AuthenticationException("Authentication required: Missing Bearer Token")
    try:
        raw_payload = decode_token(token)
        claims = extract_user_claims(raw_payload)
        return claims
    except Exception as e:
        raise AuthenticationException(f"Invalid or expired credentials: {str(e)}")


# Alias for backward compatibility with tests
get_current_user_token = get_current_user_claims


async def get_current_user(
    claims: dict = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Retrieves and validates the current active User entity from the database.
    If the user authenticated via Supabase, synchronizes the user into local state.
    """
    user_id_str = claims.get("user_id")
    if not user_id_str:
        raise AuthenticationException("Invalid token payload: Missing subject claim")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise AuthenticationException("Malformed user identifier in token")

    user = await AuthService.get_user_by_id(db, user_id)
    if not user:
        # If user authenticated via Supabase Auth, auto-sync profile
        user = await AuthService.sync_or_create_supabase_user(db, claims)

    if not user.is_active:
        raise ForbiddenException("User account has been deactivated. Access denied.")

    return user


def require_roles(allowed_roles: List[str]) -> Callable:
    """
    Factory creating a FastAPI dependency that enforces server-side Role-Based Access Control (RBAC).
    Allowed roles e.g. ["ADMIN"], ["PACKAGING"], ["DELIVERY"].
    """
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise ForbiddenException(
                f"Access denied: User role '{current_user.role}' is not authorized. Required: {allowed_roles}"
            )
        return current_user

    return role_checker


# Convenient pre-configured role dependencies
require_admin = require_roles(["ADMIN"])
require_packaging = require_roles(["ADMIN", "PACKAGING"])
require_delivery = require_roles(["ADMIN", "DELIVERY"])
require_operator = require_roles(["ADMIN", "PACKAGING", "DELIVERY"])
require_authenticated_staff = require_roles(["ADMIN", "PACKAGING", "DELIVERY"])

