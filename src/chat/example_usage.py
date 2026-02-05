"""
채팅 클라이언트 사용 예제
다양한 플랫폼 지원 예제
"""

import asyncio
import logging
from chat import (
    ChatClientFactory,
    ChatMessage,
    ChatParser,
    FilterConfig
)

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
    
    # 팩토리를 사용하여 클라이언트 생성 (플랫폼 변경이 쉬움)
    # TODO: 실제 채널 ID와 액세스 토큰으로 변경
    # 참고: https://chzzk.gitbook.io/chzzk/chzzk-api/session
    client = ChatClientFactory.create(
        platform="chzzk",  # "youtube", "twitch" 등으로 쉽게 변경 가능
        channel_id="YOUR_CHANNEL_ID",  # 실제 채널 ID로 변경
        access_token="YOUR_ACCESS_TOKEN",  # Access Token 필요
        # 또는 client_id, client_secret 사용 (Client 인증)
        on_message=on_chat_message,
        reconnect_delay=5.0,
        max_reconnect_attempts=10
    )
    
    print(f"지원 플랫폼: {ChatClientFactory.get_supported_platforms()}")
    print(f"현재 플랫폼: {client.platform_name}")
    
    try:
        # 클라이언트 시작
        await client.start()
    except KeyboardInterrupt:
        print("\n클라이언트 종료 중...")
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
