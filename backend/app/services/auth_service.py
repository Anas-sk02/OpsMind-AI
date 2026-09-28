import uuid
import logging
from typing import Optional, List, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.exceptions import (
    AuthenticationException,
    NotFoundException,
    ConflictException,
    ValidationException,
)
from app.models.user import User
from app.models.audit_log import AuditLog
from app.schemas.auth import (
    CreateStaffRequest,
    UpdateStaffRequest,
    TokenResponse,
    UserResponse,
)

logger = logging.getLogger("opsmind.auth_service")


class AuthService:
    """
    Business logic layer for staff authentication, session token issuance,
    and employee role administration.
    """

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
        stmt = select(User).where(func.lower(User.email) == email.lower().strip())
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def authenticate_user(
        db: AsyncSession, email: str, password: str
    ) -> User:
        """
        Validates email and password credentials for active staff users.
        """
        user = await AuthService.get_user_by_email(db, email)
        if not user:
            logger.warning(f"Login attempt failed: Email '{email}' not found")
            raise AuthenticationException("Invalid email or password credentials")

        if not user.is_active:
            logger.warning(f"Login attempt blocked: User account '{user.email}' is deactivated")
            raise AuthenticationException("User account has been deactivated. Contact system admin.")

        if not verify_password(password, user.hashed_password):
            logger.warning(f"Login attempt failed: Invalid password for user '{user.email}'")
            raise AuthenticationException("Invalid email or password credentials")

        return user

    @staticmethod
    def generate_auth_tokens(user: User) -> TokenResponse:
        """
        Generates access and refresh tokens for an authenticated user.
        """
        access_token = create_access_token(
            subject=user.id,
            role=user.role,
            extra_claims={"email": user.email, "full_name": user.full_name},
        )
        refresh_token = create_refresh_token(
            subject=user.id,
            role=user.role,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=3600,
            user=UserResponse.model_validate(user),
        )

    @staticmethod
    async def refresh_user_token(db: AsyncSession, refresh_token: str) -> TokenResponse:
        """
        Validates refresh token and issues a new access token pair.
        """
        try:
            payload = decode_token(refresh_token)
        except Exception as exc:
            raise AuthenticationException(f"Invalid or expired refresh token: {str(exc)}")

        token_type = payload.get("type")
        if token_type != "refresh":
            raise AuthenticationException("Invalid token type: Expected refresh token")

        user_id_str = payload.get("sub")
        if not user_id_str:
            raise AuthenticationException("Invalid token subject")

        try:
            user_id = uuid.UUID(user_id_str)
        except ValueError:
            raise AuthenticationException("Malformed user identifier in token")

        user = await AuthService.get_user_by_id(db, user_id)
        if not user or not user.is_active:
            raise AuthenticationException("User session no longer valid or user is deactivated")

        return AuthService.generate_auth_tokens(user)

    @staticmethod
    async def register_staff(
        db: AsyncSession, data: CreateStaffRequest, actor_id: Optional[uuid.UUID] = None
    ) -> User:
        """
        Provisions a new staff user with an Argon2id hashed password and audit trail.
        """
        existing = await AuthService.get_user_by_email(db, data.email)
        if existing:
            raise ConflictException(f"A staff user with email '{data.email}' already exists.")

        hashed_pw = get_password_hash(data.password)
        new_user = User(
            email=data.email.lower().strip(),
            hashed_password=hashed_pw,
            full_name=data.full_name.strip(),
            role=data.role,
            is_active=data.is_active,
        )
        db.add(new_user)
        await db.flush()

        # Record audit log
        audit = AuditLog(
            actor_id=actor_id,
            action="CREATE",
            entity_name="users",
            entity_id=new_user.id,
            change_diff={"email": new_user.email, "role": new_user.role},
        )
        db.add(audit)
        await db.commit()
        await db.refresh(new_user)
        logger.info(f"Staff user '{new_user.email}' created with role '{new_user.role}'")
        return new_user

    @staticmethod
    async def list_staff(
        db: AsyncSession,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[User], int]:
        """
        Lists staff employees with optional role and status filters.
        """
        query = select(User)
        count_query = select(func.count(User.id))

        if role:
            query = query.where(User.role == role.upper())
            count_query = count_query.where(User.role == role.upper())

        if is_active is not None:
            query = query.where(User.is_active == is_active)
            count_query = count_query.where(User.is_active == is_active)

        total_res = await db.execute(count_query)
        total = total_res.scalar() or 0

        query = query.order_by(User.created_at.desc()).offset(skip).limit(limit)
        res = await db.execute(query)
        users = list(res.scalars().all())

        return users, total

    @staticmethod
    async def update_staff(
        db: AsyncSession,
        user_id: uuid.UUID,
        data: UpdateStaffRequest,
        actor_id: Optional[uuid.UUID] = None,
    ) -> User:
        """
        Updates staff details, role, password, or soft-deactivation status.
        """
        user = await AuthService.get_user_by_id(db, user_id)
        if not user:
            raise NotFoundException(f"Staff user with ID '{user_id}' not found")

        diff = {}
        if data.full_name is not None and data.full_name != user.full_name:
            diff["full_name"] = {"old": user.full_name, "new": data.full_name}
            user.full_name = data.full_name

        if data.role is not None and data.role != user.role:
            diff["role"] = {"old": user.role, "new": data.role}
            user.role = data.role

        if data.is_active is not None and data.is_active != user.is_active:
            diff["is_active"] = {"old": user.is_active, "new": data.is_active}
            user.is_active = data.is_active

        if data.password:
            user.hashed_password = get_password_hash(data.password)
            diff["password"] = "PASSWORD_UPDATED"

        if diff:
            audit = AuditLog(
                actor_id=actor_id,
                action="UPDATE" if data.is_active is not False else "SOFT_DELETE",
                entity_name="users",
                entity_id=user.id,
                change_diff=diff,
            )
            db.add(audit)

        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def sync_or_create_supabase_user(
        db: AsyncSession, claims: dict
    ) -> User:
        """
        Idempotently synchronizes a Supabase authenticated user into the local database.
        """
        user_id_str = claims.get("user_id")
        email = claims.get("email")
        role = claims.get("role", "PACKAGING")

        if not user_id_str or not email:
            raise AuthenticationException("Invalid Supabase token claims: Missing user identity")

        user_id = uuid.UUID(user_id_str)
        user = await AuthService.get_user_by_id(db, user_id)

        if not user:
            # Check by email
            user = await AuthService.get_user_by_email(db, email)

        if not user:
            # Auto-provision
            user = User(
                id=user_id,
                email=email.lower().strip(),
                hashed_password="SUPABASE_AUTH_MANAGED",
                full_name=claims.get("raw_payload", {}).get("user_metadata", {}).get("full_name") or email.split("@")[0],
                role=role if role in ["ADMIN", "PACKAGING", "DELIVERY"] else "PACKAGING",
                is_active=True,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            logger.info(f"Synchronized new Supabase user '{user.email}' with ID '{user.id}'")

        return user
