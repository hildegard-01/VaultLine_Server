"""
Presence API — heartbeat, 온라인/오프라인 상태 관리
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from db.database import get_db
from db.models import User
from schemas.auth import MessageResponse
from api.deps import get_current_user

router = APIRouter()


# ─── POST /presence/heartbeat ───

@router.post("/heartbeat", response_model=MessageResponse)
def heartbeat(
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """60초 간격 heartbeat — 온라인 상태 유지"""
    now = datetime.now(timezone.utc)
    current_user.last_heartbeat = now
    current_user.is_online = True
    current_user.last_seen = now
    db.commit()
    return MessageResponse(message="ok")


# ─── POST /presence/online ───

@router.post("/online", response_model=MessageResponse)
def go_online(
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """앱 시작 시 온라인 알림"""
    now = datetime.now(timezone.utc)
    current_user.is_online = True
    current_user.last_heartbeat = now
    current_user.last_seen = now
    db.commit()
    return MessageResponse(message="온라인 상태로 전환되었습니다.")


# ─── POST /presence/offline ───

@router.post("/offline", response_model=MessageResponse)
def go_offline(
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """앱 종료 시 오프라인 알림"""
    current_user.is_online = False
    current_user.last_seen = datetime.now(timezone.utc)
    db.commit()
    return MessageResponse(message="오프라인 상태로 전환되었습니다.")
