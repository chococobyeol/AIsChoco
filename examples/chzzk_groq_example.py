"""
치지직 채팅 수신 → Groq 호출 → 답변+감정 출력 → TTS wav 저장

.env에 CHZZK_CHANNEL_ID, CHZZK_ACCESS_TOKEN, GROQ_API_KEY 설정 후 실행.
실행: python examples/chzzk_groq_example.py  (프로젝트 루트에서)

TTS: Qwen3-TTS Base 클로닝. assets/voice_samples/ref.wav + ref_text.txt 필요. 감정별 ref_happy.wav 등 있으면 사용.
C: 공간 부족 시 .env에 HF_HOME=D:\\경로 또는 TTSService(hf_home="D:/cache/hf") 로 캐시 경로 지정.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from src.chat import ChatClientFactory, ChatMessage
from src.ai import GroqClient, AIResponse
from src.tts import TTSService

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _groq_reply(client: GroqClient, message: ChatMessage) -> AIResponse:
    """동기 Groq 호출 (asyncio.to_thread에서 사용)"""
    return client.reply(message.message, user_name=message.user)


async def on_chat_message(groq_client: GroqClient, tts_service: TTSService, message: ChatMessage):
    """채팅 수신 시 Groq로 답변 생성 → 출력 → TTS로 wav 저장"""
    print(f"\n[{message.timestamp}] {message.user}: {message.message}")
    try:
        ai_response = await asyncio.to_thread(
            _groq_reply, groq_client, message
        )
        print(f"  → [감정:{ai_response.emotion}] {ai_response.response}")
        print(f"  (처리: {ai_response.processing_time:.2f}s)")
        try:
            out_path = await asyncio.to_thread(
                tts_service.synthesize_to_file,
                ai_response.response,
                emotion=ai_response.emotion,
            )
            print(f"  TTS 저장: {out_path}")
        except Exception as tts_e:
            logger.exception("TTS 변환 중 오류: %s", tts_e)
            print(f"  TTS 오류: {tts_e}")
    except Exception as e:
        logger.exception("Groq 처리 중 오류: %s", e)
        print(f"  → 오류: {e}")


async def main():
    channel_id = os.getenv("CHZZK_CHANNEL_ID")
    access_token = os.getenv("CHZZK_ACCESS_TOKEN")
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not channel_id or not access_token:
        print("❌ .env에 CHZZK_CHANNEL_ID, CHZZK_ACCESS_TOKEN을 설정해주세요.")
        print("   토큰 발급: python examples/chzzk_auth_example.py")
        return
    if not groq_key or groq_key == "여기에-groq-api-key-입력":
        print("❌ .env에 GROQ_API_KEY를 설정해주세요.")
        return

    groq_client = GroqClient()
    tts_service = TTSService()
    client = ChatClientFactory.create(
        platform="chzzk",
        channel_id=channel_id,
        access_token=access_token,
        on_message=lambda msg: on_chat_message(groq_client, tts_service, msg),
        reconnect_delay=5.0,
        max_reconnect_attempts=10,
    )

    print(f"플랫폼: {client.platform_name}, 채널: {channel_id}")
    print("채팅 수신 중... Groq 답변 후 TTS로 wav 저장 (종료: Ctrl+C)\n")
    try:
        await client.start()
    except KeyboardInterrupt:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
