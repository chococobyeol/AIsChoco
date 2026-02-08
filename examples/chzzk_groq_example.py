"""
치지직 채팅 수신 → 큐 적재 → 말 끝난 뒤 일괄 처리(합치기/걸러내기) → 히스토리 + Groq → TTS 재생

.env에 CHZZK_CHANNEL_ID, CHZZK_ACCESS_TOKEN, GROQ_API_KEY 설정 후 실행.
실행: python examples/chzzk_groq_example.py  (프로젝트 루트에서)

- 채팅은 큐에만 쌓고, 말하기가 끝난 뒤에만 쌓인 채팅을 한꺼번에 처리합니다.
- Groq가 도배/스팸을 걸러내고 비슷한 내용을 묶어 답변 1개만 생성합니다 (한 문장이 길어도 됨).
- 대화 히스토리(토큰 기반 + 요약 + RAG용 백업)를 유지합니다.
립싱크: .env에 TTS_OUTPUT_DEVICE=VB-Audio Virtual Cable 등으로 TTS 출력을 가상 케이블로 두고, VTS 오디오 입력을 해당 장치로 설정.
Colab TTS: .env에 TTS_REMOTE_URL=https://xxx.ngrok-free.app 설정 시 TTS를 Colab에서 원격 실행. docs/COLAB_TTS.md 참고.
수동 백업: history/DO_BACKUP 파일을 만들면 다음 채팅 처리 시점에 history/backups/ 에 타임스탬프 백업 후 삭제됩니다.
방송 오버레이: 채팅/대사를 OBS에 표시하려면 OBS에서 브라우저 소스 추가 → URL에 http://127.0.0.1:8765/ 입력. 포트 변경 시 .env에 OVERLAY_PORT=8765 설정.
"""

import asyncio
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from src.chat import ChatClientFactory, ChatMessage
from src.ai import GroqClient, AIResponse, ChatHistory
from src.tts import TTSService
from src.vtuber import VTSClient
from src.overlay.state import (
    overlay_state,
    MAX_VIEWER_MESSAGES,
    MAX_ASSISTANT_MESSAGES,
)

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _tts_synthesize_only(tts_service: TTSService, text: str, emotion: str):
    """동기: TTS만 합성해 파일로 저장(재생 안 함). asyncio.to_thread에서 호출."""
    return tts_service.synthesize_to_file(text, emotion=emotion, play=False)


async def _animate_look_back_to_center(
    vts_client: VTSClient,
    start_x: float = 0.7,
    start_y: float = -0.7,
    duration_sec: float = 0.4,
    steps: int = 12,
) -> None:
    """말하는 동안 시선을 (start_x, start_y)에서 (0, 0)으로 서서히 돌림."""
    if steps < 2:
        return
    delay = duration_sec / (steps - 1)
    for i in range(steps):
        t = i / (steps - 1) if steps > 1 else 1.0
        x = start_x * (1 - t)
        y = start_y * (1 - t)
        try:
            await vts_client.set_mouse_position(x, y)
        except Exception:
            pass
        if i < steps - 1:
            await asyncio.sleep(delay)


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
    root = Path(__file__).resolve().parent.parent
    backup_trigger = root / "history" / "DO_BACKUP"
    while True:
        try:
            if backup_trigger.exists():
                try:
                    chat_history.save_manual_backup()
                    backup_trigger.unlink()
                except Exception as be:
                    logger.warning("수동 백업 실패: %s", be)
            first = await queue.get()
            pending: List[Tuple[ChatMessage, int]] = [first]
            while True:
                try:
                    item = queue.get_nowait()
                    pending.append(item)
                except asyncio.QueueEmpty:
                    break

            pending_msgs = [m for m, _ in pending]
            pending_ids = [oid for _, oid in pending]
            for m in pending_msgs:
                print(f"  [대기] {m.user}: {m.message}")
                chat_history.add_user_message(m.user or "?", m.message or "")

            chat_history.flush_summary(groq_client)
            context = chat_history.get_context_messages()

            replies = await asyncio.to_thread(
                groq_client.reply_batch, pending_msgs, context
            )
            if not replies:
                logger.info("답변 없음 (모델이 replies 빈 배열 반환 또는 파싱 실패)")

            for ai_response in replies:
                if not (ai_response.response or "").strip():
                    continue
                chat_history.add_assistant_message(ai_response.response)
                print(f"  → [감정:{ai_response.emotion}] {ai_response.response}")
                try:
                    path = await asyncio.to_thread(
                        _tts_synthesize_only,
                        tts_service,
                        ai_response.response,
                        ai_response.emotion,
                    )
                except Exception as tts_e:
                    logger.exception("TTS 오류: %s", tts_e)
                    continue
                overlay_state.setdefault("assistant_messages", []).append({
                    "message": str(ai_response.response or ""),
                    "ts": time.time(),
                })
                a_msgs = overlay_state.get("assistant_messages") or []
                if len(a_msgs) > MAX_ASSISTANT_MESSAGES:
                    overlay_state["assistant_messages"] = a_msgs[-MAX_ASSISTANT_MESSAGES:]
                for oid in pending_ids:
                    for v in overlay_state.get("viewer_messages") or []:
                        if v.get("id") == oid:
                            v["processed"] = True
                            break
                logger.info("Overlay: speech=%d chars", len(ai_response.response or ""))
                if vts_client:
                    try:
                        await vts_client.set_mouse_position(0.7, -0.7)
                        await vts_client.set_emotion(ai_response.emotion)
                    except Exception as vts_e:
                        logger.debug("VTS 포즈 실패: %s", vts_e)
                try:
                    play_task = asyncio.create_task(
                        asyncio.to_thread(tts_service.play_file, path)
                    )
                    if vts_client:
                        await asyncio.sleep(0.5)
                        await _animate_look_back_to_center(
                            vts_client, start_x=0.8, start_y=-0.9, duration_sec=0.4
                        )
                    await play_task
                except Exception as play_e:
                    logger.warning("재생 실패: %s", play_e)
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

    overlay_port = int(os.getenv("OVERLAY_PORT", "8765"))
    try:
        from src.overlay.server import app
        import uvicorn
        def run_overlay():
            uvicorn.run(app, host="127.0.0.1", port=overlay_port, log_level="warning")
        t = threading.Thread(target=run_overlay, daemon=True)
        t.start()
        print(f"방송 오버레이: http://127.0.0.1:{overlay_port}/ (OBS 브라우저 소스에 추가, uvicorn 따로 실행 금지)")
    except Exception as e:
        logger.debug("오버레이 서버 미시작: %s", e)

    queue: asyncio.Queue = asyncio.Queue()
    worker_task = asyncio.create_task(
        reply_worker(queue, groq_client, tts_service, vts_client, chat_history)
    )

    def on_message(msg: ChatMessage):
        viewer_list = overlay_state.setdefault("viewer_messages", [])
        next_id = overlay_state.get("_next_id", 0) + 1
        overlay_state["_next_id"] = next_id
        viewer_list.append({
            "id": next_id,
            "user": str(getattr(msg, "user", None) or "?"),
            "message": str(getattr(msg, "message", None) or ""),
            "processed": False,
            "ts": time.time(),
        })
        if len(viewer_list) > MAX_VIEWER_MESSAGES:
            overlay_state["viewer_messages"] = viewer_list[-MAX_VIEWER_MESSAGES:]
        queue.put_nowait((msg, next_id))

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
