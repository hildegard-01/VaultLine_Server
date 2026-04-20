# 테스트 가이드

## 실행

```bash
# 전체
python -m pytest tests/ -v

# 특정 파일
python -m pytest tests/test_auth.py -v

# 특정 테스트
python -m pytest tests/test_auth.py::TestLogin::test_login_success -v
```

## 파일 구성

| 파일 | 테스트 수 | 대상 |
|------|-----------|------|
| `test_health.py` | 1 | `GET /health` |
| `test_auth.py` | 16 | `/auth/*` — login, refresh, logout, password-change, verify-token |
| `test_users.py` | 15 | `/users/*` — CRUD, 권한 분리 |
| `test_repos.py` | 14 | `/repos/*` — 저장소 등록/수정/삭제 |
| `test_groups.py` | 15 | `/groups/*` — 그룹 CRUD + 멤버 관리 |

## 픽스처 (`conftest.py`)

| 픽스처 | 설명 |
|--------|------|
| `setup_db` (autouse) | 테스트마다 테이블 생성 → 삭제 |
| `db` | 인메모리 SQLite 세션 |
| `client` | DB 오버라이드된 FastAPI TestClient |
| `admin_user` | role=admin 사용자 (username: admin) |
| `regular_user` | role=user 사용자 (username: testuser) |
| `auth_headers(user)` | Bearer 헤더 딕셔너리 반환 함수 |

## 설계 결정

**StaticPool 사용**  
`sqlite:///:memory:`는 연결마다 새 DB 인스턴스를 생성한다. `StaticPool`을 사용해 모든 연결이 동일한 인메모리 DB를 공유하도록 강제.

**Lifespan 비활성화**  
`app.router.lifespan_context = _noop_lifespan`으로 교체해 테스트 중 실제 파일(`./data/app.db`) 생성 및 백그라운드 스케줄러 시작을 방지.

**DB 의존성 오버라이드**  
`app.dependency_overrides[get_db]`로 모든 엔드포인트가 테스트 세션을 사용하도록 교체.

## 의존성

```
pytest
pytest-asyncio
httpx
bcrypt>=4.0.0,<4.3.0   # 5.x는 passlib 1.7.4와 호환 안 됨
```
