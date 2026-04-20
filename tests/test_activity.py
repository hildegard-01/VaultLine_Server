"""
활동 로그 API 테스트 — /activity
"""

import pytest
from tests.conftest import auth_headers
from db.models import ActivityLog


@pytest.fixture()
def activity_logs(db, regular_user, admin_user):
    logs = [
        ActivityLog(user_id=regular_user.id, action="sync.push", detail="r.1 push"),
        ActivityLog(user_id=regular_user.id, action="tag.attach", detail="README.md ← 중요"),
        ActivityLog(user_id=admin_user.id, action="admin.force-logout", detail="testuser 강제 로그아웃"),
    ]
    for log in logs:
        db.add(log)
    db.commit()
    return logs


class TestListActivity:
    def test_list_activity(self, client, regular_user, activity_logs):
        resp = client.get("/activity", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_filter_by_action(self, client, regular_user, activity_logs):
        resp = client.get("/activity?action=sync", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["action"] == "sync.push"

    def test_filter_by_user_id(self, client, regular_user, admin_user, activity_logs):
        resp = client.get(f"/activity?user_id={admin_user.id}", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["action"] == "admin.force-logout"

    def test_pagination(self, client, regular_user, activity_logs):
        resp = client.get("/activity?skip=0&limit=2", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 2

    def test_unauthenticated(self, client):
        resp = client.get("/activity")
        assert resp.status_code == 403

    def test_items_include_username(self, client, regular_user, activity_logs):
        resp = client.get(f"/activity?user_id={regular_user.id}", headers=auth_headers(regular_user))
        items = resp.json()["items"]
        assert all(item["username"] == "testuser" for item in items)


class TestMyActivity:
    def test_my_activity(self, client, regular_user, activity_logs):
        resp = client.get("/activity/mine", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert all(item["user_id"] == regular_user.id for item in data["items"])

    def test_my_activity_empty(self, client, regular_user):
        resp = client.get("/activity/mine", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_my_activity_unauthenticated(self, client):
        resp = client.get("/activity/mine")
        assert resp.status_code == 403
