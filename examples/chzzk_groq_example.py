"""
치지직 채팅 수신 → 큐 적재 → 말 끝난 뒤 일괄 처리(합치기/걸러내기) → 히스토리 + Groq → TTS 재생

.env에 CHZZK_CHANNEL_ID, CHZZK_ACCESS_TOKEN, GROQ_API_KEY 설정 후 실행.
실행: python examples/chzzk_groq_example.py  (프로젝트 루트에서)

- 채팅은 큐에만 쌓고, 말하기가 끝난 뒤에만 쌓인 채팅을 한꺼번에 처리합니다.
- Groq가 도배/스팸을 걸러내고 비슷한 내용을 묶어 답변 1개만 생성합니다 (한 문장이 길어도 됨).
- 대화 히스토리(토큰 기반 + 요약 + RAG용 백업)를 유지합니다.
립싱크: .env에 TTS_OUTPUT_DEVICE=VB-Audio Virtual Cable 등으로 TTS 출력을 가상 케이블로 두고, VTS 오디오 입력을 해당 장치로 설정.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from src.chat import ChatClientFactory, ChatMessage
from src.ai import GroqClient, AIResponse, ChatHistory
from src.tts import TTSService
from src.vtuber import VTSClient

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _tts_and_play(tts_service: TTSService, text: str, emotion: str):
    """동기: TTS 생성 후 재생(끝날 때까지 대기). asyncio.to_thread에서 호출."""
    tts_service.synthesize_to_file(text, emotion=emotion, play=True)


async def reply_worker(
    queue: asyncio.Queue,
    groq_client: GroqClient,
    tts_service: TTSService,
    vts_client: Optional[VTSClient],
    chat_history: ChatHistory,
):
    """
    큐에서 메시지를 꺼내, 말 끝난 뒤에만 일괄 처리.
    1) 한 개 get(대기) → 나머지 전부 drain
    2) 히스토리에 user 추가, flush_summary, context 획득
    3) reply_batch(합치기/걸러내기) → 답변 1개
    4) 해당 답변: 히스토리에 assistant 추가 → TTS+재생 → VTS 감정
    5) flush_summary 한 번 더 후 반복
    """
    while True:
        try:
            first = await queue.get()
            pending: List[ChatMessage] = [first]
            while True:
                try:
                    msg = queue.get_nowait()
                    pending.append(msg)
                except asyncio.QueueEmpty:
                    break

            for m in pending:
                print(f"  [대기] {m.user}: {m.message}")
                chat_history.add_user_message(m.user or "?", m.message or "")

            chat_history.flush_summary(groq_client)
            context = chat_history.get_context_messages()

            replies = await asyncio.to_thread(
                groq_client.reply_batch, pending, context
            )

            for ai_response in replies:
                if not (ai_response.response or "").strip():
                    continue
                chat_history.add_assistant_message(ai_response.response)
                print(f"  → [감정:{ai_response.emotion}] {ai_response.response}")
                if vts_client:
                    try:
                        await vts_client.set_emotion(ai_response.emotion)
                    except Exception as vts_e:
                        logger.debug("VTS 포즈 실패: %s", vts_e)
                try:
                    await asyncio.to_thread(
                        _tts_and_play,
                        tts_service,
                        ai_response.response,
                        ai_response.emotion,
                    )
                except Exception as tts_e:
                    logger.exception("TTS 오류: %s", tts_e)
            chat_history.flush_summary(groq_client)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.exception("reply_worker 오류: %s", e)


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
    chat_history = ChatHistory()
    root = Path(__file__).resolve().parent.parent
    pose_config = root / "config" / "pose_mapping.json"
    vts_client = VTSClient() if pose_config.exists() else None
    if vts_client:
        print("VTube Studio 포즈 연동: config/pose_mapping.json 사용")

    queue: asyncio.Queue = asyncio.Queue()
    worker_task = asyncio.create_task(
        reply_worker(queue, groq_client, tts_service, vts_client, chat_history)
    )

    def on_message(msg: ChatMessage):
        queue.put_nowait(msg)

    client = ChatClientFactory.create(
        platform="chzzk",
        channel_id=channel_id,
        access_token=access_token,
        on_message=on_message,
        reconnect_delay=5.0,
        max_reconnect_attempts=10,
    )

    print(f"플랫폼: {client.platform_name}, 채널: {channel_id}")
    print("채팅 수신 중... (큐 → 말 끝난 뒤 일괄 처리 + 히스토리) (종료: Ctrl+C)\n")
    try:
        await client.start()
    except KeyboardInterrupt:
        pass
    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
