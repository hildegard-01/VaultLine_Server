"""
인증 API — login, refresh, logout, password-change, verify-token
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session as DbSession

from db.database import get_db
from db.models import User, Session, LoginAttempt, ActivityLog
from schemas.auth import (
    LoginRequest, LoginResponse,
    RefreshRequest, RefreshResponse,
    LogoutRequest, PasswordChangeRequest, MessageResponse,
)
from utils.security import (
    verify_password, hash_password,
    create_access_token, decode_access_token,
    create_refresh_token, hash_refresh_token,
)
from api.deps import get_current_user
from config import get_settings

router = APIRouter()


def _get_client_ip(request: Request) -> str:
    """클라이언트 IP 추출"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_login_lockout(db: DbSession, username: str, ip: str) -> None:
    """로그인 시도 횟수 확인 → 잠금 여부"""
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.auth.login_lockout_minutes)

    recent_failures = db.query(LoginAttempt).filter(
        LoginAttempt.username == username,
        LoginAttempt.success == False,
        LoginAttempt.attempted_at >= cutoff,
    ).count()

    if recent_failures >= settings.auth.login_max_attempts:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"로그인 시도 횟수 초과. {settings.auth.login_lockout_minutes}분 후 다시 시도하세요.",
        )


def _record_login_attempt(db: DbSession, username: str, ip: str, success: bool) -> None:
    """로그인 시도 기록"""
    db.add(LoginAttempt(username=username, ip_address=ip, success=success))
    db.commit()


def _create_session(db: DbSession, user: User, ip: str, device: str | None = None) -> tuple[str, str]:
    """새 세션 생성 → (access_token, refresh_token) 반환"""
    settings = get_settings()

    access_token = create_access_token(user.id, user.username, user.role)
    refresh_token = create_refresh_token()
    refresh_hash = hash_refresh_token(refresh_token)

    session = Session(
        user_id=user.id,
        refresh_token_hash=refresh_hash,
        device_info=device,
        ip_address=ip,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.auth.refresh_token_expire_days),
    )
    db.add(session)

    # 온라인 상태 갱신
    user.is_online = True
    user.last_seen = datetime.now(timezone.utc)
    db.commit()

    return access_token, refresh_token


# ─── POST /auth/login ───

@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request, db: DbSession = Depends(get_db)):
    """로그인 — JWT 토큰 발급"""
    ip = _get_client_ip(request)

    # 잠금 확인
    _check_login_lockout(db, body.username, ip)

    # 사용자 조회
    user = db.query(User).filter(User.username == body.username).first()
    if user is None or not verify_password(body.password, user.password_hash):
        _record_login_attempt(db, body.username, ip, False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 올바르지 않습니다.",
        )

    # 계정 상태 확인
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성 계정입니다. 관리자에게 문의하세요.",
        )

    # 로그인 성공
    _record_login_attempt(db, body.username, ip, True)
    access_token, refresh_token = _create_session(db, user, ip)

    # 활동 로그
    db.add(ActivityLog(user_id=user.id, action="auth.login", ip_address=ip))
    db.commit()

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
    )


# ─── POST /auth/refresh ───

@router.post("/refresh", response_model=RefreshResponse)
def refresh_token(body: RefreshRequest, request: Request, db: DbSession = Depends(get_db)):
    """토큰 갱신 — Refresh Token으로 새 Access + Refresh 발급 (Rotation)"""
    ip = _get_client_ip(request)
    old_hash = hash_refresh_token(body.refresh_token)

    # DB에서 세션 조회
    session = db.query(Session).filter(Session.refresh_token_hash == old_hash).first()
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 세션입니다.")

    # 만료 확인
    if session.expires_at < datetime.now(timezone.utc):
        db.delete(session)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="세션이 만료되었습니다. 다시 로그인하세요.")

    # 사용자 확인
    user = db.query(User).filter(User.id == session.user_id, User.status == "active").first()
    if user is None:
        db.delete(session)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="사용자를 찾을 수 없습니다.")

    # 기존 세션 삭제 (Rotation — 재사용 공격 방지)
    db.delete(session)
    db.flush()

    # 새 토큰 발급
    access_token, new_refresh = _create_session(db, user, ip)

    return RefreshResponse(
        access_token=access_token,
        refresh_token=new_refresh,
    )


# ─── POST /auth/logout ───

@router.post("/logout", response_model=MessageResponse)
def logout(body: LogoutRequest, db: DbSession = Depends(get_db)):
    """로그아웃 — Refresh Token 무효화"""
    token_hash = hash_refresh_token(body.refresh_token)
    session = db.query(Session).filter(Session.refresh_token_hash == token_hash).first()
    if session:
        # 온라인 상태 갱신
        user = db.query(User).filter(User.id == session.user_id).first()
        if user:
            user.is_online = False
            user.last_seen = datetime.now(timezone.utc)
        db.delete(session)
        db.commit()

    return MessageResponse(message="로그아웃되었습니다.")


# ─── POST /auth/password-change ───

@router.post("/password-change", response_model=MessageResponse)
def change_password(
    body: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """비밀번호 변경"""
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="현재 비밀번호가 올바르지 않습니다.")

    settings = get_settings()
    if len(body.new_password) < settings.auth.password_min_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"비밀번호는 최소 {settings.auth.password_min_length}자 이상이어야 합니다.",
        )

    current_user.password_hash = hash_password(body.new_password)

    # 다른 세션 전부 무효화 (보안: 비밀번호 변경 시 기존 세션 정리)
    db.query(Session).filter(Session.user_id == current_user.id).delete()
    db.commit()

    return MessageResponse(message="비밀번호가 변경되었습니다. 다시 로그인하세요.")


# ─── GET /auth/verify-token ───

@router.get("/verify-token")
def verify_token(current_user: User = Depends(get_current_user)):
    """토큰 유효성 확인"""
    return {
        "valid": True,
        "user_id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
    }
