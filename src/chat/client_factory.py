"""
채팅 클라이언트 팩토리
플랫폼별 클라이언트를 생성하는 팩토리 패턴
"""

from typing import Optional, Dict, Any
from .base_client import ChatClient
from .chzzk_client import ChzzkWebSocketClient

# TODO: 나중에 추가할 플랫폼들
# from .youtube_client import YouTubeChatClient
# from .twitch_client import TwitchChatClient


class ChatClientFactory:
    """채팅 클라이언트 팩토리 클래스"""
    
    _platforms: Dict[str, type[ChatClient]] = {
        "chzzk": ChzzkWebSocketClient,
        # TODO: 다른 플랫폼 추가
        # "youtube": YouTubeChatClient,
        # "twitch": TwitchChatClient,
    }
    
    @classmethod
    def create(
        cls,
        platform: str,
        channel_id: str,
        **kwargs
    ) -> ChatClient:
        """
        플랫폼별 채팅 클라이언트 생성
        
        Args:
            platform: 플랫폼 이름 ("chzzk", "youtube" 등)
            channel_id: 채널 ID
            **kwargs: 플랫폼별 추가 설정 (access_token 등)
            
        Returns:
            ChatClient 인스턴스
            
        Raises:
            ValueError: 지원하지 않는 플랫폼인 경우
        """
        if platform not in cls._platforms:
            supported = ", ".join(cls._platforms.keys())
            raise ValueError(
                f"지원하지 않는 플랫폼: {platform}. "
                f"지원 플랫폼: {supported}"
            )
        
        client_class = cls._platforms[platform]
        return client_class(channel_id=channel_id, **kwargs)
    
    @classmethod
    def register_platform(cls, platform: str, client_class: type[ChatClient]):
        """
        새로운 플랫폼 등록 (런타임에 플랫폼 추가 가능)
        
        Args:
            platform: 플랫폼 이름
            client_class: ChatClient를 상속한 클라이언트 클래스
        """
        if not issubclass(client_class, ChatClient):
            raise TypeError(
                f"client_class는 ChatClient를 상속해야 합니다. "
                f"현재: {client_class.__mro__}"
            )
        cls._platforms[platform] = client_class
    
    @classmethod
    def get_supported_platforms(cls) -> list[str]:
        """지원하는 플랫폼 목록 반환"""
        return list(cls._platforms.keys())
