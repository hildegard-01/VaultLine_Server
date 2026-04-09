"""
관리자 API — 대시보드, 시스템 상태, 설정
"""

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession
from sqlalchemy import func

from db.database import get_db
from db.models import (
    User, RepoRegistry, CommitLog, ActivityLog, Approval,
    Share, Notification, PreviewCacheMeta, Session,
)
from api.deps import require_admin
from config import get_settings

router = APIRouter()

_start_time = time.time()


# ─── GET /admin/dashboard ───

@router.get("/dashboard")
def dashboard(admin: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    """관리자 대시보드 — 주요 지표"""
    total_users = db.query(User).count()
    online_users = db.query(User).filter(User.is_online == True).count()
    total_repos = db.query(RepoRegistry).filter(RepoRegistry.status == "active").count()
    total_commits = db.query(CommitLog).count()
    pending_approvals = db.query(Approval).filter(Approval.status == "pending").count()
    active_shares = db.query(Share).filter(Share.is_active == True).count()

    # 최근 24시간 활동
    day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_activity = db.query(ActivityLog).filter(ActivityLog.created_at >= day_ago).count()

    # 캐시 사용량
    cache_count = db.query(PreviewCacheMeta).count()
    cache_size = db.query(func.sum(PreviewCacheMeta.file_size)).scalar() or 0

    return {
        "users": {"total": total_users, "online": online_users},
        "repos": {"total": total_repos},
        "commits": {"total": total_commits},
        "approvals": {"pending": pending_approvals},
        "shares": {"active": active_shares},
        "activity": {"last_24h": recent_activity},
        "cache": {"count": cache_count, "size_bytes": cache_size},
    }


# ─── GET /admin/system ───

@router.get("/system")
def system_status(admin: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    """시스템 상태"""
    settings = get_settings()
    uptime_seconds = int(time.time() - _start_time)

    # DB 파일 크기 (SQLite만)
    db_size = 0
    db_url = settings.database.url
    if "sqlite" in db_url:
        db_path = db_url.replace("sqlite:///", "")
        if os.path.exists(db_path):
            db_size = os.path.getsize(db_path)

    # 캐시 디렉토리 크기
    cache_dir = Path(settings.storage.cache_dir) / "preview"
    cache_size = sum(f.stat().st_size for f in cache_dir.rglob("*") if f.is_file()) if cache_dir.exists() else 0

    sessions_count = db.query(Session).count()

    return {
        "uptime_seconds": uptime_seconds,
        "uptime_display": f"{uptime_seconds // 3600}시간 {(uptime_seconds % 3600) // 60}분",
        "db_size_bytes": db_size,
        "cache_size_bytes": cache_size,
        "active_sessions": sessions_count,
        "config": {
            "host": settings.server.host,
            "port": settings.server.port,
            "debug": settings.server.debug,
            "preview_max_size_mb": settings.storage.preview_max_size_mb,
            "preview_max_age_days": settings.storage.preview_max_age_days,
            "heartbeat_timeout_sec": settings.sync.heartbeat_timeout_seconds,
        },
    }


# ─── GET /admin/online-users ───

@router.get("/online-users")
def online_users(admin: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    """온라인 사용자 목록"""
    users = db.query(User).filter(User.is_online == True).all()
    return [{
        "id": u.id,
        "username": u.username,
        "display_name": u.display_name,
        "last_heartbeat": u.last_heartbeat,
    } for u in users]


# ─── POST /admin/users/{user_id}/force-logout ───

@router.post("/users/{user_id}/force-logout")
def force_logout(user_id: int, admin: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    """사용자 강제 로그아웃 — 모든 세션 삭제"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    deleted = db.query(Session).filter(Session.user_id == user_id).delete()
    user.is_online = False
    user.last_seen = datetime.now(timezone.utc)

    db.add(ActivityLog(user_id=admin.id, action="admin.force-logout", detail=f"{user.username} 강제 로그아웃"))
    db.commit()

    return {"message": f"{user.username}의 세션 {deleted}개가 삭제되었습니다."}
