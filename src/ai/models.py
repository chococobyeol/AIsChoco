"""
AI 모듈 데이터 모델
PRD 6.2 AI 응답
"""

from dataclasses import dataclass


VALID_EMOTIONS = frozenset({
    "happy", "sad", "angry", "surprised", "neutral", "excited"
})


@dataclass
class AIResponse:
    """Groq 등 LLM 구조화 응답 (답변 + 감정)"""
    response: str
    emotion: str
    confidence: float = 1.0
    processing_time: float = 0.0

    def __post_init__(self):
        if self.emotion not in VALID_EMOTIONS:
            self.emotion = "neutral"
