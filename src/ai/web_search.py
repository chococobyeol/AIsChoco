"""
웹 검색 (DuckDuckGo). 모델이 search_web 도구를 호출할 때 사용.
결과는 상위 N개·짧은 스니펫으로 제한해 토큰 절약.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

MAX_RESULTS = 6
SNIPPET_LEN = 100


def run_web_search(query: str) -> str:
    """
    DuckDuckGo로 검색해 상위 결과를 한 줄씩 포맷한 문자열 반환.
    실패 시 빈 문자열 또는 에러 메시지 반환.
    """
    query = (query or "").strip()
    if not query:
        return "검색어가 비어 있습니다."
    try:
        from ddgs import DDGS
    except ImportError:
        logger.warning("ddgs 패키지 없음: pip install ddgs")
        return "검색 기능을 사용하려면 ddgs 패키지가 필요합니다."
    try:
        # ddgs 9.x: text() returns list[dict] with title, href, body. region kr-kr for Korean.
        with DDGS() as ddgs:
            results = ddgs.text(query, region="kr-kr", max_results=MAX_RESULTS)
        if not isinstance(results, list):
            results = list(results) if results else []
    except Exception as e:
        logger.warning("DuckDuckGo 검색 실패: %s", e)
        return f"검색 중 오류가 났어요: {str(e)[:80]}"
    if not results:
        return "검색 결과가 없습니다."
    lines = []
    for i, r in enumerate(results[:MAX_RESULTS], 1):
        if not isinstance(r, dict):
            continue
        title = (r.get("title") or "").strip()
        body = (r.get("body") or r.get("snippet") or "").strip()
        if len(body) > SNIPPET_LEN:
            body = body[: SNIPPET_LEN - 1].rstrip() + "…"
        if title or body:
            lines.append(f"{i}. {title}: {body}")
    return "\n".join(lines) if lines else "검색 결과가 없습니다."
