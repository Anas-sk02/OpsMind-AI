from typing import AsyncGenerator, Callable, List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AuthenticationException, ForbiddenException
from app.core.security import decode_token, extract_user_claims

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user_token(
    token: str = Depends(oauth2_scheme)
) -> dict:
    """
    Validates Bearer token from incoming request headers (supports Supabase Auth tokens).
    Returns normalized token claims dict {user_id, email, role, raw_payload}.
    """
    if not token:
        raise AuthenticationException("Authentication required: Missing Bearer Token")
    try:
        raw_payload = decode_token(token)
        claims = extract_user_claims(raw_payload)
        return claims
    except Exception as e:
        raise AuthenticationException(f"Invalid or expired Supabase credentials: {str(e)}")


def require_roles(allowed_roles: List[str]) -> Callable:
    """
    Factory creating a dependency that enforces server-side Role-Based Access Control (RBAC).
    Allowed roles e.g. ["ADMIN"], ["PACKAGING"], ["DELIVERY"].
    """
    async def role_checker(claims: dict = Depends(get_current_user_token)) -> dict:
        user_role = claims.get("role")
        if not user_role or user_role not in allowed_roles:
            raise ForbiddenException(
                f"Access denied: Role '{user_role}' is not authorized for this resource. Required: {allowed_roles}"
            )
        return claims

    return role_checker
