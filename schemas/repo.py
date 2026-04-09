"""
저장소 레지스트리 요청/응답 스키마
"""

from datetime import datetime

from pydantic import BaseModel, Field


class RepoCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    type: str = "personal"  # personal / team
    group_id: int | None = None


class RepoUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    type: str | None = None
    group_id: int | None = None
    status: str | None = None


class RepoOwnerOut(BaseModel):
    id: int
    username: str
    display_name: str | None
    is_online: bool

    model_config = {"from_attributes": True}


class RepoOut(BaseModel):
    id: int
    name: str
    description: str | None
    owner: RepoOwnerOut
    type: str
    group_id: int | None
    group_name: str | None = None
    latest_revision: int
    total_files: int
    total_size_bytes: int
    last_sync_at: datetime | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RepoListOut(BaseModel):
    items: list[RepoOut]
    total: int
