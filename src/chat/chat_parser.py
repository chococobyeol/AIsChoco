"""
채팅 메시지 파싱 및 필터링
"""

import re
import logging
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

from .base_client import ChatMessage

logger = logging.getLogger(__name__)


@dataclass
class FilterConfig:
    """필터 설정"""
    min_length: int = 1  # 최소 메시지 길이
    max_length: int = 500  # 최대 메시지 길이
    filter_bots: bool = True  # 봇 메시지 필터링
    filter_spam: bool = True  # 스팸 메시지 필터링
    blocked_keywords: list[str] = None  # 차단 키워드 목록
    
    def __post_init__(self):
        if self.blocked_keywords is None:
            self.blocked_keywords = []


class ChatParser:
    """채팅 메시지 파싱 및 필터링 클래스"""
    
    def __init__(self, filter_config: Optional[FilterConfig] = None):
        """
        Args:
            filter_config: 필터 설정 (None이면 기본 설정 사용)
        """
        self.filter_config = filter_config or FilterConfig()
        
        # 봇 패턴 (닉네임이 'bot', '봇'으로 끝나는 경우)
        self.bot_pattern = re.compile(r'(bot|봇)$', re.IGNORECASE)
        
        # 스팸 패턴 (같은 문자 반복, URL 등)
        self.spam_patterns = [
            re.compile(r'(.)\1{10,}'),  # 같은 문자 10번 이상 반복
            re.compile(r'https?://\S+'),  # URL (필요시 제외 가능)
        ]
    
    def parse(self, raw_message: dict, platform: str = "chzzk") -> Optional[ChatMessage]:
        """
        원시 메시지를 ChatMessage로 파싱

        Args:
            raw_message: WebSocket에서 수신한 원시 메시지 딕셔너리
            platform: 플랫폼 이름 (기본: chzzk)

        Returns:
            파싱된 ChatMessage 또는 None (파싱 실패 시)
        """
        try:
            # TODO: 실제 치지직 메시지 구조에 맞게 수정
            ts = raw_message.get("timestamp")
            if ts is None:
                ts = datetime.now()
            elif not isinstance(ts, datetime):
                # ms 또는 초 단위 숫자면 datetime으로 변환
                try:
                    n = float(ts)
                    ts = datetime.fromtimestamp(n / 1000 if n > 1e12 else n)
                except (TypeError, ValueError, OSError):
                    ts = datetime.now()
            message = ChatMessage(
                user=raw_message.get("user", ""),
                message=raw_message.get("message", ""),
                timestamp=ts,
                emoticons=raw_message.get("emoticons", []),
                channel_id=raw_message.get("channelId", ""),
                platform=platform,
                message_id=raw_message.get("messageId"),
            )
            
            return message
            
        except Exception as e:
            logger.error(f"메시지 파싱 실패: {e}, 원본: {raw_message}")
            return None
    
    def filter(self, message: ChatMessage) -> bool:
        """
        메시지 필터링
        
        Args:
            message: 필터링할 메시지
            
        Returns:
            True: 메시지 통과, False: 메시지 차단
        """
        # 길이 체크
        if len(message.message) < self.filter_config.min_length:
            return False
        
        if len(message.message) > self.filter_config.max_length:
            return False
        
        # 봇 필터링
        if self.filter_config.filter_bots:
            if self.bot_pattern.search(message.user):
                logger.debug(f"봇 메시지 차단: {message.user}")
                return False
        
        # 스팸 필터링
        if self.filter_config.filter_spam:
            for pattern in self.spam_patterns:
                if pattern.search(message.message):
                    logger.debug(f"스팸 메시지 차단: {message.message[:50]}")
                    return False
        
        # 키워드 필터링
        message_lower = message.message.lower()
        for keyword in self.filter_config.blocked_keywords:
            if keyword.lower() in message_lower:
                logger.debug(f"차단 키워드 발견: {keyword}")
                return False
        
        return True
    
    def parse_and_filter(self, raw_message: dict, platform: str = "chzzk") -> Optional[ChatMessage]:
        """
        메시지 파싱 및 필터링을 한 번에 수행

        Args:
            raw_message: WebSocket에서 수신한 원시 메시지 딕셔너리
            platform: 플랫폼 이름 (기본: chzzk)

        Returns:
            파싱되고 필터링된 ChatMessage 또는 None
        """
        message = self.parse(raw_message, platform=platform)
        if message and self.filter(message):
            return message
        return None
