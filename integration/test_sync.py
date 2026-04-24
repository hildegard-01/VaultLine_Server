from datetime import datetime, timezone
import requests
from integration.conftest import BASE_URL


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def test_push_commit(base_url, admin_headers, temp_repo):
    resp = requests.post(
        f"{base_url}/sync/commit",
        json={
            "repo_id": temp_repo["id"],
            "revision": 1,
            "author": "admin",
            "message": "첫 번째 커밋",
            "date": _now_iso(),
            "changed_files": [{"action": "A", "path": "README.md", "size": 100}],
            "file_tree_snapshot": [
                {"path": "README.md", "is_directory": False, "size": 100, "rev": 1, "author": "admin"},
            ],
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["received"] is True


def test_push_commit_forbidden(base_url, temp_user, temp_repo):
    resp = requests.post(
        f"{base_url}/sync/commit",
        json={"repo_id": temp_repo["id"], "revision": 99, "author": "x", "date": _now_iso(), "changed_files": []},
        headers=temp_user["headers"],
    )
    assert resp.status_code == 403


def test_get_sync_status(base_url, admin_headers, temp_repo):
    resp = requests.get(f"{base_url}/sync/status/{temp_repo['id']}", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["repo_id"] == temp_repo["id"]


def test_get_file_tree(base_url, admin_headers, temp_repo):
    requests.post(
        f"{base_url}/sync/commit",
        json={
            "repo_id": temp_repo["id"],
            "revision": 1,
            "author": "admin",
            "date": _now_iso(),
            "changed_files": [],
            "file_tree_snapshot": [
                {"path": "a", "is_directory": True, "size": 0},
                {"path": "a/b.txt", "is_directory": False, "size": 512, "rev": 1, "author": "admin"},
            ],
        },
        headers=admin_headers,
    )
    resp = requests.get(f"{base_url}/sync/file-tree/{temp_repo['id']}", headers=admin_headers)
    assert resp.status_code == 200
    paths = [e["path"] for e in resp.json()]
    assert "a" in paths
    assert "a/b.txt" in paths
