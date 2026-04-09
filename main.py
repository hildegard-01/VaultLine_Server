"""
VaultLine Server — FastAPI 엔트리포인트
"""

from contextlib import asynccontextmanager
from threading import Thread

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from db.database import engine
from db import models
from api.auth import router as auth_router
from api.users import router as users_router
from api.groups import router as groups_router
from api.repos import router as repos_router
from api.sync import router as sync_router
from api.presence import router as presence_router
from api.proxy import router as proxy_router
from api.activity import router as activity_router
from api.tags import router as tags_router
from api.shares import router as shares_router
from api.notifications import router as notifications_router
from api.approvals import router as approvals_router
from api.admin import router as admin_router
from ws.endpoint import router as ws_router


def _start_scheduler():
    """백그라운드 스케줄러 시작 (APScheduler 미설치 시 간단 Thread 기반)"""
    import time
    from scheduler.jobs import presence_check, cache_cleanup, log_archive, session_cleanup

    def run():
        tick = 0
        while True:
            time.sleep(60)
            tick += 1
            # 3분마다: presence 체크
            if tick % 3 == 0:
                try:
                    presence_check()
                except Exception as e:
                    print(f"[스케줄러 오류] presence_check: {e}")
            # 1시간마다: 세션 정리
            if tick % 60 == 0:
                try:
                    session_cleanup()
                except Exception as e:
                    print(f"[스케줄러 오류] session_cleanup: {e}")
            # 24시간마다: 캐시 + 로그 정리
            if tick % 1440 == 0:
                try:
                    cache_cleanup()
                    log_archive()
                except Exception as e:
                    print(f"[스케줄러 오류] cleanup: {e}")

    t = Thread(target=run, daemon=True)
    t.start()
    print("[스케줄러] 백그라운드 작업 시작")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작 시 DB 테이블 생성 + 스케줄러 시작"""
    models.Base.metadata.create_all(bind=engine)

    # 관리자 계정 초기화
    from db.init_db import ensure_admin_exists
    ensure_admin_exists()

    # 스케줄러 시작
    _start_scheduler()

    yield


settings = get_settings()

app = FastAPI(
    title="VaultLine Server",
    description="VaultLine Lite 하이브리드 에디션 경량 서버",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — 개발 환경 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.server.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(auth_router, prefix="/auth", tags=["인증"])
app.include_router(users_router, prefix="/users", tags=["사용자"])
app.include_router(groups_router, prefix="/groups", tags=["그룹"])
app.include_router(repos_router, prefix="/repos", tags=["저장소"])
app.include_router(sync_router, prefix="/sync", tags=["동기화"])
app.include_router(presence_router, prefix="/presence", tags=["Presence"])
app.include_router(proxy_router, prefix="/proxy", tags=["파일 프록시"])
app.include_router(activity_router, prefix="/activity", tags=["활동 로그"])
app.include_router(tags_router, prefix="/tags", tags=["태그"])
app.include_router(shares_router, prefix="/shares", tags=["공유"])
app.include_router(notifications_router, prefix="/notifications", tags=["알림"])
app.include_router(approvals_router, prefix="/approvals", tags=["승인"])
app.include_router(admin_router, prefix="/admin", tags=["관리자"])
app.include_router(ws_router)


@app.get("/health")
def health_check():
    """서버 상태 확인"""
    return {"status": "ok", "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=settings.server.debug,
    )
