import requests
from integration.conftest import BASE_URL, ADMIN_USER, ADMIN_PASS


def test_login_success(admin_auth):
    assert "access_token" in admin_auth
    assert "refresh_token" in admin_auth
    assert admin_auth["username"] == ADMIN_USER
    assert admin_auth["role"] == "admin"


def test_login_wrong_password():
    resp = requests.post(f"{BASE_URL}/auth/login", json={"username": ADMIN_USER, "password": "wrongpassword"})
    assert resp.status_code == 401


def test_login_nonexistent_user():
    resp = requests.post(f"{BASE_URL}/auth/login", json={"username": "no_such_user_xyz", "password": "anything"})
    assert resp.status_code == 401


def test_verify_token(admin_headers):
    resp = requests.get(f"{BASE_URL}/auth/verify-token", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["username"] == ADMIN_USER


def test_verify_token_invalid():
    resp = requests.get(f"{BASE_URL}/auth/verify-token", headers={"Authorization": "Bearer invalid.token.here"})
    assert resp.status_code == 401


def test_token_refresh(admin_auth, base_url):
    resp = requests.post(f"{base_url}/auth/refresh", json={"refresh_token": admin_auth["refresh_token"]})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["refresh_token"] != admin_auth["refresh_token"]


def test_logout(temp_user, base_url):
    resp = requests.post(f"{base_url}/auth/logout", json={"refresh_token": temp_user["refresh_token"]})
    assert resp.status_code == 200

    resp2 = requests.post(f"{base_url}/auth/refresh", json={"refresh_token": temp_user["refresh_token"]})
    assert resp2.status_code == 401


def test_password_change(temp_user, base_url):
    headers = {"Authorization": f"Bearer {temp_user['access_token']}"}
    resp = requests.post(
        f"{base_url}/auth/password-change",
        json={"current_password": "TempPass1!", "new_password": "NewPass2@"},
        headers=headers,
    )
    assert resp.status_code == 200

    login_resp = requests.post(
        f"{base_url}/auth/login",
        json={"username": temp_user["username"], "password": "NewPass2@"},
    )
    assert login_resp.status_code == 200
