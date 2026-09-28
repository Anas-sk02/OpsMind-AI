from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# CryptContext configured with Argon2 as default scheme, falling back to bcrypt if needed
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain text password against a stored hashed password.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Generates a secure Argon2id hash of the plain text password.
    """
    return pwd_context.hash(password)


DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES = 60
DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS = 7


def create_access_token(
    subject: Union[str, Any],
    role: str,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Generates a signed JWT access token for local testing or mock tokens.
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode: Dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "exp": expire,
        "type": "access",
        "iat": datetime.now(timezone.utc),
    }

    if extra_claims:
        to_encode.update(extra_claims)

    jwt_secret = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY
    return jwt.encode(to_encode, jwt_secret, algorithm=settings.ALGORITHM)


def create_refresh_token(
    subject: Union[str, Any],
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Generates a signed JWT refresh token.
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode: Dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "exp": expire,
        "type": "refresh",
        "iat": datetime.now(timezone.utc),
    }

    jwt_secret = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY
    return jwt.encode(to_encode, jwt_secret, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decodes and validates a JWT token.
    Supports both Supabase Auth JWTs (using SUPABASE_JWT_SECRET if present)
    and standard local JWTs.
    """
    # Try with Supabase JWT Secret if provided, else fall back to application SECRET_KEY
    jwt_secret = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY
    try:
        return jwt.decode(
            token,
            jwt_secret,
            algorithms=[settings.ALGORITHM],
            options={"verify_aud": False},  # Supabase tokens often use "authenticated" audience
        )
    except JWTError:
        # Fallback to local SECRET_KEY if distinct
        if jwt_secret != settings.SECRET_KEY:
            return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        raise


def extract_user_claims(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizes claims from both Supabase Auth tokens and custom tokens.
    Extracts user_id, email, and role ('ADMIN', 'PACKAGING', 'DELIVERY').
    """
    user_id = payload.get("sub")
    email = payload.get("email") or payload.get("user_metadata", {}).get("email")

    # Supabase roles can be in app_metadata.role or user_metadata.role or direct 'role' claim
    app_meta = payload.get("app_metadata", {})
    user_meta = payload.get("user_metadata", {})
    
    role = (
        app_meta.get("role")
        or user_meta.get("role")
        or payload.get("role")
        or "AUTHENTICATED"
    )

    if isinstance(role, str):
        role = role.upper()

    return {
        "user_id": user_id,
        "email": email,
        "role": role,
        "raw_payload": payload,
    }
