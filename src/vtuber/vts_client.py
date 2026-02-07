"""
VTube Studio API 클라이언트. pyvts로 연결·인증 후 파라미터 주입.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# 기본 포즈 설정 경로
DEFAULT_POSE_CONFIG = Path(__file__).resolve().parent.parent.parent / "config" / "pose_mapping.json"


def load_pose_config(path: Optional[Union[Path, str]] = None) -> dict:
    """pose_mapping.json 로드. parameter_mapping 있으면 감정별 dict 키를 VTS 파라미터 이름으로 변환에 사용."""
    p = Path(path) if path else DEFAULT_POSE_CONFIG
    if not p.exists():
        return {"emotions": {}, "default": "neutral", "parameter_mapping": {}}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


class VTSClient:
    """
    VTube Studio 연결 및 감정별 파라미터 주입.
    연결: VTS 실행 → 스크립트 실행 → VTS에서 플러그인 연결 허용(최초 1회) → 토큰 저장 후 재사용.
    """

    def __init__(
        self,
        plugin_name: str = "AIsChoco",
        developer: str = "AIsChoco",
        token_path: Optional[Union[Path, str]] = None,
        pose_config_path: Optional[Union[Path, str]] = None,
    ):
        self.plugin_name = plugin_name
        self.developer = developer
        self.token_path = Path(token_path) if token_path else Path(__file__).resolve().parent.parent.parent / "config" / "vts_token.txt"
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.pose_config = load_pose_config(pose_config_path)
        self._vts = None
        self._lock = asyncio.Lock()

    async def connect(self) -> bool:
        """VTube Studio에 연결·인증. 최초 실행 시 VTS에서 허용 버튼을 눌러야 함."""
        try:
            import pyvts
        except ImportError:
            logger.error("pyvts 미설치. pip install pyvts")
            return False

        async with self._lock:
            if self._vts is not None:
                return True

            plugin_info = {
                "plugin_name": self.plugin_name,
                "developer": self.developer,
                "authentication_token_path": str(self.token_path),
            }
            self._vts = pyvts.vts(plugin_info=plugin_info)
            await self._vts.connect()

            if self.token_path.exists():
                try:
                    await self._vts.request_authenticate()
                except Exception:
                    await self._vts.request_authenticate_token()
                    await self._vts.request_authenticate()
                    logger.info("VTube Studio에서 플러그인 연결을 허용해주세요. (토큰 갱신)")
            else:
                await self._vts.request_authenticate_token()
                await self._vts.request_authenticate()
                logger.info("VTube Studio에서 플러그인 연결을 허용해주세요. (최초 1회)")

            logger.info("VTube Studio 연결됨.")
            return True

    async def disconnect(self) -> None:
        async with self._lock:
            if self._vts is not None:
                await self._vts.close()
                self._vts = None
                logger.info("VTube Studio 연결 해제.")

    def _emotion_to_parameters(self, emotion: str) -> List[Tuple[str, float]]:
        """감정 → (파라미터 이름, 값) 리스트. parameter_mapping 있으면 키를 매핑."""
        emotions = self.pose_config.get("emotions") or {}
        default_emotion = self.pose_config.get("default", "neutral")
        mapping = self.pose_config.get("parameter_mapping") or {}
        params = emotions.get(emotion) or emotions.get(default_emotion) or {}
        out = []
        for key, value in params.items():
            if not isinstance(value, (int, float)):
                continue
            param_name = mapping.get(key, key)
            out.append((param_name, float(value)))
        return out

    async def set_emotion(self, emotion: str) -> bool:
        """감정에 해당하는 파라미터 값을 VTS에 주입."""
        if self._vts is None:
            if not await self.connect():
                return False
        params = self._emotion_to_parameters(emotion)
        if not params:
            logger.debug("해당 감정 포즈 없음: %s", emotion)
            return True
        names = [p[0] for p in params]
        values = [p[1] for p in params]
        try:
            req = self._vts.vts_request.requestSetMultiParameterValue(
                parameters=names,
                values=values,
                weight=1.0,
                face_found=True,
                mode="set",
            )
            await self._vts.request(req)
            return True
        except Exception as e:
            logger.warning("VTS 파라미터 주입 실패: %s", e)
            return False
