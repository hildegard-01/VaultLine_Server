"""
공유 링크 API 테스트 — /shares
"""

import pytest
from tests.conftest import auth_headers
from db.models import RepoRegistry, Share
from utils.security import hash_password


@pytest.fixture()
def repo(db, regular_user):
    r = RepoRegistry(name="공유저장소", owner_user_id=regular_user.id, type="personal")
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


@pytest.fixture()
def share(db, regular_user, repo):
    s = Share(
        repo_id=repo.id,
        file_path="docs/guide.md",
        share_token="testtoken123",
        created_by=regular_user.id,
        permission="view",
        is_active=True,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


class TestListShares:
    def test_list_shares(self, client, regular_user, share):
        resp = client.get("/shares", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(s["file_path"] == "docs/guide.md" for s in data["items"])

    def test_list_shares_unauthenticated(self, client):
        resp = client.get("/shares")
        assert resp.status_code == 403

    def test_list_shares_only_mine(self, client, admin_user, regular_user, share):
        resp = client.get("/shares", headers=auth_headers(admin_user))
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


class TestCreateShare:
    def test_create_share_basic(self, client, regular_user, repo):
        resp = client.post("/shares", json={
            "repo_id": repo.id,
            "file_path": "README.md",
            "permission": "view",
        }, headers=auth_headers(regular_user))
        assert resp.status_code == 201
        data = resp.json()
        assert data["file_path"] == "README.md"
        assert data["permission"] == "view"
        assert data["share_token"] != ""

    def test_create_share_with_recipient(self, client, db, regular_user, admin_user, repo):
        resp = client.post("/shares", json={
            "repo_id": repo.id,
            "permission": "view",
            "recipient_user_ids": [admin_user.id],
        }, headers=auth_headers(regular_user))
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["recipients"]) == 1
        assert data["recipients"][0]["user_id"] == admin_user.id


class TestGetShare:
    def test_get_share(self, client, regular_user, share):
        resp = client.get(f"/shares/{share.id}", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        assert resp.json()["id"] == share.id

    def test_get_nonexistent_share(self, client, regular_user):
        resp = client.get("/shares/99999", headers=auth_headers(regular_user))
        assert resp.status_code == 404


class TestUpdateShare:
    def test_update_share(self, client, regular_user, share):
        resp = client.put(f"/shares/{share.id}", json={"permission": "edit", "is_active": False},
                          headers=auth_headers(regular_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["permission"] == "edit"
        assert data["is_active"] is False

    def test_update_other_users_share(self, client, admin_user, share):
        resp = client.put(f"/shares/{share.id}", json={"is_active": False}, headers=auth_headers(admin_user))
        assert resp.status_code == 404


class TestDeleteShare:
    def test_delete_share(self, client, regular_user, share):
        resp = client.delete(f"/shares/{share.id}", headers=auth_headers(regular_user))
        assert resp.status_code == 200

    def test_delete_other_users_share(self, client, admin_user, share):
        resp = client.delete(f"/shares/{share.id}", headers=auth_headers(admin_user))
        assert resp.status_code == 404


class TestPublicShare:
    def test_public_share_access(self, client, share):
        resp = client.get(f"/shares/public/{share.share_token}")
        assert resp.status_code == 200
        assert resp.json()["file_path"] == "docs/guide.md"

    def test_public_share_wrong_token(self, client):
        resp = client.get("/shares/public/wrongtoken")
        assert resp.status_code == 404

    def test_public_share_inactive(self, client, db, share):
        share.is_active = False
        db.commit()
        resp = client.get(f"/shares/public/{share.share_token}")
        assert resp.status_code == 404

    def test_public_share_with_password(self, client, db, share):
        share.password_hash = hash_password("secret123")
        db.commit()
        resp = client.get(f"/shares/public/{share.share_token}?password=secret123")
        assert resp.status_code == 200

    def test_public_share_wrong_password(self, client, db, share):
        share.password_hash = hash_password("secret123")
        db.commit()
        resp = client.get(f"/shares/public/{share.share_token}?password=wrongpass")
        assert resp.status_code == 403
