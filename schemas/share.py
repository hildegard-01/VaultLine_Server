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
    svnserve_url: str | None = None
    svn_username: str | None = None
    svn_password_plain: str | None = None


class ShareUpdate(BaseModel):
    permission: str | None = None
    is_active: bool | None = None
    expires_at: datetime | None = None
    max_downloads: int | None = None


class RecipientOut(BaseModel):
    user_id: int
    username: str | None = None
    status: str = "pending"
    accessed_at: datetime | None = None
    responded_at: datetime | None = None


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
    svnserve_url: str | None = None
    svn_username: str | None = None
    svn_password_plain: str | None = None


class ShareListOut(BaseModel):
    items: list[ShareOut]
    total: int


class ShareReceivedOut(BaseModel):
    """공유받은 항목 — 수신자 관점"""
    id: int
    repo_id: int
    file_path: str | None
    share_token: str
    created_by: int
    creator_name: str | None = None
    permission: str
    has_password: bool = False
    expires_at: datetime | None
    is_active: bool
    created_at: datetime
    my_status: str  # pending / accepted / rejected
    responded_at: datetime | None = None


class ShareReceivedListOut(BaseModel):
    items: list[ShareReceivedOut]
    total: int
