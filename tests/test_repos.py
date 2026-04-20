"""
저장소 레지스트리 API 테스트 — /repos
"""

import pytest
from tests.conftest import auth_headers
from db.models import RepoRegistry, Group


@pytest.fixture()
def repo(db, regular_user):
    r = RepoRegistry(
        name="내저장소",
        owner_user_id=regular_user.id,
        type="personal",
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


@pytest.fixture()
def group(db):
    g = Group(name="팀A", description="테스트 팀")
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


class TestListRepos:
    def test_list_repos(self, client, regular_user, repo):
        resp = client.get("/repos", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(r["name"] == "내저장소" for r in data["items"])

    def test_filter_by_type(self, client, regular_user, repo):
        resp = client.get("/repos?type=personal", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(r["type"] == "personal" for r in items)

    def test_unauthenticated_rejected(self, client):
        resp = client.get("/repos")
        assert resp.status_code == 403


class TestGetRepo:
    def test_get_repo(self, client, regular_user, repo):
        resp = client.get(f"/repos/{repo.id}", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        assert resp.json()["name"] == "내저장소"

    def test_get_nonexistent(self, client, regular_user):
        resp = client.get("/repos/99999", headers=auth_headers(regular_user))
        assert resp.status_code == 404


class TestRegisterRepo:
    def test_register_personal_repo(self, client, regular_user):
        resp = client.post("/repos", json={
            "name": "새저장소",
            "type": "personal",
        }, headers=auth_headers(regular_user))
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "새저장소"
        assert data["owner"]["username"] == "testuser"

    def test_register_team_repo_requires_group(self, client, regular_user):
        resp = client.post("/repos", json={
            "name": "팀저장소",
            "type": "team",
        }, headers=auth_headers(regular_user))
        assert resp.status_code == 400

    def test_register_team_repo_with_group(self, client, regular_user, group):
        resp = client.post("/repos", json={
            "name": "팀저장소",
            "type": "team",
            "group_id": group.id,
        }, headers=auth_headers(regular_user))
        assert resp.status_code == 201
        assert resp.json()["group_id"] == group.id

    def test_register_invalid_group(self, client, regular_user):
        resp = client.post("/repos", json={
            "name": "팀저장소",
            "type": "team",
            "group_id": 99999,
        }, headers=auth_headers(regular_user))
        assert resp.status_code == 404


class TestUpdateRepo:
    def test_owner_can_update(self, client, regular_user, repo):
        resp = client.put(f"/repos/{repo.id}", json={
            "name": "수정된저장소",
        }, headers=auth_headers(regular_user))
        assert resp.status_code == 200
        assert resp.json()["name"] == "수정된저장소"

    def test_other_user_cannot_update(self, client, admin_user, regular_user, repo):
        other = admin_user  # admin은 다른 사용자지만 admin 권한 있음 → 200
        resp = client.put(f"/repos/{repo.id}", json={"name": "변경"}, headers=auth_headers(other))
        assert resp.status_code == 200  # admin은 허용

    def test_nonexistent_repo(self, client, regular_user):
        resp = client.put("/repos/99999", json={"name": "없음"}, headers=auth_headers(regular_user))
        assert resp.status_code == 404


class TestUnregisterRepo:
    def test_owner_can_delete(self, client, regular_user, repo):
        resp = client.delete(f"/repos/{repo.id}", headers=auth_headers(regular_user))
        assert resp.status_code == 200

    def test_other_user_cannot_delete(self, client, db, regular_user):
        from db.models import User
        from utils.security import hash_password
        other = User(username="other", password_hash=hash_password("otherpass1"), role="user", status="active")
        db.add(other)
        db.commit()
        db.refresh(other)

        r = RepoRegistry(name="남의저장소", owner_user_id=regular_user.id, type="personal")
        db.add(r)
        db.commit()
        db.refresh(r)

        resp = client.delete(f"/repos/{r.id}", headers=auth_headers(other))
        assert resp.status_code == 403
