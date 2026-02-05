"""
치지직 WebSocket 클라이언트 사용 예제
"""

import asyncio
import logging
from chzzk_client import ChzzkWebSocketClient, ChatMessage
from chat_parser import ChatParser, FilterConfig

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


async def on_chat_message(message: ChatMessage):
    """채팅 메시지 수신 시 호출되는 콜백"""
    print(f"[{message.timestamp}] {message.user}: {message.message}")


async def main():
    """메인 함수"""
    # 필터 설정
    filter_config = FilterConfig(
        min_length=1,
        max_length=500,
        filter_bots=True,
        filter_spam=True,
        blocked_keywords=["스팸", "광고"]
    )
    
    parser = ChatParser(filter_config)
    
    # WebSocket 클라이언트 생성
    # TODO: 실제 채널 ID와 액세스 토큰으로 변경
    client = ChzzkWebSocketClient(
        channel_id="YOUR_CHANNEL_ID",  # 실제 채널 ID로 변경
        access_token="YOUR_ACCESS_TOKEN",  # 필요시 토큰 추가
        on_message=on_chat_message,
        reconnect_delay=5.0,
        max_reconnect_attempts=10
    )
    
    try:
        # 클라이언트 시작
        await client.start()
    except KeyboardInterrupt:
        print("\n클라이언트 종료 중...")
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
