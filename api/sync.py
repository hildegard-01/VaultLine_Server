"""
동기화 API — 커밋 메타 수신, 파일 트리 조회, 커밋 로그 조회
"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session as DbSession

from db.database import get_db
from db.models import RepoRegistry, CommitLog, FileTree, User, ActivityLog
from schemas.sync import (
    CommitPushRequest, CommitPushResponse,
    CommitLogOut, FileTreeOut, SyncStatusOut,
)
from api.deps import get_current_user

router = APIRouter()


# ─── POST /sync/commit ───

@router.post("/commit", response_model=CommitPushResponse)
def push_commit(
    body: CommitPushRequest,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """커밋 메타데이터 수신 — 클라이언트 앱이 로컬 커밋 후 호출"""
    repo = db.query(RepoRegistry).filter(RepoRegistry.id == body.repo_id).first()
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="등록된 저장소를 찾을 수 없습니다.")

    # 소유자 확인
    if repo.owner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="저장소 소유자만 커밋을 push할 수 있습니다.")

    # 중복 리비전 확인
    existing = db.query(CommitLog).filter(
        CommitLog.repo_id == body.repo_id,
        CommitLog.revision == body.revision,
    ).first()
    if existing:
        return CommitPushResponse(received=True, server_revision=repo.latest_revision)

    # 커밋 로그 저장
    changed_json = json.dumps(
        [{"action": f.action, "path": f.path, "size": f.size} for f in body.changed_files],
        ensure_ascii=False,
    ) if body.changed_files else None

    commit = CommitLog(
        repo_id=body.repo_id,
        revision=body.revision,
        author=body.author,
        message=body.message,
        committed_at=body.date,
        changed_files=changed_json,
    )
    db.add(commit)

    # 파일 트리 스냅샷 갱신 (전체 교체)
    if body.file_tree_snapshot:
        db.query(FileTree).filter(FileTree.repo_id == body.repo_id).delete()
        for entry in body.file_tree_snapshot:
            ft = FileTree(
                repo_id=body.repo_id,
                file_path=entry.path,
                is_directory=entry.is_directory,
                file_size=entry.size,
                last_revision=entry.rev,
                last_author=entry.author,
                last_modified=entry.modified,
            )
            db.add(ft)

    # 저장소 메타 갱신
    repo.latest_revision = max(repo.latest_revision, body.revision)
    repo.last_sync_at = datetime.now(timezone.utc)
    if body.file_tree_snapshot:
        repo.total_files = len([e for e in body.file_tree_snapshot if not e.is_directory])
        repo.total_size_bytes = sum(e.size for e in body.file_tree_snapshot)

    # 활동 로그
    db.add(ActivityLog(
        user_id=current_user.id,
        action="sync.push",
        detail=f"r.{body.revision} push ({len(body.changed_files)}개 파일 변경)",
    ))

    db.commit()

    return CommitPushResponse(received=True, server_revision=repo.latest_revision)


# ─── GET /sync/status/{repo_id} ───

@router.get("/status/{repo_id}", response_model=SyncStatusOut)
def get_sync_status(
    repo_id: int,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """저장소 동기화 상태 조회"""
    repo = db.query(RepoRegistry).filter(RepoRegistry.id == repo_id).first()
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="저장소를 찾을 수 없습니다.")

    owner = db.query(User).filter(User.id == repo.owner_user_id).first()

    return SyncStatusOut(
        repo_id=repo.id,
        repo_name=repo.name,
        latest_revision=repo.latest_revision,
        total_files=repo.total_files,
        last_sync_at=repo.last_sync_at,
        owner_online=owner.is_online if owner else False,
    )


# ─── GET /sync/commits ───

@router.get("/commits", response_model=list[CommitLogOut])
def list_commits(
    repo_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """커밋 로그 조회 (페이지네이션)"""
    commits = db.query(CommitLog).filter(
        CommitLog.repo_id == repo_id,
    ).order_by(CommitLog.revision.desc()).offset(skip).limit(limit).all()

    return commits


# ─── GET /sync/file-tree/{repo_id} ───

@router.get("/file-tree/{repo_id}", response_model=list[FileTreeOut])
def get_file_tree(
    repo_id: int,
    path: str | None = None,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """파일 트리 조회 — 특정 경로 하위 또는 전체"""
    query = db.query(FileTree).filter(FileTree.repo_id == repo_id)

    if path:
        # 해당 경로의 직접 하위만 반환
        prefix = f"{path}/" if not path.endswith("/") else path
        query = query.filter(FileTree.file_path.like(f"{prefix}%"))

    entries = query.order_by(FileTree.is_directory.desc(), FileTree.file_path).all()

    return [FileTreeOut(
        path=e.file_path,
        is_directory=e.is_directory,
        size=e.file_size,
        last_revision=e.last_revision,
        last_author=e.last_author,
        last_modified=e.last_modified,
    ) for e in entries]
