"""
알림 스키마
"""
from datetime import datetime
from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: int
    kind: str
    title: str
    message: str | None
    link: str | None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UnreadCountOut(BaseModel):
    unread_count: int
