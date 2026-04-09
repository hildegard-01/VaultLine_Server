"""
DB 초기화 — 관리자 계정 생성
"""

from db.database import SessionLocal
from db.models import User
from utils.security import hash_password


def ensure_admin_exists():
    """관리자 계정이 없으면 기본 관리자 생성"""
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == "admin").first()
        if admin is None:
            admin = User(
                username="admin",
                password_hash=hash_password("admin1234"),
                display_name="관리자",
                role="admin",
                status="active",
            )
            db.add(admin)
            db.commit()
            print("[DB] 기본 관리자 계정 생성: admin / admin1234")
        else:
            print("[DB] 관리자 계정 확인 완료")
    finally:
        db.close()
