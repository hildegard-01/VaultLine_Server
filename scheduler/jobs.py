"""
백그라운드 스케줄러 작업

- presence_check: 3분마다 — stale heartbeat 감지 → 오프라인 처리
- cache_cleanup: 매일 03:30 — 만료된 미리보기 캐시 삭제
- log_archive: 매일 03:00 — 오래된 활동 로그 정리
- session_cleanup: 매일 04:00 — 만료된 세션 삭제
"""

import os
from datetime import datetime, timedelta, timezone

from db.database import SessionLocal
from db.models import User, PreviewCacheMeta, ActivityLog, Session
from config import get_settings


def presence_check():
    """stale heartbeat 감지 → 오프라인 처리"""
    settings = get_settings()
    timeout = timedelta(seconds=settings.sync.heartbeat_timeout_seconds)
    cutoff = datetime.now(timezone.utc) - timeout

    db = SessionLocal()
    try:
        stale_users = db.query(User).filter(
            User.is_online == True,
            User.last_heartbeat < cutoff,
        ).all()

        for user in stale_users:
            user.is_online = False
            user.last_seen = user.last_heartbeat

        if stale_users:
            db.commit()
            print(f"[스케줄러] {len(stale_users)}명 오프라인 처리")
    finally:
        db.close()


def cache_cleanup():
    """만료된 미리보기 캐시 삭제"""
    settings = get_settings()
    max_age = timedelta(days=settings.storage.preview_max_age_days)
    cutoff = datetime.now(timezone.utc) - max_age

    db = SessionLocal()
    try:
        expired = db.query(PreviewCacheMeta).filter(
            PreviewCacheMeta.last_accessed < cutoff,
        ).all()

        deleted = 0
        for cache in expired:
            if os.path.exists(cache.cache_file_path):
                try:
                    os.remove(cache.cache_file_path)
                except OSError:
                    pass
            db.delete(cache)
            deleted += 1

        if deleted:
            db.commit()
            print(f"[스케줄러] 미리보기 캐시 {deleted}개 삭제")
    finally:
        db.close()


def log_archive():
    """오래된 활동 로그 정리 (hot 기간 초과 삭제)"""
    settings = get_settings()
    hot_months = settings.log_retention.hot_months
    cutoff = datetime.now(timezone.utc) - timedelta(days=hot_months * 30)

    db = SessionLocal()
    try:
        deleted = db.query(ActivityLog).filter(
            ActivityLog.created_at < cutoff,
        ).delete()

        if deleted:
            db.commit()
            print(f"[스케줄러] 활동 로그 {deleted}건 정리 ({hot_months}개월 초과)")
    finally:
        db.close()


def session_cleanup():
    """만료된 세션 삭제"""
    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        deleted = db.query(Session).filter(Session.expires_at < now).delete()
        if deleted:
            db.commit()
            print(f"[스케줄러] 만료 세션 {deleted}개 삭제")
    finally:
        db.close()
