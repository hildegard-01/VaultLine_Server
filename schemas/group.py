"""
그룹 요청/응답 스키마
"""

from datetime import datetime

from pydantic import BaseModel, Field


class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class MemberOut(BaseModel):
    user_id: int
    username: str
    display_name: str | None
    role: str  # owner / admin / member
    joined_at: datetime


class GroupOut(BaseModel):
    id: int
    name: str
    description: str | None
    members: list[MemberOut] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class GroupListOut(BaseModel):
    items: list[GroupOut]
    total: int


class MemberAdd(BaseModel):
    user_id: int
    role: str = "member"  # owner / admin / member


class MemberUpdate(BaseModel):
    role: str  # owner / admin / member
