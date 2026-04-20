"""
공통 테스트 픽스처 — 인메모리 SQLite, TestClient, 사용자 계정
"""

from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.database import Base, get_db
from db.models import User
from utils.security import hash_password, create_access_token
from main import app

SQLALCHEMY_TEST_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_TEST_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# lifespan을 no-op으로 교체 — 실제 DB 파일 생성 및 스케줄러 시작 방지
@asynccontextmanager
async def _noop_lifespan(application):
    yield

app.router.lifespan_context = _noop_lifespan


@pytest.fixture(autouse=True)
def setup_db():
    """각 테스트마다 테이블 생성 → 실행 → 삭제"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    """테스트용 DB 세션"""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    """DB 의존성을 테스트 세션으로 교체한 TestClient"""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


# ─── 사용자 픽스처 ───

@pytest.fixture()
def admin_user(db):
    user = User(
        username="admin",
        password_hash=hash_password("admin1234"),
        display_name="관리자",
        role="admin",
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def regular_user(db):
    user = User(
        username="testuser",
        password_hash=hash_password("testpass1"),
        display_name="테스트유저",
        role="user",
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def auth_headers(user: User) -> dict:
    """유저 → Bearer 헤더 딕셔너리 반환"""
    token = create_access_token(user.id, user.username, user.role)
    return {"Authorization": f"Bearer {token}"}
