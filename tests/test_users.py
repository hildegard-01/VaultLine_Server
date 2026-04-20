"""
사용자 CRUD API 테스트 — /users
"""

from tests.conftest import auth_headers


class TestListUsers:
    def test_list_users_authenticated(self, client, regular_user):
        resp = client.get("/users", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_list_users_unauthenticated(self, client):
        resp = client.get("/users")
        assert resp.status_code == 403

    def test_list_users_search(self, client, regular_user):
        resp = client.get("/users?search=testuser", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert any(u["username"] == "testuser" for u in items)

    def test_list_users_pagination(self, client, regular_user):
        resp = client.get("/users?skip=0&limit=1", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        assert len(resp.json()["items"]) <= 1


class TestGetUser:
    def test_get_self(self, client, regular_user):
        resp = client.get(f"/users/{regular_user.id}", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        assert resp.json()["username"] == "testuser"

    def test_get_nonexistent(self, client, regular_user):
        resp = client.get("/users/99999", headers=auth_headers(regular_user))
        assert resp.status_code == 404


class TestCreateUser:
    def test_admin_can_create_user(self, client, admin_user):
        resp = client.post("/users", json={
            "username": "newbie",
            "password": "newpass99",
            "display_name": "새유저",
            "role": "user",
        }, headers=auth_headers(admin_user))
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "newbie"
        assert data["role"] == "user"

    def test_regular_user_cannot_create(self, client, regular_user):
        resp = client.post("/users", json={
            "username": "newbie2",
            "password": "newpass99",
        }, headers=auth_headers(regular_user))
        assert resp.status_code == 403

    def test_duplicate_username_rejected(self, client, admin_user, regular_user):
        resp = client.post("/users", json={
            "username": "testuser",
            "password": "newpass99",
        }, headers=auth_headers(admin_user))
        assert resp.status_code == 409

    def test_short_password_rejected(self, client, admin_user):
        resp = client.post("/users", json={
            "username": "shortpwuser",
            "password": "abc",
        }, headers=auth_headers(admin_user))
        # Pydantic min_length=8 검증 → 422
        assert resp.status_code == 422


class TestUpdateUser:
    def test_user_updates_own_display_name(self, client, regular_user):
        resp = client.put(f"/users/{regular_user.id}", json={
            "display_name": "새이름",
        }, headers=auth_headers(regular_user))
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "새이름"

    def test_user_cannot_change_own_role(self, client, regular_user):
        resp = client.put(f"/users/{regular_user.id}", json={
            "role": "admin",
        }, headers=auth_headers(regular_user))
        assert resp.status_code == 403

    def test_admin_can_change_role(self, client, admin_user, regular_user):
        resp = client.put(f"/users/{regular_user.id}", json={
            "role": "admin",
        }, headers=auth_headers(admin_user))
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    def test_user_cannot_update_other(self, client, admin_user, regular_user):
        resp = client.put(f"/users/{admin_user.id}", json={
            "display_name": "해킹시도",
        }, headers=auth_headers(regular_user))
        assert resp.status_code == 403


class TestDeleteUser:
    def test_admin_can_delete_user(self, client, admin_user, regular_user):
        resp = client.delete(f"/users/{regular_user.id}", headers=auth_headers(admin_user))
        assert resp.status_code == 200

    def test_admin_cannot_delete_self(self, client, admin_user):
        resp = client.delete(f"/users/{admin_user.id}", headers=auth_headers(admin_user))
        assert resp.status_code == 400

    def test_regular_user_cannot_delete(self, client, regular_user, admin_user):
        resp = client.delete(f"/users/{admin_user.id}", headers=auth_headers(regular_user))
        assert resp.status_code == 403
