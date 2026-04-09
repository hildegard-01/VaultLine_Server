"""
파일 프록시 + 미리보기 캐시 API

역할:
- 미리보기 요청 시 캐시 HIT → 즉시 반환, MISS → 소유자 앱에 WebSocket 요청
- 미리보기 push 수신 (클라이언트가 커밋 후 eager push)
- 캐시 관리
"""

import os
import uuid
import base64
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session as DbSession

from db.database import get_db
from db.models import RepoRegistry, PreviewCacheMeta, User
from api.deps import get_current_user
from ws.manager import manager
from config import get_settings

router = APIRouter()


def _get_cache_dir() -> Path:
    """캐시 디렉토리 경로"""
    settings = get_settings()
    cache_dir = Path(settings.storage.cache_dir) / "preview"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


# ─── GET /proxy/preview/{repo_id} ───

@router.get("/preview/{repo_id}")
async def get_preview(
    repo_id: int,
    path: str,
    revision: int | None = None,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """
    미리보기 조회
    1. 캐시 HIT → 파일 반환
    2. 캐시 MISS + 소유자 온라인 → WebSocket file_request → 응답 캐시 후 반환
    3. 소유자 오프라인 → 에러
    """
    repo = db.query(RepoRegistry).filter(RepoRegistry.id == repo_id).first()
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="저장소를 찾을 수 없습니다.")

    target_rev = revision or repo.latest_revision

    # 1. 캐시 확인
    cache = db.query(PreviewCacheMeta).filter(
        PreviewCacheMeta.repo_id == repo_id,
        PreviewCacheMeta.file_path == path,
        PreviewCacheMeta.revision == target_rev,
    ).first()

    if cache and os.path.exists(cache.cache_file_path):
        cache.last_accessed = datetime.now(timezone.utc)
        db.commit()
        return FileResponse(cache.cache_file_path, media_type="application/pdf", filename=f"preview.pdf")

    # 2. 소유자에게 WebSocket 요청
    owner_id = repo.owner_user_id
    if not manager.is_user_connected(owner_id):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="파일 소유자가 오프라인입니다. 미리보기를 생성할 수 없습니다.",
        )

    req_id = f"preview_{uuid.uuid4().hex[:12]}"
    result = await manager.request_file(owner_id, req_id, repo_id, path, action="preview")

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="소유자 앱에서 응답을 받지 못했습니다. (타임아웃)",
        )

    # 3. 응답 캐시 저장
    data_b64 = result.get("data")
    if not data_b64:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="미리보기 데이터가 비어 있습니다.")

    cache_path = _save_preview_cache(db, repo_id, path, target_rev, data_b64)

    return FileResponse(cache_path, media_type="application/pdf", filename="preview.pdf")


# ─── POST /proxy/preview-push ───

@router.post("/preview-push")
def push_preview(
    repo_id: int,
    path: str,
    revision: int,
    data: str,  # base64 encoded PDF
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """
    미리보기 eager push — 클라이언트가 커밋 후 미리보기 PDF를 서버에 푸시
    """
    repo = db.query(RepoRegistry).filter(RepoRegistry.id == repo_id).first()
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="저장소를 찾을 수 없습니다.")

    if repo.owner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="소유자만 미리보기를 push할 수 있습니다.")

    cache_path = _save_preview_cache(db, repo_id, path, revision, data)

    return {"cached": True, "path": cache_path}


def _save_preview_cache(db: DbSession, repo_id: int, file_path: str, revision: int, data_b64: str) -> str:
    """Base64 PDF 데이터를 파일로 저장하고 DB에 메타 기록"""
    cache_dir = _get_cache_dir()
    file_name = f"{repo_id}_{file_path.replace('/', '_')}_{revision}.pdf"
    cache_file = str(cache_dir / file_name)

    # 파일 저장
    pdf_bytes = base64.b64decode(data_b64)
    with open(cache_file, "wb") as f:
        f.write(pdf_bytes)

    # DB 메타 upsert
    existing = db.query(PreviewCacheMeta).filter(
        PreviewCacheMeta.repo_id == repo_id,
        PreviewCacheMeta.file_path == file_path,
        PreviewCacheMeta.revision == revision,
    ).first()

    now = datetime.now(timezone.utc)
    if existing:
        existing.cache_file_path = cache_file
        existing.file_size = len(pdf_bytes)
        existing.last_accessed = now
    else:
        db.add(PreviewCacheMeta(
            repo_id=repo_id,
            file_path=file_path,
            revision=revision,
            cache_file_path=cache_file,
            file_size=len(pdf_bytes),
            last_accessed=now,
        ))

    db.commit()
    return cache_file
