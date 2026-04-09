"""
WebSocket 엔드포인트 — /ws 경로
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from datetime import datetime, timezone

from db.database import SessionLocal
from db.models import User
from utils.security import decode_access_token
from ws.manager import manager

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str = Query(...)):
    """
    WebSocket 연결 — 쿼리 파라미터로 JWT 인증
    예: ws://localhost:8080/ws?token={access_token}
    """
    # JWT 인증
    payload = decode_access_token(token)
    if payload is None:
        await ws.close(code=4001, reason="인증 실패")
        return

    user_id = int(payload["sub"])

    # 사용자 상태 확인
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id, User.status == "active").first()
        if user is None:
            await ws.close(code=4001, reason="사용자를 찾을 수 없습니다")
            return

        # 온라인 상태 갱신
        now = datetime.now(timezone.utc)
        user.is_online = True
        user.last_heartbeat = now
        user.last_seen = now
        db.commit()
    finally:
        db.close()

    # 연결 등록
    await manager.connect(ws, user_id)

    try:
        while True:
            raw = await ws.receive_text()
            await manager.handle_message(user_id, raw, SessionLocal)
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(ws, user_id)

        # 오프라인 상태 갱신 (모든 연결이 끊긴 경우)
        if not manager.is_user_connected(user_id):
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    user.is_online = False
                    user.last_seen = datetime.now(timezone.utc)
                    db.commit()
            finally:
                db.close()
