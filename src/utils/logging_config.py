"""
프로젝트 공통 로깅 설정.

- 콘솔: WARNING 이상
- 통합: logs/app.log (INFO 이상)
- 에러: logs/error.log (ERROR 이상)
- 카테고리: logs/chat.log, logs/ai.log, logs/tts.log
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


class _PrefixFilter(logging.Filter):
    """logger name prefix 기반 필터."""

    def __init__(self, *prefixes: str):
        super().__init__()
        self._prefixes = tuple(p for p in prefixes if p)

    def filter(self, record: logging.LogRecord) -> bool:
        name = record.name or ""
        return any(name.startswith(p) for p in self._prefixes)


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _mk_rotating_handler(path: Path, level: int, fmt: logging.Formatter) -> RotatingFileHandler:
    max_mb = int(os.environ.get("LOG_MAX_MB", "10"))
    backups = int(os.environ.get("LOG_BACKUP_COUNT", "5"))
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        filename=str(path),
        maxBytes=max_mb * 1024 * 1024,
        backupCount=backups,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(fmt)
    return handler


def setup_logging() -> Path:
    """루트 로거/핸들러를 재설정하고 로그 디렉터리 경로 반환."""
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.DEBUG)

    log_dir = _project_root() / "logs"
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    console_level_name = (os.environ.get("LOG_CONSOLE_LEVEL") or "WARNING").upper()
    console_level = getattr(logging, console_level_name, logging.WARNING)
    ch = logging.StreamHandler()
    ch.setLevel(console_level)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    app_h = _mk_rotating_handler(log_dir / "app.log", logging.INFO, fmt)
    root.addHandler(app_h)

    err_h = _mk_rotating_handler(log_dir / "error.log", logging.ERROR, fmt)
    root.addHandler(err_h)

    chat_h = _mk_rotating_handler(log_dir / "chat.log", logging.DEBUG, fmt)
    chat_h.addFilter(_PrefixFilter("src.chat", "engineio", "socketio"))
    root.addHandler(chat_h)

    ai_h = _mk_rotating_handler(log_dir / "ai.log", logging.DEBUG, fmt)
    ai_h.addFilter(_PrefixFilter("src.ai"))
    root.addHandler(ai_h)

    tts_h = _mk_rotating_handler(log_dir / "tts.log", logging.DEBUG, fmt)
    tts_h.addFilter(_PrefixFilter("src.tts"))
    root.addHandler(tts_h)

    vtuber_h = _mk_rotating_handler(log_dir / "vtuber.log", logging.DEBUG, fmt)
    vtuber_h.addFilter(_PrefixFilter("src.vtuber", "src.overlay"))
    root.addHandler(vtuber_h)

    # noisy logger 억제 (파일에는 남기고 싶으면 WARNING, 완전 억제는 ERROR)
    noisy_level_name = (os.environ.get("ENGINEIO_LOG_LEVEL") or "WARNING").upper()
    noisy_level = getattr(logging, noisy_level_name, logging.WARNING)
    logging.getLogger("engineio").setLevel(noisy_level)
    logging.getLogger("engineio.client").setLevel(noisy_level)
    logging.getLogger("socketio").setLevel(noisy_level)
    logging.getLogger("socketio.client").setLevel(noisy_level)

    return log_dir
