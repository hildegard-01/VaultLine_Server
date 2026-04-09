"""
보안 유틸 — JWT 생성/검증, bcrypt 비밀번호 해싱
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from passlib.context import CryptContext

from config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ─── 비밀번호 ───

def hash_password(password: str) -> str:
    """비밀번호 → bcrypt 해시"""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """비밀번호 검증"""
    return pwd_context.verify(plain, hashed)


# ─── JWT Access Token ───

def create_access_token(user_id: int, username: str, role: str) -> str:
    """Access Token 생성 (HS256)"""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.auth.access_token_expire_hours)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.auth.jwt_secret, algorithm=settings.auth.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    """Access Token 디코드 — 유효하면 payload, 아니면 None"""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.auth.jwt_secret, algorithms=[settings.auth.jwt_algorithm])
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


# ─── Refresh Token ───

def create_refresh_token() -> str:
    """랜덤 Refresh Token 문자열 생성 (URL-safe 64바이트)"""
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    """Refresh Token → SHA-256 해시 (DB 저장용)"""
    return hashlib.sha256(token.encode()).hexdigest()
