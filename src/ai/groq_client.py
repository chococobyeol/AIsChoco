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
from pathlib import Path
from typing import Any, List, Optional

from openai import OpenAI

from .models import AIResponse, VALID_EMOTIONS

logger = logging.getLogger(__name__)


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
    return ""

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

타로(운세) 관련:
- "타로 봐줘" / "타로 봐달라"처럼 주제 없이만 말한 경우: 반드시 "뭐에 대해 볼지"만 물어라. 번호(1~78 등) 말하면 안 됨. action "tarot_ask_question"만.
- 시청자가 이미 주제를 말했을 때만: 그 주제로 타로 보겠다고 한 뒤, 1~78 중 번호 N개를 골라달라고 요청하는 멘트를 반드시 존댓말로, 매번 표현을 다르게 자연스럽게. action "tarot", tarot_question에 주제, **tarot_spread_count에 주제에 맞는 장수(1~5)를 반드시 넣을 것. 생략 금지.** 주제에 따라 정하기: 예/아니오 질문(비 올까? 될까? 만날까?)→1, 단순·짧은 주제(내일 뭐할지, 오늘 운세, 이번 주)→3, 복잡·장기(내년 계획, 진로/인생 방향, 올해 운세)→5. 시청자가 "한 장만"/"1장"/"5장" 등으로 말했으면 그에 따름. 말 없으면 주제 성격으로 1·3·5 중 골라서 넣기.
- 주제를 안 말했거나 거절이면 일반 답변만, action 없음.
- 일반 대화면 action 생략.

JSON 형식 (한 줄, 설명 없이):
{"replies": [{"response": "한 문장(화면 표시용)", "tts_text": "TTS로 읽었을 때 한국어로 자연스럽게 들리도록 같은 내용을 말하기 좋은 문장(선택)", "emotion": "감정키", "action": "tarot_ask_question"|"tarot"|생략, "tarot_question": "주제"|""|생략, "tarot_spread_count": 1|2|3|4|5}]}
action이 "tarot"일 때는 tarot_spread_count 반드시 1~5 중 하나로 넣기. 생략하지 말 것.
replies는 최대 1개. emotion은 반드시: happy, sad, angry, surprised, neutral, excited 중 하나. tts_text 없으면 response로 TTS."""

SUMMARIZE_PROMPT = """다음 대화 내용을 간결하게 요약해주세요. 중요한 맥락과 주제는 유지하세요. 한국어로 한 문단 이내."""

# src/ai/groq_client.py 의 TAROT_INTERPRET_SYSTEM 변수를 이걸로 교체하세요.

TAROT_INTERPRET_SYSTEM = """당신은 타로 해석가입니다. 질문과 카드에 맞춰 해석과 시각화 데이터를 JSON으로 출력하세요.

visual_data 작성 규칙 (반드시 지킬 것):
- scores는 **항상 JSON 배열**이며, **labels 개수와 동일한 개수**의 숫자(0~100)를 넣으세요. 한 개의 숫자로 합치지 말 것.
1. **Yes/No 질문** (예: 비 올까? 합격할까?):
   - "visual_type": "yes_no"
   - "recommendation": "YES" 또는 "NO" (또는 "SEMI-YES")
   - "score": 긍정 확률 (0~100, 숫자 하나)

2. **양자택일/비교** (예: A가 좋을까 B가 좋을까?):
   - "visual_type": "bar"
   - "labels": ["A 선택", "B 선택"]
   - "scores": [70, 30]  ← 배열, 항목별 점수

3. **종합 운세/일반** (오늘의 운세, 내일 뭐할지 등):
   - "visual_type": "radar"
   - "labels": ["금전", "애정", "건강", "학업/일", "대인관계"] (상황에 맞게 변형 가능)
   - "scores": [80, 70, 60, 90, 75]  ← labels와 **같은 개수**의 숫자 배열, 각 0~100

출력 예시(JSON 한 줄):
yes_no: {"interpretation": "...", "tts_text": "...", "visual_data": {"visual_type": "yes_no", "recommendation": "YES", "score": 85}, "soul_color": "#FFD700", "danger_alert": false}
radar: {"interpretation": "...", "tts_text": "...", "visual_data": {"visual_type": "radar", "labels": ["금전","애정","건강","학업","대인"], "scores": [80,70,60,90,75]}, "soul_color": "#FFD700", "danger_alert": false}"""


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
        tarot_state: Optional[dict] = None,
        tarot_enabled: bool = True,
    ) -> List[AIResponse]:
        """
        말하는 동안 쌓인 채팅을 한 번에 보고, 합치기/걸러내기 후 답변 1개 생성 (길어도 됨).
        pending: .user, .message 속성 있는 객체 리스트 (ChatMessage 등).
        tarot_state: 현재 타로 상태. phase가 "asking_question"이면 방금 채팅이 "뭐에 대해 볼지"에 대한 답이므로, 주제면 action tarot, 거절/모르겠음이면 action 없이 일반 답변.
        tarot_enabled: False면 타로 기능 비활성화. 타로 요청해도 AI가 거절만 하도록 안내.
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

        user_content = f"채팅 목록:\n{content}"
        if not tarot_enabled:
            user_content += "\n\n[오늘은 타로/운세 기능 비활성화. 지금 당장 타로 해달라고 요청하면 거절하고 action 넣지 말 것. \"내일은 되나\", \"언제 되나\"처럼 다음에 가능한지·일정을 묻는 말에는 문맥에 맞게 답할 것 (예: 내일/다음 방송 때는 될 수 있다고).]"
        elif tarot_state and tarot_state.get("phase") in ("selecting", "revealed"):
            requester = tarot_state.get("requester_nickname") or "다른 분"
            user_content += f"\n\n[현재 타로 진행 중. {requester}님이 보고 있는 중이므로, 새로 \"타로 봐줘\" 요청한 사람에게는 거절하고 \"지금 다른 분이 보고 있어서 지금은 안 됩니다\" 같은 한 문장만 답할 것. action 절대 넣지 말 것. 지금 타로 보는 사람(요청자)이 번호 등을 말한 내용만 타로 선택으로 처리하고, 그 외 사람의 타로 요청은 위처럼 거절만.]"
        elif tarot_state and tarot_state.get("phase") == "asking_question":
            user_content += "\n\n[현재 타로 단계: 시청자가 \"뭐에 대해 볼지\"에 답한 상태. 위 채팅이 그 답변. 주제를 말했으면 action \"tarot\", tarot_question에 주제, **tarot_spread_count에 주제에 맞는 장수(1~5)를 반드시 넣을 것.** 예/아니오 질문→1, 단순 주제→3, 장기·복잡→5. response에는 그 주제로 볼게요 + 1~78 중 N개 골라달라는 멘트를 존댓말로. 거절·모르겠음·없음이면 일반 답변만, action 넣지 말 것.]"

        messages = [{"role": "system", "content": self._system_prompt(BATCH_SYSTEM_PROMPT)}]
        if context_messages:
            messages.extend(context_messages)
        messages.append({"role": "user", "content": user_content})

        start = time.perf_counter()
        raw = None
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content
        except Exception as e:
            err_msg = str(e).lower()
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
                    raw = response.choices[0].message.content
                except Exception as retry_e:
                    logger.exception("Groq batch 피드백 재시도 실패: %s", retry_e)
                    return []
            else:
                logger.exception("Groq batch 호출 실패: %s", e)
                return []
        elapsed = time.perf_counter() - start
        if not raw or not raw.strip():
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
            return out
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Groq batch JSON 파싱 실패: %s", e)
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

        user_content = f"질문: {question}\n뽑은 카드: {cards_desc}\n상황에 맞는 visual_data를 포함해 JSON으로 답하세요."

        messages = [
            {"role": "system", "content": self._system_prompt(TAROT_INTERPRET_SYSTEM)},
            {"role": "user", "content": user_content},
        ]

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            raw = (response.choices[0].message.content or "").strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].replace("```", "").strip()
            data = json.loads(raw)

            v = data.get("visual_data") or {}
            logger.info("타로 해석 raw visual_data: %s", v)

            # [검증 로직 강화] 데이터가 깨졌거나 조건에 안 맞으면 과감하게 None 처리
            valid_visual = None
            labels = v.get("labels") or []
            scores = v.get("scores")

            # 모델이 scores를 한 개 정수로 이어붙여 보낸 경우 복구 시도 (예: [4080603070] → [40,80,60,30,70])
            if labels and isinstance(scores, list) and len(scores) == 1 and isinstance(scores[0], int):
                one = scores[0]
                s = str(one)
                n = len(labels)
                if n >= 2 and len(s) == n * 2 and s.isdigit():
                    try:
                        scores = [min(100, int(s[i * 2 : (i + 1) * 2])) for i in range(n)]
                    except (ValueError, IndexError):
                        pass
                if isinstance(scores, list) and len(scores) == n:
                    v = {**v, "scores": scores}

            # 1. Yes/No 검증
            if v.get("visual_type") == "yes_no" and v.get("recommendation"):
                valid_visual = v
            # 2. 막대/레이더 검증 (라벨과 점수 개수가 일치해야 함)
            elif v.get("labels") and v.get("scores") and isinstance(v["scores"], list):
                if len(v["labels"]) == len(v["scores"]) and len(v["scores"]) > 1:
                    valid_visual = v

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

    TAROT_SELECTION_SYSTEM = """현재 타로 번호 선택 단계입니다. 시청자에게 1~78 중 N개를 골라달라고 요청한 상태에서 시청자가 말한 내용을 자연어로 이해하세요.
**중요: 시청자가 1~78 번호를 제시했으면 반드시 tarot_numbers에 정수 배열을 넣어야 합니다. 숫자·한글 모두 인식: "123"→[1,2,3], "하나 다섯 십삼"→[1,5,13], "열한번 스무번 일번"→[11,20,1], "일곱 여덟 아홉"→[7,8,9] 등. 생략 금지.**
"이미 고른 번호"가 있으면 이번에 말한 번호와 합쳐서 총 N개가 되도록 tarot_numbers에 **전체 번호 배열**을 넣으세요.

(1) 시청자가 1~78 범위의 **정수** 번호를 제시했으면 → **반드시** tarot_numbers에 [전체 N개] 넣고, response에는 그걸 확인하는 짧은 한 문장(존댓말). tts_text에는 같은 내용을 TTS로 읽었을 때 한국어로 자연스럽게 들리도록 말하기 좋은 문장으로.
(2) 시청자가 타로를 하지 않겠다는 의도(취소, 그만, 안 볼래 등)면 → tarot_cancel을 true로 하고, response에는 취소 인사 한 문장(존댓말).
(3) 시청자가 "결과 알려줘", "답변해" 등 해석을 요구하면 → tarot_numbers 없이, response에 이유 한 줄 설명 후 재요청. tts_text는 읽었을 때 자연스러운 한국어로.
(4) 번호가 아니거나 부족/애매하면 → tarot_numbers 없이, response에 왜 인식 안 됐는지 한 줄 설명 후 재요청. tts_text는 읽었을 때 자연스러운 한국어로.

emotion: happy, sad, angry, surprised, neutral, excited 중 하나.
번호를 인식했으면 response에 확인 멘트를 쓸 때 반드시 tarot_numbers에도 같은 번호 배열을 넣어야 해석 단계로 진행됩니다. 생략하지 마세요.
JSON 한 줄만: {"response": "표시용 문장", "tts_text": "TTS로 읽었을 때 자연스러운 한국어 문장", "emotion": "감정키", "tarot_numbers": [1,2,3] 또는 생략, "tarot_cancel": true 또는 생략}
예시(번호 인식 시): {"response": "1, 5, 13번 선택하셨네요.", "tts_text": "일, 오, 십삼 번 선택하셨네요.", "emotion": "neutral", "tarot_numbers": [1, 5, 13]}"""

    def process_tarot_selection(
        self,
        user_message: str,
        spread_count: int = 3,
        context_messages: Optional[List[dict]] = None,
        pending_numbers: Optional[List[int]] = None,
    ) -> dict:
        """
        타로 번호 선택 단계에서 시청자 말을 AI로 해석. 키워드 없이 자연어 처리.
        pending_numbers: 이전 턴에 이미 고른 번호(예: [19,22]). 있으면 이번 말과 합쳐서 N개가 되면 반환.
        Returns: {"response": str, "emotion": str, "tarot_numbers": list|None, "tarot_cancel": bool}
        """
        out: dict = {
            "response": "1번부터 78번까지 번호 %s개만 골라주세요." % spread_count,
            "emotion": "neutral",
            "tarot_numbers": None,
            "tarot_cancel": False,
        }
        msg = (user_message or "").strip()
        # 시청자 말에 1~78 번호가 중복으로 들어갔는지 검사 (순서 유지해서 중복만 판별)
        _all = [int(m) for m in re.findall(r"\d+", msg) if m.isdigit() and 1 <= int(m) <= 78]
        user_has_duplicate = len(_all) != len(set(_all))
        pending = [int(x) for x in (pending_numbers or []) if isinstance(x, (int, float)) and 1 <= int(x) <= 78]
        pending = list(dict.fromkeys(pending))[:spread_count]
        if pending:
            user_content = f"이미 고른 번호: {', '.join(map(str, pending))}. 아직 부족한 개수: {spread_count - len(pending)}개. 요청한 총 개수 N: {spread_count}\n시청자 이번 말: {msg or '(추가로 고름)'}"
        elif not msg:
            return out
        else:
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
            raw = (response.choices[0].message.content or "").strip()
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
                    raw = (response.choices[0].message.content or "").strip()
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
                fallback_text = (resp.choices[0].message.content or "").strip().strip("'\"")
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
            nums = data.get("tarot_numbers") or data.get("tarotNumbers")
            if not isinstance(nums, list) and isinstance(nums, str):
                nums = [x.strip() for x in nums.replace("，", ",").split(",") if x.strip()]
            has_duplicate = False
            if isinstance(nums, list):
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
                if pending:
                    merged = list(pending)
                    for n in clean:
                        if n not in merged:
                            merged.append(n)
                        if len(merged) >= spread_count:
                            break
                    clean = merged[:spread_count]
                else:
                    clean = clean[:spread_count]
                if has_duplicate:
                    out["tarot_numbers"] = None
                    out["response"] = f"중복된 번호가 있어요. 처음부터 다시 {spread_count}개 골라주세요."
                    out["tts_text"] = out["response"]
                    logger.info("타로 번호 중복 감지 → 처음부터 재선택 요청")
                elif len(clean) >= spread_count:
                    out["tarot_numbers"] = clean[:spread_count]
                    logger.info("타로 번호 인식: %s", out["tarot_numbers"])
            # AI가 JSON에 tarot_numbers를 안 넣은 경우 → 응답 문장에서 번호 추출 (전체 또는 부분)
            if out["tarot_numbers"] is None and out.get("response") and not has_duplicate:
                resp = out["response"]
                from_resp = self._parse_tarot_numbers_fallback(resp, spread_count, return_partial=True)
                if from_resp:
                    if len(from_resp) >= spread_count:
                        out["tarot_numbers"] = from_resp[:spread_count]
                        logger.info("타로 번호 AI 응답문에서 추출: %s", out["tarot_numbers"])
                    else:
                        # 부분만 인식(예: 77, 65) → pending_numbers로 저장되도록
                        out["tarot_numbers"] = from_resp
                        logger.info("타로 번호 AI 응답문에서 부분 추출(누적용): %s", out["tarot_numbers"])

            # 시청자 말에 중복 번호가 있으면 무조건 처음부터 다시 뽑으라고 함 (JSON/fallback 경로 상관없이)
            if user_has_duplicate:
                out["tarot_numbers"] = None
                out["response"] = f"중복된 번호가 있어요. 처음부터 다시 {spread_count}개 골라주세요."
                out["tts_text"] = out["response"]
                logger.info("타로 번호 시청자 말 중복 감지 → 처음부터 재선택 요청")

            # 시청자 말에서 추출한 번호와 AI 해석이 다르면 피드백으로 한 번 재시도 (중복 안내한 경우는 제외)
            parsed_from_msg = _parse_numbers_1_78(msg)
            ai_nums = out.get("tarot_numbers")
            ai_nums = list(ai_nums)[:spread_count] if isinstance(ai_nums, list) else []
            if not has_duplicate and not user_has_duplicate and parsed_from_msg and set(ai_nums) != set(parsed_from_msg):
                feedback = (
                    f"[번호 해석 오류] 시청자 말: \"{msg}\". 위에서 추출한 번호가 시청자가 말한 숫자와 다릅니다. "
                    f"시청자가 말한 숫자 중 1~78만 순서대로 사용하세요. (예: 50 46 88 → 50, 46만 유효, 88은 78 초과 제외. "
                    f"{spread_count}개 필요하면 부족분만큼 더 골라달라고 재요청.) 동일한 JSON 형식으로 다시 출력하세요."
                )
                retry_messages = api_messages + [
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": feedback},
                ]
                try:
                    response2 = self._client.chat.completions.create(
                        model=self.model,
                        messages=retry_messages,
                        max_tokens=max_tok,
                        response_format={"type": "json_object"},
                    )
                    raw2 = (response2.choices[0].message.content or "").strip()
                    data2 = json.loads(raw2)
                    out["response"] = (data2.get("response") or out["response"]).strip() or out["response"]
                    if (data2.get("tts_text") or "").strip():
                        out["tts_text"] = (data2.get("tts_text") or "").strip()
                    out["emotion"] = (data2.get("emotion") or "neutral").strip()
                    if out["emotion"] not in VALID_EMOTIONS:
                        out["emotion"] = "neutral"
                    if data2.get("tarot_cancel") is True:
                        out["tarot_cancel"] = True
                        return out
                    nums2 = data2.get("tarot_numbers") or data2.get("tarotNumbers")
                    if isinstance(nums2, list):
                        clean2: List[int] = []
                        for x in nums2:
                            try:
                                if isinstance(x, float) and x != int(x):
                                    continue
                                n = int(x) if not isinstance(x, int) else x
                                if 1 <= n <= 78 and n not in clean2:
                                    clean2.append(n)
                            except (TypeError, ValueError):
                                continue
                        if pending:
                            merged2 = list(pending)
                            for n in clean2:
                                if n not in merged2:
                                    merged2.append(n)
                                if len(merged2) >= spread_count:
                                    break
                            clean2 = merged2[:spread_count]
                        else:
                            clean2 = clean2[:spread_count]
                        if len(clean2) >= spread_count:
                            out["tarot_numbers"] = clean2[:spread_count]
                            logger.info("타로 번호 피드백 재시도 후: %s", out["tarot_numbers"])
                    if out.get("tarot_numbers") is None and out.get("response"):
                        from_resp2 = self._parse_tarot_numbers_fallback(out["response"], spread_count, return_partial=True)
                        if from_resp2:
                            out["tarot_numbers"] = from_resp2[:spread_count] if len(from_resp2) >= spread_count else from_resp2
                            logger.info("타로 번호 피드백 재시도 응답문에서 추출: %s", out["tarot_numbers"])
                except Exception as retry_e:
                    logger.warning("타로 선택 피드백 재시도 실패: %s", retry_e)
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
                fallback_text = (resp.choices[0].message.content or "").strip().strip("'\"")
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
        if not (user_message or "").strip():
            return None
        messages = [
            {"role": "system", "content": self.TAROT_NUMBERS_SYSTEM},
            {"role": "user", "content": f"사용자 말: {user_message.strip()}\n\n1~78 번호 {spread_count}개만 JSON으로."},
        ]
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=128,
                response_format={"type": "json_object"},
            )
            raw = (response.choices[0].message.content or "").strip()
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
                    raw = (response.choices[0].message.content or "").strip()
                except Exception as retry_e:
                    logger.warning("타로 번호 추출 피드백 재시도 실패: %s", retry_e)
                    return self._parse_tarot_numbers_fallback(user_message, spread_count)
            else:
                logger.warning("타로 번호 추출 Groq 실패: %s", e)
                return self._parse_tarot_numbers_fallback(user_message, spread_count)
        try:
            data = json.loads(raw)
            nums = data.get("numbers")
            if not isinstance(nums, list):
                return self._parse_tarot_numbers_fallback(user_message, spread_count)
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
            return self._parse_tarot_numbers_fallback(user_message, spread_count)
        except (json.JSONDecodeError, TypeError):
            return self._parse_tarot_numbers_fallback(user_message, spread_count)
