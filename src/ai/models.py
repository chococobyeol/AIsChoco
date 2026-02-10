"""
AI 모듈 데이터 모델
PRD 6.2 AI 응답
"""

from dataclasses import dataclass
from typing import Optional


VALID_EMOTIONS = frozenset({
    "happy", "sad", "angry", "surprised", "neutral", "excited"
})


@dataclass
class AIResponse:
    """Groq 등 LLM 구조화 응답 (답변 + 감정 + 선택적 타로 액션)"""
    response: str
    emotion: str
    confidence: float = 1.0
    processing_time: float = 0.0
    action: Optional[str] = None  # "tarot_ask_question" | "tarot" | None(일반 채팅)
    tarot_question: Optional[str] = None  # action이 "tarot"일 때 질문 주제
    tarot_spread_count: Optional[int] = None  # 1~5, 생략 시 3. "한 장만" 등이면 1
    tts_text: Optional[str] = None  # TTS 읽기용(숫자 한글 등). 없으면 response 사용

    def __post_init__(self):
        if self.emotion not in VALID_EMOTIONS:
            self.emotion = "neutral"
        if self.tarot_spread_count is not None and (self.tarot_spread_count < 1 or self.tarot_spread_count > 5):
            self.tarot_spread_count = 3
