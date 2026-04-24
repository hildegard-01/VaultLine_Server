import uuid
import requests
from integration.conftest import BASE_URL


def test_list_repos(admin_headers):
    resp = requests.get(f"{BASE_URL}/repos", headers=admin_headers)
    assert resp.status_code == 200
    assert "items" in resp.json()


def test_create_team_repo_without_group_fails(base_url, admin_headers):
    resp = requests.post(
        f"{base_url}/repos",
        json={"name": f"team_{uuid.uuid4().hex[:6]}", "type": "team"},
        headers=admin_headers,
    )
    assert resp.status_code == 400


def test_create_and_delete_repo(base_url, admin_headers):
    name = f"repo_{uuid.uuid4().hex[:8]}"
    resp = requests.post(
        f"{base_url}/repos",
        json={"name": name, "type": "personal"},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    repo_id = resp.json()["id"]

    del_resp = requests.delete(f"{base_url}/repos/{repo_id}", headers=admin_headers)
    assert del_resp.status_code == 200

    get_resp = requests.get(f"{base_url}/repos/{repo_id}", headers=admin_headers)
    assert get_resp.status_code == 404


def test_update_repo(base_url, admin_headers, temp_repo):
    resp = requests.put(
        f"{base_url}/repos/{temp_repo['id']}",
        json={"description": "수정됨"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "수정됨"


def test_update_repo_forbidden(base_url, temp_user, temp_repo):
    resp = requests.put(
        f"{base_url}/repos/{temp_repo['id']}",
        json={"description": "권한 없음"},
        headers=temp_user["headers"],
    )
    assert resp.status_code == 403
