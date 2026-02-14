"""
Groq API 클라이언트
채팅 메시지를 받아 JSON 형식(response, emotion)으로 답변을 생성합니다.
PRD 4.5.2 요청/출력 형식 준수.
"""

import json
import logging
import os
import re
import time
import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, List, Optional

from openai import OpenAI

from .models import AIResponse, VALID_EMOTIONS
from .web_search import run_web_search

logger = logging.getLogger(__name__)

# 웹 검색 도구 스키마 (모델이 필요 시 호출)
SEARCH_WEB_TOOL = {
    "type": "function",
    "function": {
        "name": "search_web",
        "description": "최신 정보, 뉴스, 날씨, 시세 등 사용자가 현재/실제 정보를 요청할 때 웹 검색을 수행합니다. 검색이 필요 없다면 호출하지 마세요.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "검색 쿼리 (한국어 가능)",
                },
            },
            "required": ["query"],
        },
    },
}


def _parse_numbers_1_78(text: str) -> List[int]:
    """메시지에서 1~78 숫자만 순서대로 추출 (검증/피드백용)."""
    if not (text or "").strip():
        return []
    seen = set()
    out: List[int] = []
    for m in re.findall(r"\d+", text):
        n = int(m)
        if 1 <= n <= 78 and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _extract_failed_generation(err: Exception) -> str:
    """Groq 400 json_validate_failed 시 에러 본문에서 failed_generation 추출."""
    try:
        body = getattr(err, "body", None)
        if isinstance(body, dict):
            return (body.get("error") or {}).get("failed_generation") or ""
        if hasattr(err, "response") and err.response is not None:
            resp = getattr(err, "response", None)
            if hasattr(resp, "json"):
                data = resp.json()
                return (data.get("error") or {}).get("failed_generation") or ""
    except Exception:
        pass

    # 일부 클라이언트/예외 타입은 failed_generation을 str(err) 안에만 담아 전달한다.
    # 예: "Error code: 400 - {'error': {..., 'failed_generation': '{\"name\":\"JSON\",...}'}}"
    try:
        e_text = str(err or "")
        brace = e_text.find("{")
        if brace != -1:
            payload_text = e_text[brace:]
            payload = ast.literal_eval(payload_text)
            if isinstance(payload, dict):
                fg = (payload.get("error") or {}).get("failed_generation")
                if isinstance(fg, str) and fg.strip():
                    return fg
                fg2 = payload.get("failed_generation")
                if isinstance(fg2, str) and fg2.strip():
                    return fg2
    except Exception:
        pass
    return ""


def _first_choice_message(response: Any, where: str):
    """OpenAI 응답에서 첫 message를 안전하게 추출."""
    choices = getattr(response, "choices", None) or []
    if not choices:
        logger.warning("%s: response.choices가 비어 있습니다.", where)
        return None
    msg = getattr(choices[0], "message", None)
    if msg is None:
        logger.warning("%s: response.choices[0].message가 없습니다.", where)
    return msg


def _first_choice_content(response: Any, where: str) -> str:
    """OpenAI 응답 첫 message.content를 안전하게 문자열로 반환."""
    msg = _first_choice_message(response, where)
    if msg is None:
        return ""
    content = getattr(msg, "content", "")
    if content is None:
        return ""
    return str(content)


def _parse_int_list(raw_value: Any) -> List[int]:
    """list/문자열(세미콜론, 콤마, JSON 배열) 입력을 int 리스트로 변환."""
    if isinstance(raw_value, list):
        out: List[int] = []
        for v in raw_value:
            try:
                out.append(int(v))
            except (TypeError, ValueError):
                continue
        return out
    if not isinstance(raw_value, str):
        return []

    s = raw_value.strip()
    if not s:
        return []
    if ";" in s:
        parts = [p.strip() for p in s.split(";") if p.strip()]
    elif "," in s:
        parts = [p.strip() for p in s.split(",") if p.strip()]
    elif s.startswith("[") and s.endswith("]"):
        try:
            return _parse_int_list(json.loads(s))
        except json.JSONDecodeError:
            return []
    else:
        parts = [s]

    out: List[int] = []
    for p in parts:
        try:
            out.append(int(p))
        except (TypeError, ValueError):
            continue
    return out


def _sanitize_user_text(value: Any, max_len: int = 1000) -> str:
    """프롬프트에 삽입하기 전 사용자 입력 최소 정제."""
    s = str(value or "")
    s = s.replace("\r", " ").replace("\0", " ")
    s = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > max_len:
        s = s[:max_len]
    return s

# config/character.txt 가 있으면 시스템 프롬프트 앞에 붙임
def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _load_character_prompt(character_path: Optional[Path] = None) -> str:
    """config/character.txt 내용 로드. 없으면 빈 문자열."""
    p = character_path or (_project_root() / "config" / "character.txt")
    if not p.exists():
        return ""
    try:
        text = p.read_text(encoding="utf-8").replace("\0", "").strip()
        # character 프롬프트 과도 확장을 막기 위한 상한
        if len(text) > 12000:
            logger.warning("캐릭터 프롬프트가 너무 깁니다(%d자). 12000자로 잘라서 사용합니다.", len(text))
            text = text[:12000]
        return text
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

타로(운세) 관련:
- **타로 액션(tarot_ask_question, tarot)은 시청자가 타로/운세를 명시적으로 요청했을 때만 사용한다.** 채팅에 "타로", "운세", "점", "봐줘", "봐달라" 등 타로 요청 표현이 없으면 action 절대 넣지 말고 일반 대화로만 답할 것. 예: "내일 뭐할까?", "오늘 뭐 먹을까?", "이번 주 뭐하지?" → 타로 언급 없음 = 일반 답변만, action 없음.
- **최근 채팅이 ㅠ, ㅋㅋ, 한두 글자만 있거나 "타로 봐줘", "번호 골라줘" 같은 명시적 요청이 없으면** 타로를 새로 시작하거나 이전 타로를 이어가지 말 것. 일반 반응 한 문장만 할 것.
- "타로 봐줘" / "타로 봐달라"처럼 **타로를 요청했지만** 주제 없이만 말한 경우: 반드시 "뭐에 대해 볼지"만 물어라. 번호(1~78 등) 말하면 안 됨. action "tarot_ask_question"만.
- 시청자가 **타로를 요청한 뒤** 이미 주제를 말했을 때만: 그 주제로 타로 보겠다고 한 뒤, 1~78 중 번호 N개를 골라달라고 요청. action "tarot", tarot_question, tarot_spread_count(1~5) 반드시. 주제 성격에 따라 장수: 예/아니오→1, 단순→3, 복잡→5.
- 주제를 안 말했거나 거절이면 일반 답변만, action 없음.
- **숫자만 있는 채팅**(예: 7 11 18, 1 2 3)은 타로 요청이 아님. 이전 대화에 타로 요청이 있어도, 현재 채팅이 "타로·운세·봐줘" 등 없이 숫자·공백 위주면 action 절대 넣지 말고 일반 반응만 할 것.
- 일반 대화면 action 생략.

JSON 형식 (한 줄, 설명 없이):
{"replies": [{"response": "한 문장(화면 표시용)", "tts_text": "TTS로 읽었을 때 한국어로 자연스럽게 들리도록 같은 내용을 말하기 좋은 문장(선택)", "emotion": "감정키", "action": "tarot_ask_question"|"tarot"|생략, "tarot_question": "주제"|""|생략, "tarot_spread_count": 1|2|3|4|5}]}
action이 "tarot"일 때는 tarot_spread_count 반드시 1~5 중 하나로 넣기. 생략하지 말 것.
replies는 최대 1개. emotion은 반드시: happy, sad, angry, surprised, neutral, excited 중 하나. tts_text 없으면 response로 TTS."""

# 검색 도구 사용 시 추가 지시 (최종 답변은 동일 JSON)
BATCH_SYSTEM_PROMPT_SEARCH_SUFFIX = """

웹 검색: 시청자가 최신 뉴스, 날씨, 시세, 현재 정보 등을 물을 때는 search_web 도구를 호출하세요. 검색이 필요 없다면 도구를 호출하지 말고 바로 위 JSON 형식으로 답하세요. 검색 결과를 받은 뒤에는 그 내용을 바탕으로 한 문장으로 요약해, 반드시 같은 JSON 한 줄만 출력하세요. 시간·날짜를 물어보면 [현재 시각 (한국 기준)]이 있으면 그 값을 쓰고, 별말 없으면 한국 시간 기준으로 답하세요."""

SUMMARIZE_PROMPT = """다음 대화 내용을 간결하게 요약해주세요. 중요한 맥락과 주제는 유지하세요. 한국어로 한 문단 이내."""

# src/ai/groq_client.py 의 TAROT_INTERPRET_SYSTEM 변수를 이걸로 교체하세요.

TAROT_INTERPRET_SYSTEM = """당신은 타로 해석가입니다. 질문과 카드에 맞춰 해석과 시각화 데이터를 JSON으로 출력하세요.

visual_data 작성 규칙 (반드시 지킬 것):
- scores는 **세미콜론(;)으로 구분한 문자열**만 사용. 배열·쉼표 말고 이 형식만. 예: "80;70;60;90;75". labels 개수와 같은 개수의 숫자(0~100). 이어쓰지 말 것.
- interpretation과 그래프 점수가 **일치**해야 함. (추천한 항목의 score가 가장 높게)
1. **Yes/No 질문** (예: 비 올까? 합격할까?):
   - "visual_type": "yes_no"
   - "recommendation": "YES" 또는 "NO" (또는 "SEMI-YES")
   - "score": 긍정 확률 (0~100, 숫자 하나)

2. **양자택일/비교** (예: A가 좋을까 B가 좋을까?):
   - "visual_type": "bar"
   - "labels": ["A 선택", "B 선택"]
   - "scores": "70;30"  ← 세미콜론 구분 문자열

3. **종합 운세/일반** (오늘의 운세, 내일 뭐할지 등):
   - "visual_type": "radar"
   - "labels": ["금전", "애정", "건강", "학업/일", "대인관계"] (상황에 맞게 변형 가능)
   - "scores": "80;70;60;90;75"  ← 세미콜론 구분, labels와 같은 개수, 각 0~100

출력 예시(JSON 한 줄):
yes_no: {"interpretation": "...", "tts_text": "...", "visual_data": {"visual_type": "yes_no", "recommendation": "YES", "score": 85}, "soul_color": "#FFD700", "danger_alert": false}
radar: {"interpretation": "...", "tts_text": "...", "visual_data": {"visual_type": "radar", "labels": ["금전","애정","건강","학업","대인"], "scores": "80;70;60;90;75"}, "soul_color": "#FFD700", "danger_alert": false}"""


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
        logger.info(
            "GroqClient 초기화 완료: model=%s, max_tokens=%s, character_prompt=%s",
            self.model,
            self.max_tokens,
            bool(self._character_prompt),
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
        content = _sanitize_user_text(user_message, max_len=1000)
        if not content:
            return AIResponse(response="", emotion="neutral", confidence=0.0)

        if user_name:
            safe_name = _sanitize_user_text(user_name, max_len=40).replace(":", " ")
            content = f"{safe_name}: {content}"
        logger.debug(
            "reply 요청: user=%s, msg_len=%d, context_count=%d",
            (user_name or "?"),
            len(content),
            len(context_messages or []),
        )

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
            raw = _first_choice_content(response, "reply")
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
            raw = _first_choice_content(response, "summarize").strip()
            return raw
        except Exception as e:
            logger.warning("요약 생성 실패: %s", e)
            return ""

    TAROT_WAIT_SYSTEM = (
        "지금 타로 결과 화면이 60초 동안 표시 중입니다. "
        "시청자가 타로 또 봐줘, 봐줘 등 요청해도 창이 닫힐 때까지 기다려 달라고 한 문장으로 짧게 한국어로 답하세요. "
        "반드시 JSON 한 줄만 출력: {\"response\": \"한 문장 답변\"}"
    )

    def generate_tarot_wait_reply(self, user_message: str) -> str:
        """60초 대기 중 타로/봐줘 요청에 쓸 '창 닫힐 때까지 기다려 주세요' 멘트 생성."""
        content = (user_message or "").strip()
        if not content:
            return "아직 이번 타로가 끝나지 않았어요. 창이 닫힐 때까지 잠시만 기다려 주세요."
        messages = [
            {"role": "system", "content": self._system_prompt(self.TAROT_WAIT_SYSTEM)},
            {"role": "user", "content": content},
        ]
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=128,
                response_format={"type": "json_object"},
            )
            raw = _first_choice_content(response, "generate_tarot_wait_reply").strip()
            data = json.loads(raw)
            text = (data.get("response") or "").strip()
            return text or "아직 이번 타로가 끝나지 않았어요. 창이 닫힐 때까지 잠시만 기다려 주세요."
        except Exception as e:
            logger.warning("타로 대기 멘트 생성 실패: %s", e)
            return "아직 이번 타로가 끝나지 않았어요. 창이 닫힐 때까지 잠시만 기다려 주세요."

    def _reply_batch_with_search(self, messages: List[dict], start_time: float, max_iterations: int = 3) -> Optional[str]:
        """도구(search_web) 루프: tool_calls 있으면 검색 실행 후 재호출, content 나올 때까지 반복. 최종 답변이 평문이면 JSON으로 한 번 더 요청."""
        for _ in range(max_iterations):
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=1024,
                tools=[SEARCH_WEB_TOOL],
                tool_choice="auto",
            )
            msg = _first_choice_message(response, "_reply_batch_with_search")
            if msg is None:
                return None
            if not getattr(msg, "tool_calls", None):
                content = (msg.content or "").strip()
                if not content:
                    return None
                # 검색 경로는 모델이 평문으로 답할 수 있음 → replies JSON이면 그대로, 아니면 JSON으로 한 번 더 요청
                try:
                    data = json.loads(content)
                    if isinstance(data, dict) and isinstance(data.get("replies"), list) and len(data["replies"]) > 0:
                        return content
                except json.JSONDecodeError:
                    pass
                # 평문이면 동일 형식(JSON)으로 다시 요청
                formatted = messages + [
                    {"role": "assistant", "content": content},
                    {"role": "user", "content": "위 답변을 그대로 유지한 채, 아래 JSON 형식 한 줄로만 출력하세요. 설명·마크다운 없이. {\"replies\": [{\"response\": \"위 답변 내용 전체\", \"emotion\": \"neutral\"}]}"},
                ]
                try:
                    resp2 = self._client.chat.completions.create(
                        model=self.model,
                        messages=formatted,
                        max_tokens=1024,
                        response_format={"type": "json_object"},
                    )
                    out = _first_choice_content(resp2, "_reply_batch_with_search.reformat").strip()
                    if out:
                        return out
                except Exception as e:
                    logger.warning("검색 답변 JSON 재요청 실패, 평문 반환: %s", e)
                return content
            messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": msg.tool_calls})
            for tc in msg.tool_calls:
                name = getattr(tc.function, "name", None) or ""
                args_str = getattr(tc.function, "arguments", None) or "{}"
                try:
                    args = json.loads(args_str)
                except json.JSONDecodeError:
                    args = {}
                if name == "search_web":
                    query = args.get("query", "").strip()
                    result = run_web_search(query)
                    logger.info("search_web 실행: query=%r, 결과 %d자", query, len(result))
                else:
                    result = "도구를 처리할 수 없습니다."
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
        return None

    def reply_batch(
        self,
        pending: List[Any],
        context_messages: Optional[List[dict]] = None,
        tarot_state: Optional[dict] = None,
        tarot_enabled: bool = True,
        search_enabled: bool = False,
    ) -> List[AIResponse]:
        """
        말하는 동안 쌓인 채팅을 한 번에 보고, 합치기/걸러내기 후 답변 1개 생성 (길어도 됨).
        search_enabled: True면 search_web 도구 사용 가능. 모델이 필요 시 검색 후 답변.
        """
        if not pending:
            return []
        logger.debug(
            "reply_batch 요청: pending=%d, context_count=%d, tarot_phase=%s, tarot_enabled=%s, search_enabled=%s",
            len(pending),
            len(context_messages or []),
            (tarot_state or {}).get("phase"),
            tarot_enabled,
            search_enabled,
        )
        lines = []
        for m in pending:
            user = getattr(m, "user", None) or (m.get("user") if isinstance(m, dict) else None)
            user = _sanitize_user_text(user, max_len=40)
            msg = getattr(m, "message", None) or (m.get("message") if isinstance(m, dict) else None) or ""
            msg = _sanitize_user_text(msg, max_len=500)
            if (msg or "").strip():
                lines.append(f"{user or '?'}: {msg}")
        content = "\n".join(lines)
        if not content.strip():
            return []

        user_content = f"채팅 목록:\n{content}"
        if not tarot_enabled:
            user_content += "\n\n[오늘은 타로/운세 기능 비활성화. 지금 당장 타로 해달라고 요청하면 거절하고 action 넣지 말 것. \"내일은 되나\", \"언제 되나\"처럼 다음에 가능한지·일정을 묻는 말에는 문맥에 맞게 답할 것 (예: 내일/다음 방송 때는 될 수 있다고).]"
        elif tarot_state and tarot_state.get("phase") == "selecting":
            requester = tarot_state.get("requester_nickname") or "다른 분"
            user_content += f"\n\n[현재 타로 **번호 선택** 단계. {requester}님이 1~78 중 N개 고르는 중. 새로 \"타로 봐줘\" 요청한 사람에게는 거절만. action 절대 넣지 말 것. 요청자가 번호(숫자)만 말한 내용은 타로 선택으로 처리되고, 그 외 사람의 타로 요청은 \"지금 다른 분이 보고 있어서 지금은 안 됩니다\" 같은 한 문장만.]"
        elif tarot_state and tarot_state.get("phase") == "revealed":
            user_content += "\n\n[현재 타로 **결과 공개** 단계. 이미 카드를 뽑은 뒤 해석 보여주는 중임. 시청자가 숫자만 말해도(예: 5, 1) **새 타로나 N장 뽑기로 해석하지 말 것**. \"5장 골라주세요\", \"1번부터 78번 중\" 같은 멘트 금지. action 절대 넣지 말 것. 짧게 반응만 하거나 \"이번 타로 끝날 때까지 잠시만 기다려 주세요\" 식으로만 답할 것.]"
        elif tarot_state and tarot_state.get("phase") == "asking_question":
            user_content += "\n\n[현재 타로 단계: 시청자가 \"뭐에 대해 볼지\"에 답한 상태. 위 채팅이 그 답변. 주제를 말했으면 action \"tarot\", tarot_question에 주제, **tarot_spread_count에 주제에 맞는 장수(1~5)를 반드시 넣을 것.** 예/아니오 질문→1, 단순 주제→3, 장기·복잡→5. response에는 그 주제로 볼게요 + 1~78 중 N개 골라달라는 멘트를 존댓말로. 거절·모르겠음·없음이면 일반 답변만, action 넣지 말 것.]"

        if search_enabled:
            kst = timezone(timedelta(hours=9))
            now_str = datetime.now(kst).strftime("%Y-%m-%d %H:%M KST")
            user_content += f"\n\n[현재 시각 (한국 기준): {now_str}]"

        system_content = self._system_prompt(BATCH_SYSTEM_PROMPT)
        if search_enabled:
            system_content += BATCH_SYSTEM_PROMPT_SEARCH_SUFFIX
        messages = [{"role": "system", "content": system_content}]
        if context_messages:
            messages.extend(context_messages)
        messages.append({"role": "user", "content": user_content})

        start = time.perf_counter()
        raw = None
        try:
            if search_enabled:
                raw = self._reply_batch_with_search(messages, start)
            else:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=1024,
                    response_format={"type": "json_object"},
                )
                raw = _first_choice_content(response, "reply_batch")
        except Exception as e:
            err_msg = str(e).lower()
            if "429" in err_msg or "rate_limit" in err_msg:
                # Groq는 TPM(분당)·TPD(일일) 둘 다 있음. 에러에 TPD만 적혀도 실제로는 TPM으로 걸렸을 수 있어, 잠시 후 재시도하면 될 때가 있음.
                e_str = str(e)
                if "tokens per day" in e_str.lower() or "tpd" in e_str.lower():
                    hint = "에러는 TPD(일일) 표시지만, TPM(분당 8K)일 수 있음. 1분 후 재시도 또는 한도 리셋 후 재시도."
                else:
                    hint = "TPM(분당) 또는 TPD(일일) 한도. 1분 후 재시도 또는 한도 리셋 후 재시도."
                logger.warning("Groq 429 Rate limit: %s 원문: %s", hint, e_str[:280])
                return []
            if "400" in err_msg and "json_validate_failed" in err_msg:
                failed_gen = _extract_failed_generation(e)
                if failed_gen:
                    feedback = (
                        "[JSON 검증 실패] 아래 출력이 유효한 JSON이 아니었습니다. "
                        "같은 내용을 반드시 유효한 JSON 한 줄로만 다시 출력하세요. 마크다운·설명 없이.\n\n실패한 출력:\n"
                        + (failed_gen[:2000] if len(failed_gen) > 2000 else failed_gen)
                    )
                else:
                    feedback = (
                        "[JSON 검증 실패] 이전 응답이 JSON 검증에 걸렸습니다. "
                        "반드시 요청한 형식({\"replies\": [{\"response\": \"...\", \"emotion\": \"...\", ...}]})만 한 줄로 출력하세요. 마크다운·설명·추가 문자 없이."
                    )
                logger.warning("Groq JSON 검증 실패, 피드백 담아 재시도: %s", e)
                retry_messages = messages + [{"role": "user", "content": feedback}]
                try:
                    response = self._client.chat.completions.create(
                        model=self.model,
                        messages=retry_messages,
                        max_tokens=1024,
                        response_format={"type": "json_object"},
                    )
                    raw = _first_choice_content(response, "reply_batch.retry_json_validate_failed")
                except Exception as retry_e:
                    logger.exception("Groq batch 피드백 재시도 실패: %s", retry_e)
                    return []
            elif "400" in err_msg and ("tool_use_failed" in err_msg or "request.tools" in err_msg) and "json" in err_msg:
                # 모델이 등록되지 않은 도구 'json'으로 답변을 보낸 경우: failed_generation에서 replies 추출
                failed_gen = _extract_failed_generation(e)
                if failed_gen:
                    try:
                        data = json.loads(failed_gen)
                        if isinstance(data, dict) and (data.get("name") or "").strip().lower() == "json":
                            args = data.get("arguments")
                            if isinstance(args, dict) and "replies" in args:
                                raw = json.dumps(args)
                    except Exception:
                        pass
                if not raw or not raw.strip():
                    logger.warning("Groq tool_use_failed(json) 복구 실패: %s", e)
                    return []
            else:
                logger.exception("Groq batch 호출 실패: %s", e)
                return []
        elapsed = time.perf_counter() - start
        if not raw or not raw.strip():
            if search_enabled:
                return [AIResponse(
                    response="검색으로는 찾지 못했어요. 다른 방법으로 확인해 보시면 좋을 것 같아요.",
                    emotion="neutral",
                    confidence=1.0,
                    processing_time=elapsed,
                )]
            return []

        try:
            text = (raw or "").strip()
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
                action = (item.get("action") or "").strip() or None
                if action and action not in ("tarot_ask_question", "tarot"):
                    action = None
                tarot_question = (item.get("tarot_question") or "").strip() or None
                raw_spread = item.get("tarot_spread_count")
                spread_count = None
                if raw_spread is not None:
                    try:
                        spread_count = int(raw_spread)
                        if spread_count < 1 or spread_count > 5:
                            spread_count = 3
                    except (TypeError, ValueError):
                        spread_count = 3
                if r:
                    tts_text = (item.get("tts_text") or "").strip()
                    out.append(AIResponse(
                        response=r,
                        emotion=e,
                        confidence=1.0,
                        processing_time=elapsed,
                        action=action,
                        tarot_question=tarot_question,
                        tarot_spread_count=spread_count,
                        tts_text=tts_text or None,
                    ))
            # 웹 검색 경로: 모델이 JSON이 아닌 평문으로 답할 수 있음 → 그대로 한 개 답변으로 사용
            if not out and (raw or "").strip():
                out.append(AIResponse(
                    response=(raw or "").strip(),
                    emotion="neutral",
                    confidence=1.0,
                    processing_time=elapsed,
                ))
            logger.info("reply_batch 완료: replies=%d, elapsed=%.3fs", len(out), elapsed)
            return out
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Groq batch JSON 파싱 실패: %s", e)
            # 검색 등으로 평문만 온 경우 그대로 한 개 답변으로 반환
            if raw and (raw or "").strip():
                logger.info("reply_batch 완료(plain fallback): replies=1, elapsed=%.3fs", time.perf_counter() - start)
                return [AIResponse(
                    response=(raw or "").strip(),
                    emotion="neutral",
                    confidence=1.0,
                    processing_time=time.perf_counter() - start,
                )]
            return []

    def get_tarot_interpretation(
        self,
        question: str,
        cards: List[dict],
    ) -> Optional[dict]:
        if not cards:
            return None

        cards_desc = ", ".join(
            f"{c.get('id', '')}" + ("(역방향)" if c.get("reversed") else "")
            for c in cards
        )

        safe_question = _sanitize_user_text(question, max_len=500)
        user_content = f"질문: {safe_question}\n뽑은 카드: {cards_desc}\n상황에 맞는 visual_data를 포함해 JSON으로 답하세요."

        messages = [
            {"role": "system", "content": self._system_prompt(TAROT_INTERPRET_SYSTEM)},
            {"role": "user", "content": user_content},
        ]

        try:
            # 해석 문장이 길면 1024로는 JSON 완성 전에 한도 도달 → 2048로 여유
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=2048,
                response_format={"type": "json_object"},
            )
            raw = _first_choice_content(response, "get_tarot_interpretation").strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].replace("```", "").strip()
            data = json.loads(raw)

            v = data.get("visual_data") or {}
            raw_scores = v.get("scores")
            logger.info("타로 해석 raw visual_data: visual_type=%s, labels=%s, scores=%s", v.get("visual_type"), v.get("labels"), raw_scores)

            # scores가 세미콜론(;) 구분 문자열이면 배열로 변환 (그래프 숫자 붙여 오는 문제 방지)
            labels = v.get("labels") or []
            scores = v.get("scores")
            if isinstance(scores, str) and ";" in scores:
                try:
                    scores = [min(100, max(0, int(x.strip()))) for x in scores.split(";") if x.strip()]
                    v = {**v, "scores": scores}
                except ValueError:
                    scores = None
            if isinstance(scores, list) and labels and len(scores) == len(labels):
                v = {**v, "scores": scores}

            valid_visual = None
            # 1. Yes/No 검증
            if v.get("visual_type") == "yes_no" and v.get("recommendation"):
                valid_visual = v
            # 2. 막대/레이더 검증 (라벨과 점수 개수 일치)
            elif v.get("labels") and v.get("scores") and isinstance(v["scores"], list):
                if len(v["labels"]) == len(v["scores"]) and len(v["scores"]) > 1:
                    valid_visual = v
                    logger.info("타로 visual_data 채택: type=%s, labels=%s, scores=%s", v.get("visual_type"), v.get("labels"), v.get("scores"))

            if valid_visual is None and v:
                reason = "yes_no인데 recommendation 없음" if v.get("visual_type") == "yes_no" else \
                    "labels/scores 없거나 scores 비리스트" if not (v.get("labels") and isinstance(v.get("scores"), list)) else \
                    "labels/scores 개수 불일치 또는 1개뿐"
                logger.info("타로 visual_data 검증 탈락: %s (수신: %s)", reason, v)

            return {
                "interpretation": data.get("interpretation") or "해석을 불러오는 중입니다.",
                "tts_text": data.get("tts_text"),
                "visual_data": valid_visual,
                "soul_color": data.get("soul_color") or "#a855f7",
                "danger_alert": bool(data.get("danger_alert")),
            }

        except Exception as e:
            logger.error("타로 해석 실패: %s", e)
            return None

    TAROT_NUMBERS_SYSTEM = """사용자가 타로 카드 번호를 말했습니다. 1~78 사이 번호를 아래에서 요청한 개수(N개)만큼만 추출하세요.
- 숫자: 123 → [1,2,3], 1 2 3, 12 34 56 78 5 (5장이면 5개)
- 한글: 일 십삼 오십 → [1,13,50], 이십일, 삼십, 사십오 등
- 요청한 N개만 순서대로. 없거나 부족하면 빈 배열.
반드시 JSON 한 줄만: {"numbers": [1, 13, 50]} (개수는 사용자 요청 N에 맞춤)"""

    TAROT_SELECTION_SYSTEM = """현재 타로 번호 선택 단계입니다. 시청자에게 1~78 중 N개를 골라달라고 요청한 상태입니다.

(1) 시청자가 1~78 범위의 정수 번호를 **정확히 N개** 제시했으면 → **반드시** tarot_numbers에 그 N개 배열을 넣고, response에는 확인 멘트(존댓말). tarot_numbers를 비우고 response에만 "N번 선택하셨네요" 쓰면 안 됨. tts_text는 TTS용 문장.
(2) 시청자가 타로 취소(그만, 안 볼래 등)면 → tarot_cancel true, response에 취소 인사.
(3) **N개가 안 나오면**(부족, 범위 밖 포함, 중복, 애매함 등) → tarot_numbers 넣지 말고, response에 "처음부터 다시 N개만 골라주세요" 식으로만 재요청. 부분 인식·누적 없음.

**tarot_numbers 형식:** 숫자를 **세미콜론(;)으로만** 구분한 문자열. 쉼표나 배열 말고 이 형식만 쓸 것. 예: 시청자 "34 35 56" → tarot_numbers: "34;35;56". "343556"처럼 이어쓰지 말 것.
**78 초과·비유효:** 1~78이 아닌 수는 인식하지 말고 response에 "처음부터 다시 N개 골라주세요"만. 중복 번호도 같은 재요청.
emotion: happy, sad, angry, surprised, neutral, excited 중 하나.
JSON: {"response": "...", "tts_text": "...", "emotion": "감정키", "tarot_numbers": "34;35;56" 형식 또는 생략, "tarot_cancel": true 또는 생략}
예시: {"response": "34, 35, 56번 선택하셨네요.", "tts_text": "삼십사, 삼십오, 오십육 번.", "emotion": "neutral", "tarot_numbers": "34;35;56"}"""

    def process_tarot_selection(
        self,
        user_message: str,
        spread_count: int = 3,
        context_messages: Optional[List[dict]] = None,
    ) -> dict:
        """
        타로 번호 선택 단계에서 시청자 말을 AI로 해석. 키워드 없이 자연어 처리.
        Returns: {"response": str, "emotion": str, "tarot_numbers": list|None, "tarot_cancel": bool}
        """
        try:
            spread_count = int(spread_count)
        except (TypeError, ValueError):
            spread_count = 3
        if spread_count < 1 or spread_count > 5:
            spread_count = 3

        out: dict = {
            "response": "1번부터 78번까지 번호 %s개만 골라주세요." % spread_count,
            "emotion": "neutral",
            "tarot_numbers": None,
            "tarot_cancel": False,
        }
        msg = _sanitize_user_text(user_message, max_len=500)
        if not msg:
            return out
        user_content = f"요청한 개수 N: {spread_count}\n시청자 말: {msg}"
        messages: List[dict] = []
        if context_messages:
            messages.extend(context_messages[-6:])
        messages.append({"role": "user", "content": user_content})
        system = self._system_prompt(self.TAROT_SELECTION_SYSTEM)
        api_messages = [{"role": "system", "content": system}, *messages]
        # 토큰 여유 필요 (JSON + tts_text 등). 256이면 'max completion tokens reached' 발생 가능
        max_tok = 512
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=api_messages,
                max_tokens=max_tok,
                response_format={"type": "json_object"},
            )
            raw = _first_choice_content(response, "process_tarot_selection").strip()
        except Exception as e:
            err_msg = str(e).lower()
            if "400" in err_msg and "json_validate_failed" in err_msg:
                failed_gen = _extract_failed_generation(e)
                if failed_gen:
                    feedback = "[JSON 검증 실패] 아래 출력을 유효한 JSON 한 줄로만 다시 출력하세요.\n\n실패한 출력:\n" + (failed_gen[:2000] if len(failed_gen) > 2000 else failed_gen)
                else:
                    feedback = "[JSON 검증 실패] 이전 응답이 JSON 검증에 실패했습니다. response, emotion, tarot_numbers/tarot_cancel 형식만 한 줄 JSON으로 출력하세요."
                try:
                    response = self._client.chat.completions.create(
                        model=self.model,
                        messages=api_messages + [{"role": "user", "content": feedback}],
                        max_tokens=max_tok,
                        response_format={"type": "json_object"},
                    )
                    raw = _first_choice_content(response, "process_tarot_selection.retry_json_validate_failed").strip()
                except Exception as retry_e:
                    logger.warning("타로 선택 피드백 재시도 실패: %s", retry_e)
                    raw = None
            else:
                logger.warning("타로 선택 단계 Groq 실패: %s", e)
                raw = None
        if raw is None:
            default_reask = out["response"]  # "1번부터 78번까지 번호 N개만 골라주세요."
            try:
                explain_prompt = (
                    f"시청자가 \"{msg}\"라고 했습니다. 이건 1~78 범위의 자연수 {spread_count}개로 인식되지 않습니다. "
                    f"왜 안 되는지 한 줄 설명한 뒤, 1~78 중 {spread_count}개만 골라달라고 재요청하는 문장을 한국어 존댓말로 한 문장만 출력하세요. JSON·마크다운 없이 그 문장만."
                )
                resp = self._client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "system", "content": "한 문장만 출력하세요. JSON·설명 추가 없이."}, {"role": "user", "content": explain_prompt}],
                    max_tokens=256,
                )
                fallback_text = _first_choice_content(resp, "process_tarot_selection.fallback_sentence").strip().strip("'\"")
                # 사용자 말 그대로 돌려받거나 짧으면 기본 재요청 문구 사용
                if fallback_text and len(fallback_text) > 20 and fallback_text.strip() != msg.strip():
                    if msg.strip() not in fallback_text or len(fallback_text) > len(msg) + 15:
                        out["response"] = fallback_text
                if not (out["response"] or "").strip() or out["response"].strip() == msg.strip():
                    out["response"] = default_reask
            except Exception as fallback_e:
                logger.warning("타로 선택 설명 문장 생성 실패: %s", fallback_e)
            return out
        try:
            data = json.loads(raw)
            out["response"] = (data.get("response") or out["response"]).strip() or out["response"]
            tts_text = (data.get("tts_text") or "").strip()
            if tts_text:
                out["tts_text"] = tts_text
            out["emotion"] = (data.get("emotion") or "neutral").strip()
            if out["emotion"] not in VALID_EMOTIONS:
                out["emotion"] = "neutral"
            if data.get("tarot_cancel") is True:
                out["tarot_cancel"] = True
                return out
            nums = _parse_int_list(data.get("tarot_numbers") or data.get("tarotNumbers"))
            has_duplicate = False
            clean: List[int] = []
            for x in nums:
                try:
                    if isinstance(x, float) and x != int(x):
                        continue
                    n = int(x) if not isinstance(x, int) else x
                    if 1 <= n <= 78:
                        if n not in clean:
                            clean.append(n)
                        else:
                            has_duplicate = True
                except (TypeError, ValueError):
                    continue
            clean = clean[:spread_count]
            if has_duplicate:
                out["tarot_numbers"] = None
                out["response"] = f"중복된 번호가 있어요. 처음부터 다시 {spread_count}개 골라주세요."
                out["tts_text"] = out["response"]
                logger.info("타로 번호 중복 감지 → 처음부터 재선택 요청")
            elif len(clean) >= spread_count:
                out["tarot_numbers"] = clean[:spread_count]
                logger.info("타로 번호 인식: %s", out["tarot_numbers"])
            # AI가 tarot_numbers를 빼먹었고 response가 확인 멘트면 → 이전 응답 + 시청자 말 주고 "tarot_numbers 채워서 JSON 다시 출력" 요청
            if out["tarot_numbers"] is None and out.get("response") and ("번 선택" in out["response"] or "번 골라" in out["response"]):
                try:
                    prev = json.dumps({"response": out["response"], "tts_text": out.get("tts_text") or "", "emotion": out["emotion"]}, ensure_ascii=False)
                    retry_system = (
                        "이전 JSON에 tarot_numbers가 빠져있다. tarot_numbers는 **세미콜론(;)으로 구분한 문자열**만 넣을 것. "
                        "예: 시청자 '34 35 56' → tarot_numbers: \"34;35;56\". 숫자 이어쓰지 말 것."
                    )
                    retry_user = f"요청 개수 N: {spread_count}\n시청자 말: {msg}\n\n이전 응답:\n{prev}\n\n위 이전 응답에 tarot_numbers를 \"숫자;숫자;...\" 형식(세미콜론 구분)으로 넣은 JSON 한 줄로 출력."
                    retry_resp = self._client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": retry_system},
                            {"role": "user", "content": retry_user},
                        ],
                        max_tokens=max_tok,
                        response_format={"type": "json_object"},
                    )
                    retry_raw = _first_choice_content(retry_resp, "process_tarot_selection.retry_fill_tarot_numbers").strip()
                    if retry_raw:
                        retry_data = json.loads(retry_raw)
                        nums = _parse_int_list(retry_data.get("tarot_numbers") or retry_data.get("tarotNumbers"))
                        retry_clean = [n for n in nums if 1 <= int(n) <= 78]
                        if len(retry_clean) >= spread_count:
                            out["tarot_numbers"] = [int(x) for x in retry_clean[:spread_count]]
                            logger.info("타로 번호 AI 재요청으로 채움: %s", out["tarot_numbers"])
                        elif len(retry_clean) > 0:
                            # [3419]처럼 잘못 온 경우 → AI에게 그대로 보여주고 "N개 별도 번호로 다시" 한 번 더 요청
                            wrong_json = json.dumps(retry_data, ensure_ascii=False)
                            fix_resp = self._client.chat.completions.create(
                                model=self.model,
                                messages=[
                                    {"role": "system", "content": "tarot_numbers를 **세미콜론(;)으로 구분한 문자열**로 수정. 예: \"34;35;56\". 숫자 이어쓰지 말 것. 같은 JSON 한 줄로 출력."},
                                    {"role": "user", "content": f"요청 개수 N: {spread_count}\n시청자 말: {msg}\n\n잘못된 응답:\n{wrong_json}\n\ntarot_numbers만 \"숫자;숫자;숫자\" 형식(세미콜론 구분)으로 고친 JSON 한 줄로 출력."},
                                ],
                                max_tokens=max_tok,
                                response_format={"type": "json_object"},
                            )
                            fix_raw = _first_choice_content(fix_resp, "process_tarot_selection.retry_fix_tarot_numbers").strip()
                            if fix_raw:
                                fix_data = json.loads(fix_raw)
                                fix_nums = _parse_int_list(fix_data.get("tarot_numbers") or fix_data.get("tarotNumbers"))
                                fix_clean = [n for n in fix_nums if 1 <= int(n) <= 78]
                                if len(fix_clean) >= spread_count:
                                    out["tarot_numbers"] = [int(x) for x in fix_clean[:spread_count]]
                                    logger.info("타로 번호 AI 수정 요청으로 채움: %s", out["tarot_numbers"])
                                else:
                                    logger.warning("타로 수정 요청 후에도 tarot_numbers 부족: %s", fix_raw[:200])
                        else:
                            logger.warning("타로 재요청 응답에 tarot_numbers 없음 또는 부족: %s", retry_raw[:200])
                except (json.JSONDecodeError, TypeError, Exception) as retry_e:
                    logger.warning("타로 tarot_numbers 재요청 실패: %s", retry_e)

            return out
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("타로 선택 JSON 파싱 실패: %s", e)
            default_reask = out["response"]
            try:
                explain_prompt = (
                    f"시청자가 \"{msg}\"라고 했습니다. 이건 1~78 범위의 자연수 {spread_count}개로 인식되지 않습니다. "
                    f"왜 안 되는지 한 줄 설명한 뒤, 1~78 중 {spread_count}개만 골라달라고 재요청하는 문장을 한국어 존댓말로 한 문장만 출력하세요. JSON·마크다운 없이 그 문장만."
                )
                resp = self._client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "system", "content": "한 문장만 출력하세요. JSON·설명 추가 없이."}, {"role": "user", "content": explain_prompt}],
                    max_tokens=256,
                )
                fallback_text = _first_choice_content(resp, "process_tarot_selection.json_parse_fallback_sentence").strip().strip("'\"")
                if fallback_text and len(fallback_text) > 20 and fallback_text.strip() != msg.strip():
                    if msg.strip() not in fallback_text or len(fallback_text) > len(msg) + 15:
                        out["response"] = fallback_text
                if not (out["response"] or "").strip() or out["response"].strip() == msg.strip():
                    out["response"] = default_reask
            except Exception:
                pass
            return out

    def _korean_numbers_to_digits(self, text: str) -> str:
        """한글 숫자 표현을 아라비아 숫자로 치환 (하나 다섯 십삼 → 1 5 13)."""
        if not text or not text.strip():
            return text
        # 긴 패턴 먼저 치환 (십삼 before 십/삼)
        table = [
            ("십삼", " 13 "), ("십이", " 12 "), ("십일", " 11 "), ("십구", " 19 "), ("십팔", " 18 "),
            ("십칠", " 17 "), ("십육", " 16 "), ("십오", " 15 "), ("십사", " 14 "),
            ("열셋", " 13 "), ("열둘", " 12 "), ("열하나", " 11 "), ("열한", " 11 "), ("열아홉", " 19 "), ("열여덟", " 18 "),
            ("열일곱", " 17 "), ("열여섯", " 16 "), ("열다섯", " 15 "), ("열넷", " 14 "),
            ("스무아홉", " 29 "), ("스무여덟", " 28 "), ("스무일곱", " 27 "), ("스무여섯", " 26 "),
            ("스무다섯", " 25 "), ("스무넷", " 24 "), ("스무셋", " 23 "), ("스무둘", " 22 "), ("스무하나", " 21 "),
            ("스물", " 20 "), ("스무", " 20 "), ("이십", " 20 "), ("삼십", " 30 "), ("사십", " 40 "),
            ("오십", " 50 "), ("육십", " 60 "), ("칠십", " 70 "),
            ("하나", " 1 "), ("둘", " 2 "), ("셋", " 3 "), ("넷", " 4 "), ("다섯", " 5 "),
            ("여섯", " 6 "), ("일곱", " 7 "), ("여덟", " 8 "), ("아홉", " 9 "), ("열", " 10 "),
            ("일", " 1 "), ("이", " 2 "), ("삼", " 3 "), ("사", " 4 "), ("오", " 5 "),
            ("육", " 6 "), ("칠", " 7 "), ("팔", " 8 "), ("구", " 9 "), ("십", " 10 "),
        ]
        s = " " + (text or "") + " "
        for k, v in table:
            s = s.replace(k, v)
        return s

    def _parse_tarot_numbers_fallback(
        self, text: str, spread_count: int, return_partial: bool = False
    ) -> Optional[List[int]]:
        """숫자만 추출. 'N번' 패턴을 먼저 쓰고, 한글(하나/다섯/십삼 등)은 숫자로 치환.
        return_partial True면 N개 미만이어도 찾은 번호만 반환(누적용). '3장' 같은 건 번호로 안 씀."""
        import re
        out: List[int] = []
        # "77번과 65번"처럼 카드 번호만 추출 (3장·한 장 등 제외)
        for m in re.findall(r"(\d+)\s*번", text or ""):
            n = int(m)
            if 1 <= n <= 78 and n not in out:
                out.append(n)
                if len(out) >= spread_count:
                    return out[:spread_count]
        normalized = self._korean_numbers_to_digits(text or "")
        for m in re.findall(r"\d+", normalized):
            n = int(m)
            if 1 <= n <= 78 and n not in out:
                out.append(n)
                if len(out) >= spread_count:
                    return out[:spread_count]
        if len(out) < spread_count:
            for m in re.findall(r"\d+", text or ""):
                n = int(m)
                if 1 <= n <= 78 and n not in out:
                    out.append(n)
                    if len(out) >= spread_count:
                        return out[:spread_count]
        if len(out) < spread_count:
            for m in re.findall(r"\d+", text or ""):
                if len(m) >= spread_count:
                    for c in m:
                        if len(out) >= spread_count:
                            break
                        x = int(c)
                        if 1 <= x <= 9 and x not in out:
                            out.append(x)
                    if len(out) >= spread_count:
                        return out[:spread_count]
                    break
        if return_partial and out:
            return out
        return out[:spread_count] if len(out) >= spread_count else None

    def parse_tarot_card_numbers(
        self,
        user_message: str,
        spread_count: int = 3,
    ) -> Optional[List[int]]:
        """사용자 멘트(123, 일 십삼 오십 등)에서 1~78 번호를 AI가 추출. 실패 시 단순 숫자 파싱 폴백."""
        try:
            spread_count = int(spread_count)
        except (TypeError, ValueError):
            spread_count = 3
        if spread_count < 1 or spread_count > 5:
            spread_count = 3

        safe_user_message = _sanitize_user_text(user_message, max_len=500)
        if not safe_user_message:
            return None
        messages = [
            {"role": "system", "content": self.TAROT_NUMBERS_SYSTEM},
            {"role": "user", "content": f"사용자 말: {safe_user_message}\n\n1~78 번호 {spread_count}개만 JSON으로."},
        ]
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=128,
                response_format={"type": "json_object"},
            )
            raw = _first_choice_content(response, "parse_tarot_card_numbers").strip()
        except Exception as e:
            err_msg = str(e).lower()
            if "400" in err_msg and "json_validate_failed" in err_msg:
                failed_gen = _extract_failed_generation(e)
                if failed_gen:
                    feedback = "[JSON 검증 실패] 아래 출력을 유효한 JSON 한 줄로만 다시 출력하세요.\n\n실패한 출력:\n" + (failed_gen[:1500] if len(failed_gen) > 1500 else failed_gen)
                else:
                    feedback = "[JSON 검증 실패] 이전 응답이 JSON 검증에 실패했습니다. {\"numbers\": [1,2,3]} 형식만 한 줄로 출력하세요."
                try:
                    response = self._client.chat.completions.create(
                        model=self.model,
                        messages=messages + [{"role": "user", "content": feedback}],
                        max_tokens=128,
                        response_format={"type": "json_object"},
                    )
                    raw = _first_choice_content(response, "parse_tarot_card_numbers.retry_json_validate_failed").strip()
                except Exception as retry_e:
                    logger.warning("타로 번호 추출 피드백 재시도 실패: %s", retry_e)
                    return self._parse_tarot_numbers_fallback(safe_user_message, spread_count)
            else:
                logger.warning("타로 번호 추출 Groq 실패: %s", e)
                return self._parse_tarot_numbers_fallback(safe_user_message, spread_count)
        try:
            data = json.loads(raw)
            nums = data.get("numbers")
            if not isinstance(nums, list):
                return self._parse_tarot_numbers_fallback(safe_user_message, spread_count)
            out = []
            for x in nums[:spread_count]:
                try:
                    n = int(x) if not isinstance(x, int) else x
                    if 1 <= n <= 78 and n not in out:
                        out.append(n)
                except (TypeError, ValueError):
                    continue
            if len(out) >= spread_count:
                return out[:spread_count]
            return self._parse_tarot_numbers_fallback(safe_user_message, spread_count)
        except (json.JSONDecodeError, TypeError):
            return self._parse_tarot_numbers_fallback(safe_user_message, spread_count)
