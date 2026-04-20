"""
그룹 API 테스트 — /groups
"""

import pytest
from tests.conftest import auth_headers
from db.models import Group, UserGroup


@pytest.fixture()
def group(db, admin_user):
    g = Group(name="개발팀", description="개발자 그룹")
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


class TestListGroups:
    def test_list_groups(self, client, regular_user, group):
        resp = client.get("/groups", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(g["name"] == "개발팀" for g in data["items"])


class TestCreateGroup:
    def test_admin_creates_group(self, client, admin_user):
        resp = client.post("/groups", json={
            "name": "새팀",
            "description": "설명",
        }, headers=auth_headers(admin_user))
        assert resp.status_code == 201
        assert resp.json()["name"] == "새팀"

    def test_regular_user_cannot_create(self, client, regular_user):
        resp = client.post("/groups", json={"name": "해킹팀"}, headers=auth_headers(regular_user))
        assert resp.status_code == 403

    def test_duplicate_name_rejected(self, client, admin_user, group):
        resp = client.post("/groups", json={"name": "개발팀"}, headers=auth_headers(admin_user))
        assert resp.status_code == 409


class TestUpdateGroup:
    def test_admin_updates_group(self, client, admin_user, group):
        resp = client.put(f"/groups/{group.id}", json={
            "description": "수정된 설명",
        }, headers=auth_headers(admin_user))
        assert resp.status_code == 200
        assert resp.json()["description"] == "수정된 설명"

    def test_nonexistent_group(self, client, admin_user):
        resp = client.put("/groups/99999", json={"name": "없음"}, headers=auth_headers(admin_user))
        assert resp.status_code == 404


class TestDeleteGroup:
    def test_admin_deletes_group(self, client, admin_user, group):
        resp = client.delete(f"/groups/{group.id}", headers=auth_headers(admin_user))
        assert resp.status_code == 200

    def test_regular_user_cannot_delete(self, client, regular_user, group):
        resp = client.delete(f"/groups/{group.id}", headers=auth_headers(regular_user))
        assert resp.status_code == 403


class TestGroupMembers:
    def test_add_member(self, client, admin_user, regular_user, group):
        resp = client.post(f"/groups/{group.id}/members", json={
            "user_id": regular_user.id,
            "role": "member",
        }, headers=auth_headers(admin_user))
        assert resp.status_code == 200
        members = resp.json()["members"]
        assert any(m["user_id"] == regular_user.id for m in members)

    def test_add_member_nonexistent_user(self, client, admin_user, group):
        resp = client.post(f"/groups/{group.id}/members", json={
            "user_id": 99999,
        }, headers=auth_headers(admin_user))
        assert resp.status_code == 404

    def test_add_duplicate_member_rejected(self, client, admin_user, regular_user, group, db):
        ug = UserGroup(user_id=regular_user.id, group_id=group.id, role="member")
        db.add(ug)
        db.commit()

        resp = client.post(f"/groups/{group.id}/members", json={
            "user_id": regular_user.id,
        }, headers=auth_headers(admin_user))
        assert resp.status_code == 409

    def test_update_member_role(self, client, admin_user, regular_user, group, db):
        ug = UserGroup(user_id=regular_user.id, group_id=group.id, role="member")
        db.add(ug)
        db.commit()

        resp = client.put(f"/groups/{group.id}/members/{regular_user.id}", json={
            "role": "admin",
        }, headers=auth_headers(admin_user))
        assert resp.status_code == 200

    def test_remove_member(self, client, admin_user, regular_user, group, db):
        ug = UserGroup(user_id=regular_user.id, group_id=group.id, role="member")
        db.add(ug)
        db.commit()

        resp = client.delete(f"/groups/{group.id}/members/{regular_user.id}",
                             headers=auth_headers(admin_user))
        assert resp.status_code == 200
