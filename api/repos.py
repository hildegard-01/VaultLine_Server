"""
저장소 레지스트리 API — 메타데이터만 관리 (파일 저장 안 함)
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session as DbSession

from db.database import get_db
from db.models import RepoRegistry, User, Group, ActivityLog
from schemas.repo import RepoCreate, RepoUpdate, RepoOut, RepoListOut, RepoOwnerOut
from api.deps import get_current_user, require_admin

router = APIRouter()


def _build_repo_out(repo: RepoRegistry, db: DbSession) -> RepoOut:
    """RepoRegistry 모델 → RepoOut 변환"""
    owner = db.query(User).filter(User.id == repo.owner_user_id).first()
    group_name = None
    if repo.group_id:
        group = db.query(Group).filter(Group.id == repo.group_id).first()
        group_name = group.name if group else None

    return RepoOut(
        id=repo.id,
        name=repo.name,
        description=repo.description,
        owner=RepoOwnerOut(
            id=owner.id,
            username=owner.username,
            display_name=owner.display_name,
            is_online=owner.is_online,
        ) if owner else RepoOwnerOut(id=0, username="unknown", display_name=None, is_online=False),
        type=repo.type,
        group_id=repo.group_id,
        group_name=group_name,
        latest_revision=repo.latest_revision,
        total_files=repo.total_files,
        total_size_bytes=repo.total_size_bytes,
        last_sync_at=repo.last_sync_at,
        status=repo.status,
        created_at=repo.created_at,
    )


# ─── GET /repos ───

@router.get("", response_model=RepoListOut)
def list_repos(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    type: str | None = None,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """저장소 목록 조회 (소유자 온라인 상태 포함)"""
    query = db.query(RepoRegistry).filter(RepoRegistry.status == "active")

    if type and type in ("personal", "team"):
        query = query.filter(RepoRegistry.type == type)

    total = query.count()
    repos = query.order_by(RepoRegistry.created_at.desc()).offset(skip).limit(limit).all()
    items = [_build_repo_out(r, db) for r in repos]

    return RepoListOut(items=items, total=total)


# ─── GET /repos/{repo_id} ───

@router.get("/{repo_id}", response_model=RepoOut)
def get_repo(
    repo_id: int,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """저장소 상세 조회"""
    repo = db.query(RepoRegistry).filter(RepoRegistry.id == repo_id).first()
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="저장소를 찾을 수 없습니다.")
    return _build_repo_out(repo, db)


# ─── POST /repos ───

@router.post("", response_model=RepoOut, status_code=status.HTTP_201_CREATED)
def register_repo(
    body: RepoCreate,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """저장소 등록 — 클라이언트 앱이 로컬 저장소 생성 후 서버에 메타 등록"""
    # 팀 저장소는 그룹 필수
    if body.type == "team" and not body.group_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="팀 저장소는 그룹을 지정해야 합니다.")

    if body.group_id:
        group = db.query(Group).filter(Group.id == body.group_id).first()
        if group is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="그룹을 찾을 수 없습니다.")

    repo = RepoRegistry(
        name=body.name,
        description=body.description,
        owner_user_id=current_user.id,
        type=body.type if body.type in ("personal", "team") else "personal",
        group_id=body.group_id,
    )
    db.add(repo)
    db.flush()

    db.add(ActivityLog(user_id=current_user.id, action="repo.register", detail=f"저장소 등록: {body.name}"))
    db.commit()
    db.refresh(repo)

    return _build_repo_out(repo, db)


# ─── PUT /repos/{repo_id} ───

@router.put("/{repo_id}", response_model=RepoOut)
def update_repo(
    repo_id: int,
    body: RepoUpdate,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """저장소 메타 수정 — 소유자 또는 관리자"""
    repo = db.query(RepoRegistry).filter(RepoRegistry.id == repo_id).first()
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="저장소를 찾을 수 없습니다.")

    # 권한: 소유자 또는 관리자
    if repo.owner_user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="수정 권한이 없습니다.")

    if body.name is not None:
        repo.name = body.name
    if body.description is not None:
        repo.description = body.description
    if body.type is not None and body.type in ("personal", "team"):
        repo.type = body.type
    if body.group_id is not None:
        repo.group_id = body.group_id
    if body.status is not None and body.status in ("active", "archived") and current_user.role == "admin":
        repo.status = body.status

    db.commit()
    db.refresh(repo)
    return _build_repo_out(repo, db)


# ─── DELETE /repos/{repo_id} ───

@router.delete("/{repo_id}")
def unregister_repo(
    repo_id: int,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """저장소 등록 해제 — 소유자 또는 관리자"""
    repo = db.query(RepoRegistry).filter(RepoRegistry.id == repo_id).first()
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="저장소를 찾을 수 없습니다.")

    if repo.owner_user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="삭제 권한이 없습니다.")

    name = repo.name
    db.delete(repo)
    db.add(ActivityLog(user_id=current_user.id, action="repo.unregister", detail=f"저장소 해제: {name}"))
    db.commit()

    return {"message": f"저장소 '{name}'이(가) 등록 해제되었습니다."}
