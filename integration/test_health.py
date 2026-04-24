import requests
from integration.conftest import BASE_URL


def test_health_ok():
    resp = requests.get(f"{BASE_URL}/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_docs_accessible():
    resp = requests.get(f"{BASE_URL}/docs")
    assert resp.status_code == 200
