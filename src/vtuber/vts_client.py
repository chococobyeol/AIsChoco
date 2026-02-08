"""
VTube Studio API 클라이언트. pyvts로 연결·인증 후 파라미터 주입.

중요: VTS API의 InjectParameterDataRequest는 Live2D(출력) 파라미터가 아니라
"default or custom 입력 파라미터"에만 값을 넣습니다. 따라서 FaceAngleX, EyeOpenLeft
같은 입력 이름으로 보내야 하며, 모델 설정에서 해당 입력을 Live2D 파라미터(ParamAngleX 등)에
매핑해 두어야 합니다. body/breath/leg 등은 기본 입력이 없어 커스텀 파라미터를 생성합니다.
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

# pose_mapping.json의 짧은 키 → VTS "입력" 파라미터 이름.
# 얼굴/몸 X는 MousePositionX, Y는 MousePositionY로 통일 (VTS에서 마우스→각도 매핑 가능).
KEY_TO_INPUT_PARAM = {
    "angle_x": "MousePositionX",
    "angle_y": "MousePositionY",
    "angle_z": "FaceAngleZ",
    "eye_l_open": "EyeOpenLeft",
    "eye_r_open": "EyeOpenRight",
    "brow_l_y": "BrowLeftY",
    "brow_r_y": "BrowRightY",
    "brow_l_angle": "AIsChocoBrowLAngle",
    "brow_r_angle": "AIsChocoBrowRAngle",
    "mouth_open_y": "MouthOpen",
    "body_angle_y": "MousePositionY",
    "body_angle_z": "MousePositionX",
    "breath": "AIsChocoBreath",
    "right_leg": "AIsChocoLegR",
    "left_leg": "AIsChocoLegL",
}

# 감정 적용 시 제외할 키: 현재 포즈(각도·몸) 유지, 입은 립싱크가 제어하므로 보내지 않음.
KEYS_EXCLUDED_FOR_EMOTION = frozenset({
    "angle_x", "angle_y", "angle_z", "body_angle_y", "body_angle_z", "mouth_open_y",
})

# 커스텀 파라미터 생성 시 사용 (body/face X·Y는 MousePositionX/Y 사용으로 제외)
CUSTOM_PARAMS = [
    ("AIsChocoBrowLAngle", -1.0, 1.0, 0.0),
    ("AIsChocoBrowRAngle", -1.0, 1.0, 0.0),
    ("AIsChocoBreath", 0.0, 1.0, 0.5),
    ("AIsChocoLegR", -30.0, 30.0, 0.0),
    ("AIsChocoLegL", -30.0, 30.0, 0.0),
]


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

            await self._ensure_custom_parameters()
            logger.info("VTube Studio 연결됨.")
            return True

    async def _ensure_custom_parameters(self) -> None:
        """커스텀 입력 파라미터가 없으면 생성 (body, breath, leg 등)."""
        for name, min_val, max_val, default_val in CUSTOM_PARAMS:
            try:
                req = self._vts.vts_request.requestCustomParameter(
                    name,
                    min=min_val,
                    max=max_val,
                    default_value=default_val,
                    info=f"AIsChoco pose: {name}",
                )
                await self._vts.request(req)
                logger.debug("VTS 커스텀 파라미터 생성: %s", name)
            except Exception as e:
                logger.debug("VTS 커스텀 파라미터 %s (이미 있거나 무시): %s", name, e)

    async def disconnect(self) -> None:
        async with self._lock:
            if self._vts is not None:
                await self._vts.close()
                self._vts = None
                logger.info("VTube Studio 연결 해제.")

    def _emotion_to_parameters(self, emotion: str) -> List[Tuple[str, float]]:
        """감정 → (VTS 입력 파라미터 이름, 값) 리스트. 각도·몸·입은 제외해 현재 포즈 유지, 표정만 적용."""
        emotions = self.pose_config.get("emotions") or {}
        default_emotion = self.pose_config.get("default", "neutral")
        params = emotions.get(emotion) or emotions.get(default_emotion) or {}
        by_name: dict[str, list[float]] = {}
        for key, value in params.items():
            if key in KEYS_EXCLUDED_FOR_EMOTION or not isinstance(value, (int, float)):
                continue
            input_name = KEY_TO_INPUT_PARAM.get(key, key)
            by_name.setdefault(input_name, []).append(float(value))
        out = [(name, sum(vals) / len(vals)) for name, vals in by_name.items()]
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
        values = [float(p[1]) for p in params]
        try:
            req = self._vts.vts_request.requestSetMultiParameterValue(
                parameters=names,
                values=values,
                weight=1.0,
                face_found=True,
                mode="set",
            )
            await self._vts.request(req)
            logger.info("VTS 포즈 적용: %s (파라미터 %d개)", emotion, len(params))
            return True
        except Exception as e:
            logger.warning("VTS 파라미터 주입 실패: %s", e)
            return False

    async def set_mouse_position(self, x: float, y: float) -> bool:
        """시선/몸 방향용 마우스 입력만 전송 (MousePositionX, Y). 말하기 전 '채팅 보는' 동작에 사용."""
        if self._vts is None:
            if not await self.connect():
                return False
        try:
            req = self._vts.vts_request.requestSetMultiParameterValue(
                parameters=["MousePositionX", "MousePositionY"],
                values=[float(x), float(y)],
                weight=1.0,
                face_found=True,
                mode="set",
            )
            await self._vts.request(req)
            logger.debug("VTS 마우스 위치: x=%.2f y=%.2f", x, y)
            return True
        except Exception as e:
            logger.warning("VTS 마우스 위치 주입 실패: %s", e)
            return False
