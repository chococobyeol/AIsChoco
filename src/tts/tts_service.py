"""
Qwen3-TTS Base 클로닝 래퍼. ref.wav(및 감정별 ref_emotion.wav)로 목소리 클론.

감정에 따라 ref_happy.wav, ref_sad.wav 등이 있으면 해당 참조 사용, 없으면 ref.wav 사용.
동일 emotion은 VTube 포즈 등 다른 모듈에서도 사용 가능.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Tuple, Union

from src.ai.models import VALID_EMOTIONS

logger = logging.getLogger(__name__)

# Groq AIResponse.emotion → CustomVoice instruct (CustomVoice 사용 시. 포즈 모듈 참고용)
EMOTION_TO_INSTRUCT: dict[str, str] = {
    "happy": "기쁘고 밝게 말해줘.",
    "sad": "슬프고 우울한 어조로 말해줘.",
    "angry": "화난 어조로 말해줘.",
    "surprised": "놀란 톤으로 말해줘.",
    "neutral": "",
    "excited": "신나고 들뜬 어조로 말해줘.",
}


def emotion_to_instruct(emotion: str) -> str:
    """감정 문자열을 instruct 문구로 변환. 포즈 모듈은 emotion 그대로 사용 가능."""
    return EMOTION_TO_INSTRUCT.get(emotion.strip().lower(), "")


def _default_ref_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "assets" / "voice_samples"


class TTSService:
    """Qwen3-TTS Base 클로닝. 감정별 ref_emotion.wav 있으면 사용, 없으면 ref.wav."""

    def __init__(
        self,
        ref_audio_dir: Optional[Union[Path, str]] = None,
        ref_text: Optional[str] = None,
        model_id: str = "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
        language: str = "Korean",
    ):
        self.ref_audio_dir = Path(ref_audio_dir) if ref_audio_dir else _default_ref_dir()
        self.model_id = model_id
        self.language = language
        self._model = None

        if ref_text is not None and ref_text.strip():
            self.ref_text = ref_text.strip()
        else:
            ref_text_file = self.ref_audio_dir / "ref_text.txt"
            if ref_text_file.exists():
                self.ref_text = ref_text_file.read_text(encoding="utf-8").strip()
            else:
                self.ref_text = ""
                logger.warning(
                    "ref_text 없음. %s 에 참조 음성 원문을 넣어주세요.",
                    ref_text_file,
                )

    def _resolve_ref_audio(self, emotion: str) -> Path:
        """감정에 따라 ref_emotion.wav 사용, 없으면 ref.wav."""
        emotion = (emotion or "neutral").strip().lower()
        if emotion not in VALID_EMOTIONS:
            emotion = "neutral"
        candidate = self.ref_audio_dir / f"ref_{emotion}.wav"
        if candidate.exists():
            return candidate
        default_ref = self.ref_audio_dir / "ref.wav"
        return default_ref

    def _get_model(self):
        if self._model is not None:
            return self._model
        import torch
        from qwen_tts import Qwen3TTSModel

        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        load_kwargs = {
            "device_map": device,
            "dtype": torch.bfloat16 if device != "cpu" else torch.float32,
        }
        try:
            import flash_attn  # noqa: F401
            load_kwargs["attn_implementation"] = "flash_attention_2"
        except ImportError:
            pass
        self._model = Qwen3TTSModel.from_pretrained(self.model_id, **load_kwargs)
        return self._model

    def synthesize(
        self,
        text: str,
        emotion: str = "neutral",
        language: Optional[str] = None,
    ) -> Tuple[list, int]:
        """
        텍스트를 클론 목소리로 변환. 감정에 따라 ref_emotion.wav 또는 ref.wav 사용.

        Returns:
            (wavs, sample_rate): wavs[0]이 numpy 배열, sample_rate는 int.
        """
        if not text.strip():
            import numpy as np
            return [np.array([], dtype=np.float32)], 24000

        ref_path = self._resolve_ref_audio(emotion)
        if not ref_path.exists():
            raise FileNotFoundError(
                f"참조 음성이 없습니다: {ref_path}. ref.wav 를 넣고 ref_text.txt 에 원문을 적어주세요."
            )
        if not self.ref_text:
            raise ValueError(
                "ref_text가 비어 있습니다. ref_text.txt 에 참조 음성 원문을 적어주세요."
            )

        model = self._get_model()
        lang = language or self.language
        wavs, sr = model.generate_voice_clone(
            text=text.strip(),
            language=lang,
            ref_audio=str(ref_path),
            ref_text=self.ref_text,
        )
        return wavs, sr

    def synthesize_to_file(
        self,
        text: str,
        emotion: str = "neutral",
        out_path: Optional[Union[Path, str]] = None,
    ) -> Path:
        """합성 후 wav 파일로 저장. out_path 없으면 assets/voice_samples/latest_reply.wav."""
        wavs, sr = self.synthesize(text, emotion=emotion)
        if out_path is None:
            out_path = _default_ref_dir() / "latest_reply.wav"
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        import soundfile as sf
        sf.write(str(out_path), wavs[0], sr)
        return out_path
