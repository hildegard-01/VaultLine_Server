"""
알림 API
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DbSession

from db.database import get_db
from db.models import Notification, User
from schemas.notification import NotificationOut, UnreadCountOut
from api.deps import get_current_user

router = APIRouter()


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
    unread_only: bool = False,
    current_user: User = Depends(get_current_user), db: DbSession = Depends(get_db),
):
    """알림 목록"""
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread_only:
        query = query.filter(Notification.is_read == False)
    return query.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/unread-count", response_model=UnreadCountOut)
def unread_count(current_user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    """미읽음 알림 수"""
    count = db.query(Notification).filter(
        Notification.user_id == current_user.id, Notification.is_read == False,
    ).count()
    return UnreadCountOut(unread_count=count)


@router.put("/{notif_id}/read")
def mark_read(notif_id: int, current_user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    """읽음 처리"""
    notif = db.query(Notification).filter(Notification.id == notif_id, Notification.user_id == current_user.id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다.")
    notif.is_read = True
    db.commit()
    return {"message": "읽음 처리되었습니다."}


@router.put("/read-all")
def mark_all_read(current_user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    """전체 읽음 처리"""
    db.query(Notification).filter(
        Notification.user_id == current_user.id, Notification.is_read == False,
    ).update({"is_read": True})
    db.commit()
    return {"message": "전체 읽음 처리되었습니다."}


@router.delete("/{notif_id}")
def delete_notification(notif_id: int, current_user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    """알림 삭제"""
    notif = db.query(Notification).filter(Notification.id == notif_id, Notification.user_id == current_user.id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다.")
    db.delete(notif)
    db.commit()
    return {"message": "알림이 삭제되었습니다."}
