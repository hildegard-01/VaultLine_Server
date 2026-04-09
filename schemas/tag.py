"""
태그 스키마
"""

from datetime import datetime

from pydantic import BaseModel, Field


class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    color: str | None = None


class TagUpdate(BaseModel):
    name: str | None = None
    color: str | None = None


class TagOut(BaseModel):
    id: int
    name: str
    color: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FileTagAttach(BaseModel):
    repo_id: int
    file_path: str
    tag_id: int


class FileTagOut(BaseModel):
    id: int
    repo_id: int
    file_path: str
    tag_id: int
    tag_name: str
    tag_color: str | None
    attached_at: datetime
