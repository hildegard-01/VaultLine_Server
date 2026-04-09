"""
공통 의존성 — DB 세션, 현재 사용자 인증
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session as DbSession

from db.database import get_db
from db.models import User
from utils.security import decode_access_token

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: DbSession = Depends(get_db),
) -> User:
    """Authorization 헤더에서 JWT 추출 → 사용자 반환"""
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 인증 토큰입니다.",
        )

    user_id = int(payload["sub"])
    user = db.query(User).filter(User.id == user_id, User.status == "active").first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자를 찾을 수 없거나 비활성 상태입니다.",
        )
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """관리자 권한 필수"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다.",
        )
    return current_user
