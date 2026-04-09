"""
사용자 CRUD API
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session as DbSession

from db.database import get_db
from db.models import User, Session, ActivityLog
from schemas.user import UserCreate, UserUpdate, UserOut, UserListOut
from utils.security import hash_password
from api.deps import get_current_user, require_admin
from config import get_settings

router = APIRouter()


# ─── GET /users ───

@router.get("", response_model=UserListOut)
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: str | None = None,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """사용자 목록 조회 (페이지네이션, 검색)"""
    query = db.query(User)

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            (User.username.ilike(pattern)) |
            (User.display_name.ilike(pattern)) |
            (User.email.ilike(pattern))
        )

    total = query.count()
    items = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()

    return UserListOut(items=items, total=total)


# ─── GET /users/{user_id} ───

@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """사용자 상세 조회"""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")
    return user


# ─── POST /users ───

@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    admin: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
):
    """사용자 생성 (관리자 전용)"""
    # 중복 검사
    existing = db.query(User).filter(User.username == body.username).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 존재하는 사용자명입니다.")

    settings = get_settings()
    if len(body.password) < settings.auth.password_min_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"비밀번호는 최소 {settings.auth.password_min_length}자 이상이어야 합니다.",
        )

    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        display_name=body.display_name or body.username,
        email=body.email,
        role=body.role if body.role in ("admin", "user") else "user",
    )
    db.add(user)
    db.flush()

    # 활동 로그
    db.add(ActivityLog(user_id=admin.id, action="admin.user-create", detail=f"사용자 생성: {body.username}"))
    db.commit()
    db.refresh(user)

    return user


# ─── PUT /users/{user_id} ───

@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    body: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """사용자 정보 수정 — 본인 또는 관리자"""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")

    # 권한 확인: 본인이거나 관리자
    if current_user.id != user_id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="수정 권한이 없습니다.")

    # role/status 변경은 관리자만
    if body.role is not None and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="역할 변경은 관리자만 가능합니다.")
    if body.status is not None and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="상태 변경은 관리자만 가능합니다.")

    if body.display_name is not None:
        user.display_name = body.display_name
    if body.email is not None:
        user.email = body.email
    if body.role is not None and body.role in ("admin", "user"):
        user.role = body.role
    if body.status is not None and body.status in ("active", "locked", "inactive"):
        user.status = body.status

    db.commit()
    db.refresh(user)
    return user


# ─── DELETE /users/{user_id} ───

@router.delete("/{user_id}", response_model=dict)
def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
):
    """사용자 삭제 (관리자 전용)"""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")

    # 자기 자신 삭제 방지
    if user.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="자기 자신은 삭제할 수 없습니다.")

    username = user.username

    # 세션 정리
    db.query(Session).filter(Session.user_id == user_id).delete()
    db.delete(user)

    db.add(ActivityLog(user_id=admin.id, action="admin.user-delete", detail=f"사용자 삭제: {username}"))
    db.commit()

    return {"message": f"사용자 '{username}'이(가) 삭제되었습니다."}


# ─── POST /users/{user_id}/password-reset ───

@router.post("/{user_id}/password-reset", response_model=dict)
def admin_password_reset(
    user_id: int,
    admin: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
):
    """관리자 비밀번호 초기화 — 임시 비밀번호 발급"""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자를 찾을 수 없습니다.")

    import secrets
    temp_password = secrets.token_urlsafe(10)
    user.password_hash = hash_password(temp_password)

    # 기존 세션 전부 무효화
    db.query(Session).filter(Session.user_id == user_id).delete()

    db.add(ActivityLog(user_id=admin.id, action="admin.password-reset", detail=f"{user.username} 비밀번호 초기화"))
    db.commit()

    return {"message": f"임시 비밀번호가 발급되었습니다.", "temp_password": temp_password}
