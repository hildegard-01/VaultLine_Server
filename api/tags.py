"""
태그 API — 시스템 태그 CRUD + 파일 태그 부착/해제
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session as DbSession

from db.database import get_db
from db.models import Tag, FileTag, User, ActivityLog
from schemas.tag import TagCreate, TagUpdate, TagOut, FileTagAttach, FileTagOut
from api.deps import get_current_user, require_admin

router = APIRouter()


# ─── GET /tags ───

@router.get("", response_model=list[TagOut])
def list_tags(
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """시스템 태그 목록"""
    return db.query(Tag).order_by(Tag.name).all()


# ─── POST /tags ───

@router.post("", response_model=TagOut, status_code=status.HTTP_201_CREATED)
def create_tag(
    body: TagCreate,
    admin: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
):
    """태그 생성 (관리자)"""
    existing = db.query(Tag).filter(Tag.name == body.name).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 존재하는 태그명입니다.")

    tag = Tag(name=body.name, color=body.color, created_by=admin.id)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


# ─── PUT /tags/{tag_id} ───

@router.put("/{tag_id}", response_model=TagOut)
def update_tag(
    tag_id: int,
    body: TagUpdate,
    admin: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
):
    """태그 수정 (관리자)"""
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="태그를 찾을 수 없습니다.")

    if body.name is not None:
        dup = db.query(Tag).filter(Tag.name == body.name, Tag.id != tag_id).first()
        if dup:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 존재하는 태그명입니다.")
        tag.name = body.name
    if body.color is not None:
        tag.color = body.color

    db.commit()
    db.refresh(tag)
    return tag


# ─── GET /tags/file ───

@router.get("/file", response_model=list[FileTagOut])
def get_file_tags(
    repo_id: int,
    path: str,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """특정 파일의 태그 조회"""
    file_tags = db.query(FileTag).filter(
        FileTag.repo_id == repo_id,
        FileTag.file_path == path,
    ).all()

    result = []
    for ft in file_tags:
        tag = db.query(Tag).filter(Tag.id == ft.tag_id).first()
        if tag:
            result.append(FileTagOut(
                id=ft.id,
                repo_id=ft.repo_id,
                file_path=ft.file_path,
                tag_id=ft.tag_id,
                tag_name=tag.name,
                tag_color=tag.color,
                attached_at=ft.attached_at,
            ))
    return result


# ─── POST /tags/attach ───

@router.post("/attach", response_model=FileTagOut)
def attach_tag(
    body: FileTagAttach,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """파일에 태그 부착"""
    tag = db.query(Tag).filter(Tag.id == body.tag_id).first()
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="태그를 찾을 수 없습니다.")

    existing = db.query(FileTag).filter(
        FileTag.repo_id == body.repo_id,
        FileTag.file_path == body.file_path,
        FileTag.tag_id == body.tag_id,
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 부착된 태그입니다.")

    ft = FileTag(
        repo_id=body.repo_id,
        file_path=body.file_path,
        tag_id=body.tag_id,
        attached_by=current_user.id,
    )
    db.add(ft)
    db.add(ActivityLog(user_id=current_user.id, action="tag.attach", detail=f"{body.file_path} ← {tag.name}"))
    db.commit()
    db.refresh(ft)

    return FileTagOut(
        id=ft.id,
        repo_id=ft.repo_id,
        file_path=ft.file_path,
        tag_id=ft.tag_id,
        tag_name=tag.name,
        tag_color=tag.color,
        attached_at=ft.attached_at,
    )


# ─── DELETE /tags/detach ───

@router.delete("/detach")
def detach_tag(
    repo_id: int,
    file_path: str,
    tag_id: int,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """파일에서 태그 해제"""
    ft = db.query(FileTag).filter(
        FileTag.repo_id == repo_id,
        FileTag.file_path == file_path,
        FileTag.tag_id == tag_id,
    ).first()
    if ft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="부착된 태그를 찾을 수 없습니다.")

    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    tag_name = tag.name if tag else str(tag_id)

    db.delete(ft)
    db.add(ActivityLog(user_id=current_user.id, action="tag.detach", detail=f"{file_path} → {tag_name} 해제"))
    db.commit()

    return {"message": "태그가 해제되었습니다."}


# ─── DELETE /tags/{tag_id} — /detach 뒤에 등록해야 라우팅 충돌 방지 ───

@router.delete("/{tag_id}")
def delete_tag(
    tag_id: int,
    admin: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
):
    """태그 삭제 (관리자)"""
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="태그를 찾을 수 없습니다.")

    name = tag.name
    db.delete(tag)
    db.commit()
    return {"message": f"태그 '{name}'이(가) 삭제되었습니다."}


# ─── GET /tags/search ───

@router.get("/search", response_model=list[FileTagOut])
def search_by_tag(
    tag_id: int,
    repo_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """태그별 파일 검색"""
    query = db.query(FileTag).filter(FileTag.tag_id == tag_id)
    if repo_id:
        query = query.filter(FileTag.repo_id == repo_id)

    file_tags = query.all()
    tag = db.query(Tag).filter(Tag.id == tag_id).first()

    return [FileTagOut(
        id=ft.id,
        repo_id=ft.repo_id,
        file_path=ft.file_path,
        tag_id=ft.tag_id,
        tag_name=tag.name if tag else "",
        tag_color=tag.color if tag else None,
        attached_at=ft.attached_at,
    ) for ft in file_tags]
