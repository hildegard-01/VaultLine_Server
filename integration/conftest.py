"""
통합테스트 공통 fixture — 실제 서버 대상
환경변수 VAULTLINE_BASE_URL 로 대상 서버 지정 (기본: http://localhost:8080)
"""

import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("VAULTLINE_BASE_URL", "http://localhost:8080").rstrip("/")
ADMIN_USER = os.environ.get("VAULTLINE_ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("VAULTLINE_ADMIN_PASS", "admin1234")


def _login(username: str, password: str) -> dict:
    resp = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": password})
    resp.raise_for_status()
    return resp.json()


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL


@pytest.fixture(scope="session")
def admin_auth() -> dict:
    return _login(ADMIN_USER, ADMIN_PASS)


@pytest.fixture(scope="session")
def admin_headers(admin_auth) -> dict:
    return {"Authorization": f"Bearer {admin_auth['access_token']}"}


@pytest.fixture
def temp_user(base_url, admin_headers):
    username = f"t_{uuid.uuid4().hex[:8]}"
    password = "TempPass1!"

    resp = requests.post(
        f"{base_url}/users",
        json={"username": username, "password": password, "display_name": "Temp User"},
        headers=admin_headers,
    )
    resp.raise_for_status()
    user = resp.json()

    auth = _login(username, password)
    user["access_token"] = auth["access_token"]
    user["refresh_token"] = auth["refresh_token"]
    user["headers"] = {"Authorization": f"Bearer {auth['access_token']}"}

    yield user

    requests.delete(f"{base_url}/users/{user['id']}", headers=admin_headers)


@pytest.fixture
def temp_group(base_url, admin_headers):
    name = f"group_{uuid.uuid4().hex[:8]}"
    resp = requests.post(
        f"{base_url}/groups",
        json={"name": name, "description": "통합테스트 임시 그룹"},
        headers=admin_headers,
    )
    resp.raise_for_status()
    group = resp.json()

    yield group

    requests.delete(f"{base_url}/groups/{group['id']}", headers=admin_headers)


@pytest.fixture
def temp_repo(base_url, admin_headers, admin_auth):
    name = f"repo_{uuid.uuid4().hex[:8]}"
    resp = requests.post(
        f"{base_url}/repos",
        json={"name": name, "description": "통합테스트 임시 저장소", "type": "personal"},
        headers=admin_headers,
    )
    resp.raise_for_status()
    repo = resp.json()

    yield repo

    requests.delete(f"{base_url}/repos/{repo['id']}", headers=admin_headers)
