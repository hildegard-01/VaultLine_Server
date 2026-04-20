"""
승인 워크플로우 API 테스트 — /approvals
"""

import pytest
from tests.conftest import auth_headers
from db.models import RepoRegistry, Approval, ApprovalReviewer, User
from utils.security import hash_password


@pytest.fixture()
def repo(db, regular_user):
    r = RepoRegistry(name="승인저장소", owner_user_id=regular_user.id, type="personal")
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


@pytest.fixture()
def reviewer_user(db):
    u = User(
        username="reviewer",
        password_hash=hash_password("reviewpass1"),
        display_name="검토자",
        role="user",
        status="active",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture()
def approval_with_reviewer(db, regular_user, reviewer_user, repo):
    a = Approval(
        repo_id=repo.id,
        file_path="src/main.py",
        revision=1,
        requester_id=regular_user.id,
        message="검토 부탁드립니다",
    )
    db.add(a)
    db.flush()
    db.add(ApprovalReviewer(approval_id=a.id, user_id=reviewer_user.id))
    db.commit()
    db.refresh(a)
    return a


class TestListApprovals:
    def test_list_approvals_empty(self, client, regular_user):
        resp = client.get("/approvals", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    def test_list_approvals_as_requester(self, client, regular_user, approval_with_reviewer):
        resp = client.get("/approvals", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_list_approvals_as_reviewer(self, client, reviewer_user, approval_with_reviewer):
        resp = client.get("/approvals", headers=auth_headers(reviewer_user))
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_filter_by_status(self, client, regular_user, approval_with_reviewer):
        resp = client.get("/approvals?status_filter=pending", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

        resp = client.get("/approvals?status_filter=approved", headers=auth_headers(regular_user))
        assert resp.json()["total"] == 0


class TestGetApproval:
    def test_get_approval(self, client, regular_user, approval_with_reviewer):
        resp = client.get(f"/approvals/{approval_with_reviewer.id}", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["file_path"] == "src/main.py"
        assert data["status"] == "pending"

    def test_get_nonexistent(self, client, regular_user):
        resp = client.get("/approvals/99999", headers=auth_headers(regular_user))
        assert resp.status_code == 404


class TestCreateApproval:
    def test_create_approval(self, client, regular_user, repo):
        resp = client.post("/approvals", json={
            "repo_id": repo.id,
            "file_path": "README.md",
            "revision": 1,
            "message": "리뷰 요청",
            "reviewer_user_ids": [],
        }, headers=auth_headers(regular_user))
        assert resp.status_code == 201
        data = resp.json()
        assert data["file_path"] == "README.md"
        assert data["status"] == "pending"

    def test_create_approval_with_reviewer(self, client, regular_user, reviewer_user, repo):
        resp = client.post("/approvals", json={
            "repo_id": repo.id,
            "file_path": "main.py",
            "revision": 2,
            "reviewer_user_ids": [reviewer_user.id],
        }, headers=auth_headers(regular_user))
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["reviewers"]) == 1
        assert data["reviewers"][0]["user_id"] == reviewer_user.id
        assert data["reviewers"][0]["status"] == "pending"


class TestApprove:
    def test_approve(self, client, reviewer_user, approval_with_reviewer):
        resp = client.post(
            f"/approvals/{approval_with_reviewer.id}/approve",
            json={"comment": "LGTM"},
            headers=auth_headers(reviewer_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["reviewers"][0]["status"] == "approved"

    def test_approve_not_reviewer(self, client, admin_user, approval_with_reviewer):
        resp = client.post(
            f"/approvals/{approval_with_reviewer.id}/approve",
            json={},
            headers=auth_headers(admin_user),
        )
        assert resp.status_code == 403

    def test_approve_twice_rejected(self, client, reviewer_user, approval_with_reviewer):
        client.post(f"/approvals/{approval_with_reviewer.id}/approve", json={}, headers=auth_headers(reviewer_user))
        resp = client.post(f"/approvals/{approval_with_reviewer.id}/approve", json={}, headers=auth_headers(reviewer_user))
        assert resp.status_code == 400


class TestReject:
    def test_reject(self, client, reviewer_user, approval_with_reviewer):
        resp = client.post(
            f"/approvals/{approval_with_reviewer.id}/reject",
            json={"comment": "수정 필요"},
            headers=auth_headers(reviewer_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"

    def test_reject_not_reviewer(self, client, admin_user, approval_with_reviewer):
        resp = client.post(
            f"/approvals/{approval_with_reviewer.id}/reject",
            json={},
            headers=auth_headers(admin_user),
        )
        assert resp.status_code == 403


class TestApprovalRules:
    def test_create_rule(self, client, admin_user, repo):
        resp = client.post("/approvals/rules", json={
            "repo_id": repo.id,
            "path_pattern": "*.py",
            "required_reviewers": 2,
            "auto_assign_user_ids": [],
        }, headers=auth_headers(admin_user))
        assert resp.status_code == 201
        data = resp.json()
        assert data["path_pattern"] == "*.py"
        assert data["required_reviewers"] == 2

    def test_list_rules(self, client, admin_user, repo):
        client.post("/approvals/rules", json={
            "repo_id": repo.id, "path_pattern": "src/**", "required_reviewers": 1,
        }, headers=auth_headers(admin_user))
        resp = client.get("/approvals/rules", headers=auth_headers(admin_user))
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_delete_rule(self, client, admin_user, repo):
        create_resp = client.post("/approvals/rules", json={
            "repo_id": repo.id, "path_pattern": "docs/**", "required_reviewers": 1,
        }, headers=auth_headers(admin_user))
        rule_id = create_resp.json()["id"]
        resp = client.delete(f"/approvals/rules/{rule_id}", headers=auth_headers(admin_user))
        assert resp.status_code == 200

    def test_regular_user_cannot_create_rule(self, client, regular_user, repo):
        resp = client.post("/approvals/rules", json={
            "repo_id": repo.id, "path_pattern": "*.md", "required_reviewers": 1,
        }, headers=auth_headers(regular_user))
        assert resp.status_code == 403
