"""
사용자 요청/응답 스키마
"""

from datetime import datetime

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=8)
    display_name: str | None = None
    email: str | None = None
    role: str = "user"


class UserUpdate(BaseModel):
    display_name: str | None = None
    email: str | None = None
    role: str | None = None
    status: str | None = None


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str | None
    email: str | None
    role: str
    status: str
    is_online: bool
    last_seen: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserListOut(BaseModel):
    items: list[UserOut]
    total: int
