# VaultLine Server — CLAUDE.md

FastAPI 기반 경량 하이브리드 서버. 파일 자체는 저장하지 않고 메타데이터와 동기화 상태만 관리한다.

---

## 프로젝트 구조

```
VaultLine_Server/
├── main.py              # FastAPI 앱 엔트리포인트
├── config.py            # 설정 클래스 (pydantic-settings)
├── config.yaml          # 설정 파일 (git 추적, 비밀값은 변경 필요)
├── requirements.txt
├── api/                 # HTTP 라우터
│   ├── auth.py          # POST /auth/login|refresh|logout|password-change, GET /auth/verify-token
│   ├── users.py         # GET|POST /users, GET|PUT|DELETE /users/{id}
│   ├── groups.py        # CRUD /groups + /groups/{id}/members
│   ├── repos.py         # CRUD /repos
│   ├── sync.py          # POST /sync/commit, GET /sync/status|commits|file-tree
│   ├── presence.py      # POST /presence/heartbeat, GET /presence/online
│   ├── proxy.py         # GET /proxy/preview
│   ├── activity.py      # GET /activity
│   ├── tags.py          # CRUD /tags, POST /tags/{id}/attach
│   ├── shares.py        # CRUD /shares, GET /shares/public/{token}
│   ├── notifications.py # GET|PUT|DELETE /notifications
│   ├── approvals.py     # CRUD /approvals, POST /approvals/{id}/review
│   ├── admin.py         # GET /admin/stats|activity|sessions
│   └── deps.py          # 공통 의존성: get_current_user, require_admin
├── db/
│   ├── database.py      # SQLAlchemy 엔진/세션 (get_db 의존성)
│   ├── models.py        # 전체 ORM 모델
│   └── init_db.py       # ensure_admin_exists()
├── schemas/             # Pydantic 요청/응답 스키마 (모듈별 분리)
├── utils/
│   └── security.py      # bcrypt 해싱, JWT 생성/검증, refresh token 해싱
├── scheduler/
│   └── jobs.py          # presence_check, cache_cleanup, log_archive, session_cleanup
├── ws/
│   ├── endpoint.py      # WebSocket /ws (JWT 쿼리 파라미터 인증)
│   └── manager.py       # ConnectionManager
└── tests/
    ├── conftest.py      # 공통 픽스처
    ├── test_health.py
    ├── test_auth.py
    ├── test_users.py
    ├── test_repos.py
    └── test_groups.py
```

---

## 개발 환경

### 서버 실행

```bash
python main.py
# 또는
uvicorn main:app --reload --port 8080
```

- 기본 포트: **8080**
- Swagger UI: `http://localhost:8080/docs`
- 헬스 체크: `GET /health`

### 초기 관리자 계정

서버 최초 실행 시 자동 생성: `admin / admin1234`  
**운영 환경에서는 반드시 비밀번호 변경 필요.**

---

## 테스트

```bash
python -m pytest tests/ -v
```

61개 테스트, 전부 인메모리 SQLite로 실행 (실제 DB 파일 불필요).

### 의존성 주의

```
bcrypt>=4.0.0,<4.3.0   # bcrypt 5.x는 passlib 1.7.4와 호환 안 됨
```

bcrypt 5.x가 설치되어 있으면 다운그레이드 필요:
```bash
pip install "bcrypt>=4.0.0,<4.3.0" --force-reinstall
```

### 테스트 아키텍처 (`tests/conftest.py`)

| 구성 요소 | 이유 |
|-----------|------|
| `StaticPool` | SQLite in-memory는 연결마다 새 DB 생성 → 단일 연결 공유 강제 |
| `app.router.lifespan_context = _noop_lifespan` | 실제 DB 파일 생성 및 스케줄러 시작 방지 |
| `app.dependency_overrides[get_db]` | 테스트 세션으로 교체 |

---

## DB 모델 구조

| 모델 | 테이블 | 설명 |
|------|--------|------|
| `User` | `users` | 사용자 (admin/user, active/locked/inactive) |
| `Session` | `sessions` | Refresh Token 세션 (SHA-256 해시 저장) |
| `LoginAttempt` | `login_attempts` | 브루트포스 방어용 시도 기록 |
| `ActivityLog` | `activity_log` | 사용자 행동 로그 |
| `Group` | `groups` | 사용자 그룹 |
| `UserGroup` | `user_groups` | 그룹-사용자 M:N (owner/admin/member) |
| `RepoRegistry` | `repos_registry` | 저장소 메타데이터 (파일 미저장) |
| `CommitLog` | `commit_log` | 클라이언트가 push한 커밋 메타 |
| `FileTree` | `file_tree` | 저장소 파일 트리 스냅샷 |
| `PreviewCacheMeta` | `preview_cache_meta` | 미리보기 캐시 메타 |
| `Tag` | `tags` | 시스템 전역 태그 |
| `FileTag` | `file_tags` | 파일-태그 M:N |
| `Share` | `shares` | 공유 링크 (토큰 기반) |
| `ShareRecipient` | `share_recipients` | 공유 수신자 접근 기록 |
| `Notification` | `notifications` | 사용자 알림 |
| `ApprovalRule` | `approval_rules` | 경로 패턴 기반 승인 규칙 |
| `Approval` | `approvals` | 승인 요청 |
| `ApprovalReviewer` | `approval_reviewers` | 승인 검토자 |

---

## 인증 구조

- **Access Token**: JWT HS256, 만료 8시간 (기본값)
- **Refresh Token**: `secrets.token_urlsafe(64)` → SHA-256 해시로 DB 저장, Rotation 방식
- **로그인 잠금**: 15분 내 5회 실패 시 429 반환
- **WebSocket 인증**: 쿼리 파라미터 `?token={access_token}`

---

## 설정 (`config.yaml`)

```yaml
auth:
  jwt_secret: "변경 필요"       # 운영 환경에서 반드시 교체
  access_token_expire_hours: 8
  refresh_token_expire_days: 30
  password_min_length: 8
  login_max_attempts: 5
  login_lockout_minutes: 15

database:
  url: "sqlite:///./data/app.db"  # 운영 시 PostgreSQL 권장

storage:
  data_dir: "./data"
  cache_dir: "./data/cache"
```

---

## 알려진 제약 / 주의사항

- **SQLite datetime**: SQLite는 timezone 정보를 저장하지 않음. 비교 시 `datetime.now(timezone.utc).replace(tzinfo=None)` 사용 (`api/auth.py:143` 참조).
- **파일 미저장**: 서버는 메타데이터만 관리. 실제 파일은 클라이언트 로컬에 존재.
- **스케줄러**: APScheduler 없이 Thread 기반 간이 스케줄러 사용. 다중 워커 환경에서는 중복 실행 가능.
- **운영 환경**: `config.yaml`의 `jwt_secret`, `debug: false`, DB URL을 반드시 변경.
