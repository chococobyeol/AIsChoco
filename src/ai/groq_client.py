"""
Groq API 클라이언트
채팅 메시지를 받아 JSON 형식(response, emotion)으로 답변을 생성합니다.
PRD 4.5.2 요청/출력 형식 준수.
"""

import json
import logging
import os
import time
from typing import Optional

from openai import OpenAI

from .models import AIResponse, VALID_EMOTIONS

logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """당신은 친근한 AI 버튜버입니다. 시청자 채팅에 한 문장으로 짧게 한국어로 답하세요.
반드시 아래 JSON만 출력하세요. 따옴표나 줄바꿈 없이 한 줄로 작성하세요.
{"response": "한 문장 답변", "emotion": "감정키"}
emotion은 반드시 다음 중 하나: happy, sad, angry, surprised, neutral, excited."""


class GroqClient:
    """Groq API로 채팅 답변 + 감정 생성"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 256,
    ):
        self.api_key = (api_key or os.environ.get("GROQ_API_KEY", "")).strip()
        if not self.api_key:
            raise ValueError("GROQ_API_KEY가 설정되지 않았습니다. .env 또는 인자로 전달하세요.")
        self.model = model
        self.max_tokens = max_tokens
        self._client = OpenAI(
            api_key=self.api_key,
            base_url=GROQ_BASE_URL,
        )

    def reply(
        self,
        user_message: str,
        user_name: Optional[str] = None,
    ) -> AIResponse:
        """
        사용자 메시지에 대해 답변 텍스트와 감정을 반환합니다.

        Args:
            user_message: 채팅 메시지 내용
            user_name: 보낸 사람 닉네임 (선택, 맥락용)

        Returns:
            AIResponse(response, emotion, ...)
        """
        content = user_message.strip()
        if not content:
            return AIResponse(response="", emotion="neutral", confidence=0.0)

        if user_name:
            content = f"{user_name}: {content}"

        start = time.perf_counter()
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": content},
                ],
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content
            elapsed = time.perf_counter() - start
        except Exception as e:
            logger.exception("Groq API 호출 실패: %s", e)
            return AIResponse(
                response="",
                emotion="neutral",
                confidence=0.0,
                processing_time=time.perf_counter() - start,
            )

        try:
            text = raw.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0].strip()
            data = json.loads(text)
            response_text = data.get("response", "").strip() or "(응답 없음)"
            emotion = (data.get("emotion") or "neutral").strip().lower()
            if emotion not in VALID_EMOTIONS:
                emotion = "neutral"
            return AIResponse(
                response=response_text,
                emotion=emotion,
                confidence=1.0,
                processing_time=elapsed,
            )
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Groq JSON 파싱 실패, raw=%r: %s", raw, e)
            return AIResponse(
                response=raw[:200] if raw else "",
                emotion="neutral",
                confidence=0.5,
                processing_time=elapsed,
            )
