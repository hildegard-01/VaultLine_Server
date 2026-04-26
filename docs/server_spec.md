# VaultLine Server — 서버 명세서

> FastAPI 기반 경량 하이브리드 서버. 파일 자체는 저장하지 않고 메타데이터와 동기화 상태만 관리한다.

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [아키텍처](#2-아키텍처)
3. [디렉토리 구조](#3-디렉토리-구조)
4. [인증 및 보안](#4-인증-및-보안)
5. [API 엔드포인트](#5-api-엔드포인트)
6. [WebSocket](#6-websocket)
7. [데이터베이스 모델](#7-데이터베이스-모델)
8. [백그라운드 스케줄러](#8-백그라운드-스케줄러)
9. [설정](#9-설정)
10. [배포](#10-배포)
11. [테스트](#11-테스트)
12. [OAuth2 도입 계획](#12-oauth2-도입-계획)

---

## 1. 프로젝트 개요

| 항목 | 내용 |
|------|------|
| 런타임 | Python 3.11+ / FastAPI |
| DB | SQLite (운영: PostgreSQL 권장) |
| 인증 | JWT HS256 + Refresh Token Rotation |
| 실시간 | WebSocket (다중 기기, SVN 프록시) |
| 기본 포트 | **8080** |
| Swagger UI | `http://<host>:8080/docs` |
| 헬스 체크 | `GET /health` → `{"status":"ok","version":"0.1.0"}` |

**설계 원칙**
- 서버는 파일을 저장하지 않는다. 실제 파일은 클라이언트 로컬에 존재하며 서버는 메타데이터만 관리한다.
- 클라이언트가 소유한 SVN 저장소를 WebSocket 프록시로 다른 사용자에게 중계한다.

---

## 2. 아키텍처

```
┌─────────────────────────────────────────────┐
│              VaultLine Client (App)         │
│  - 로컬 파일 보유                             │
│  - svnserve 실행 (공유 시)                    │
└───────┬──────────────────┬──────────────────┘
        │ HTTPS REST       │ WebSocket
        ▼                  ▼
┌──────────────────────────────────────────────┐
│           VaultLine Server (FastAPI)         │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ HTTP API │  │    WS    │  │ Scheduler │  │
│  │ (라우터) │  │ Manager  │  │ (Thread)  │  │
│  └────┬─────┘  └────┬─────┘  └─────┬─────┘  │
│       └─────────────┴──────────────┘         │
│                    │                         │
│            ┌───────▼────────┐                │
│            │  SQLAlchemy ORM│                │
│            │  SQLite / PG   │                │
│            └────────────────┘                │
└──────────────────────────────────────────────┘
```

### SVN 프록시 흐름

```
수신자 ──[svn_new_session]──▶ 서버 ──[svn_connect]──▶ 소유자
수신자 ◀──[svn_owner_ready]── 서버 ◀──[svn_owner_ready]── 소유자
수신자 ◀══[svn_data 양방향]══ 서버 ══[svn_data 양방향]══ 소유자
수신자 ──[svn_close]────────▶ 서버 ──[svn_close]────────▶ 소유자
```

---

## 3. 디렉토리 구조

```
VaultLine_Server/
├── main.py                  # FastAPI 앱 엔트리포인트, 라우터 등록
├── config.py                # pydantic-settings 기반 설정 클래스
├── config.yaml              # 실제 설정값 (git 추적, 비밀값 변경 필요)
├── requirements.txt
│
├── api/                     # HTTP 라우터
│   ├── auth.py              # POST /auth/login|refresh|logout|password-change
│   ├── users.py             # CRUD /users
│   ├── groups.py            # CRUD /groups + 멤버 관리
│   ├── repos.py             # CRUD /repos
│   ├── sync.py              # POST /sync/commit, GET /sync/status|commits|file-tree
│   ├── presence.py          # POST /presence/heartbeat, GET /presence/online
│   ├── proxy.py             # GET /proxy/preview (파일 미리보기 프록시)
│   ├── activity.py          # GET /activity
│   ├── tags.py              # CRUD /tags, POST /tags/{id}/attach
│   ├── shares.py            # CRUD /shares + 수락/거절/SVN 자격증명
│   ├── notifications.py     # GET|PUT|DELETE /notifications
│   ├── approvals.py         # CRUD /approvals + 승인/반려
│   ├── admin.py             # GET /admin/dashboard|system|online-users|shares
│   └── deps.py              # get_current_user, require_admin
│
├── db/
│   ├── database.py          # SQLAlchemy 엔진/세션 팩토리
│   ├── models.py            # 전체 ORM 모델 (18개 테이블)
│   └── init_db.py           # ensure_admin_exists()
│
├── schemas/                 # Pydantic v2 요청/응답 스키마
│   ├── auth.py
│   ├── user.py
│   ├── group.py
│   ├── repo.py
│   ├── sync.py
│   ├── share.py
│   ├── notification.py
│   ├── approval.py
│   ├── tag.py
│   └── activity.py
│
├── utils/
│   └── security.py          # bcrypt 해싱, JWT 생성/검증, Refresh Token 해싱
│
├── scheduler/
│   └── jobs.py              # 백그라운드 작업 4종
│
├── ws/
│   ├── endpoint.py          # WebSocket /ws (JWT 쿼리 파라미터 인증)
│   └── manager.py           # ConnectionManager (연결 관리 + 메시지 라우팅)
│
├── scripts/
│   ├── setup.sh             # 최초 서버 환경 구성 (venv, pip, systemd)
│   ├── start.sh             # 개발 서버 실행
│   ├── pull.sh              # 운영 서버 업데이트 (git pull + 재시작)
│   ├── seed_data.py         # 테스트 데이터 삽입
│   ├── migrate_share_status.py   # share_recipients 컬럼 마이그레이션
│   └── migrate_share_svn.py      # shares SVN 컬럼 마이그레이션
│
├── tests/                   # 단위 테스트 (TestClient + in-memory SQLite)
└── integration/             # 통합 테스트 (실서버 대상 requests)
```

---

## 4. 인증 및 보안

### 비밀번호 저장

- **bcrypt** 해시로 변환 후 `users.password_hash`에 저장 (평문 미저장)
- `passlib.CryptContext(schemes=["bcrypt"])` 사용
- 의존성 주의: `bcrypt>=4.0.0,<4.3.0` (5.x는 passlib 1.7.4와 호환 불가)

### 토큰 구조

| 종류 | 생성 방식 | 유효기간 | 저장 위치 |
|------|-----------|----------|-----------|
| Access Token | JWT HS256 (`python-jose`) | 8시간 | 클라이언트 메모리 |
| Refresh Token | `secrets.token_urlsafe(64)` | 30일 | DB에 SHA-256 해시로 저장 |

- Refresh Token은 **Rotation 방식** — 갱신 시 기존 토큰 폐기 후 신규 발급
- 비밀번호 변경 시 해당 계정의 **모든 세션 무효화**

### 로그인 보호

- 15분 내 5회 실패 시 **429 Too Many Requests** (계정 잠금)
- `login_attempts` 테이블에 성공/실패 기록
- 잠금 해제: DB에서 `DELETE FROM login_attempts WHERE success=0` 실행

### WebSocket 인증

- 쿼리 파라미터로 Access Token 전달: `ws://<host>/ws?token={access_token}`
- 토큰 검증 실패 시 `code=4001`로 연결 거부

### SVN 자격증명

- `shares.svn_password_plain`에 SVN 접속 비밀번호 **평문 저장**
- 클라이언트가 svnserve에 직접 인증해야 하기 때문
- 보안 강화 필요 시 AES 암호화 적용 고려

---

## 5. API 엔드포인트

### 인증 `/auth`

| 메서드 | 경로 | 설명 | 인증 |
|--------|------|------|------|
| POST | `/auth/login` | 로그인 → JWT 발급 | 불필요 |
| POST | `/auth/refresh` | Access + Refresh Token 갱신 | 불필요 |
| POST | `/auth/logout` | 로그아웃 (세션 삭제) | 불필요 |
| POST | `/auth/password-change` | 비밀번호 변경 | 필요 |
| GET | `/auth/verify-token` | 토큰 유효성 확인 | 필요 |

### 사용자 `/users`

| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| GET | `/users` | 사용자 목록 | 로그인 |
| POST | `/users` | 사용자 생성 | 관리자 |
| GET | `/users/{id}` | 사용자 상세 | 로그인 |
| PUT | `/users/{id}` | 사용자 수정 | 본인/관리자 |
| DELETE | `/users/{id}` | 사용자 삭제 | 관리자 |

### 그룹 `/groups`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/groups` | 그룹 목록 |
| POST | `/groups` | 그룹 생성 |
| GET | `/groups/{id}` | 그룹 상세 |
| PUT | `/groups/{id}` | 그룹 수정 |
| DELETE | `/groups/{id}` | 그룹 삭제 |
| POST | `/groups/{id}/members` | 멤버 추가 |
| DELETE | `/groups/{id}/members/{user_id}` | 멤버 제거 |

### 저장소 `/repos`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/repos` | 저장소 목록 |
| POST | `/repos` | 저장소 등록 |
| GET | `/repos/{id}` | 저장소 상세 |
| PUT | `/repos/{id}` | 저장소 수정 |
| DELETE | `/repos/{id}` | 저장소 삭제 |

### 동기화 `/sync`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/sync/commit` | 커밋 메타데이터 push |
| GET | `/sync/status` | 동기화 상태 조회 |
| GET | `/sync/commits` | 커밋 이력 조회 |
| GET | `/sync/file-tree` | 파일 트리 조회 |

### Presence `/presence`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/presence/heartbeat` | 온라인 상태 갱신 |
| GET | `/presence/online` | 온라인 사용자 목록 |

### 공유 `/shares`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/shares` | 내가 만든 공유 목록 |
| POST | `/shares` | 공유 생성 |
| GET | `/shares/received` | 나에게 공유된 목록 (status 필터 가능) |
| GET | `/shares/{id}` | 공유 상세 |
| PUT | `/shares/{id}` | 공유 수정 |
| DELETE | `/shares/{id}` | 공유 삭제 (수신자 WS 알림) |
| GET | `/shares/{id}/credentials` | SVN 자격증명 조회 (소유자 전용) |
| POST | `/shares/{id}/accept` | 공유 수락 → SVN 접속정보 반환 |
| POST | `/shares/{id}/reject` | 공유 거절 |
| POST | `/shares/{id}/undo-accept` | 수락 롤백 → pending 복원 |
| GET | `/shares/public/{token}` | 공개 공유 접근 (인증 불필요) |

**공유 수락 응답 예시**
```json
{
  "status": "accepted",
  "svnserve_url": "svn://192.168.x.x/repo",
  "svn_username": "user1",
  "svn_password_plain": "...",
  "permission": "view",
  "repo_id": 1,
  "share_id": 3
}
```

### 알림 `/notifications`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/notifications` | 알림 목록 (읽음 필터 가능) |
| PUT | `/notifications/{id}/read` | 읽음 처리 |
| PUT | `/notifications/read-all` | 전체 읽음 처리 |
| DELETE | `/notifications/{id}` | 알림 삭제 |

### 승인 워크플로우 `/approvals`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/approvals` | 승인 목록 (내 요청 + 내 검토 항목) |
| POST | `/approvals` | 승인 요청 생성 |
| GET | `/approvals/{id}` | 승인 상세 |
| POST | `/approvals/{id}/approve` | 승인 |
| POST | `/approvals/{id}/reject` | 반려 |
| GET | `/approvals/rules` | 승인 규칙 목록 (관리자) |
| POST | `/approvals/rules` | 승인 규칙 생성 (관리자) |
| DELETE | `/approvals/rules/{id}` | 승인 규칙 삭제 (관리자) |

### 태그 `/tags`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/tags` | 태그 목록 |
| POST | `/tags` | 태그 생성 |
| DELETE | `/tags/{id}` | 태그 삭제 |
| POST | `/tags/{id}/attach` | 파일에 태그 부착 |
| DELETE | `/tags/{id}/detach` | 태그 해제 |

### 관리자 `/admin`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/admin/dashboard` | 주요 지표 (사용자 수, 저장소, 승인 등) |
| GET | `/admin/system` | 시스템 상태 (uptime, DB/캐시 크기) |
| GET | `/admin/online-users` | 온라인 사용자 목록 |
| POST | `/admin/users/{id}/force-logout` | 강제 로그아웃 |
| GET | `/admin/shares` | 전체 공유 목록 |
| DELETE | `/admin/shares/{id}` | 공유 강제 삭제 |

### 기타

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/health` | 서버 상태 확인 |
| GET | `/proxy/preview` | 파일 미리보기 프록시 (소유자 앱에 요청 중계) |
| GET | `/activity` | 활동 로그 조회 |

---

## 6. WebSocket

### 연결

```
ws://<host>:8080/ws?token={access_token}
```

- 한 사용자가 여러 기기에서 동시 연결 가능
- JWT 인증 실패 시 `code=4001`로 연결 거부

### 메시지 타입

#### 클라이언트 → 서버

| type | 설명 |
|------|------|
| `heartbeat` | 온라인 상태 갱신 (DB `last_heartbeat` 업데이트) |
| `file_response` | 파일 요청에 대한 응답 (`req_id` 포함) |
| `svn_register_provider` | 소유자: 담당 share_id 목록 등록 |
| `svn_new_session` | 수신자: 새 SVN 프록시 세션 요청 |
| `svn_data` | SVN 데이터 중계 (양방향) |
| `svn_owner_ready` | 소유자: svnserve TCP 연결 성공 알림 |
| `svn_relay_error` | 소유자: 오류 발생 알림 |
| `svn_close` | SVN 세션 종료 |

#### 서버 → 클라이언트

| type | 설명 |
|------|------|
| `notification` | 실시간 알림 (공유, 승인 등) |
| `share_revoked` | 공유 취소 알림 |
| `file_request` | 파일 미리보기 요청 (소유자 앱에 전달) |
| `svn_connect` | 소유자에게 SVN 연결 요청 |
| `svn_owner_ready` | 수신자에게 소유자 준비 완료 전달 |
| `svn_data` | SVN 데이터 중계 |
| `svn_relay_error` | 수신자에게 오류 전달 |
| `svn_close` | SVN 세션 종료 중계 |
| `svn_error` | 소유자 오프라인 등 오류 |

---

## 7. 데이터베이스 모델

| 모델 | 테이블 | 설명 |
|------|--------|------|
| `User` | `users` | 사용자 (admin/user, active/locked/inactive) |
| `Session` | `sessions` | Refresh Token 세션 |
| `LoginAttempt` | `login_attempts` | 브루트포스 방어용 기록 |
| `ActivityLog` | `activity_log` | 사용자 행동 로그 |
| `Group` | `groups` | 사용자 그룹 |
| `UserGroup` | `user_groups` | 그룹-사용자 M:N (owner/admin/member) |
| `RepoRegistry` | `repos_registry` | 저장소 메타데이터 |
| `CommitLog` | `commit_log` | 클라이언트 push 커밋 메타 |
| `FileTree` | `file_tree` | 저장소 파일 트리 스냅샷 |
| `PreviewCacheMeta` | `preview_cache_meta` | 미리보기 캐시 메타 |
| `Tag` | `tags` | 시스템 전역 태그 |
| `FileTag` | `file_tags` | 파일-태그 M:N |
| `Share` | `shares` | 공유 링크 (토큰 기반, SVN 접속정보 포함) |
| `ShareRecipient` | `share_recipients` | 공유 수신자 (pending/accepted/rejected) |
| `Notification` | `notifications` | 사용자 알림 |
| `ApprovalRule` | `approval_rules` | 경로 패턴 기반 승인 규칙 |
| `Approval` | `approvals` | 승인 요청 |
| `ApprovalReviewer` | `approval_reviewers` | 승인 검토자 |

### 주의사항

- **SQLite datetime**: timezone 정보를 저장하지 않음. 만료 비교 시 `datetime.now(timezone.utc).replace(tzinfo=None)` 사용
- **운영 환경**: PostgreSQL 사용 시 위 문제 없음

---

## 8. 백그라운드 스케줄러

APScheduler 없이 단일 daemon Thread로 구동.

| 작업 | 주기 | 설명 |
|------|------|------|
| `presence_check` | 3분마다 | heartbeat 미갱신 사용자 오프라인 처리 |
| `session_cleanup` | 1시간마다 | 만료된 Refresh Token 세션 삭제 |
| `cache_cleanup` | 24시간마다 | 미리보기 캐시 파일 + DB 레코드 삭제 |
| `log_archive` | 24시간마다 | 보존 기간(기본 6개월) 초과 활동 로그 삭제 |

> 다중 워커 환경에서는 스케줄러 중복 실행 가능. 운영 환경에서는 Celery Beat 또는 단일 워커 권장.

---

## 9. 설정

`config.yaml` 파일로 관리 (git 추적, 비밀값은 반드시 변경).

```yaml
server:
  host: "0.0.0.0"
  port: 8080
  debug: true          # 운영: false

auth:
  jwt_secret: "변경필수"
  access_token_expire_hours: 8
  refresh_token_expire_days: 30
  password_min_length: 8
  login_max_attempts: 5
  login_lockout_minutes: 15

database:
  url: "sqlite:///./data/app.db"   # 운영: postgresql://...

storage:
  data_dir: "./data"
  cache_dir: "./data/cache"
  preview_max_size_mb: 5000
  preview_max_age_days: 30

sync:
  heartbeat_timeout_seconds: 180

log_retention:
  hot_months: 6
```

### 초기 관리자 계정

서버 최초 실행 시 자동 생성: `admin / admin1234`
**운영 환경에서는 반드시 비밀번호 변경 필요.**

---

## 10. 배포

### 최초 설치 (Ubuntu)

```bash
bash scripts/setup.sh
```

- Python venv 생성 및 pip 설치
- `data/` 디렉토리 생성
- systemd 서비스 등록 (선택)

### 서버 실행

```bash
bash scripts/start.sh
# 또는
uvicorn main:app --reload --port 8080
```

### 업데이트 배포 (운영 서버)

```bash
bash scripts/pull.sh
```

동작 순서:
1. `git pull origin main`
2. `config.yaml` 백업 유지 (덮어쓰지 않음)
3. requirements 변경 시 `pip install` 자동 실행
4. 서버 재시작

### DB 마이그레이션

```bash
# shares 테이블 SVN 컬럼 추가
python scripts/migrate_share_svn.py

# share_recipients 상태 컬럼 추가
python scripts/migrate_share_status.py
```

### 테스트 데이터 삽입

```bash
python scripts/seed_data.py
```

삽입 데이터: `admin`, `user1/1234`, `user2/1234`, 테스트 그룹/저장소/태그

---

## 11. 테스트

### 단위 테스트 (`tests/`)

```bash
python -m pytest tests/ -v
```

- TestClient + in-memory SQLite (`StaticPool`)
- 스케줄러 비활성화 (`lifespan` noop 처리)
- 총 61개 테스트

### 통합 테스트 (`integration/`)

실서버(`http://192.168.219.148:8080`)를 대상으로 실행.

```bash
python -m pytest integration/ -v
```

대상: 인증, 사용자, 그룹, 저장소, 동기화, 헬스체크

---

## 12. OAuth2 도입 계획

### 개요

현재 자체 ID/PW 인증에 추가로 **소셜 로그인(OAuth2)** 을 연동할 계획.
기존 JWT/Refresh Token 구조를 그대로 유지하고, OAuth2는 **대체 로그인 경로**로 추가한다.

### 플로우

```
클라이언트 → GET /auth/oauth2/{provider}
           → Provider 로그인 페이지 리다이렉트
           → 사용자 인증 완료
           → GET /auth/oauth2/{provider}/callback?code=...
           → 서버: Provider API로 사용자 정보 조회
           → 기존 계정 연결 or 신규 계정 생성
           → Access Token + Refresh Token 발급 (기존과 동일)
```

### DB 변경 계획

`users` 테이블에 컬럼 추가:

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `oauth_provider` | VARCHAR(30) | `google`, `github`, `kakao` 등 |
| `oauth_sub` | VARCHAR(200) | Provider 측 고유 ID |

### 지원 예정 Provider

| Provider | 라이브러리 |
|----------|-----------|
| Google | `authlib` + Google OAuth2 |
| GitHub | `authlib` + GitHub OAuth App |
| Kakao | `httpx` + Kakao REST API |

### 구현 범위

- `api/auth.py`에 `/auth/oauth2/{provider}`, `/auth/oauth2/{provider}/callback` 추가
- 기존 로그인(`/auth/login`) 코드 변경 없음
- `config.yaml`에 각 Provider의 `client_id`, `client_secret` 추가

### 고려사항

- OAuth2 계정과 로컬 계정의 **이메일 기반 연결** (동일 이메일 존재 시 병합)
- 비밀번호 없이 OAuth2로만 가입한 계정은 `password_hash = NULL` 허용 필요
- SVN 비밀번호 등 민감 정보는 OAuth2 연동과 무관하게 별도 설정
