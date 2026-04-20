"""
동기화 API 테스트 — /sync
"""

from datetime import datetime, timezone

import pytest
from tests.conftest import auth_headers
from db.models import RepoRegistry


@pytest.fixture()
def repo(db, regular_user):
    r = RepoRegistry(name="동기화저장소", owner_user_id=regular_user.id, type="personal")
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def _commit_body(repo_id: int, revision: int = 1):
    return {
        "repo_id": repo_id,
        "revision": revision,
        "author": "testuser",
        "message": "테스트 커밋",
        "date": "2024-01-01T00:00:00Z",
        "changed_files": [{"action": "A", "path": "README.md", "size": 100}],
        "file_tree_snapshot": [
            {"path": "README.md", "is_directory": False, "size": 100, "rev": revision, "author": "testuser"},
            {"path": "src", "is_directory": True, "size": 0},
        ],
    }


class TestPushCommit:
    def test_push_commit_success(self, client, regular_user, repo):
        resp = client.post("/sync/commit", json=_commit_body(repo.id), headers=auth_headers(regular_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["received"] is True
        assert data["server_revision"] == 1

    def test_push_commit_not_owner(self, client, admin_user, repo):
        resp = client.post("/sync/commit", json=_commit_body(repo.id), headers=auth_headers(admin_user))
        assert resp.status_code == 403

    def test_push_commit_nonexistent_repo(self, client, regular_user):
        resp = client.post("/sync/commit", json=_commit_body(99999), headers=auth_headers(regular_user))
        assert resp.status_code == 404

    def test_push_commit_duplicate_revision(self, client, regular_user, repo):
        body = _commit_body(repo.id, revision=1)
        client.post("/sync/commit", json=body, headers=auth_headers(regular_user))
        resp = client.post("/sync/commit", json=body, headers=auth_headers(regular_user))
        assert resp.status_code == 200
        assert resp.json()["received"] is True


class TestSyncStatus:
    def test_get_status(self, client, regular_user, repo):
        resp = client.get(f"/sync/status/{repo.id}", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["repo_id"] == repo.id
        assert data["repo_name"] == "동기화저장소"

    def test_get_status_nonexistent(self, client, regular_user):
        resp = client.get("/sync/status/99999", headers=auth_headers(regular_user))
        assert resp.status_code == 404

    def test_get_status_unauthenticated(self, client, repo):
        resp = client.get(f"/sync/status/{repo.id}")
        assert resp.status_code == 403


class TestListCommits:
    def test_list_commits_empty(self, client, regular_user, repo):
        resp = client.get(f"/sync/commits?repo_id={repo.id}", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_commits_after_push(self, client, regular_user, repo):
        client.post("/sync/commit", json=_commit_body(repo.id, revision=1), headers=auth_headers(regular_user))
        client.post("/sync/commit", json=_commit_body(repo.id, revision=2), headers=auth_headers(regular_user))
        resp = client.get(f"/sync/commits?repo_id={repo.id}", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        commits = resp.json()
        assert len(commits) == 2
        assert commits[0]["revision"] > commits[1]["revision"]  # desc 정렬


class TestFileTree:
    def test_get_file_tree_empty(self, client, regular_user, repo):
        resp = client.get(f"/sync/file-tree/{repo.id}", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_file_tree_after_push(self, client, regular_user, repo):
        client.post("/sync/commit", json=_commit_body(repo.id), headers=auth_headers(regular_user))
        resp = client.get(f"/sync/file-tree/{repo.id}", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        entries = resp.json()
        assert len(entries) == 2
        paths = [e["path"] for e in entries]
        assert "README.md" in paths
        assert "src" in paths

    def test_get_file_tree_path_filter(self, client, regular_user, repo):
        body = _commit_body(repo.id)
        body["file_tree_snapshot"].append({"path": "src/main.py", "is_directory": False, "size": 200, "rev": 1, "author": "testuser"})
        client.post("/sync/commit", json=body, headers=auth_headers(regular_user))
        resp = client.get(f"/sync/file-tree/{repo.id}?path=src", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        paths = [e["path"] for e in resp.json()]
        assert "src/main.py" in paths
        assert "README.md" not in paths
