"""
DB 마이그레이션 — share_recipients 테이블에 status, responded_at 컬럼 추가
사용: python scripts/migrate_share_status.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from db.database import engine
from sqlalchemy import text


def migrate():
    with engine.connect() as conn:
        # 컬럼이 이미 있는지 확인
        result = conn.execute(text("PRAGMA table_info(share_recipients)"))
        columns = {row[1] for row in result}

        added = []
        if "status" not in columns:
            conn.execute(text("ALTER TABLE share_recipients ADD COLUMN status VARCHAR(20) DEFAULT 'pending'"))
            added.append("status")

        if "responded_at" not in columns:
            conn.execute(text("ALTER TABLE share_recipients ADD COLUMN responded_at DATETIME"))
            added.append("responded_at")

        conn.commit()

        if added:
            print(f"마이그레이션 완료: {', '.join(added)} 컬럼 추가")
        else:
            print("이미 최신 상태입니다.")


if __name__ == "__main__":
    migrate()
