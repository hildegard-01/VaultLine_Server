"""
WebSocket 연결 관리자

역할:
- 사용자별 WebSocket 연결 관리 (다중 기기 지원)
- 메시지 라우팅 (특정 사용자 / 브로드캐스트)
- heartbeat 수신, file_request/response 중계, notification 전달
"""

import json
import asyncio
from datetime import datetime, timezone

from fastapi import WebSocket


class ConnectionManager:
    """WebSocket 연결 관리 싱글턴"""

    def __init__(self):
        # user_id → [WebSocket, ...]  (한 사용자 다중 연결 허용)
        self._connections: dict[int, list[WebSocket]] = {}
        # 파일 요청 대기 큐: req_id → asyncio.Future
        self._file_requests: dict[str, asyncio.Future] = {}
        # SVN 프록시: session_id → {owner_user_id, recipient_user_id, share_id}
        self._svn_sessions: dict[str, dict] = {}
        # share_id → owner_user_id (provider 등록 테이블)
        self._share_providers: dict[int, int] = {}

    async def connect(self, ws: WebSocket, user_id: int) -> None:
        """WebSocket 연결 등록"""
        await ws.accept()
        if user_id not in self._connections:
            self._connections[user_id] = []
        self._connections[user_id].append(ws)

    def disconnect(self, ws: WebSocket, user_id: int) -> None:
        """WebSocket 연결 해제"""
        if user_id in self._connections:
            self._connections[user_id] = [c for c in self._connections[user_id] if c is not ws]
            if not self._connections[user_id]:
                del self._connections[user_id]
        # SVN provider 등록 해제
        for sid in [k for k, v in self._share_providers.items() if v == user_id]:
            del self._share_providers[sid]

    def is_user_connected(self, user_id: int) -> bool:
        """사용자 WebSocket 연결 여부"""
        return user_id in self._connections and len(self._connections[user_id]) > 0

    @property
    def online_user_ids(self) -> set[int]:
        """현재 연결된 사용자 ID 목록"""
        return set(self._connections.keys())

    async def send_to_user(self, user_id: int, message: dict) -> bool:
        """특정 사용자에게 메시지 전송 (모든 연결)"""
        if user_id not in self._connections:
            return False
        data = json.dumps(message, ensure_ascii=False, default=str)
        for ws in self._connections[user_id]:
            try:
                await ws.send_text(data)
            except Exception:
                pass  # 끊어진 연결은 disconnect에서 정리
        return True

    async def broadcast(self, message: dict, exclude: int | None = None) -> None:
        """전체 연결에 메시지 브로드캐스트"""
        data = json.dumps(message, ensure_ascii=False, default=str)
        for user_id, connections in self._connections.items():
            if user_id == exclude:
                continue
            for ws in connections:
                try:
                    await ws.send_text(data)
                except Exception:
                    pass

    # ─── 파일 요청/응답 중계 ───

    async def request_file(self, owner_user_id: int, req_id: str, repo_id: int, path: str, action: str = "preview") -> dict | None:
        """소유자 앱에 파일 요청 → 응답 대기 (타임아웃 30초)"""
        if not self.is_user_connected(owner_user_id):
            return None

        # Future 등록
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._file_requests[req_id] = future

        # 소유자에게 요청 전송
        await self.send_to_user(owner_user_id, {
            "type": "file_request",
            "req_id": req_id,
            "repo_id": repo_id,
            "path": path,
            "action": action,
        })

        try:
            result = await asyncio.wait_for(future, timeout=30.0)
            return result
        except asyncio.TimeoutError:
            return None
        finally:
            self._file_requests.pop(req_id, None)

    def resolve_file_response(self, req_id: str, data: dict) -> None:
        """소유자 앱의 file_response 수신 → Future 완료"""
        future = self._file_requests.get(req_id)
        if future and not future.done():
            future.set_result(data)

    async def handle_message(self, user_id: int, raw: str, db_session_factory) -> None:
        """수신 메시지 라우팅"""
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return

        msg_type = msg.get("type")

        if msg_type == "heartbeat":
            # DB에 heartbeat 갱신
            from db.models import User
            db = db_session_factory()
            try:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    now = datetime.now(timezone.utc)
                    user.last_heartbeat = now
                    user.is_online = True
                    user.last_seen = now
                    db.commit()
            finally:
                db.close()

        elif msg_type == "file_response":
            req_id = msg.get("req_id")
            if req_id:
                self.resolve_file_response(req_id, msg)

        elif msg_type == "preview_push":
            # 미리보기 캐시 저장 (Week 4에서 구현)
            pass

        # ── SVN 프록시 메시지 ──

        elif msg_type == "svn_register_provider":
            # 소유자: 담당 share_id 목록 등록
            share_ids = msg.get("share_ids", [])
            # 기존 등록 제거
            for sid in [k for k, v in self._share_providers.items() if v == user_id]:
                del self._share_providers[sid]
            for sid in share_ids:
                self._share_providers[int(sid)] = user_id

        elif msg_type == "svn_new_session":
            # 수신자: 새 SVN 세션 요청
            session_id = msg.get("session_id")
            share_id = int(msg.get("share_id", 0))
            if not session_id or not share_id:
                return

            owner_user_id = self._share_providers.get(share_id)
            if not owner_user_id:
                # DB 조회 fallback
                from db.models import Share
                from db.database import SessionLocal
                db = SessionLocal()
                try:
                    share = db.query(Share).filter(Share.id == share_id).first()
                    if share:
                        owner_user_id = share.created_by
                finally:
                    db.close()

            if not owner_user_id or not self.is_user_connected(owner_user_id):
                await self.send_to_user(user_id, {
                    "type": "svn_error",
                    "session_id": session_id,
                    "error": "소유자가 오프라인 상태입니다. 잠시 후 다시 시도해 주세요.",
                })
                return

            self._svn_sessions[session_id] = {
                "owner_user_id": owner_user_id,
                "recipient_user_id": user_id,
                "share_id": share_id,
            }
            await self.send_to_user(owner_user_id, {
                "type": "svn_connect",
                "session_id": session_id,
                "share_id": share_id,
            })

        elif msg_type == "svn_data":
            # 양방향 데이터 중계
            session_id = msg.get("session_id")
            data = msg.get("data")
            if not session_id or data is None:
                return
            session = self._svn_sessions.get(session_id)
            if not session:
                return
            target_id = (
                session["recipient_user_id"]
                if user_id == session["owner_user_id"]
                else session["owner_user_id"]
            )
            await self.send_to_user(target_id, {
                "type": "svn_data",
                "session_id": session_id,
                "data": data,
            })

        elif msg_type == "svn_close":
            # 세션 종료 중계
            session_id = msg.get("session_id")
            if not session_id:
                return
            session = self._svn_sessions.pop(session_id, None)
            if not session:
                return
            target_id = (
                session["recipient_user_id"]
                if user_id == session["owner_user_id"]
                else session["owner_user_id"]
            )
            await self.send_to_user(target_id, {
                "type": "svn_close",
                "session_id": session_id,
            })


# 전역 싱글턴
manager = ConnectionManager()
