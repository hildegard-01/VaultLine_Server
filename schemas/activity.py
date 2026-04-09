"""
활동 로그 스키마
"""

from datetime import datetime

from pydantic import BaseModel


class ActivityOut(BaseModel):
    id: int
    user_id: int | None
    username: str | None = None
    action: str
    detail: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ActivityListOut(BaseModel):
    items: list[ActivityOut]
    total: int
