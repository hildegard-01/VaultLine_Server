"""
VaultLine Server — 테스트용 시드 데이터 삽입
사용: python scripts/seed_data.py
      python scripts/seed_data.py --reset  (기존 테스트 데이터 삭제 후 재삽입)
"""

import sys
import secrets
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from db.database import SessionLocal, engine
from db import models
from utils.security import hash_password

TEST_USER_PREFIX = "test_"


def reset_test_data(db):
    """test_ 접두사 사용자 및 연관 데이터 삭제"""
    users = db.query(models.User).filter(models.User.username.like(f"{TEST_USER_PREFIX}%")).all()
    for u in users:
        print(f"  삭제: {u.username}")
        db.delete(u)

    # 테스트 그룹 삭제
    groups = db.query(models.Group).filter(models.Group.name.like("테스트_%")).all()
    for g in groups:
        print(f"  삭제 그룹: {g.name}")
        db.delete(g)

    db.commit()
    print("기존 테스트 데이터 삭제 완료\n")


def seed(db):
    # ─── 사용자 생성 ───
    print("[1/5] 사용자 생성...")
    users_data = [
        {"username": "user1",        "display_name": "사용자1", "email": "",                   "role": "user",  "password": "1234"},
        {"username": "user2",        "display_name": "사용자2", "email": "",                   "role": "user",  "password": "1234"},
        {"username": "test_alice",   "display_name": "Alice",   "email": "alice@test.local",   "role": "user"},
        {"username": "test_bob",     "display_name": "Bob",     "email": "bob@test.local",     "role": "user"},
        {"username": "test_carol",   "display_name": "Carol",   "email": "carol@test.local",   "role": "user"},
        {"username": "test_manager", "display_name": "매니저",  "email": "manager@test.local", "role": "admin"},
    ]

    users = {}
    for data in users_data:
        existing = db.query(models.User).filter(models.User.username == data["username"]).first()
        if existing:
            print(f"  이미 존재: {data['username']} — 스킵")
            users[data["username"]] = existing
            continue

        user = models.User(
            username=data["username"],
            password_hash=hash_password(data.get("password", "Test1234!")),
            display_name=data["display_name"],
            email=data["email"],
            role=data["role"],
            status="active",
        )
        db.add(user)
        db.flush()
        users[data["username"]] = user
        print(f"  생성: {data['username']} (비밀번호: Test1234!)")

    # ─── 그룹 생성 ───
    print("\n[2/5] 그룹 생성...")
    groups = {}
    for name, desc in [("테스트_개발팀", "개발팀 테스트 그룹"), ("테스트_디자인팀", "디자인팀 테스트 그룹")]:
        existing = db.query(models.Group).filter(models.Group.name == name).first()
        if existing:
            print(f"  이미 존재: {name} — 스킵")
            groups[name] = existing
            continue

        group = models.Group(name=name, description=desc)
        db.add(group)
        db.flush()
        groups[name] = group
        print(f"  생성: {name}")

    # 멤버 추가
    dev_group = groups.get("테스트_개발팀")
    if dev_group:
        for username, role in [("test_alice", "owner"), ("test_bob", "member"), ("test_manager", "admin")]:
            u = users.get(username)
            if u and not db.query(models.UserGroup).filter_by(user_id=u.id, group_id=dev_group.id).first():
                db.add(models.UserGroup(user_id=u.id, group_id=dev_group.id, role=role))

    design_group = groups.get("테스트_디자인팀")
    if design_group:
        for username, role in [("test_carol", "owner"), ("test_alice", "member")]:
            u = users.get(username)
            if u and not db.query(models.UserGroup).filter_by(user_id=u.id, group_id=design_group.id).first():
                db.add(models.UserGroup(user_id=u.id, group_id=design_group.id, role=role))

    # ─── 저장소 생성 ───
    print("\n[3/5] 저장소 생성...")
    repos = {}
    repo_defs = [
        {"name": "Alice의 문서함",   "owner": "test_alice",   "type": "personal"},
        {"name": "Bob의 작업공간",   "owner": "test_bob",     "type": "personal"},
        {"name": "개발팀 공유저장소", "owner": "test_manager", "type": "team",     "group": "테스트_개발팀"},
    ]
    for rd in repo_defs:
        owner = users.get(rd["owner"])
        if not owner:
            continue
        existing = db.query(models.RepoRegistry).filter_by(name=rd["name"], owner_user_id=owner.id).first()
        if existing:
            print(f"  이미 존재: {rd['name']} — 스킵")
            repos[rd["name"]] = existing
            continue

        group_id = None
        if rd.get("group"):
            g = groups.get(rd["group"])
            group_id = g.id if g else None

        repo = models.RepoRegistry(
            name=rd["name"],
            description=f"{rd['name']} 테스트 저장소",
            owner_user_id=owner.id,
            type=rd["type"],
            group_id=group_id,
            latest_revision=3,
            total_files=5,
            total_size_bytes=1024 * 1024 * 2,
            last_sync_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        db.add(repo)
        db.flush()
        repos[rd["name"]] = repo
        print(f"  생성: {rd['name']}")

    # 커밋 로그 샘플
    alice_repo = repos.get("Alice의 문서함")
    if alice_repo:
        for rev, msg in [(1, "초기 문서 업로드"), (2, "보고서 수정"), (3, "최종본 확정")]:
            if not db.query(models.CommitLog).filter_by(repo_id=alice_repo.id, revision=rev).first():
                db.add(models.CommitLog(
                    repo_id=alice_repo.id,
                    revision=rev,
                    author="test_alice",
                    message=msg,
                    committed_at=datetime.now(timezone.utc) - timedelta(days=3 - rev),
                    changed_files=json.dumps([{"action": "M", "path": f"doc{rev}.pdf", "size": 512000}]),
                ))

        # 파일 트리
        if not db.query(models.FileTree).filter_by(repo_id=alice_repo.id).first():
            for path, is_dir, size in [
                ("보고서", True, 0),
                ("보고서/2026년_1분기.pdf", False, 1024 * 500),
                ("보고서/2026년_2분기_초안.docx", False, 1024 * 300),
                ("회의록", True, 0),
                ("회의록/2026-04-15.txt", False, 1024 * 10),
            ]:
                db.add(models.FileTree(
                    repo_id=alice_repo.id,
                    file_path=path,
                    is_directory=is_dir,
                    file_size=size,
                    last_revision=3,
                    last_author="test_alice",
                    last_modified=datetime.now(timezone.utc) - timedelta(days=1),
                ))

    # ─── 공유 생성 ───
    print("\n[4/5] 공유 생성...")
    alice = users.get("test_alice")
    bob = users.get("test_bob")
    carol = users.get("test_carol")

    if alice_repo and alice and bob:
        existing_share = db.query(models.Share).filter_by(repo_id=alice_repo.id, created_by=alice.id).first()
        if not existing_share:
            share = models.Share(
                repo_id=alice_repo.id,
                file_path="보고서/2026년_1분기.pdf",
                share_token=secrets.token_urlsafe(32),
                created_by=alice.id,
                permission="view",
                is_active=True,
            )
            db.add(share)
            db.flush()

            # Bob에게 공유
            db.add(models.ShareRecipient(share_id=share.id, user_id=bob.id))
            # Bob 알림
            db.add(models.Notification(
                user_id=bob.id,
                kind="share",
                title="Alice님이 문서를 공유했습니다",
                message="보고서/2026년_1분기.pdf",
                link=f"/shares/{share.id}",
            ))
            print(f"  생성: Alice → Bob 공유 (보고서/2026년_1분기.pdf)")

    # Carol → Alice 공유
    if carol and alice:
        carol_repo = repos.get("Bob의 작업공간")  # 임시로 bob repo 사용
        if not carol_repo and bob:
            carol_repo = db.query(models.RepoRegistry).filter_by(owner_user_id=bob.id).first()

        if carol_repo:
            existing_carol_share = db.query(models.Share).filter_by(created_by=carol.id).first()
            if not existing_carol_share:
                share2 = models.Share(
                    repo_id=carol_repo.id,
                    file_path=None,
                    share_token=secrets.token_urlsafe(32),
                    created_by=carol.id,
                    permission="download",
                    is_active=True,
                )
                db.add(share2)
                db.flush()
                db.add(models.ShareRecipient(share_id=share2.id, user_id=alice.id))
                db.add(models.Notification(
                    user_id=alice.id,
                    kind="share",
                    title="Carol님이 저장소를 공유했습니다",
                    message="저장소 전체",
                    link=f"/shares/{share2.id}",
                ))
                print(f"  생성: Carol → Alice 공유 (저장소 전체)")

    # ─── 태그 ───
    print("\n[5/5] 태그 생성...")
    admin_user = db.query(models.User).filter_by(role="admin", username="admin").first()
    for tag_name, color in [("중요", "#e74c3c"), ("검토필요", "#f39c12"), ("완료", "#27ae60"), ("보관", "#95a5a6")]:
        if not db.query(models.Tag).filter_by(name=tag_name).first():
            db.add(models.Tag(
                name=tag_name,
                color=color,
                created_by=admin_user.id if admin_user else None,
            ))
            print(f"  생성: #{tag_name}")

    db.commit()


def main():
    reset = "--reset" in sys.argv

    models.Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        if reset:
            print("=== 기존 테스트 데이터 초기화 ===")
            reset_test_data(db)

        print("=== 테스트 데이터 삽입 ===")
        seed(db)
        print("\n완료!")
        print("\n테스트 계정")
        print("  user1        — 일반 사용자 (비밀번호: 1234)")
        print("  user2        — 일반 사용자 (비밀번호: 1234)")
        print("  test_alice   — 일반 사용자 (비밀번호: Test1234!)")
        print("  test_bob     — 일반 사용자 (비밀번호: Test1234!)")
        print("  test_carol   — 일반 사용자 (비밀번호: Test1234!)")
        print("  test_manager — 관리자     (비밀번호: Test1234!)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
