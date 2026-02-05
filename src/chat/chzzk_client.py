"""
치지직 WebSocket 클라이언트
실시간 채팅 메시지를 수신합니다.
"""

import asyncio
import json
import logging
from typing import Optional, Callable
from datetime import datetime

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from .base_client import ChatClient, ChatMessage

logger = logging.getLogger(__name__)


class ChzzkWebSocketClient(ChatClient):
    """치지직 WebSocket 클라이언트"""
    
    @property
    def platform_name(self) -> str:
        """플랫폼 이름"""
        return "chzzk"
    
    def __init__(
        self,
        channel_id: str,
        access_token: Optional[str] = None,
        on_message: Optional[Callable[[ChatMessage], None]] = None,
        reconnect_delay: float = 5.0,
        max_reconnect_attempts: int = 10
    ):
        """
        Args:
            channel_id: 치지직 채널 ID
            access_token: API 액세스 토큰 (필요한 경우)
            on_message: 메시지 수신 시 호출할 콜백 함수
            reconnect_delay: 재연결 지연 시간 (초)
            max_reconnect_attempts: 최대 재연결 시도 횟수
        """
        super().__init__(channel_id, on_message, reconnect_delay, max_reconnect_attempts)
        self.access_token = access_token
        
        # WebSocket 연결
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        
        # WebSocket 엔드포인트 (실제 API 문서 확인 후 수정 필요)
        # TODO: 실제 치지직 WebSocket 엔드포인트로 변경
        # 확인 방법: docs/CHZZK_API_RESEARCH.md 참고
        # 1. 브라우저 DevTools에서 WebSocket 연결 확인
        # 2. 기존 오픈소스 프로젝트 분석 (chzzk-tts 등)
        self.ws_url = f"wss://kr-ss1.chat.naver.com/chat"  # 예시 URL (수정 필요)
        
    async def connect(self):
        """WebSocket 연결"""
        try:
            # TODO: 실제 인증 헤더 추가 필요
            headers = {}
            if self.access_token:
                headers["Authorization"] = f"Bearer {self.access_token}"
            
            logger.info(f"[{self.platform_name}] WebSocket 연결 시도: {self.ws_url}")
            self.websocket = await websockets.connect(
                self.ws_url,
                extra_headers=headers
            )
            self.is_connected = True
            self.reconnect_attempts = 0
            logger.info(f"[{self.platform_name}] WebSocket 연결 성공")
            
            # 채널 구독 메시지 전송 (실제 포맷 확인 필요)
            await self._subscribe_channel()
            
        except Exception as e:
            logger.error(f"WebSocket 연결 실패: {e}")
            self.is_connected = False
            raise
    
    async def _subscribe_channel(self):
        """채널 구독 메시지 전송"""
        # TODO: 실제 치지직 구독 메시지 포맷 확인 후 수정
        # 확인 방법: docs/CHZZK_API_RESEARCH.md 참고
        # 브라우저 DevTools에서 실제 구독 메시지 확인
        subscribe_message = {
            "type": "subscribe",
            "channelId": self.channel_id
        }
        await self.websocket.send(json.dumps(subscribe_message))
        logger.info(f"채널 구독 요청: {self.channel_id}")
    
    async def disconnect(self):
        """WebSocket 연결 종료"""
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False
            logger.info(f"[{self.platform_name}] WebSocket 연결 종료")
    
    async def _handle_message(self, raw_message: str):
        """수신한 메시지 처리"""
        try:
            data = json.loads(raw_message)
            
            # TODO: 실제 메시지 구조에 맞게 파싱 로직 수정
            # 확인 방법: docs/CHZZK_API_RESEARCH.md 참고
            # 브라우저 DevTools에서 실제 메시지 포맷 확인
            # 예시 구조 (실제 구조 확인 필요)
            if data.get("type") == "chat":
                message = self._create_message(
                    user=data.get("user", ""),
                    message=data.get("message", ""),
                    timestamp=datetime.fromisoformat(
                        data.get("timestamp", datetime.now().isoformat())
                    ),
                    emoticons=data.get("emoticons", []),
                    message_id=data.get("messageId"),
                    user_id=data.get("userId")
                )
                
                if self.on_message:
                    await self.on_message(message)
                    
        except json.JSONDecodeError as e:
            logger.error(f"메시지 JSON 파싱 실패: {e}, 원본: {raw_message}")
        except Exception as e:
            logger.error(f"메시지 처리 중 오류: {e}")
    
    async def listen(self):
        """메시지 수신 루프"""
        self._running = True
        
        while self._running:
            try:
                if not self.is_connected:
                    if not await super()._reconnect():
                        break
                    continue
                
                # 메시지 수신 (타임아웃 설정)
                raw_message = await asyncio.wait_for(
                    self.websocket.recv(),
                    timeout=30.0
                )
                
                await self._handle_message(raw_message)
                
            except asyncio.TimeoutError:
                # 타임아웃 시 핑 메시지 전송 (연결 유지)
                try:
                    await self.websocket.ping()
                except:
                    self.is_connected = False
                    logger.warning("연결 타임아웃, 재연결 시도")
                    
            except ConnectionClosed:
                logger.warning("WebSocket 연결 종료됨")
                self.is_connected = False
                
            except WebSocketException as e:
                logger.error(f"WebSocket 오류: {e}")
                self.is_connected = False
                
            except Exception as e:
                logger.error(f"예상치 못한 오류: {e}")
                self.is_connected = False
    
