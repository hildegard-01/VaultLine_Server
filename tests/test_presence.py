"""
Presence API 테스트 — /presence
"""

from tests.conftest import auth_headers


class TestHeartbeat:
    def test_heartbeat_success(self, client, regular_user):
        resp = client.post("/presence/heartbeat", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        assert resp.json()["message"] == "ok"

    def test_heartbeat_sets_online(self, client, db, regular_user):
        client.post("/presence/heartbeat", headers=auth_headers(regular_user))
        db.refresh(regular_user)
        assert regular_user.is_online is True
        assert regular_user.last_heartbeat is not None

    def test_heartbeat_unauthenticated(self, client):
        resp = client.post("/presence/heartbeat")
        assert resp.status_code == 403


class TestGoOnline:
    def test_go_online(self, client, regular_user):
        resp = client.post("/presence/online", headers=auth_headers(regular_user))
        assert resp.status_code == 200

    def test_go_online_sets_flag(self, client, db, regular_user):
        client.post("/presence/online", headers=auth_headers(regular_user))
        db.refresh(regular_user)
        assert regular_user.is_online is True


class TestGoOffline:
    def test_go_offline(self, client, regular_user):
        client.post("/presence/online", headers=auth_headers(regular_user))
        resp = client.post("/presence/offline", headers=auth_headers(regular_user))
        assert resp.status_code == 200

    def test_go_offline_clears_flag(self, client, db, regular_user):
        client.post("/presence/online", headers=auth_headers(regular_user))
        client.post("/presence/offline", headers=auth_headers(regular_user))
        db.refresh(regular_user)
        assert regular_user.is_online is False
