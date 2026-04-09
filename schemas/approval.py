"""
승인 워크플로우 스키마
"""
from datetime import datetime
from pydantic import BaseModel, Field


class ApprovalCreate(BaseModel):
    repo_id: int
    file_path: str
    revision: int
    message: str | None = None
    reviewer_user_ids: list[int] = []


class ApprovalAction(BaseModel):
    comment: str | None = None


class ReviewerOut(BaseModel):
    user_id: int
    username: str | None = None
    status: str
    comment: str | None
    reviewed_at: datetime | None


class ApprovalOut(BaseModel):
    id: int
    repo_id: int
    file_path: str
    revision: int
    requester_id: int
    requester_name: str | None = None
    message: str | None
    status: str
    reviewers: list[ReviewerOut] = []
    resolved_at: datetime | None
    created_at: datetime


class ApprovalListOut(BaseModel):
    items: list[ApprovalOut]
    total: int


class ApprovalRuleCreate(BaseModel):
    repo_id: int | None = None
    path_pattern: str = Field(..., min_length=1)
    required_reviewers: int = 1
    auto_assign_user_ids: list[int] = []


class ApprovalRuleOut(BaseModel):
    id: int
    repo_id: int | None
    path_pattern: str
    required_reviewers: int
    auto_assign_user_ids: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
