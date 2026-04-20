"""
관리자 API 테스트 — /admin
"""

import pytest
from tests.conftest import auth_headers
from db.models import Session as DbSession
from utils.security import hash_refresh_token


class TestDashboard:
    def test_admin_dashboard(self, client, admin_user):
        resp = client.get("/admin/dashboard", headers=auth_headers(admin_user))
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data
        assert "repos" in data
        assert "commits" in data
        assert "approvals" in data
        assert "shares" in data
        assert "activity" in data
        assert "cache" in data

    def test_regular_user_forbidden(self, client, regular_user):
        resp = client.get("/admin/dashboard", headers=auth_headers(regular_user))
        assert resp.status_code == 403

    def test_unauthenticated_forbidden(self, client):
        resp = client.get("/admin/dashboard")
        assert resp.status_code == 403


class TestSystemStatus:
    def test_system_status(self, client, admin_user):
        resp = client.get("/admin/system", headers=auth_headers(admin_user))
        assert resp.status_code == 200
        data = resp.json()
        assert "uptime_seconds" in data
        assert "active_sessions" in data
        assert "config" in data
        assert data["uptime_seconds"] >= 0

    def test_regular_user_forbidden(self, client, regular_user):
        resp = client.get("/admin/system", headers=auth_headers(regular_user))
        assert resp.status_code == 403


class TestOnlineUsers:
    def test_online_users_empty(self, client, admin_user):
        resp = client.get("/admin/online-users", headers=auth_headers(admin_user))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_online_users_after_heartbeat(self, client, admin_user, regular_user):
        client.post("/presence/heartbeat", headers=auth_headers(regular_user))
        resp = client.get("/admin/online-users", headers=auth_headers(admin_user))
        assert resp.status_code == 200
        usernames = [u["username"] for u in resp.json()]
        assert "testuser" in usernames

    def test_regular_user_forbidden(self, client, regular_user):
        resp = client.get("/admin/online-users", headers=auth_headers(regular_user))
        assert resp.status_code == 403


class TestForceLogout:
    def test_force_logout(self, client, db, admin_user, regular_user):
        from datetime import datetime, timedelta, timezone
        token_raw = "sometokenvalue"
        session = DbSession(
            user_id=regular_user.id,
            refresh_token_hash=hash_refresh_token(token_raw),
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(session)
        db.commit()

        resp = client.post(f"/admin/users/{regular_user.id}/force-logout", headers=auth_headers(admin_user))
        assert resp.status_code == 200
        assert "1개가 삭제" in resp.json()["message"]

    def test_force_logout_nonexistent_user(self, client, admin_user):
        resp = client.post("/admin/users/99999/force-logout", headers=auth_headers(admin_user))
        assert resp.status_code == 404

    def test_regular_user_cannot_force_logout(self, client, regular_user, admin_user):
        resp = client.post(f"/admin/users/{admin_user.id}/force-logout", headers=auth_headers(regular_user))
        assert resp.status_code == 403
