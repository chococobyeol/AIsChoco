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
방송 오버레이: 채팅/대사를 OBS에 표시하려면 OBS에서 브라우저 소스 추가 → URL에 http://127.0.0.1:8765/ 입력. 타로 전용 오버레이는 http://127.0.0.1:8765/tarot. 포트 변경 시 .env에 OVERLAY_PORT=8765 설정.
타로: 시청자가 "타로 봐줘" 등으로 요청하면 1~78번 중 N장 선택 → 해석·시각화. .env TAROT_ENABLED=0 또는 false 로 두면 당일 타로 비활성화(요청 시 거절). TAROT_SELECT_TIMEOUT_SEC=300 (기본 5분).
"""

import asyncio
import logging
import os
import random
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from src.chat import ChatClientFactory, ChatMessage
from src.ai import GroqClient, AIResponse, ChatHistory
from src.tts import TTSService, text_for_tts_numbers
from src.vtuber import VTSClient
from src.overlay.state import (
    overlay_state,
    MAX_VIEWER_MESSAGES,
    MAX_ASSISTANT_MESSAGES,
    TAROT_SELECT_TIMEOUT_SEC,
)
from src.overlay.tarot_deck import build_deck

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _tts_synthesize_only(
    tts_service: TTSService, text: str, emotion: str, language: str = "Korean"
):
    """동기: TTS만 합성해 파일로 저장(재생 안 함). asyncio.to_thread에서 호출. language로 원격 TTS 한국어 강제."""
    return tts_service.synthesize_to_file(
        text, emotion=emotion, language=language, play=False
    )


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


async def idle_worker(
    vts_client: Optional[VTSClient],
    is_speaking: List[bool],
) -> None:
    """
    말하기와 겹치지 않게 아이들 자세: 마우스는 (-0.25,-0.65)↔(+0.25,-0.65) 왔다갔다 2~3번 후
    ~10초 쉬기 반복. 다리는 별도로 ~10초 주기로 LegR/LegL 살짝 좌우.
    """
    if not vts_client:
        return
    move_duration = 1.0
    rest_after_mouse = 10.0
    leg_interval = 10.0
    next_mouse_cycle = time.monotonic()
    next_leg = time.monotonic()
    while True:
        try:
            await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            break
        if is_speaking[0]:
            continue
        now = time.monotonic()

        # 마우스: 왼쪽↔오른쪽 1~5번 왔다갔다 후, 다음 사이클은 10초 뒤
        if now >= next_mouse_cycle:
            rounds = random.randint(1, 5)
            y_base = -0.65
            y_jitter = 0.04
            for _ in range(rounds):
                if is_speaking[0]:
                    break
                y = y_base + random.uniform(-y_jitter, y_jitter)
                try:
                    await vts_client.set_mouse_position(-0.25, y)
                except Exception:
                    pass
                await asyncio.sleep(move_duration + random.uniform(-0.2, 0.3))
                if is_speaking[0]:
                    break
                y = y_base + random.uniform(-y_jitter, y_jitter)
                try:
                    await vts_client.set_mouse_position(0.25, y)
                except Exception:
                    pass
                await asyncio.sleep(move_duration + random.uniform(-0.2, 0.3))
            next_mouse_cycle = time.monotonic() + rest_after_mouse + random.uniform(-1, 1.5)

        # 다리: 주기적으로 살짝 이동 (마우스와 독립, 마우스 블록 끝난 뒤 현재 시각으로 재확인)
        now = time.monotonic()
        if now >= next_leg:
            leg_r = random.uniform(-20, 20)
            leg_l = random.uniform(-20, 20)
            try:
                await vts_client.set_leg_idle(leg_r, leg_l)
            except Exception:
                pass
            next_leg = now + leg_interval + random.uniform(-4, 4)


async def tarot_timeout_worker():
    """revealed 1분 만료 / failed 표시 만료 시 주기적으로 타로 상태 초기화 (메인 루프는 queue.get 대기라 채팅 없으면 체크 안 함)."""
    while True:
        try:
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            break
        tarot = overlay_state.get("tarot")
        if not tarot or not isinstance(tarot, dict):
            continue
        phase = tarot.get("phase")
        now = time.time()
        if phase == "failed":
            until = tarot.get("failed_until_ts") or 0
            if until and now >= until:
                overlay_state["tarot"] = None
        elif phase == "revealed":
            reset_at = tarot.get("auto_reset_at_ts") or 0
            if reset_at and now >= reset_at:
                overlay_state["tarot"] = None


async def reply_worker(
    queue: asyncio.Queue,
    groq_client: GroqClient,
    tts_service: TTSService,
    vts_client: Optional[VTSClient],
    chat_history: ChatHistory,
    is_speaking: List[bool],
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
            tarot_enabled = os.environ.get("TAROT_ENABLED", "1").strip().lower() in ("1", "true", "yes", "on")
            if not tarot_enabled:
                overlay_state["tarot"] = None
            tarot = overlay_state.get("tarot")

            # ----- 타로 "뭐에 대해 볼지" 단계는 AI 판단으로 처리: 일반 채팅으로 넘겨 reply_batch에서 tarot_state 전달

            # ----- 타로 실패 표시 후 초기화
            if tarot and tarot.get("phase") == "failed":
                until = tarot.get("failed_until_ts") or 0
                if time.time() >= until:
                    overlay_state["tarot"] = None
                    continue
            # ----- 타로 해석 공개 후 1분 지나면 자동 리셋
            if tarot and tarot.get("phase") == "revealed":
                reset_at = tarot.get("auto_reset_at_ts") or 0
                if reset_at and time.time() >= reset_at:
                    overlay_state["tarot"] = None
                    continue
                # 60초 대기 중 아무나 타로/봐줘 요청하면 "창 닫힐 때까지 기다려 주세요" 멘트만 (AI 처리)
                did_wait_ment = False
                for m, oid in zip(pending_msgs, pending_ids):
                    msg = (getattr(m, "message", "") or "").strip()
                    looks_tarot = "타로" in msg or "봐줘" in msg or "볼래" in msg
                    looks_again = ("또" in msg or "다시" in msg) and ("봐" in msg or "볼" in msg or "해" in msg)
                    if looks_tarot or looks_again:
                        reply_text = await asyncio.to_thread(
                            groq_client.generate_tarot_wait_reply, msg
                        )
                        if not reply_text:
                            reply_text = "아직 이번 타로가 끝나지 않았어요. 창이 닫힐 때까지 잠시만 기다려 주세요."
                        try:
                            path = await asyncio.to_thread(
                                _tts_synthesize_only, tts_service, text_for_tts_numbers(reply_text), "neutral", "Korean"
                            )
                            is_speaking[0] = True
                            await asyncio.to_thread(tts_service.play_file, path)
                        except Exception:
                            pass
                        finally:
                            is_speaking[0] = False
                        overlay_state.setdefault("assistant_messages", []).append({
                            "message": reply_text,
                            "ts": time.time(),
                        })
                        a_msgs = overlay_state.get("assistant_messages") or []
                        if len(a_msgs) > MAX_ASSISTANT_MESSAGES:
                            overlay_state["assistant_messages"] = a_msgs[-MAX_ASSISTANT_MESSAGES:]
                        for v in overlay_state.get("viewer_messages") or []:
                            if v.get("id") == oid:
                                v["processed"] = True
                                break
                        kept = [(mm, oid2) for mm, oid2 in zip(pending_msgs, pending_ids) if mm != m]
                        pending_msgs = [x for x, _ in kept]
                        pending_ids = [y for _, y in kept]
                        logger.info("타로 60초 대기 중 요청 → 기다리라 멘트 TTS: %s", reply_text[:50])
                        did_wait_ment = True
                        break
                if did_wait_ment:
                    continue
            # ----- 타로 선택 단계: 타임아웃 체크
            if tarot and tarot.get("phase") == "selecting":
                deadline = tarot.get("select_deadline_ts") or 0
                if time.time() > deadline:
                    overlay_state["tarot"] = None
                    timeout_msg = "시간이 지나서 이번 타로는 마무리할게요."
                    try:
                        path = await asyncio.to_thread(
                            _tts_synthesize_only, tts_service, text_for_tts_numbers(timeout_msg), "neutral", "Korean"
                        )
                        is_speaking[0] = True
                        await asyncio.to_thread(tts_service.play_file, path)
                    except Exception as e:
                        logger.debug("타로 타임아웃 TTS 실패: %s", e)
                    finally:
                        is_speaking[0] = False
                    continue

            # ----- 타로 선택 단계: 요청자 말을 AI API로 보내서 자연어로만 처리 (번호/취소/재요청)
            if tarot and tarot.get("phase") == "selecting":
                requester_id = tarot.get("requester_id")
                requester_msgs = [
                    m for m in pending_msgs
                    if getattr(m, "user_id", None) is not None
                    and str(m.user_id) == str(requester_id)
                ]
                if requester_msgs:
                    combined = " ".join((getattr(m, "message", "") or "") for m in requester_msgs)
                    spread_count = tarot.get("spread_count", 3)
                    pending_numbers = tarot.get("pending_numbers") or []
                    context = chat_history.get_context_messages()
                    selection = await asyncio.to_thread(
                        groq_client.process_tarot_selection,
                        combined.strip(),
                        spread_count,
                        context,
                        pending_numbers,
                    )
                    if selection.get("tarot_cancel"):
                        overlay_state["tarot"] = None
                        try:
                            path = await asyncio.to_thread(
                                _tts_synthesize_only,
                                tts_service,
                                text_for_tts_numbers(selection.get("tts_text") or selection["response"]),
                                selection.get("emotion") or "neutral",
                                "Korean",
                            )
                            is_speaking[0] = True
                            await asyncio.to_thread(tts_service.play_file, path)
                        except Exception:
                            pass
                        finally:
                            is_speaking[0] = False
                        continue
                    # AI 해석 우선. 1~78만 걸러서 사용.
                    raw_numbers = selection.get("tarot_numbers") or []
                    numbers = [int(x) for x in raw_numbers if isinstance(x, (int, float)) and 1 <= int(x) <= 78]
                    numbers = numbers[:spread_count] if numbers else None
                    logger.info("타로 선택 결과: numbers=%s, spread_count=%s", numbers, spread_count)
                    # 중복 안내 시 누적 번호 비우고 처음부터 다시 뽑게 함
                    if numbers is None and "중복" in (selection.get("response") or ""):
                        overlay_state["tarot"] = {**tarot, "pending_numbers": []}
                        try:
                            path = await asyncio.to_thread(
                                _tts_synthesize_only,
                                tts_service,
                                text_for_tts_numbers(selection.get("tts_text") or selection["response"]),
                                selection.get("emotion") or "neutral",
                                "Korean",
                            )
                            is_speaking[0] = True
                            await asyncio.to_thread(tts_service.play_file, path)
                        except Exception:
                            pass
                        finally:
                            is_speaking[0] = False
                        continue
                    # N개 미만이면 누적 안 함 → 재요청 분기에서 "처음부터 다시 N개" 멘트만
                    if numbers and len(numbers) >= spread_count:
                        deck = tarot.get("deck") or []
                        chosen = [deck[n - 1] for n in numbers[:spread_count] if 1 <= n <= len(deck)]
                        logger.info("타로 번호 확정: %s, 덱 %s장, chosen %s장", numbers[:spread_count], len(deck), len(chosen))
                        if len(chosen) == spread_count:
                            # 선택 확인 멘트가 있으면 먼저 TTS (예: "9, 3, 1번 선택하셨네요")
                            confirm_ment = (selection.get("response") or "").strip()
                            if confirm_ment and any(k in confirm_ment for k in ("선택", "고르셨", "확인")):
                                try:
                                    path_ment = await asyncio.to_thread(
                                        _tts_synthesize_only,
                                        tts_service,
                                        text_for_tts_numbers(confirm_ment),
                                        selection.get("emotion") or "neutral",
                                        "Korean",
                                    )
                                    is_speaking[0] = True
                                    await asyncio.to_thread(tts_service.play_file, path_ment)
                                except Exception:
                                    pass
                                finally:
                                    is_speaking[0] = False
                            question = tarot.get("question") or ""
                            result = await asyncio.to_thread(
                                groq_client.get_tarot_interpretation, question, chosen
                            )
                            if result:
                                overlay_state["tarot"] = {
                                    "visible": True,
                                    "phase": "revealed",
                                    "question": question,
                                    "cards": chosen,
                                    "selected_indices": list(numbers[:spread_count]),
                                    "interpretation": result["interpretation"],
                                    "visual_data": result.get("visual_data") or {},
                                    "soul_color": result.get("soul_color"),
                                    "danger_alert": result.get("danger_alert"),
                                }
                                chat_history.add_assistant_message(result["interpretation"])
                                overlay_state.setdefault("assistant_messages", []).append({
                                    "message": result["interpretation"],
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
                                try:
                                    interp_tts = result.get("tts_text") or result["interpretation"]
                                    path = await asyncio.to_thread(
                                        _tts_synthesize_only,
                                        tts_service,
                                        text_for_tts_numbers(interp_tts),
                                        "neutral",
                                        "Korean",
                                    )
                                    is_speaking[0] = True
                                    await asyncio.to_thread(tts_service.play_file, path)
                                    if vts_client:
                                        await vts_client.set_emotion("neutral")
                                except Exception as tts_e:
                                    logger.warning("타로 해석 TTS 실패: %s", tts_e)
                                finally:
                                    is_speaking[0] = False
                                # TTS 끝난 뒤 1분 후 자동 리셋 (오버레이에서 타이머 표시용)
                                t = overlay_state.get("tarot")
                                if isinstance(t, dict) and t.get("phase") == "revealed":
                                    t["auto_reset_at_ts"] = time.time() + 60
                            else:
                                logger.warning("타로 해석 실패: get_tarot_interpretation 반환 없음 (Groq/JSON 오류)")
                                fail_msg = "이번에는 해석을 불러오지 못했어요."
                                overlay_state["tarot"] = {
                                    "visible": True,
                                    "phase": "failed",
                                    "message": fail_msg,
                                    "failed_until_ts": time.time() + 5,
                                }
                                try:
                                    path = await asyncio.to_thread(
                                        _tts_synthesize_only,
                                        tts_service,
                                        fail_msg,
                                        "neutral",
                                        "Korean",
                                    )
                                    is_speaking[0] = True
                                    await asyncio.to_thread(tts_service.play_file, path)
                                except Exception:
                                    pass
                                finally:
                                    is_speaking[0] = False
                        else:
                            logger.warning("타로 카드 선택 불일치: chosen %s장 (필요 %s)", len(chosen), spread_count)
                        continue
                    # 번호 부족/애매 → AI가 준 재요청 문장으로 TTS + 오버레이 표시 + 해당 시청자 메시지 처리됨
                    reask_text = selection.get("response") or ""
                    reask_tts = (selection.get("tts_text") or reask_text).strip() or reask_text
                    print(f"  → [타로 재요청] {reask_text}")
                    logger.info("타로 재요청 멘트: %s", reask_text[:100])
                    overlay_state.setdefault("assistant_messages", []).append({
                        "message": reask_text,
                        "ts": time.time(),
                    })
                    a_msgs = overlay_state.get("assistant_messages") or []
                    if len(a_msgs) > MAX_ASSISTANT_MESSAGES:
                        overlay_state["assistant_messages"] = a_msgs[-MAX_ASSISTANT_MESSAGES:]
                    for m, oid in zip(pending_msgs, pending_ids):
                        if m in requester_msgs:
                            for v in overlay_state.get("viewer_messages") or []:
                                if v.get("id") == oid:
                                    v["processed"] = True
                                    break
                    try:
                        path = await asyncio.to_thread(
                            _tts_synthesize_only,
                            tts_service,
                            text_for_tts_numbers(reask_tts),
                            selection.get("emotion") or "neutral",
                            "Korean",
                        )
                        is_speaking[0] = True
                        await asyncio.to_thread(tts_service.play_file, path)
                    except Exception:
                        pass
                    finally:
                        is_speaking[0] = False
                    continue

            # ----- 일반 채팅 처리
            for m in pending_msgs:
                print(f"  [대기] {m.user}: {m.message}")
                chat_history.add_user_message(m.user or "?", m.message or "")

            chat_history.flush_summary(groq_client)
            context = chat_history.get_context_messages()
            tarot_state = overlay_state.get("tarot")

            replies = await asyncio.to_thread(
                groq_client.reply_batch, pending_msgs, context, tarot_state, tarot_enabled
            )
            if not replies:
                logger.info("답변 없음 (모델이 replies 빈 배열 반환 또는 파싱 실패)")

            for ai_response in replies:
                if not (ai_response.response or "").strip():
                    continue
                chat_history.add_assistant_message(ai_response.response)
                print(f"  → [감정:{ai_response.emotion}] {ai_response.response}")

                # ----- Groq가 타로 액션을 반환한 경우: 진행 중(selecting/revealed)이면 새 타로로 덮어쓰지 않음
                action = getattr(ai_response, "action", None)
                current_phase = (tarot_state or {}).get("phase")
                if current_phase in ("selecting", "revealed"):
                    # 진행 중에는 action이 와도 타로 상태 유지 (AI는 거절 멘트 반환했을 것)
                    pass
                elif action == "tarot_ask_question":
                    first_msg = pending_msgs[0] if pending_msgs else None
                    if first_msg:
                        overlay_state["tarot"] = {
                            "visible": False,
                            "phase": "asking_question",
                            "requester_id": getattr(first_msg, "user_id", None) or "",
                            "requester_nickname": getattr(first_msg, "user", None) or "?",
                        }
                elif action == "tarot":
                    # asking_question에서 넘어온 경우 기존 요청자 유지, 아니면 첫 메시지 기준
                    prev_tarot = overlay_state.get("tarot")
                    if prev_tarot and prev_tarot.get("phase") == "asking_question":
                        requester_id = prev_tarot.get("requester_id") or ""
                        requester_nickname = prev_tarot.get("requester_nickname") or "?"
                    else:
                        first_msg = pending_msgs[0] if pending_msgs else None
                        requester_id = getattr(first_msg, "user_id", None) or "" if first_msg else ""
                        requester_nickname = getattr(first_msg, "user", None) or "?" if first_msg else "?"
                    if requester_id or pending_msgs:
                        timeout_sec = int(os.getenv("TAROT_SELECT_TIMEOUT_SEC", str(TAROT_SELECT_TIMEOUT_SEC)))
                        question = (getattr(ai_response, "tarot_question", None) or "").strip() or "오늘의 운세"
                        sc = getattr(ai_response, "tarot_spread_count", None)
                        spread_count = sc if sc in (1, 2, 3, 4, 5) else 3
                        overlay_state["tarot"] = {
                            "visible": True,
                            "phase": "selecting",
                            "requester_id": requester_id,
                            "requester_nickname": requester_nickname,
                            "question": question,
                            "spread_count": spread_count,
                            "select_deadline_ts": time.time() + timeout_sec,
                            "deck": build_deck(shuffle=True),
                        }
                elif tarot_state and tarot_state.get("phase") == "asking_question":
                    # AI가 타로 액션 없이 답했으면 = 거절/모르겠음 판단 → 타로 해제
                    overlay_state["tarot"] = None

                try:
                    chat_tts = getattr(ai_response, "tts_text", None) or ai_response.response
                    path = await asyncio.to_thread(
                        _tts_synthesize_only,
                        tts_service,
                        text_for_tts_numbers(chat_tts),
                        ai_response.emotion,
                        "Korean",
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
                    is_speaking[0] = True
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
                finally:
                    is_speaking[0] = False
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

    is_speaking: List[bool] = [False]
    queue: asyncio.Queue = asyncio.Queue()
    worker_task = asyncio.create_task(
        reply_worker(
            queue, groq_client, tts_service, vts_client, chat_history, is_speaking
        )
    )
    tarot_timeout_task = asyncio.create_task(tarot_timeout_worker())
    idle_task: Optional[asyncio.Task] = None
    if vts_client:
        idle_task = asyncio.create_task(idle_worker(vts_client, is_speaking))

    def _is_streamer(m: ChatMessage, ch_id: str) -> bool:
        """방장(스트리머) 여부: 발신자 채널 ID == 방송 채널 ID"""
        uid = getattr(m, "user_id", None) or ""
        return bool(uid and ch_id and str(uid) == str(ch_id))

    def on_message(msg: ChatMessage):
        if overlay_state.get("ignore_streamer_chat") and _is_streamer(msg, channel_id):
            return
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
        tarot_timeout_task.cancel()
        if idle_task is not None:
            idle_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        try:
            await tarot_timeout_task
        except asyncio.CancelledError:
            pass
        if idle_task is not None:
            try:
                await idle_task
            except asyncio.CancelledError:
                pass
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
