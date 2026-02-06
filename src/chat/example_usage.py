"""
채팅 클라이언트 사용 예제 (다중 플랫폼)

플랫폼을 바꿔가며 사용하는 예제입니다.
- platform: "chzzk", "youtube", "twitch" 등
- 플랫폼별 channel_id, access_token 등은 아래 kwargs 자리에서 설정하세요.
  필요하면 .env에서 읽어와서 넘기면 됩니다.
"""

import asyncio
import logging

from . import (
    ChatClientFactory,
    ChatMessage,
    ChatParser,
    FilterConfig,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


async def on_chat_message(message: ChatMessage):
    """채팅 메시지 수신 시 호출되는 콜백"""
    print(f"[{message.timestamp}] {message.user}: {message.message}")


async def main():
    """메인 함수"""
    filter_config = FilterConfig(
        min_length=1,
        max_length=500,
        filter_bots=True,
        filter_spam=True,
        blocked_keywords=["스팸", "광고"],
    )
    parser = ChatParser(filter_config)

    # 플랫폼별로 channel_id, access_token 등만 바꿔서 사용
    client = ChatClientFactory.create(
        platform="chzzk",  # "youtube", "twitch" 등으로 변경
        channel_id="YOUR_CHANNEL_ID",
        access_token="YOUR_ACCESS_TOKEN",
        # 플랫폼별 추가 인자: client_id, client_secret 등
        on_message=on_chat_message,
        reconnect_delay=5.0,
        max_reconnect_attempts=10,
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
