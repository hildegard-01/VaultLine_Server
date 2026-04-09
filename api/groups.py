"""
그룹 CRUD API
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session as DbSession

from db.database import get_db
from db.models import Group, UserGroup, User, ActivityLog
from schemas.group import (
    GroupCreate, GroupUpdate, GroupOut, GroupListOut,
    MemberAdd, MemberUpdate, MemberOut,
)
from api.deps import get_current_user, require_admin

router = APIRouter()


def _build_group_out(group: Group, db: DbSession) -> GroupOut:
    """Group 모델 → GroupOut 변환 (멤버 포함)"""
    members = []
    for ug in group.members:
        user = db.query(User).filter(User.id == ug.user_id).first()
        if user:
            members.append(MemberOut(
                user_id=user.id,
                username=user.username,
                display_name=user.display_name,
                role=ug.role,
                joined_at=ug.joined_at,
            ))
    return GroupOut(
        id=group.id,
        name=group.name,
        description=group.description,
        members=members,
        created_at=group.created_at,
    )


# ─── GET /groups ───

@router.get("", response_model=GroupListOut)
def list_groups(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """그룹 목록 조회"""
    query = db.query(Group)
    total = query.count()
    groups = query.order_by(Group.name).offset(skip).limit(limit).all()
    items = [_build_group_out(g, db) for g in groups]
    return GroupListOut(items=items, total=total)


# ─── GET /groups/{group_id} ───

@router.get("/{group_id}", response_model=GroupOut)
def get_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """그룹 상세 조회"""
    group = db.query(Group).filter(Group.id == group_id).first()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="그룹을 찾을 수 없습니다.")
    return _build_group_out(group, db)


# ─── POST /groups ───

@router.post("", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
def create_group(
    body: GroupCreate,
    admin: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
):
    """그룹 생성 (관리자 전용)"""
    existing = db.query(Group).filter(Group.name == body.name).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 존재하는 그룹명입니다.")

    group = Group(name=body.name, description=body.description)
    db.add(group)
    db.flush()

    db.add(ActivityLog(user_id=admin.id, action="admin.group-create", detail=f"그룹 생성: {body.name}"))
    db.commit()
    db.refresh(group)

    return _build_group_out(group, db)


# ─── PUT /groups/{group_id} ───

@router.put("/{group_id}", response_model=GroupOut)
def update_group(
    group_id: int,
    body: GroupUpdate,
    admin: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
):
    """그룹 정보 수정 (관리자 전용)"""
    group = db.query(Group).filter(Group.id == group_id).first()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="그룹을 찾을 수 없습니다.")

    if body.name is not None:
        dup = db.query(Group).filter(Group.name == body.name, Group.id != group_id).first()
        if dup:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 존재하는 그룹명입니다.")
        group.name = body.name
    if body.description is not None:
        group.description = body.description

    db.commit()
    db.refresh(group)
    return _build_group_out(group, db)


# ─── DELETE /groups/{group_id} ───

@router.delete("/{group_id}")
def delete_group(
    group_id: int,
    admin: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
):
    """그룹 삭제 (관리자 전용)"""
    group = db.query(Group).filter(Group.id == group_id).first()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="그룹을 찾을 수 없습니다.")

    name = group.name
    db.delete(group)
    db.add(ActivityLog(user_id=admin.id, action="admin.group-delete", detail=f"그룹 삭제: {name}"))
    db.commit()

    return {"message": f"그룹 '{name}'이(가) 삭제되었습니다."}


# ─── POST /groups/{group_id}/members ───

@router.post("/{group_id}/members", response_model=GroupOut)
def add_member(
    group_id: int,
    body: MemberAdd,
    admin: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
):
    """그룹에 멤버 추가 (관리자 전용)"""
    group = db.query(Group).filter(Group.id == group_id).first()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="그룹을 찾을 수 없습니다.")

    user = db.query(User).filter(User.id == body.user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")

    existing = db.query(UserGroup).filter(
        UserGroup.group_id == group_id, UserGroup.user_id == body.user_id
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 그룹에 속한 사용자입니다.")

    role = body.role if body.role in ("owner", "admin", "member") else "member"
    ug = UserGroup(user_id=body.user_id, group_id=group_id, role=role)
    db.add(ug)
    db.commit()
    db.refresh(group)

    return _build_group_out(group, db)


# ─── PUT /groups/{group_id}/members/{user_id} ───

@router.put("/{group_id}/members/{user_id}", response_model=GroupOut)
def update_member_role(
    group_id: int,
    user_id: int,
    body: MemberUpdate,
    admin: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
):
    """멤버 역할 변경 (관리자 전용)"""
    ug = db.query(UserGroup).filter(
        UserGroup.group_id == group_id, UserGroup.user_id == user_id
    ).first()
    if ug is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="그룹 멤버를 찾을 수 없습니다.")

    if body.role in ("owner", "admin", "member"):
        ug.role = body.role

    db.commit()

    group = db.query(Group).filter(Group.id == group_id).first()
    return _build_group_out(group, db)


# ─── DELETE /groups/{group_id}/members/{user_id} ───

@router.delete("/{group_id}/members/{user_id}")
def remove_member(
    group_id: int,
    user_id: int,
    admin: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
):
    """멤버 제거 (관리자 전용)"""
    ug = db.query(UserGroup).filter(
        UserGroup.group_id == group_id, UserGroup.user_id == user_id
    ).first()
    if ug is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="그룹 멤버를 찾을 수 없습니다.")

    db.delete(ug)
    db.commit()

    return {"message": "멤버가 그룹에서 제거되었습니다."}
