"""
Groq API 클라이언트
채팅 메시지를 받아 JSON 형식(response, emotion)으로 답변을 생성합니다.
PRD 4.5.2 요청/출력 형식 준수.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, List, Optional

from openai import OpenAI

from .models import AIResponse, VALID_EMOTIONS

logger = logging.getLogger(__name__)

# config/character.txt 가 있으면 시스템 프롬프트 앞에 붙임
def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _load_character_prompt(character_path: Optional[Path] = None) -> str:
    """config/character.txt 내용 로드. 없으면 빈 문자열."""
    p = character_path or (_project_root() / "config" / "character.txt")
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8").strip()
    except Exception as e:
        logger.warning("캐릭터 파일 로드 실패 %s: %s", p, e)
        return ""

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
# openai/gpt-oss-120b: 131K context, 8K 분당 등 제한에 맞춰 .env GROQ_MODEL 로 변경 가능
DEFAULT_MODEL = "openai/gpt-oss-120b"

SYSTEM_PROMPT = """시청자 채팅에 한 문장으로 짧게 한국어로 답하세요.
반드시 아래 JSON만 출력하세요. 따옴표나 줄바꿈 없이 한 줄로 작성하세요.
{"response": "한 문장 답변", "emotion": "감정키"}
emotion은 반드시 다음 중 하나: happy, sad, angry, surprised, neutral, excited."""

BATCH_SYSTEM_PROMPT = """아래는 말하는 동안 들어온 채팅 목록입니다.
도배·스팸만 무시하고, 채팅이 있으면 반드시 답변 하나 생성하세요. 짧은 한마디(예: 그냥 알아, ㅇㅇ)에도 한 문장으로 응답하세요.
정말 답할 수 없는 경우에만 replies를 빈 배열로 두세요.
설명·생각·추론 없이, 아래 형식의 JSON 한 줄만 출력하세요.
{"replies": [{"response": "한 문장(길어도 됨)", "emotion": "감정키"}]}
replies는 최대 1개. emotion은 반드시: happy, sad, angry, surprised, neutral, excited 중 하나."""

SUMMARIZE_PROMPT = """다음 대화 내용을 간결하게 요약해주세요. 중요한 맥락과 주제는 유지하세요. 한국어로 한 문단 이내."""


class GroqClient:
    """Groq API로 채팅 답변 + 감정 생성. config/character.txt 있으면 성격·자기 정보로 시스템 프롬프트 보강."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 256,
        character_path: Optional[Path] = None,
    ):
        self.api_key = (api_key or os.environ.get("GROQ_API_KEY", "")).strip()
        if not self.api_key:
            raise ValueError("GROQ_API_KEY가 설정되지 않았습니다. .env 또는 인자로 전달하세요.")
        _model = (model or "").strip()
        self.model = _model or (os.environ.get("GROQ_MODEL") or "").strip() or DEFAULT_MODEL
        self.max_tokens = max_tokens
        self._character_prompt = _load_character_prompt(character_path)
        if self._character_prompt:
            logger.info("캐릭터 설정 로드: config/character.txt")
        self._client = OpenAI(
            api_key=self.api_key,
            base_url=GROQ_BASE_URL,
        )

    def _system_prompt(self, base: str) -> str:
        """캐릭터 설정이 있으면 앞에 붙여서 반환."""
        if not self._character_prompt:
            return base
        return f"{self._character_prompt}\n\n{base}"

    def reply(
        self,
        user_message: str,
        user_name: Optional[str] = None,
        context_messages: Optional[List[dict]] = None,
    ) -> AIResponse:
        """
        사용자 메시지에 대해 답변 텍스트와 감정을 반환합니다.

        Args:
            user_message: 채팅 메시지 내용
            user_name: 보낸 사람 닉네임 (선택, 맥락용)
            context_messages: 이전 대화 맥락 [{"role":"user"|"assistant","content":"..."}, ...]

        Returns:
            AIResponse(response, emotion, ...)
        """
        content = user_message.strip()
        if not content:
            return AIResponse(response="", emotion="neutral", confidence=0.0)

        if user_name:
            content = f"{user_name}: {content}"

        messages = [{"role": "system", "content": self._system_prompt(SYSTEM_PROMPT)}]
        if context_messages:
            messages.extend(context_messages)
        messages.append({"role": "user", "content": content})

        start = time.perf_counter()
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
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

    def summarize(self, messages: List[dict]) -> str:
        """대화 목록을 한 문단 요약. messages는 [{"role":..., "content":...}, ...]."""
        if not messages:
            return ""
        text = "\n".join(
            f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages
        )
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SUMMARIZE_PROMPT},
                    {"role": "user", "content": text[:8000]},
                ],
                max_tokens=512,
            )
            raw = (response.choices[0].message.content or "").strip()
            return raw
        except Exception as e:
            logger.warning("요약 생성 실패: %s", e)
            return ""

    def reply_batch(
        self,
        pending: List[Any],
        context_messages: Optional[List[dict]] = None,
    ) -> List[AIResponse]:
        """
        말하는 동안 쌓인 채팅을 한 번에 보고, 합치기/걸러내기 후 답변 1개 생성 (길어도 됨).
        pending: .user, .message 속성 있는 객체 리스트 (ChatMessage 등).
        """
        if not pending:
            return []
        lines = []
        for m in pending:
            user = getattr(m, "user", None) or (m.get("user") if isinstance(m, dict) else None)
            msg = getattr(m, "message", None) or (m.get("message") if isinstance(m, dict) else None) or ""
            if (msg or "").strip():
                lines.append(f"{user or '?'}: {msg}")
        content = "\n".join(lines)
        if not content.strip():
            return []

        messages = [{"role": "system", "content": self._system_prompt(BATCH_SYSTEM_PROMPT)}]
        if context_messages:
            messages.extend(context_messages)
        messages.append({"role": "user", "content": f"채팅 목록:\n{content}"})

        start = time.perf_counter()
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content
            elapsed = time.perf_counter() - start
        except Exception as e:
            logger.exception("Groq batch 호출 실패: %s", e)
            return []

        try:
            text = raw.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0].strip()
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                beg, end = text.find("{"), text.rfind("}")
                if beg != -1 and end > beg:
                    data = json.loads(text[beg : end + 1])
                else:
                    raise
            arr = data.get("replies") if isinstance(data, dict) else data
            if not isinstance(arr, list):
                arr = []
            out = []
            for i, item in enumerate(arr[:1]):
                if not isinstance(item, dict):
                    continue
                r = (item.get("response") or "").strip()
                e = (item.get("emotion") or "neutral").strip().lower()
                if e not in VALID_EMOTIONS:
                    e = "neutral"
                if r:
                    out.append(AIResponse(response=r, emotion=e, confidence=1.0, processing_time=elapsed))
            return out
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Groq batch JSON 파싱 실패: %s", e)
            return []
