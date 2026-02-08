"""오버레이용 공유 상태. 컬럼 분리: 시청자 채팅 / AI 답변 각각 리스트."""

from typing import Any

# 시청자 채팅: 들어오자마자 추가, 처리되면 processed=True
# [{ "id": int, "user": str, "message": str, "processed": bool }, ...]
# AI 답변: 답변 생성 시 추가
# [{ "message": str }, ...]
overlay_state: dict[str, Any] = {
    "viewer_messages": [],
    "assistant_messages": [],
    "_next_id": 0,
}
MAX_VIEWER_MESSAGES = 50
MAX_ASSISTANT_MESSAGES = 50
