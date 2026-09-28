from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserResponse,
)
from app.schemas.common import ApiResponse
from app.services.auth_service import AuthService

router = APIRouter(tags=["Authentication"])


@router.post(
    "/login",
    response_model=ApiResponse[TokenResponse],
    summary="Staff Login",
    description="Authenticates staff credentials and issues JWT access and refresh tokens.",
)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TokenResponse]:
    user = await AuthService.authenticate_user(db, payload.email, payload.password)
    tokens = AuthService.generate_auth_tokens(user)
    return ApiResponse(
        data=tokens,
        message="Authentication successful",
    )


@router.post(
    "/refresh",
    response_model=ApiResponse[TokenResponse],
    summary="Refresh Session Token",
    description="Exchanges a valid refresh token for a new access token.",
)
async def refresh_token(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[TokenResponse]:
    tokens = await AuthService.refresh_user_token(db, payload.refresh_token)
    return ApiResponse(
        data=tokens,
        message="Token refreshed successfully",
    )


@router.get(
    "/me",
    response_model=ApiResponse[UserResponse],
    summary="Current User Profile",
    description="Retrieves profile information and role permissions of the currently authenticated staff user.",
)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
) -> ApiResponse[UserResponse]:
    return ApiResponse(
        data=UserResponse.model_validate(current_user),
        message="Profile retrieved successfully",
    )
