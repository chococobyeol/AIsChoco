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
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from src.chat import ChatClientFactory, ChatMessage
from src.ai import GroqClient, AIResponse
from src.tts import TTSService
from src.vtuber import VTSClient

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _groq_reply(client: GroqClient, message: ChatMessage) -> AIResponse:
    """동기 Groq 호출 (asyncio.to_thread에서 사용)"""
    return client.reply(message.message, user_name=message.user)


async def on_chat_message(groq_client: GroqClient, tts_service: TTSService, vts_client: Optional[VTSClient], message: ChatMessage):
    """채팅 수신 시 Groq → 답변 출력 → TTS wav 저장·재생 → VTS 감정 포즈"""
    print(f"\n[{message.timestamp}] {message.user}: {message.message}")
    try:
        ai_response = await asyncio.to_thread(
            _groq_reply, groq_client, message
        )
        print(f"  → [감정:{ai_response.emotion}] {ai_response.response}")
        print(f"  (처리: {ai_response.processing_time:.2f}s)")
        if vts_client:
            try:
                await vts_client.set_emotion(ai_response.emotion)
            except Exception as vts_e:
                logger.debug("VTS 포즈 실패: %s", vts_e)
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
    root = Path(__file__).resolve().parent.parent
    pose_config = root / "config" / "pose_mapping.json"
    vts_client = VTSClient() if pose_config.exists() else None
    if vts_client:
        print("VTube Studio 포즈 연동: config/pose_mapping.json 사용")
    client = ChatClientFactory.create(
        platform="chzzk",
        channel_id=channel_id,
        access_token=access_token,
        on_message=lambda msg: on_chat_message(groq_client, tts_service, vts_client, msg),
        reconnect_delay=5.0,
        max_reconnect_attempts=10,
    )

    print(f"플랫폼: {client.platform_name}, 채널: {channel_id}")
    print("채팅 수신 중... Groq → TTS 재생" + (" + VTS 포즈" if vts_client else "") + " (종료: Ctrl+C)\n")
    try:
        await client.start()
    except KeyboardInterrupt:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
