# VaultLine Server

VaultLine 클라이언트 앱과 연동하는 경량 FastAPI 서버.  
파일 자체는 저장하지 않고 **메타데이터, 동기화 상태, 사용자/그룹 관리**를 담당한다.

---

## 빠른 시작

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

> **주의**: `bcrypt>=4.0.0,<4.3.0` 필수. bcrypt 5.x는 passlib와 호환 안 됨.

### 2. 설정 확인

`config.yaml`을 열어 운영 환경에 맞게 수정:

```yaml
auth:
  jwt_secret: "반드시-변경-필요"

database:
  url: "sqlite:///./data/app.db"   # 운영 시 PostgreSQL 권장

server:
  debug: false                      # 운영 시 false
```

### 3. 서버 실행

```bash
python main.py
```

- 기본 주소: `http://0.0.0.0:8080`
- Swagger UI: `http://localhost:8080/docs`
- 헬스 체크: `GET /health`

### 4. 초기 관리자 계정

서버 최초 실행 시 자동 생성됩니다.

| 항목 | 값 |
|------|-----|
| 아이디 | `admin` |
| 비밀번호 | `admin1234` |

**운영 환경에서는 반드시 로그인 후 비밀번호를 변경하세요.**

---

## API 엔드포인트

| 접두사 | 설명 |
|--------|------|
| `POST /auth/login` | 로그인 (JWT 발급) |
| `POST /auth/refresh` | 토큰 갱신 (Rotation) |
| `POST /auth/logout` | 로그아웃 |
| `GET /auth/verify-token` | 토큰 유효성 확인 |
| `GET/POST /users` | 사용자 목록/생성 |
| `GET/PUT/DELETE /users/{id}` | 사용자 조회/수정/삭제 |
| `GET/POST /groups` | 그룹 목록/생성 |
| `POST /groups/{id}/members` | 그룹 멤버 추가 |
| `GET/POST /repos` | 저장소 목록/등록 |
| `POST /sync/commit` | 커밋 메타 수신 |
| `GET /sync/status/{repo_id}` | 동기화 상태 조회 |
| `GET /sync/commits` | 커밋 로그 조회 |
| `GET /sync/file-tree/{repo_id}` | 파일 트리 조회 |
| `POST /presence/heartbeat` | 온라인 상태 갱신 |
| `GET /proxy/preview` | 파일 미리보기 프록시 |
| `GET /activity` | 활동 로그 |
| `GET/POST /tags` | 태그 관리 |
| `GET/POST /shares` | 공유 링크 관리 |
| `GET /notifications` | 알림 목록 |
| `GET/POST /approvals` | 승인 요청 관리 |
| `GET /admin/stats` | 관리자 통계 |
| `WS /ws?token=...` | WebSocket 실시간 연결 |

전체 API 명세: `http://localhost:8080/docs`

---

## 인증 방식

모든 보호 엔드포인트는 `Authorization: Bearer {access_token}` 헤더 필요.

```
POST /auth/login
→ { access_token, refresh_token }

# Access Token 만료 시
POST /auth/refresh  { refresh_token }
→ { access_token, refresh_token }  ← 새 Refresh Token (Rotation)
```

---

## 테스트

```bash
python -m pytest tests/ -v
```

61개 테스트, 인메모리 SQLite 사용 (실제 DB 불필요).

---

## 백그라운드 스케줄러

서버 시작 시 자동으로 Thread 기반 스케줄러가 실행됩니다.

| 작업 | 주기 | 설명 |
|------|------|------|
| `presence_check` | 3분 | Heartbeat 없는 사용자 오프라인 처리 |
| `session_cleanup` | 1시간 | 만료된 Refresh Token 세션 삭제 |
| `cache_cleanup` | 24시간 | 만료된 미리보기 캐시 파일 삭제 |
| `log_archive` | 24시간 | 보존 기간 초과 활동 로그 삭제 |

---

## 데이터 디렉토리

```
data/
├── app.db          # SQLite DB (자동 생성)
└── cache/          # 미리보기 캐시 (자동 생성)
```

`.gitignore`에 `data/` 추가 권장.
