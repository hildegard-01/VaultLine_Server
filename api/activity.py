"""
활동 로그 API
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DbSession

from db.database import get_db
from db.models import ActivityLog, User
from schemas.activity import ActivityOut, ActivityListOut
from api.deps import get_current_user

router = APIRouter()


# ─── GET /activity ───

@router.get("", response_model=ActivityListOut)
def list_activity(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    action: str | None = None,
    user_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """팀 활동 로그 조회"""
    query = db.query(ActivityLog)

    if action:
        query = query.filter(ActivityLog.action.like(f"{action}%"))
    if user_id:
        query = query.filter(ActivityLog.user_id == user_id)

    total = query.count()
    logs = query.order_by(ActivityLog.created_at.desc()).offset(skip).limit(limit).all()

    items = []
    for log in logs:
        username = None
        if log.user_id:
            user = db.query(User).filter(User.id == log.user_id).first()
            username = user.username if user else None
        items.append(ActivityOut(
            id=log.id,
            user_id=log.user_id,
            username=username,
            action=log.action,
            detail=log.detail,
            created_at=log.created_at,
        ))

    return ActivityListOut(items=items, total=total)


# ─── GET /activity/mine ───

@router.get("/mine", response_model=ActivityListOut)
def my_activity(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """내 활동 로그"""
    query = db.query(ActivityLog).filter(ActivityLog.user_id == current_user.id)
    total = query.count()
    logs = query.order_by(ActivityLog.created_at.desc()).offset(skip).limit(limit).all()

    items = [ActivityOut(
        id=log.id,
        user_id=log.user_id,
        username=current_user.username,
        action=log.action,
        detail=log.detail,
        created_at=log.created_at,
    ) for log in logs]

    return ActivityListOut(items=items, total=total)
