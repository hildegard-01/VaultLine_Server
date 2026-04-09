"""
승인 워크플로우 API
"""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session as DbSession

from db.database import get_db
from db.models import Approval, ApprovalReviewer, ApprovalRule, User, Notification, ActivityLog
from schemas.approval import (
    ApprovalCreate, ApprovalAction, ApprovalOut, ApprovalListOut,
    ReviewerOut, ApprovalRuleCreate, ApprovalRuleOut,
)
from api.deps import get_current_user, require_admin
from ws.manager import manager

router = APIRouter()


def _build_approval_out(a: Approval, db: DbSession) -> ApprovalOut:
    requester = db.query(User).filter(User.id == a.requester_id).first()
    reviewers = []
    for r in a.reviewers:
        user = db.query(User).filter(User.id == r.user_id).first()
        reviewers.append(ReviewerOut(
            user_id=r.user_id,
            username=user.username if user else None,
            status=r.status, comment=r.comment, reviewed_at=r.reviewed_at,
        ))
    return ApprovalOut(
        id=a.id, repo_id=a.repo_id, file_path=a.file_path,
        revision=a.revision, requester_id=a.requester_id,
        requester_name=requester.display_name if requester else None,
        message=a.message, status=a.status,
        reviewers=reviewers, resolved_at=a.resolved_at, created_at=a.created_at,
    )


# ─── GET /approvals ───

@router.get("", response_model=ApprovalListOut)
def list_approvals(
    status_filter: str | None = None,
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user), db: DbSession = Depends(get_db),
):
    """승인 목록 — 내가 요청했거나 내가 검토자인 항목"""
    my_reviewer_ids = db.query(ApprovalReviewer.approval_id).filter(
        ApprovalReviewer.user_id == current_user.id
    ).subquery()

    query = db.query(Approval).filter(
        (Approval.requester_id == current_user.id) | (Approval.id.in_(my_reviewer_ids))
    )
    if status_filter and status_filter in ("pending", "approved", "rejected"):
        query = query.filter(Approval.status == status_filter)

    total = query.count()
    items = query.order_by(Approval.created_at.desc()).offset(skip).limit(limit).all()
    return ApprovalListOut(items=[_build_approval_out(a, db) for a in items], total=total)


# ─── GET /approvals/{id} ───

@router.get("/{approval_id}", response_model=ApprovalOut)
def get_approval(approval_id: int, current_user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    a = db.query(Approval).filter(Approval.id == approval_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="승인 요청을 찾을 수 없습니다.")
    return _build_approval_out(a, db)


# ─── POST /approvals ───

@router.post("", response_model=ApprovalOut, status_code=201)
async def create_approval(
    body: ApprovalCreate, current_user: User = Depends(get_current_user), db: DbSession = Depends(get_db),
):
    """승인 요청 생성"""
    approval = Approval(
        repo_id=body.repo_id, file_path=body.file_path,
        revision=body.revision, requester_id=current_user.id, message=body.message,
    )
    db.add(approval)
    db.flush()

    for uid in body.reviewer_user_ids:
        db.add(ApprovalReviewer(approval_id=approval.id, user_id=uid))
        notif = Notification(
            user_id=uid, kind="approval",
            title=f"{current_user.display_name or current_user.username}님이 승인을 요청했습니다",
            message=f"{body.file_path} (r.{body.revision})",
            link=f"/approvals/{approval.id}",
        )
        db.add(notif)
        await manager.send_to_user(uid, {
            "type": "notification",
            "data": {"kind": "approval", "message": notif.title, "link": notif.link},
        })

    db.add(ActivityLog(user_id=current_user.id, action="approval.create", detail=f"승인 요청: {body.file_path}"))
    db.commit()
    db.refresh(approval)
    return _build_approval_out(approval, db)


# ─── POST /approvals/{id}/approve ───

@router.post("/{approval_id}/approve", response_model=ApprovalOut)
async def approve(
    approval_id: int, body: ApprovalAction,
    current_user: User = Depends(get_current_user), db: DbSession = Depends(get_db),
):
    """승인"""
    reviewer = db.query(ApprovalReviewer).filter(
        ApprovalReviewer.approval_id == approval_id,
        ApprovalReviewer.user_id == current_user.id,
    ).first()
    if not reviewer:
        raise HTTPException(status_code=403, detail="이 승인의 검토자가 아닙니다.")
    if reviewer.status != "pending":
        raise HTTPException(status_code=400, detail="이미 처리된 검토입니다.")

    reviewer.status = "approved"
    reviewer.comment = body.comment
    reviewer.reviewed_at = datetime.now(timezone.utc)

    approval = db.query(Approval).filter(Approval.id == approval_id).first()
    # 전원 승인 시 전체 승인 처리
    all_reviewers = db.query(ApprovalReviewer).filter(ApprovalReviewer.approval_id == approval_id).all()
    if all(r.status == "approved" for r in all_reviewers):
        approval.status = "approved"
        approval.resolved_at = datetime.now(timezone.utc)

    # 요청자에게 알림
    notif = Notification(
        user_id=approval.requester_id, kind="approval",
        title=f"{current_user.display_name or current_user.username}님이 승인했습니다",
        link=f"/approvals/{approval_id}",
    )
    db.add(notif)
    await manager.send_to_user(approval.requester_id, {
        "type": "notification",
        "data": {"kind": "approval", "message": notif.title},
    })

    db.commit()
    db.refresh(approval)
    return _build_approval_out(approval, db)


# ─── POST /approvals/{id}/reject ───

@router.post("/{approval_id}/reject", response_model=ApprovalOut)
async def reject(
    approval_id: int, body: ApprovalAction,
    current_user: User = Depends(get_current_user), db: DbSession = Depends(get_db),
):
    """반려"""
    reviewer = db.query(ApprovalReviewer).filter(
        ApprovalReviewer.approval_id == approval_id,
        ApprovalReviewer.user_id == current_user.id,
    ).first()
    if not reviewer:
        raise HTTPException(status_code=403, detail="이 승인의 검토자가 아닙니다.")

    reviewer.status = "rejected"
    reviewer.comment = body.comment
    reviewer.reviewed_at = datetime.now(timezone.utc)

    approval = db.query(Approval).filter(Approval.id == approval_id).first()
    approval.status = "rejected"
    approval.resolved_at = datetime.now(timezone.utc)

    notif = Notification(
        user_id=approval.requester_id, kind="approval",
        title=f"{current_user.display_name or current_user.username}님이 반려했습니다",
        message=body.comment,
        link=f"/approvals/{approval_id}",
    )
    db.add(notif)
    await manager.send_to_user(approval.requester_id, {
        "type": "notification",
        "data": {"kind": "approval", "message": notif.title},
    })

    db.commit()
    db.refresh(approval)
    return _build_approval_out(approval, db)


# ─── 승인 규칙 (관리자) ───

@router.get("/rules", response_model=list[ApprovalRuleOut])
def list_rules(admin: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    return db.query(ApprovalRule).order_by(ApprovalRule.created_at.desc()).all()


@router.post("/rules", response_model=ApprovalRuleOut, status_code=201)
def create_rule(body: ApprovalRuleCreate, admin: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    rule = ApprovalRule(
        repo_id=body.repo_id, path_pattern=body.path_pattern,
        required_reviewers=body.required_reviewers,
        auto_assign_user_ids=json.dumps(body.auto_assign_user_ids) if body.auto_assign_user_ids else None,
        created_by=admin.id,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, admin: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    rule = db.query(ApprovalRule).filter(ApprovalRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="규칙을 찾을 수 없습니다.")
    db.delete(rule)
    db.commit()
    return {"message": "승인 규칙이 삭제되었습니다."}
