"""
공유 링크 API
"""
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session as DbSession

from db.database import get_db
from db.models import Share, ShareRecipient, User, Notification, ActivityLog
from schemas.share import (
    ShareCreate, ShareUpdate, ShareOut, ShareListOut, RecipientOut,
    ShareReceivedOut, ShareReceivedListOut,
)
from utils.security import hash_password, verify_password
from api.deps import get_current_user
from ws.manager import manager

router = APIRouter()


def _build_share_out(share: Share, db: DbSession) -> ShareOut:
    creator = db.query(User).filter(User.id == share.created_by).first()
    recipients = []
    for r in share.recipients:
        user = db.query(User).filter(User.id == r.user_id).first()
        recipients.append(RecipientOut(
            user_id=r.user_id,
            username=user.username if user else None,
            status=r.status,
            accessed_at=r.accessed_at,
            responded_at=r.responded_at,
        ))
    return ShareOut(
        id=share.id, repo_id=share.repo_id, file_path=share.file_path,
        share_token=share.share_token, created_by=share.created_by,
        creator_name=creator.display_name if creator else None,
        permission=share.permission,
        has_password=share.password_hash is not None,
        expires_at=share.expires_at, max_downloads=share.max_downloads,
        download_count=share.download_count, is_active=share.is_active,
        recipients=recipients, created_at=share.created_at,
        svnserve_url=share.svnserve_url,
        svn_username=share.svn_username,
        svn_password_plain=share.svn_password_plain,
    )


@router.get("", response_model=ShareListOut)
def list_shares(
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user), db: DbSession = Depends(get_db),
):
    """내 공유 목록"""
    query = db.query(Share).filter(Share.created_by == current_user.id)
    total = query.count()
    shares = query.order_by(Share.created_at.desc()).offset(skip).limit(limit).all()
    return ShareListOut(items=[_build_share_out(s, db) for s in shares], total=total)


@router.get("/received", response_model=ShareReceivedListOut)
def list_received_shares(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: str | None = None,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """나에게 공유된 목록 — 수락 대기 / 수락 / 거절 상태별 조회 가능"""
    query = db.query(ShareRecipient).filter(ShareRecipient.user_id == current_user.id)

    if status and status in ("pending", "accepted", "rejected"):
        query = query.filter(ShareRecipient.status == status)

    total = query.count()
    recipients = query.offset(skip).limit(limit).all()

    items = []
    for r in recipients:
        share = db.query(Share).filter(Share.id == r.share_id).first()
        if not share:
            continue
        creator = db.query(User).filter(User.id == share.created_by).first()
        items.append(ShareReceivedOut(
            id=share.id,
            repo_id=share.repo_id,
            file_path=share.file_path,
            share_token=share.share_token,
            created_by=share.created_by,
            creator_name=creator.display_name if creator else None,
            permission=share.permission,
            has_password=share.password_hash is not None,
            expires_at=share.expires_at,
            is_active=share.is_active,
            created_at=share.created_at,
            my_status=r.status,
            responded_at=r.responded_at,
        ))

    return ShareReceivedListOut(items=items, total=total)


@router.get("/{share_id}", response_model=ShareOut)
def get_share(share_id: int, current_user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    """공유 상세"""
    share = db.query(Share).filter(Share.id == share_id).first()
    if not share:
        raise HTTPException(status_code=404, detail="공유를 찾을 수 없습니다.")
    return _build_share_out(share, db)


@router.post("", response_model=ShareOut, status_code=201)
async def create_share(
    body: ShareCreate, current_user: User = Depends(get_current_user), db: DbSession = Depends(get_db),
):
    """공유 생성"""
    token = secrets.token_urlsafe(32)
    share = Share(
        repo_id=body.repo_id, file_path=body.file_path, share_token=token,
        created_by=current_user.id, permission=body.permission,
        password_hash=hash_password(body.password) if body.password else None,
        expires_at=body.expires_at, max_downloads=body.max_downloads,
        svnserve_url=body.svnserve_url,
        svn_username=body.svn_username,
        svn_password_plain=body.svn_password_plain,
    )
    db.add(share)
    db.flush()

    # 수신자 등록 + 알림
    for uid in body.recipient_user_ids:
        db.add(ShareRecipient(share_id=share.id, user_id=uid))
        notif = Notification(
            user_id=uid, kind="share",
            title=f"{current_user.display_name or current_user.username}님이 문서를 공유했습니다",
            message=body.file_path or "저장소 전체",
            link=f"/shares/{share.id}",
        )
        db.add(notif)
        # WebSocket 실시간 알림
        await manager.send_to_user(uid, {
            "type": "notification",
            "data": {"kind": "share", "message": notif.title, "link": notif.link},
        })

    db.add(ActivityLog(user_id=current_user.id, action="share.create", detail=f"공유 생성: {body.file_path or '저장소'}"))
    db.commit()
    db.refresh(share)
    return _build_share_out(share, db)


@router.get("/{share_id}/credentials")
def get_share_credentials(
    share_id: int,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """소유자 전용 — SVN 접속 정보 조회 (server_share_id 복구용)"""
    share = db.query(Share).filter(
        Share.id == share_id,
        Share.created_by == current_user.id,
    ).first()
    if not share:
        raise HTTPException(status_code=404, detail="공유를 찾을 수 없습니다.")
    return {
        "id": share.id,
        "svn_username": share.svn_username,
    }


@router.put("/{share_id}", response_model=ShareOut)
def update_share(
    share_id: int, body: ShareUpdate,
    current_user: User = Depends(get_current_user), db: DbSession = Depends(get_db),
):
    """공유 수정"""
    share = db.query(Share).filter(Share.id == share_id, Share.created_by == current_user.id).first()
    if not share:
        raise HTTPException(status_code=404, detail="공유를 찾을 수 없습니다.")
    if body.permission is not None:
        share.permission = body.permission
    if body.is_active is not None:
        share.is_active = body.is_active
    if body.expires_at is not None:
        share.expires_at = body.expires_at
    if body.max_downloads is not None:
        share.max_downloads = body.max_downloads
    db.commit()
    db.refresh(share)
    return _build_share_out(share, db)


@router.delete("/{share_id}/recipient", status_code=200)
async def leave_share(
    share_id: int,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """공유 해제 (수신자 측) — ShareRecipient 레코드 삭제 후 공유자에게 알림"""
    recipient = db.query(ShareRecipient).filter(
        ShareRecipient.share_id == share_id,
        ShareRecipient.user_id == current_user.id,
    ).first()
    if not recipient:
        raise HTTPException(status_code=404, detail="공유를 찾을 수 없습니다.")

    share = db.query(Share).filter(Share.id == share_id).first()
    db.delete(recipient)

    if share:
        notif = Notification(
            user_id=share.created_by,
            kind="share",
            title=f"{current_user.display_name or current_user.username}님이 공유를 해제했습니다",
            message=share.file_path or "저장소 전체",
            link=f"/shares/{share_id}",
        )
        db.add(notif)
        db.commit()
        await manager.send_to_user(share.created_by, {
            "type": "share_left",
            "data": {
                "share_id": share_id,
                "user_id": current_user.id,
                "username": current_user.display_name or current_user.username,
            },
        })
    else:
        db.commit()

    return {"message": "공유를 해제했습니다."}


@router.delete("/{share_id}")
async def delete_share(share_id: int, current_user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    """공유 삭제 — 수락된 수신자에게 WS 알림 + DB 알림 전송"""
    share = db.query(Share).filter(Share.id == share_id, Share.created_by == current_user.id).first()
    if not share:
        raise HTTPException(status_code=404, detail="공유를 찾을 수 없습니다.")
    # 삭제 전 수락된 수신자 목록 저장
    accepted_ids = [r.user_id for r in share.recipients if r.status == "accepted"]
    share_file = share.file_path or "저장소 전체"
    sharer_name = current_user.display_name or current_user.username
    db.delete(share)
    db.commit()
    # 수락된 수신자에게 공유 취소 알림 (WS + DB)
    for uid in accepted_ids:
        notif = Notification(
            user_id=uid, kind="share",
            title=f"{sharer_name}님이 공유를 취소했습니다",
            message=share_file,
            link=None,
        )
        db.add(notif)
        await manager.send_to_user(uid, {
            "type": "share_revoked",
            "data": {"share_id": share_id},
        })
    if accepted_ids:
        db.commit()
    return {"message": "공유가 삭제되었습니다."}


@router.post("/{share_id}/undo-accept")
async def undo_accept_share(
    share_id: int,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """수락 롤백 — SVN 연결 실패 시 pending으로 복원 (거절 알림 없음)"""
    recipient = db.query(ShareRecipient).filter(
        ShareRecipient.share_id == share_id,
        ShareRecipient.user_id == current_user.id,
    ).first()
    if not recipient:
        raise HTTPException(status_code=404, detail="공유를 찾을 수 없습니다.")
    if recipient.status not in ("accepted", "pending"):
        raise HTTPException(status_code=400, detail=f"'{recipient.status}' 상태는 되돌릴 수 없습니다.")
    recipient.status = "pending"
    recipient.responded_at = None
    db.commit()
    return {"status": "pending"}


@router.post("/{share_id}/accept")
async def accept_share(
    share_id: int,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """공유 수락"""
    recipient = db.query(ShareRecipient).filter(
        ShareRecipient.share_id == share_id,
        ShareRecipient.user_id == current_user.id,
    ).first()
    if not recipient:
        raise HTTPException(status_code=404, detail="공유를 찾을 수 없습니다.")
    if recipient.status != "pending":
        raise HTTPException(status_code=400, detail=f"이미 '{recipient.status}' 상태입니다.")

    recipient.status = "accepted"
    recipient.responded_at = datetime.now(timezone.utc)

    # 공유 생성자에게 알림
    share = db.query(Share).filter(Share.id == share_id).first()
    if share:
        notif = Notification(
            user_id=share.created_by,
            kind="share",
            title=f"{current_user.display_name or current_user.username}님이 공유를 수락했습니다",
            message=share.file_path or "저장소 전체",
            link=f"/shares/{share_id}",
        )
        db.add(notif)
        await manager.send_to_user(share.created_by, {
            "type": "notification",
            "data": {"kind": "share_accepted", "message": notif.title, "link": notif.link},
        })

    db.commit()
    creator = db.query(User).filter(User.id == share.created_by).first()
    return {
        "message": "공유를 수락했습니다.",
        "status": "accepted",
        "svnserve_url": share.svnserve_url,
        "svn_username": share.svn_username,
        "svn_password_plain": share.svn_password_plain,
        "permission": share.permission,
        "file_path": share.file_path,
        "repo_id": share.repo_id,
        "share_id": share.id,
        "creator_name": creator.display_name if creator else None,
    }


@router.post("/{share_id}/reject")
async def reject_share(
    share_id: int,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """공유 거절"""
    recipient = db.query(ShareRecipient).filter(
        ShareRecipient.share_id == share_id,
        ShareRecipient.user_id == current_user.id,
    ).first()
    if not recipient:
        raise HTTPException(status_code=404, detail="공유를 찾을 수 없습니다.")
    if recipient.status == "rejected":
        raise HTTPException(status_code=400, detail="이미 거절한 공유입니다.")

    recipient.status = "rejected"
    recipient.responded_at = datetime.now(timezone.utc)

    share = db.query(Share).filter(Share.id == share_id).first()
    if share:
        notif = Notification(
            user_id=share.created_by,
            kind="share",
            title=f"{current_user.display_name or current_user.username}님이 공유를 거절했습니다",
            message=share.file_path or "저장소 전체",
            link=f"/shares/{share_id}",
        )
        db.add(notif)
        await manager.send_to_user(share.created_by, {
            "type": "notification",
            "data": {"kind": "share_rejected", "message": notif.title, "link": notif.link},
        })

    db.commit()
    return {"message": "공유를 거절했습니다.", "status": "rejected"}


@router.get("/public/{share_token}", response_model=ShareOut)
def public_share(share_token: str, password: str | None = None, db: DbSession = Depends(get_db)):
    """공개 공유 접근 (인증 불필요)"""
    share = db.query(Share).filter(Share.share_token == share_token, Share.is_active == True).first()
    if not share:
        raise HTTPException(status_code=404, detail="공유를 찾을 수 없거나 비활성 상태입니다.")
    if share.expires_at and share.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="만료된 공유입니다.")
    if share.max_downloads and share.download_count >= share.max_downloads:
        raise HTTPException(status_code=410, detail="다운로드 횟수를 초과했습니다.")
    if share.password_hash:
        if not password or not verify_password(password, share.password_hash):
            raise HTTPException(status_code=403, detail="비밀번호가 올바르지 않습니다.")
    return _build_share_out(share, db)
