"""
채팅 클라이언트 추상 기본 클래스
모든 플랫폼(치지직, 유튜브 등)의 채팅 클라이언트가 구현해야 하는 인터페이스
"""

from abc import ABC, abstractmethod
from typing import Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """채팅 메시지 데이터 클래스 (플랫폼 공통)"""
    user: str
    message: str
    timestamp: datetime
    emoticons: list[str]
    channel_id: str
    platform: str  # 플랫폼 이름 (chzzk, youtube 등)
    message_id: Optional[str] = None
    user_id: Optional[str] = None
    user_badge: Optional[str] = None  # 구독자 배지 등


class ChatClient(ABC):
    """채팅 클라이언트 추상 기본 클래스"""
    
    def __init__(
        self,
        channel_id: str,
        on_message: Optional[Callable[[ChatMessage], None]] = None,
        reconnect_delay: float = 5.0,
        max_reconnect_attempts: int = 10
    ):
        """
        Args:
            channel_id: 채널 ID (플랫폼별 형식 다를 수 있음)
            on_message: 메시지 수신 시 호출할 콜백 함수
            reconnect_delay: 재연결 지연 시간 (초)
            max_reconnect_attempts: 최대 재연결 시도 횟수
        """
        self.channel_id = channel_id
        self.on_message = on_message
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_attempts = max_reconnect_attempts
        
        # 연결 상태
        self.is_connected = False
        self.reconnect_attempts = 0
        self._running = False
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """플랫폼 이름 반환 (예: 'chzzk', 'youtube')"""
        pass
    
    @abstractmethod
    async def connect(self):
        """플랫폼별 연결 로직 구현"""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """플랫폼별 연결 종료 로직 구현"""
        pass
    
    @abstractmethod
    async def listen(self):
        """메시지 수신 루프 구현"""
        pass
    
    async def _reconnect(self) -> bool:
        """재연결 시도 (지수 백오프) - 공통 로직"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(
                f"[{self.platform_name}] 최대 재연결 시도 횟수 "
                f"({self.max_reconnect_attempts}) 초과"
            )
            return False
        
        delay = self.reconnect_delay * (2 ** self.reconnect_attempts)
        self.reconnect_attempts += 1
        
        logger.info(
            f"[{self.platform_name}] 재연결 시도 "
            f"{self.reconnect_attempts}/{self.max_reconnect_attempts} "
            f"({delay}초 후)"
        )
        import asyncio
        await asyncio.sleep(delay)
        
        try:
            await self.connect()
            return True
        except Exception as e:
            logger.error(f"[{self.platform_name}] 재연결 실패: {e}")
            return False
    
    async def start(self):
        """클라이언트 시작"""
        await self.connect()
        await self.listen()
    
    async def stop(self):
        """클라이언트 중지"""
        self._running = False
        await self.disconnect()
    
    def _create_message(
        self,
        user: str,
        message: str,
        timestamp: datetime,
        emoticons: list[str] = None,
        message_id: Optional[str] = None,
        user_id: Optional[str] = None,
        user_badge: Optional[str] = None
    ) -> ChatMessage:
        """ChatMessage 객체 생성 헬퍼 메서드"""
        return ChatMessage(
            user=user,
            message=message,
            timestamp=timestamp,
            emoticons=emoticons or [],
            channel_id=self.channel_id,
            platform=self.platform_name,
            message_id=message_id,
            user_id=user_id,
            user_badge=user_badge
        )
