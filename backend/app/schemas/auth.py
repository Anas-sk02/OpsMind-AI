import uuid
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field


StaffRole = Literal["ADMIN", "PACKAGING", "DELIVERY"]


class LoginRequest(BaseModel):
    """
    Staff login payload.
    """
    email: EmailStr = Field(..., description="Staff user email address", json_schema_extra={"example": "manager@opsmind.io"})
    password: str = Field(..., min_length=6, description="Staff user account password", json_schema_extra={"example": "SecurePassword123!"})


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=150)
    role: StaffRole = Field(default="PACKAGING")
    is_active: bool = Field(default=True)


class CreateStaffRequest(UserBase):
    """
    Admin payload to provision a new staff employee account.
    """
    password: str = Field(..., min_length=8, description="Initial staff account password")


class UpdateStaffRequest(BaseModel):
    """
    Admin payload to update staff details, role, or active status.
    """
    full_name: Optional[str] = Field(None, min_length=1, max_length=150)
    role: Optional[StaffRole] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8)


class UserResponse(BaseModel):
    """
    Public serialization schema for staff users.
    """
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    """
    JWT authentication response payload.
    """
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int = 3600
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    """
    Token refresh request payload.
    """
    refresh_token: str = Field(..., description="Valid signed JWT refresh token")
