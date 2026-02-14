"""
치지직 채팅 수신 예제

.env에 CHZZK_CHANNEL_ID, CHZZK_ACCESS_TOKEN 설정 후 실행.
Access Token은 chzzk_auth_example.py 로 먼저 발급받으세요.

실행: python examples/chzzk_chat_example.py  (프로젝트 루트에서)
"""

import sys
from pathlib import Path

# 프로젝트 루트를 path에 넣어서 'import src' 가능하게 함
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import os

from dotenv import load_dotenv

from src.chat import ChatClientFactory, ChatMessage
from src.utils import setup_logging

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
LOG_DIR = setup_logging()


async def on_chat_message(message: ChatMessage):
    print(f"[{message.timestamp}] {message.user}: {message.message}")


async def main():
    channel_id = os.getenv("CHZZK_CHANNEL_ID")
    access_token = os.getenv("CHZZK_ACCESS_TOKEN")
    if not channel_id or not access_token:
        print("❌ .env에 CHZZK_CHANNEL_ID, CHZZK_ACCESS_TOKEN을 설정해주세요.")
        print("   토큰 발급: python examples/chzzk_auth_example.py")
        return

    client = ChatClientFactory.create(
        platform="chzzk",
        channel_id=channel_id,
        access_token=access_token,
        on_message=on_chat_message,
        reconnect_delay=5.0,
        max_reconnect_attempts=10,
    )

    print(f"플랫폼: {client.platform_name}, 채널: {channel_id}")
    print(f"로그 저장 경로: {LOG_DIR}")
    print("채팅 수신 중... (종료: Ctrl+C)\n")
    try:
        await client.start()
    except KeyboardInterrupt:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
