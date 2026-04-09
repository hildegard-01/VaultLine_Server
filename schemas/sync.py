"""
동기화 요청/응답 스키마
"""

from datetime import datetime

from pydantic import BaseModel


class ChangedFile(BaseModel):
    action: str  # A(추가) / M(수정) / D(삭제)
    path: str
    size: int = 0


class FileTreeEntry(BaseModel):
    path: str
    is_directory: bool = False
    size: int = 0
    rev: int | None = None
    author: str | None = None
    modified: datetime | None = None


class CommitPushRequest(BaseModel):
    """클라이언트 → 서버: 커밋 메타데이터 push"""
    repo_id: int
    revision: int
    author: str
    message: str | None = None
    date: datetime
    changed_files: list[ChangedFile] = []
    file_tree_snapshot: list[FileTreeEntry] = []


class CommitPushResponse(BaseModel):
    received: bool = True
    server_revision: int


class CommitLogOut(BaseModel):
    id: int
    repo_id: int
    revision: int
    author: str
    message: str | None
    committed_at: datetime
    changed_files: str | None  # JSON 문자열
    received_at: datetime

    model_config = {"from_attributes": True}


class FileTreeOut(BaseModel):
    path: str
    is_directory: bool
    size: int
    last_revision: int | None
    last_author: str | None
    last_modified: datetime | None


class SyncStatusOut(BaseModel):
    repo_id: int
    repo_name: str
    latest_revision: int
    total_files: int
    last_sync_at: datetime | None
    owner_online: bool
