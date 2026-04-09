"""
SQLAlchemy 엔진/세션 설정
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from config import get_settings

settings = get_settings()

# SQLite: check_same_thread=False (FastAPI 비동기 환경)
connect_args = {}
if settings.database.url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database.url,
    connect_args=connect_args,
    echo=settings.server.debug,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI 의존성 주입용 DB 세션 생성기"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
