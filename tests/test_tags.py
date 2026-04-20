"""
태그 API 테스트 — /tags
"""

import pytest
from tests.conftest import auth_headers
from db.models import Tag, FileTag, RepoRegistry


@pytest.fixture()
def tag(db, admin_user):
    t = Tag(name="중요", color="#FF0000", created_by=admin_user.id)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@pytest.fixture()
def repo(db, regular_user):
    r = RepoRegistry(name="태그저장소", owner_user_id=regular_user.id, type="personal")
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


class TestListTags:
    def test_list_tags(self, client, regular_user, tag):
        resp = client.get("/tags", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        names = [t["name"] for t in resp.json()]
        assert "중요" in names

    def test_list_tags_unauthenticated(self, client):
        resp = client.get("/tags")
        assert resp.status_code == 403


class TestCreateTag:
    def test_admin_creates_tag(self, client, admin_user):
        resp = client.post("/tags", json={"name": "긴급", "color": "#FF5733"}, headers=auth_headers(admin_user))
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "긴급"
        assert data["color"] == "#FF5733"

    def test_regular_user_cannot_create(self, client, regular_user):
        resp = client.post("/tags", json={"name": "긴급"}, headers=auth_headers(regular_user))
        assert resp.status_code == 403

    def test_duplicate_tag_rejected(self, client, admin_user, tag):
        resp = client.post("/tags", json={"name": "중요"}, headers=auth_headers(admin_user))
        assert resp.status_code == 409


class TestUpdateTag:
    def test_update_tag(self, client, admin_user, tag):
        resp = client.put(f"/tags/{tag.id}", json={"name": "매우중요", "color": "#0000FF"}, headers=auth_headers(admin_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "매우중요"
        assert data["color"] == "#0000FF"

    def test_update_nonexistent_tag(self, client, admin_user):
        resp = client.put("/tags/99999", json={"name": "없음"}, headers=auth_headers(admin_user))
        assert resp.status_code == 404

    def test_update_duplicate_name_rejected(self, client, db, admin_user, tag):
        other = Tag(name="다른태그", created_by=admin_user.id)
        db.add(other)
        db.commit()
        db.refresh(other)
        resp = client.put(f"/tags/{other.id}", json={"name": "중요"}, headers=auth_headers(admin_user))
        assert resp.status_code == 409


class TestDeleteTag:
    def test_delete_tag(self, client, admin_user, tag):
        resp = client.delete(f"/tags/{tag.id}", headers=auth_headers(admin_user))
        assert resp.status_code == 200

    def test_delete_nonexistent_tag(self, client, admin_user):
        resp = client.delete("/tags/99999", headers=auth_headers(admin_user))
        assert resp.status_code == 404

    def test_regular_user_cannot_delete(self, client, regular_user, tag):
        resp = client.delete(f"/tags/{tag.id}", headers=auth_headers(regular_user))
        assert resp.status_code == 403


class TestFileTags:
    def test_attach_tag(self, client, regular_user, tag, repo):
        resp = client.post("/tags/attach", json={
            "repo_id": repo.id,
            "file_path": "README.md",
            "tag_id": tag.id,
        }, headers=auth_headers(regular_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["tag_name"] == "중요"
        assert data["file_path"] == "README.md"

    def test_attach_duplicate_rejected(self, client, regular_user, tag, repo):
        body = {"repo_id": repo.id, "file_path": "README.md", "tag_id": tag.id}
        client.post("/tags/attach", json=body, headers=auth_headers(regular_user))
        resp = client.post("/tags/attach", json=body, headers=auth_headers(regular_user))
        assert resp.status_code == 409

    def test_attach_nonexistent_tag(self, client, regular_user, repo):
        resp = client.post("/tags/attach", json={
            "repo_id": repo.id, "file_path": "README.md", "tag_id": 99999,
        }, headers=auth_headers(regular_user))
        assert resp.status_code == 404

    def test_get_file_tags(self, client, regular_user, tag, repo):
        client.post("/tags/attach", json={"repo_id": repo.id, "file_path": "README.md", "tag_id": tag.id},
                    headers=auth_headers(regular_user))
        resp = client.get(f"/tags/file?repo_id={repo.id}&path=README.md", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["tag_name"] == "중요"

    def test_detach_tag(self, client, regular_user, tag, repo):
        client.post("/tags/attach", json={"repo_id": repo.id, "file_path": "README.md", "tag_id": tag.id},
                    headers=auth_headers(regular_user))
        resp = client.delete(
            f"/tags/detach?repo_id={repo.id}&file_path=README.md&tag_id={tag.id}",
            headers=auth_headers(regular_user),
        )
        assert resp.status_code == 200

    def test_detach_nonexistent(self, client, regular_user, tag, repo):
        resp = client.delete(
            f"/tags/detach?repo_id={repo.id}&file_path=없는파일.md&tag_id={tag.id}",
            headers=auth_headers(regular_user),
        )
        assert resp.status_code == 404

    def test_search_by_tag(self, client, regular_user, tag, repo):
        client.post("/tags/attach", json={"repo_id": repo.id, "file_path": "main.py", "tag_id": tag.id},
                    headers=auth_headers(regular_user))
        resp = client.get(f"/tags/search?tag_id={tag.id}", headers=auth_headers(regular_user))
        assert resp.status_code == 200
        paths = [ft["file_path"] for ft in resp.json()]
        assert "main.py" in paths
