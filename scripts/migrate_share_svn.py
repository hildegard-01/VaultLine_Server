"""
DB 마이그레이션 — shares 테이블에 SVN 연동 컬럼 추가
사용: python scripts/migrate_share_svn.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from db.database import engine
from sqlalchemy import text


def migrate():
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(shares)"))
        columns = {row[1] for row in result}

        added = []
        for col, definition in [
            ("svnserve_url",      "VARCHAR(200)"),
            ("svn_username",      "VARCHAR(100)"),
            ("svn_password_plain","VARCHAR(200)"),
        ]:
            if col not in columns:
                conn.execute(text(f"ALTER TABLE shares ADD COLUMN {col} {definition}"))
                added.append(col)

        conn.commit()

        if added:
            print(f"마이그레이션 완료: {', '.join(added)} 컬럼 추가")
        else:
            print("이미 최신 상태입니다.")


if __name__ == "__main__":
    migrate()
