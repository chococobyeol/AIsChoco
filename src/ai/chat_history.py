"""
채팅 히스토리 관리 (PRD 4.5.2, 6.2.1)
토큰 기반 슬라이딩 윈도우 + 요약 + RAG용 주기적 백업 + 수동 백업.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .groq_client import GroqClient

logger = logging.getLogger(__name__)

# rate limit 완화: API에 넘기는 컨텍스트 상한 축소 (5K→3K). 7K 도달 시 요약.
DEFAULT_MAX_TOKENS = 3000
DEFAULT_SUMMARY_THRESHOLD = 7000
DEFAULT_SUMMARY_TOKENS = 2000  # 요약 시 잘라낼 오래된 분량


def count_tokens(text: str) -> int:
    """대략적인 토큰 수. tiktoken 있으면 사용, 없으면 len//4 근사."""
    if not text:
        return 0
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text) // 4)


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


class ChatHistory:
    """
    토큰 기반 슬라이딩 윈도우 + 요약.
    요약 시 history/summaries/ 에 타임스탬프 백업 (RAG 연동 가능).
    """

    def __init__(
        self,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        summary_threshold: int = DEFAULT_SUMMARY_THRESHOLD,
        summary_tokens: int = DEFAULT_SUMMARY_TOKENS,
        history_dir: Optional[Path] = None,
        summary_file: str = "summary.json",
        summaries_dir: str = "summaries",
    ):
        self.max_tokens = int(os.environ.get("CHAT_HISTORY_MAX_TOKENS") or max_tokens)
        self.summary_threshold = int(os.environ.get("CHAT_HISTORY_SUMMARY_THRESHOLD") or summary_threshold)
        self.summary_tokens = int(os.environ.get("CHAT_HISTORY_SUMMARY_TOKENS") or summary_tokens)
        root = history_dir or (_project_root() / "history")
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.summary_path = self.root / summary_file
        self.summaries_dir = self.root / summaries_dir
        self.summaries_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir = self.root / "backups"
        self.backups_dir.mkdir(parents=True, exist_ok=True)

        self.recent_messages: List[dict] = []  # {"role": "user"|"assistant", "content": "..."}
        self._current_tokens = 0
        self.summary_content = ""
        self._load_summary()

    def _load_summary(self) -> None:
        if self.summary_path.exists():
            try:
                data = json.loads(self.summary_path.read_text(encoding="utf-8"))
                self.summary_content = (data.get("summary") or "").strip()
            except Exception as e:
                logger.warning("요약 로드 실패: %s", e)

    def _save_summary(self) -> None:
        data = {"summary": self.summary_content, "message_count": len(self.recent_messages)}
        self.summary_path.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")

    def _backup_summary(self, summary_snapshot: str) -> Path:
        """RAG용 타임스탬프 백업 파일 생성."""
        from datetime import datetime
        name = f"summary_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        path = self.summaries_dir / name
        data = {"summary": summary_snapshot, "timestamp": datetime.utcnow().isoformat() + "Z"}
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def add_user_message(self, user_name: str, content: str) -> None:
        """user 메시지 추가 (닉네임: 내용 형식)."""
        text = f"{user_name}: {content}" if user_name else content
        self.recent_messages.append({"role": "user", "content": text})
        self._current_tokens += count_tokens(text)
        self._maybe_summarize()

    def add_assistant_message(self, content: str) -> None:
        """assistant 메시지 추가."""
        self.recent_messages.append({"role": "assistant", "content": content})
        self._current_tokens += count_tokens(content)
        self._maybe_summarize()

    def _maybe_summarize(self) -> None:
        """토큰이 임계값 넘으면 오래된 분량 요약 후 제거. 백업 저장."""
        if self._current_tokens <= self.summary_threshold:
            return
        # 요약할 만큼 오래된 메시지 수집
        acc = 0
        idx = 0
        for i, m in enumerate(self.recent_messages):
            acc += count_tokens(m.get("content", ""))
            if acc >= self.summary_tokens:
                idx = i + 1
                break
        if idx == 0:
            return
        to_summarize = self.recent_messages[:idx]
        self.recent_messages = self.recent_messages[idx:]
        for m in to_summarize:
            self._current_tokens -= count_tokens(m.get("content", ""))

        # 요약 생성은 외부 GroqClient에 위임 (호출하는 쪽에서 groq_client 주입 후 호출)
        self._pending_summarize = to_summarize

    def flush_summary(self, groq_client: "GroqClient") -> None:
        """
        _maybe_summarize에서 쌓인 요약 대상을 Groq로 요약 후 summary_content에 반영.
        백업 파일 생성. 호출 측에서 add_* 직후 또는 배치 처리 후 호출.
        """
        pending = getattr(self, "_pending_summarize", None)
        if not pending:
            return
        del self._pending_summarize
        summary_text = groq_client.summarize(pending)
        if not summary_text:
            self.summary_content += "\n"
            return
        if self.summary_content:
            self.summary_content = self.summary_content.rstrip() + "\n" + summary_text.strip()
        else:
            self.summary_content = summary_text.strip()
        self._save_summary()
        self._backup_summary(self.summary_content)
        logger.info("요약 반영 및 백업 저장: %s", self.summaries_dir)

    def get_context_messages(self) -> List[dict]:
        """API에 넘길 messages (시스템 제외). 요약 + 최근 대화. 토큰 상한 유지."""
        out: List[dict] = []
        if self.summary_content:
            out.append({"role": "system", "content": f"[이전 대화 요약] {self.summary_content}"})
        acc = 0
        for m in self.recent_messages:
            t = count_tokens(m.get("content", ""))
            if acc + t > self.max_tokens:
                break
            out.append(m)
            acc += t
        return out

    def has_pending_summarize(self) -> bool:
        return getattr(self, "_pending_summarize", None) is not None

    def save_manual_backup(self) -> Path:
        """
        현재 요약 + 최근 대화 전체를 타임스탬프 파일로 저장 (수동 백업).
        history/backups/backup_YYYYMMDD_HHMMSS.json
        """
        from datetime import datetime
        name = f"backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        path = self.backups_dir / name
        data = {
            "summary": self.summary_content,
            "messages": self.recent_messages,
            "message_count": len(self.recent_messages),
            "current_tokens_approx": self._current_tokens,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")
        logger.info("수동 백업 저장: %s", path)
        return path
