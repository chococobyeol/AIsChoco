"""
방송 오버레이: 들어온 채팅·말하는 대사를 OBS 브라우저 소스로 노출.

- overlay_state: 메인 스크립트가 갱신, 서버가 /api/state 로 반환.
- OBS에서 브라우저 소스 URL을 http://127.0.0.1:8765/ 로 설정.
"""

from src.overlay.state import overlay_state

__all__ = ["overlay_state"]
