import uuid
import requests
from integration.conftest import BASE_URL


def test_list_users(admin_headers):
    resp = requests.get(f"{BASE_URL}/users", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert body["total"] >= 1


def test_list_users_requires_auth():
    resp = requests.get(f"{BASE_URL}/users")
    assert resp.status_code == 401


def test_get_user(admin_headers, admin_auth):
    resp = requests.get(f"{BASE_URL}/users/{admin_auth['user_id']}", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"


def test_get_user_not_found(admin_headers):
    resp = requests.get(f"{BASE_URL}/users/99999", headers=admin_headers)
    assert resp.status_code == 404


def test_create_and_delete_user(base_url, admin_headers):
    username = f"new_{uuid.uuid4().hex[:8]}"
    resp = requests.post(
        f"{base_url}/users",
        json={"username": username, "password": "CreatePass1!", "display_name": "신규"},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    user = resp.json()
    assert user["username"] == username

    requests.delete(f"{base_url}/users/{user['id']}", headers=admin_headers)


def test_create_user_requires_admin(base_url, temp_user):
    resp = requests.post(
        f"{base_url}/users",
        json={"username": f"x_{uuid.uuid4().hex[:6]}", "password": "Pass1234!"},
        headers=temp_user["headers"],
    )
    assert resp.status_code == 403


def test_update_user_self(base_url, temp_user):
    resp = requests.put(
        f"{base_url}/users/{temp_user['id']}",
        json={"display_name": "변경된 이름"},
        headers=temp_user["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "변경된 이름"


def test_admin_cannot_delete_self(base_url, admin_headers, admin_auth):
    resp = requests.delete(f"{base_url}/users/{admin_auth['user_id']}", headers=admin_headers)
    assert resp.status_code == 400
