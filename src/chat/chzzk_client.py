"""
치지직 Socket.IO 클라이언트
실시간 채팅 메시지를 수신합니다.

참고: https://chzzk.gitbook.io/chzzk/chzzk-api/session
"""

import asyncio
import json
import logging
from typing import Optional, Callable
from datetime import datetime

import socketio
import httpx

from .base_client import ChatClient, ChatMessage

logger = logging.getLogger(__name__)


class ChzzkSocketIOClient(ChatClient):
    """치지직 Socket.IO 클라이언트
    
    치지직은 WebSocket이 아닌 Socket.IO를 사용합니다.
    먼저 세션 생성 API를 호출하여 연결 URL을 받아야 합니다.
    """
    
    @property
    def platform_name(self) -> str:
        """플랫폼 이름"""
        return "chzzk"
    
    def __init__(
        self,
        channel_id: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        on_message: Optional[Callable[[ChatMessage], None]] = None,
        reconnect_delay: float = 5.0,
        max_reconnect_attempts: int = 10
    ):
        """
        Args:
            channel_id: 치지직 채널 ID
            client_id: Client 인증용 Client ID (Client 인증 시 필요)
            client_secret: Client 인증용 Client Secret (Client 인증 시 필요)
            access_token: Access Token (유저 인증 시 필요)
            on_message: 메시지 수신 시 호출할 콜백 함수
            reconnect_delay: 재연결 지연 시간 (초)
            max_reconnect_attempts: 최대 재연결 시도 횟수
            
        참고: https://chzzk.gitbook.io/chzzk/chzzk-api/session
        """
        super().__init__(channel_id, on_message, reconnect_delay, max_reconnect_attempts)
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        
        # Socket.IO 클라이언트
        self.sio: Optional[socketio.AsyncClient] = None
        self.session_url: Optional[str] = None
        self.session_key: Optional[str] = None
        
        # Open API 도메인 (참고사항: openapi.chzzk.naver.com, 하이픈 없음)
        self.api_base_url = "https://openapi.chzzk.naver.com"
        
    async def _get_session_url(self) -> str:
        """
        세션 생성 API를 호출하여 Socket.IO 연결 URL 획득
        
        참고: https://chzzk.gitbook.io/chzzk/chzzk-api/session
        """
        async with httpx.AsyncClient() as client:
            if self.access_token:
                # 유저 인증: Access Token 사용
                # GET /open/v1/sessions/auth
                headers = {"Authorization": f"Bearer {self.access_token}"}
                response = await client.get(
                    f"{self.api_base_url}/open/v1/sessions/auth",
                    headers=headers
                )
            elif self.client_id and self.client_secret:
                # Client 인증: Client ID/Secret 사용
                # GET /open/v1/sessions/auth/client
                # TODO: Client 인증 구현 (https://chzzk.gitbook.io/chzzk/chzzk-api/tips#client-api 참고)
                raise NotImplementedError("Client 인증은 아직 구현되지 않았습니다")
            else:
                raise ValueError("access_token 또는 (client_id, client_secret)이 필요합니다")
            
            response.raise_for_status()
            data = response.json()
            # 공통 응답: {"code": 200, "content": { "url": "..." }}
            body = data.get("content") if data.get("content") is not None else data
            return body["url"]
    
    async def connect(self):
        """Socket.IO 연결"""
        try:
            # 1. 세션 생성 API 호출하여 연결 URL 획득
            self.session_url = await self._get_session_url()
            logger.info(f"[{self.platform_name}] 세션 URL 획득 성공")
            
            # 2. Socket.IO 클라이언트 생성 및 연결
            self.sio = socketio.AsyncClient(
                reconnection=False,  # 수동 재연결 관리
                logger=False,
                engineio_logger=False
            )
            
            # 이벤트 핸들러 등록
            self.sio.on("connect", self._on_connect)
            self.sio.on("SYSTEM", self._on_system_message)
            self.sio.on("disconnect", self._on_disconnect)
            
            # Socket.IO 연결
            logger.info(f"[{self.platform_name}] Socket.IO 연결 시도")
            await self.sio.connect(
                self.session_url,
                transports=['websocket']
            )
            
            self.is_connected = True
            self.reconnect_attempts = 0
            logger.info(f"[{self.platform_name}] Socket.IO 연결 성공")
            
        except Exception as e:
            logger.error(f"[{self.platform_name}] 연결 실패: {e}")
            self.is_connected = False
            raise
    
    def _on_connect(self):
        """Socket.IO 연결 완료 시 호출"""
        logger.info(f"[{self.platform_name}] Socket.IO 연결 완료")
    
    def _on_disconnect(self):
        """Socket.IO 연결 종료 시 호출"""
        logger.warning(f"[{self.platform_name}] Socket.IO 연결 종료")
        self.is_connected = False
    
    async def _on_system_message(self, data):
        """
        시스템 메시지 수신 핸들러
        연결 완료 메시지에서 sessionKey를 추출하고 채널 구독
        문서: Event Type SYSTEM, Message Body { type, data }
        """
        try:
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    logger.debug(f"[{self.platform_name}] SYSTEM payload (non-JSON string): {data[:100]}")
                    return
            if not isinstance(data, dict):
                return
            msg_type = data.get("type")
            
            if msg_type == "connected":
                # 연결 완료 메시지: sessionKey 저장 및 채널·후원 구독
                self.session_key = data.get("data", {}).get("sessionKey")
                logger.info(f"[{self.platform_name}] 세션 키 획득: {self.session_key}")
                
                # 채널(채팅) 구독 요청
                await self._subscribe_channel()
                # 후원 이벤트 구독 (같은 세션, 같은 채널)
                await self._subscribe_donation()
                
            elif msg_type == "subscribed":
                # 구독 완료 메시지
                event_type = data.get("data", {}).get("eventType")
                channel_id = data.get("data", {}).get("channelId")
                logger.info(f"[{self.platform_name}] 채널 구독 완료: {event_type} - {channel_id}")
                
            elif msg_type == "unsubscribed":
                # 구독 취소 메시지
                logger.warning(f"[{self.platform_name}] 채널 구독 취소됨")
                
            elif msg_type == "revoked":
                # 권한 취소 메시지
                logger.error(f"[{self.platform_name}] 이벤트 권한 취소됨")
                
        except Exception as e:
            logger.error(f"[{self.platform_name}] 시스템 메시지 처리 오류: {e}")
    
    async def _subscribe_channel(self):
        """
        채널 구독 요청 (문서: POST /open/v1/sessions/events/subscribe/chat, Request Param sessionKey)
        """
        if not self.session_key:
            logger.error(f"[{self.platform_name}] 세션 키가 없어 구독할 수 없습니다")
            return
        if not self.access_token:
            logger.error(f"[{self.platform_name}] 구독 API 호출에 Access Token이 필요합니다")
            return

        # 문서: POST /open/v1/sessions/events/subscribe/chat, Request Param sessionKey
        url = f"{self.api_base_url}/open/v1/sessions/events/subscribe/chat"
        headers = {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}
        params = {"sessionKey": self.session_key, "channelId": self.channel_id}

        async with httpx.AsyncClient() as client:
            response = await client.post(url, params=params, headers=headers)
            response.raise_for_status()
        logger.info(f"[{self.platform_name}] 채널 구독 요청 완료: {self.channel_id}")

        # 채팅 메시지 이벤트 핸들러 등록 (소켓으로 CHAT 이벤트 수신)
        self.sio.on("CHAT", self._on_chat_message)

    async def _subscribe_donation(self):
        """
        후원 이벤트 구독 (문서: POST /open/v1/sessions/events/subscribe/donation)
        채팅과 동일 세션에 channelId로 구독.
        """
        if not self.session_key:
            return
        if not self.access_token:
            logger.warning(f"[{self.platform_name}] 후원 구독에 Access Token이 필요합니다")
            return
        # 문서: POST .../subscribe/donation, Request Param sessionKey (후원 조회 Scope)
        url = f"{self.api_base_url}/open/v1/sessions/events/subscribe/donation"
        headers = {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}
        params = {"sessionKey": self.session_key, "channelId": self.channel_id}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, params=params, headers=headers)
                response.raise_for_status()
            logger.info(f"[{self.platform_name}] 후원 이벤트 구독 요청 완료: {self.channel_id}")
            self.sio.on("DONATION", self._on_donation_message)
        except Exception as e:
            logger.warning(f"[{self.platform_name}] 후원 구독 실패 (채팅만 사용): {e}")

    async def _on_donation_message(self, data):
        """
        후원 이벤트 수신 (Event Type: DONATION)
        문서: donatorNickname, payAmount, donationText 등
        채팅 큐와 동일하게 on_message로 넘겨 AI/TTS가 감사 반응하도록 함.
        """
        try:
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    return
            if not isinstance(data, dict):
                return
            nickname = (data.get("donatorNickname") or "").strip() or "시청자"
            pay_amount = (data.get("payAmount") or "").strip() or "0"
            donation_text = (data.get("donationText") or "").strip()
            if donation_text:
                message_text = f"{pay_amount}원 후원: {donation_text}"
            else:
                message_text = f"{pay_amount}원 후원했습니다"
            timestamp = datetime.now()
            msg = self._create_message(
                user=nickname,
                message=message_text,
                timestamp=timestamp,
                emoticons=[],
                message_id=None,
                user_id=data.get("donatorChannelId"),
                user_badge="donation",
            )
            if self.on_message:
                cb = self.on_message(msg)
                if asyncio.iscoroutine(cb):
                    await cb
            logger.info(f"[{self.platform_name}] 후원 수신: {nickname} {pay_amount}원")
        except Exception as e:
            logger.error(f"[{self.platform_name}] 후원 메시지 처리 오류: {e}", exc_info=True)
    
    async def _on_chat_message(self, data):
        """
        채팅 메시지 수신 핸들러
        문서: Event Type CHAT, Message Body (channelId, profile, content, messageTime 등)
        """
        try:
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    logger.debug(f"[{self.platform_name}] CHAT payload (non-JSON string): {data[:100]}")
                    return
            if not isinstance(data, dict):
                return
            profile = data.get("profile", {})
            nickname = profile.get("nickname", "")
            content = data.get("content", "")
            message_time = data.get("messageTime", 0)  # Int64 (ms)
            
            # emojis는 Map 형식: {key: emoji_id, value: emoji_url}
            emojis_map = data.get("emojis", {})
            emoticons = list(emojis_map.keys()) if emojis_map else []
            
            # timestamp 변환 (ms → datetime)
            timestamp = datetime.fromtimestamp(message_time / 1000) if message_time else datetime.now()
            
            # ChatMessage 생성
            message = self._create_message(
                user=nickname,
                message=content,
                timestamp=timestamp,
                emoticons=emoticons,
                message_id=None,  # API에 messageId 필드 없음
                user_id=data.get("senderChannelId"),
                user_badge=str(data.get("userRoleCode", ""))
            )
            
            if self.on_message:
                cb = self.on_message(message)
                if asyncio.iscoroutine(cb):
                    await cb
                
        except Exception as e:
            logger.error(f"[{self.platform_name}] 채팅 메시지 처리 오류: {e}, 데이터: {data}")
    
    async def disconnect(self):
        """Socket.IO 연결 종료"""
        if self.sio:
            await self.sio.disconnect()
            self.is_connected = False
            logger.info(f"[{self.platform_name}] Socket.IO 연결 종료")
    
    async def listen(self):
        """메시지 수신 루프 (Socket.IO는 이벤트 기반이므로 대기만 함)"""
        self._running = True
        
        while self._running:
            try:
                if not self.is_connected:
                    if not await super()._reconnect():
                        break
                    continue
                
                # Socket.IO는 이벤트 기반이므로 연결 유지만 하면 됨
                # 메시지는 _on_chat_message 핸들러에서 자동 처리됨
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"[{self.platform_name}] 예상치 못한 오류: {e}")
                self.is_connected = False
                await asyncio.sleep(1)
    
