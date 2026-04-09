"""
공유 스키마
"""
from datetime import datetime
from pydantic import BaseModel, Field


class ShareCreate(BaseModel):
    repo_id: int
    file_path: str | None = None
    permission: str = "view"
    password: str | None = None
    expires_at: datetime | None = None
    max_downloads: int | None = None
    recipient_user_ids: list[int] = []


class ShareUpdate(BaseModel):
    permission: str | None = None
    is_active: bool | None = None
    expires_at: datetime | None = None
    max_downloads: int | None = None


class RecipientOut(BaseModel):
    user_id: int
    username: str | None = None
    accessed_at: datetime | None = None


class ShareOut(BaseModel):
    id: int
    repo_id: int
    file_path: str | None
    share_token: str
    created_by: int
    creator_name: str | None = None
    permission: str
    has_password: bool = False
    expires_at: datetime | None
    max_downloads: int | None
    download_count: int
    is_active: bool
    recipients: list[RecipientOut] = []
    created_at: datetime


class ShareListOut(BaseModel):
    items: list[ShareOut]
    total: int
