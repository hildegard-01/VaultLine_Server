import uuid
import requests
from integration.conftest import BASE_URL


def test_list_groups(admin_headers):
    resp = requests.get(f"{BASE_URL}/groups", headers=admin_headers)
    assert resp.status_code == 200
    assert "items" in resp.json()


def test_create_group(base_url, admin_headers):
    name = f"g_{uuid.uuid4().hex[:8]}"
    resp = requests.post(f"{base_url}/groups", json={"name": name}, headers=admin_headers)
    assert resp.status_code == 201
    group = resp.json()
    assert group["name"] == name
    requests.delete(f"{base_url}/groups/{group['id']}", headers=admin_headers)


def test_create_group_duplicate(base_url, admin_headers, temp_group):
    resp = requests.post(f"{base_url}/groups", json={"name": temp_group["name"]}, headers=admin_headers)
    assert resp.status_code == 409


def test_create_group_requires_admin(base_url, temp_user):
    resp = requests.post(
        f"{base_url}/groups",
        json={"name": f"g_{uuid.uuid4().hex[:8]}"},
        headers=temp_user["headers"],
    )
    assert resp.status_code == 403


def test_add_and_remove_member(base_url, admin_headers, temp_group, temp_user):
    resp = requests.post(
        f"{base_url}/groups/{temp_group['id']}/members",
        json={"user_id": temp_user["id"], "role": "member"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert any(m["user_id"] == temp_user["id"] for m in resp.json()["members"])

    resp2 = requests.delete(
        f"{base_url}/groups/{temp_group['id']}/members/{temp_user['id']}",
        headers=admin_headers,
    )
    assert resp2.status_code == 200
