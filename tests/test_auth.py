"""
인증 API 테스트 — /auth/login, /refresh, /logout, /password-change, /verify-token
"""

import pytest
from tests.conftest import auth_headers


class TestLogin:
    def test_login_success(self, client, regular_user):
        resp = client.post("/auth/login", json={
            "username": "testuser",
            "password": "testpass1",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["username"] == "testuser"
        assert data["role"] == "user"

    def test_login_wrong_password(self, client, regular_user):
        resp = client.post("/auth/login", json={
            "username": "testuser",
            "password": "wrongpass",
        })
        assert resp.status_code == 401

    def test_login_unknown_user(self, client):
        resp = client.post("/auth/login", json={
            "username": "nobody",
            "password": "whatever",
        })
        assert resp.status_code == 401

    def test_login_locked_account(self, client, db, regular_user):
        regular_user.status = "locked"
        db.commit()

        resp = client.post("/auth/login", json={
            "username": "testuser",
            "password": "testpass1",
        })
        assert resp.status_code == 403

    def test_login_brute_force_lockout(self, client, regular_user):
        for _ in range(5):
            client.post("/auth/login", json={"username": "testuser", "password": "bad"})

        resp = client.post("/auth/login", json={"username": "testuser", "password": "bad"})
        assert resp.status_code == 429


class TestRefreshToken:
    def _login(self, client, username="testuser", password="testpass1"):
        return client.post("/auth/login", json={"username": username, "password": password}).json()

    def test_refresh_success(self, client, regular_user):
        tokens = self._login(client)
        resp = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        # Rotation: 새 refresh token 발급
        assert data["refresh_token"] != tokens["refresh_token"]

    def test_refresh_invalid_token(self, client):
        resp = client.post("/auth/refresh", json={"refresh_token": "invalid-token-xyz"})
        assert resp.status_code == 401

    def test_refresh_reuse_rejected(self, client, regular_user):
        tokens = self._login(client)
        old_refresh = tokens["refresh_token"]

        client.post("/auth/refresh", json={"refresh_token": old_refresh})
        # 이미 사용된 토큰으로 재시도
        resp = client.post("/auth/refresh", json={"refresh_token": old_refresh})
        assert resp.status_code == 401


class TestLogout:
    def test_logout_success(self, client, regular_user):
        tokens = client.post("/auth/login", json={
            "username": "testuser", "password": "testpass1",
        }).json()

        resp = client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
        assert resp.status_code == 200
        assert "로그아웃" in resp.json()["message"]

    def test_logout_invalid_token_returns_ok(self, client):
        # 없는 토큰도 200 반환 (멱등성)
        resp = client.post("/auth/logout", json={"refresh_token": "nonexistent"})
        assert resp.status_code == 200


class TestVerifyToken:
    def test_verify_valid_token(self, client, regular_user):
        resp = client.get("/auth/verify-token", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["username"] == "testuser"

    def test_verify_no_token(self, client):
        resp = client.get("/auth/verify-token")
        assert resp.status_code == 403

    def test_verify_bad_token(self, client):
        resp = client.get("/auth/verify-token", headers={"Authorization": "Bearer bad.token.here"})
        assert resp.status_code == 401


class TestPasswordChange:
    def test_change_password_success(self, client, regular_user):
        resp = client.post(
            "/auth/password-change",
            json={"current_password": "testpass1", "new_password": "newpass99"},
            headers=auth_headers(regular_user),
        )
        assert resp.status_code == 200

        # 새 비밀번호로 로그인 가능
        login = client.post("/auth/login", json={"username": "testuser", "password": "newpass99"})
        assert login.status_code == 200

    def test_change_password_wrong_current(self, client, regular_user):
        resp = client.post(
            "/auth/password-change",
            json={"current_password": "wrongpass", "new_password": "newpass99"},
            headers=auth_headers(regular_user),
        )
        assert resp.status_code == 400

    def test_change_password_too_short(self, client, regular_user):
        resp = client.post(
            "/auth/password-change",
            json={"current_password": "testpass1", "new_password": "short"},
            headers=auth_headers(regular_user),
        )
        # Pydantic min_length=8 검증 → 422
        assert resp.status_code == 422
