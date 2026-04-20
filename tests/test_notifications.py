"""
알림 API 테스트 — /notifications
"""

import pytest
from tests.conftest import auth_headers
from db.models import Notification


@pytest.fixture()
def notif(db, regular_user):
    n = Notification(
        user_id=regular_user.id,
        kind="share",
        title="문서가 공유되었습니다",
        message="report.pdf",
        link="/shares/1",
        is_read=False,
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    return n


@pytest.fixture()
def read_notif(db, regular_user):
    n = Notification(
        user_id=regular_user.id,
        kind="approval",
        title="승인되었습니다",
        is_read=True,
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    return n


class TestListNotifications:
    def test_list_notifications(self, client, regular_user, notif):
        resp = client.get("/notifications", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_unread_only(self, client, regular_user, notif, read_notif):
        resp = client.get("/notifications?unread_only=true", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        items = resp.json()
        assert all(n["is_read"] is False for n in items)

    def test_list_only_mine(self, client, admin_user, notif):
        resp = client.get("/notifications", headers=auth_headers(admin_user))
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_unauthenticated(self, client):
        resp = client.get("/notifications")
        assert resp.status_code == 403


class TestUnreadCount:
    def test_unread_count(self, client, regular_user, notif, read_notif):
        resp = client.get("/notifications/unread-count", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        assert resp.json()["unread_count"] == 1

    def test_unread_count_zero(self, client, regular_user):
        resp = client.get("/notifications/unread-count", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        assert resp.json()["unread_count"] == 0


class TestMarkRead:
    def test_mark_read(self, client, db, regular_user, notif):
        resp = client.put(f"/notifications/{notif.id}/read", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        db.refresh(notif)
        assert notif.is_read is True

    def test_mark_read_nonexistent(self, client, regular_user):
        resp = client.put("/notifications/99999/read", headers=auth_headers(regular_user))
        assert resp.status_code == 404

    def test_mark_read_other_users_notif(self, client, admin_user, notif):
        resp = client.put(f"/notifications/{notif.id}/read", headers=auth_headers(admin_user))
        assert resp.status_code == 404


class TestMarkAllRead:
    def test_mark_all_read(self, client, db, regular_user, notif, read_notif):
        resp = client.put("/notifications/read-all", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        db.refresh(notif)
        assert notif.is_read is True


class TestDeleteNotification:
    def test_delete_notification(self, client, regular_user, notif):
        resp = client.delete(f"/notifications/{notif.id}", headers=auth_headers(regular_user))
        assert resp.status_code == 200

    def test_delete_nonexistent(self, client, regular_user):
        resp = client.delete("/notifications/99999", headers=auth_headers(regular_user))
        assert resp.status_code == 404

    def test_delete_other_users_notif(self, client, admin_user, notif):
        resp = client.delete(f"/notifications/{notif.id}", headers=auth_headers(admin_user))
        assert resp.status_code == 404
