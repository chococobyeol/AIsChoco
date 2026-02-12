"""
Qwen3-TTS Base 클로닝 래퍼. ref.wav(및 감정별 ref_emotion.wav)로 목소리 클론.

감정에 따라 ref_happy.wav, ref_sad.wav 등이 있으면 해당 참조 사용, 없으면 ref.wav 사용.
동일 emotion은 VTube 포즈 등 다른 모듈에서도 사용 가능.
"""

from __future__ import annotations

import io
import os
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


# 1~78 한글 읽기 (TTS에서 1번→일 번, 78번→칠십팔 번으로 읽히도록)
_NUM_KOR = (
    "", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구",
    "십", "십일", "십이", "십삼", "십사", "십오", "십육", "십칠", "십팔", "십구",
    "이십", "이십일", "이십이", "이십삼", "이십사", "이십오", "이십육", "이십칠", "이십팔", "이십구",
    "삼십", "삼십일", "삼십이", "삼십삼", "삼십사", "삼십오", "삼십육", "삼십칠", "삼십팔", "삼십구",
    "사십", "사십일", "사십이", "사십삼", "사십사", "사십오", "사십육", "사십칠", "사십팔", "사십구",
    "오십", "오십일", "오십이", "오십삼", "오십사", "오십오", "오십육", "오십칠", "오십팔", "오십구",
    "육십", "육십일", "육십이", "육십삼", "육십사", "육십오", "육십육", "육십칠", "육십팔", "육십구",
    "칠십", "칠십일", "칠십이", "칠십삼", "칠십사", "칠십오", "칠십육", "칠십칠", "칠십팔",
)
_NUM_KOR_CNT = ("", "한", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉", "열")


def text_for_tts_numbers(text: str) -> str:
    """TTS용: 채팅용 자모(ㅋㅎㄷㄷㅠㅜㅡ) 제거 후 '1번'→'일 번', '78번'→'칠십팔 번' 등 변환. TTS에만 이 결과를 넘기면 됨."""
    if not text or not text.strip():
        return text
    import re
    s = text
    # TTS에서 이상하게 읽히는 채팅 용어 제거 (1개든 여러 개든 전부)
    s = re.sub(r"ㅋ+", "", s)
    s = re.sub(r"ㅎ+", "", s)
    s = re.sub(r"ㄷㄷ", "", s)
    s = re.sub(r"ㅠ+", "", s)
    s = re.sub(r"ㅜ+", "", s)
    s = re.sub(r"ㅡ+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return "."  # 전부 채팅용 자모면 TTS에 넘기지 않고 짧은 대체
    # N번 (1~78) → 한글 번 (긴 숫자부터 치환해 7번이 7번으로만 매칭되게)
    for n in range(78, 0, -1):
        if n < len(_NUM_KOR):
            kor = _NUM_KOR[n]
            s = re.sub(rf"(?<!\d){n}(?!\d)\s*번", f"{kor} 번", s)
    # N개 (1~10) → 한/두/세 개
    for n in range(10, 0, -1):
        if n < len(_NUM_KOR_CNT):
            kor = _NUM_KOR_CNT[n]
            s = re.sub(rf"(?<!\d){n}(?!\d)\s*개", f"{kor} 개", s)
    return s


def _default_ref_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "assets" / "voice_samples"


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


# Base 클론 모델: 0.6B(경량) / 1.7B(품질·끝발음 개선 기대)
TTS_BASE_MODELS = {
    "0.6B": "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
    "1.7B": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
}


class TTSService:
    """Qwen3-TTS Base 클로닝. 감정별 ref_emotion.wav 있으면 사용, 없으면 ref.wav."""

    def __init__(
        self,
        ref_audio_dir: Optional[Union[Path, str]] = None,
        ref_text: Optional[str] = None,
        model_size: str = "0.6B",
        model_id: Optional[str] = None,
        language: str = "Korean",
        hf_home: Optional[Union[Path, str]] = None,
        play_device: Optional[Union[int, str]] = None,
        tts_remote_url: Optional[str] = None,
    ):
        """
        model_size: "0.6B"(경량, VRAM 약 2GB) 또는 "1.7B"(품질·끝발음 개선, VRAM 약 4GB).
        model_id를 직접 주면 model_size는 무시됨.
        hf_home: Hugging Face 모델 캐시 경로. C: 공간 부족 시 D: 등 다른 드라이브 경로 지정.
                 미지정 시 .env의 HF_HOME 또는 프로젝트/cache/huggingface 사용.
        play_device: TTS 재생 출력 장치. VB-Cable 등으로 지정하면 VTS 립싱크 가능.
                     정수(장치 인덱스) 또는 문자열(장치 이름). .env TTS_OUTPUT_DEVICE 사용 가능.
        tts_remote_url: Colab 등 원격 TTS API URL. 지정 시 로컬 모델 대신 원격 호출. .env TTS_REMOTE_URL 사용 가능.
        """
        _env_url = (os.environ.get("TTS_REMOTE_URL") or "").strip() or None
        self.tts_remote_url = (tts_remote_url or _env_url or "").rstrip("/") or None
        if self.tts_remote_url:
            logger.info("TTS 원격 API 사용: %s", self.tts_remote_url)
        self.ref_audio_dir = Path(ref_audio_dir) if ref_audio_dir else _default_ref_dir()
        _env_device = (os.environ.get("TTS_OUTPUT_DEVICE") or "").strip() or None
        self.play_device = play_device if play_device is not None else _env_device
        self._resolved_play_device = None  # VB-Cable 자동 감지 시 캐시
        self._apply_hf_cache(hf_home)
        if model_id is not None:
            self.model_id = model_id
        else:
            self.model_id = TTS_BASE_MODELS.get(model_size, TTS_BASE_MODELS["0.6B"])
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

    def _apply_hf_cache(self, hf_home: Optional[Union[Path, str]] = None) -> None:
        """Hugging Face 캐시를 hf_home 또는 .env HF_HOME 또는 프로젝트/cache로 설정."""
        if hf_home is not None:
            cache = Path(hf_home).resolve()
        else:
            cache = os.environ.get("HF_HOME") or os.environ.get("HUGGINGFACE_HUB_CACHE")
            if cache:
                cache = Path(cache).resolve()
            else:
                cache = _project_root() / "cache" / "huggingface"
        cache.mkdir(parents=True, exist_ok=True)
        cache_str = str(cache)
        os.environ["HF_HOME"] = cache_str
        os.environ["HUGGINGFACE_HUB_CACHE"] = cache_str
        logger.info("HF 캐시 경로: %s", cache_str)

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

    def _synthesize_remote(
        self,
        text: str,
        emotion: str = "neutral",
        language: Optional[str] = None,
    ) -> Tuple[list, int]:
        """원격 TTS API 호출 (Colab 등). language 미지정 시 self.language 사용."""
        import httpx
        import numpy as np
        import soundfile as sf

        url = f"{self.tts_remote_url.rstrip('/')}/synthesize"
        timeout = float(os.environ.get("TTS_REMOTE_TIMEOUT", "300"))
        lang = (language or getattr(self, "language", None) or "Korean").strip() or "Korean"
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(
                    url,
                    json={"text": text, "emotion": emotion, "language": lang},
                )
                resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.warning("원격 TTS 실패 %s: %s", e.response.status_code, e.response.text[:200])
            return [np.array([], dtype=np.float32)], 24000
        except Exception as e:
            logger.warning("원격 TTS 호출 실패: %s", e)
            return [np.array([], dtype=np.float32)], 24000

        data, sr = sf.read(io.BytesIO(resp.content), dtype="float32")
        return [data], int(sr)

    def synthesize(
        self,
        text: str,
        emotion: str = "neutral",
        language: Optional[str] = None,
    ) -> Tuple[list, int]:
        """
        텍스트를 클론 목소리로 변환. tts_remote_url 있으면 원격 API 호출, 없으면 로컬 모델 사용.
        Returns:
            (wavs, sample_rate): wavs[0]이 numpy 배열, sample_rate는 int.
        """
        if not text.strip():
            import numpy as np
            return [np.array([], dtype=np.float32)], 24000

        if self.tts_remote_url:
            lang = language or self.language
            wavs, sr = self._synthesize_remote(text.strip(), emotion, language=lang)
            if wavs and len(wavs[0]) > 0:
                return wavs, sr
            logger.warning("원격 TTS 실패, 로컬로 전환합니다.")
            # 세션 끊김 등으로 실패 시 로컬 폴백

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

    def _resolve_vb_cable_device(self):
        """출력 장치 목록에서 CABLE / VB-Audio 포함된 장치를 찾아 캐시. 립싱크용."""
        if self._resolved_play_device is not None:
            return
        try:
            import sounddevice as sd
            for i in range(64):
                try:
                    dev = sd.query_devices(i)
                except Exception:
                    break
                name = (dev.get("name", "") if isinstance(dev, dict) else getattr(dev, "name", "")) or ""
                max_out = (dev.get("max_output_channels", 0) or 0) if isinstance(dev, dict) else (getattr(dev, "max_output_channels", 0) or 0)
                if max_out > 0 and ("CABLE" in name.upper() or "VB-AUDIO" in name.upper() or "VB-CABLE" in name.upper()):
                    self._resolved_play_device = i
                    logger.info("TTS 립싱크용 출력 장치 자동 선택: [%s] %s", i, name)
                    return
        except Exception as e:
            logger.debug("VB-Cable 장치 검색 중 오류: %s", e)
        self._resolved_play_device = False  # 없음

    def _play(self, wav_array, sr: int) -> None:
        """wav 배열 재생 (sounddevice). VB-Cable 등 지정 시 해당 장치로 출력 → VTS 립싱크.
        장치가 24kHz를 지원하지 않으면 48kHz로 리샘플 후 재생 (Invalid sample rate 방지).
        """
        try:
            import sounddevice as sd
            if wav_array is None or len(wav_array) == 0:
                return
            play_sr = sr
            play_wav = wav_array
            device = self.play_device
            if device is None:
                self._resolve_vb_cable_device()
                if self._resolved_play_device is not None and self._resolved_play_device is not False:
                    device = self._resolved_play_device
            if device is not None:
                # VB-Cable 등은 보통 48kHz/44.1kHz만 지원. 24kHz면 48kHz로 리샘플.
                if sr not in (44100, 48000):
                    try:
                        import numpy as np
                        play_sr = 48000
                        n = len(play_wav)
                        new_len = int(n * play_sr / sr)
                        x_old = np.arange(n, dtype=np.float64)
                        x_new = np.linspace(0, n - 1, new_len, dtype=np.float64)
                        play_wav = np.interp(x_new, x_old, np.asarray(play_wav, dtype=np.float64)).astype(np.float32)
                    except Exception as resample_e:
                        logger.debug("리샘플 실패, 기본 sr 유지: %s", resample_e)
                        play_sr = sr
            kwargs = {"samplerate": play_sr}
            if device is not None:
                kwargs["device"] = int(device) if isinstance(device, (int, str)) and str(device).isdigit() else device
            sd.play(play_wav, **kwargs)
            sd.wait()
        except ImportError:
            logger.warning("sounddevice 미설치. pip install sounddevice 후 재생 가능.")
        except Exception as e:
            logger.warning("재생 실패: %s", e)

    def synthesize_to_file(
        self,
        text: str,
        emotion: str = "neutral",
        out_path: Optional[Union[Path, str]] = None,
        play: bool = True,
        language: Optional[str] = None,
    ) -> Path:
        """합성 후 wav 저장. play=True면 저장 직후 재생. language 지정 시 원격/로컬 모두 적용."""
        wavs, sr = self.synthesize(text, emotion=emotion, language=language)
        if out_path is None:
            out_path = _default_ref_dir() / "latest_reply.wav"
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        import soundfile as sf
        sf.write(str(out_path), wavs[0], sr)
        if play and wavs[0] is not None and len(wavs[0]) > 0:
            self._play(wavs[0], sr)
        return out_path

    def play_file(self, path: Union[Path, str]) -> None:
        """저장된 wav 파일 재생. 재생 직전에 VTS 표정 적용 시 사용."""
        path = Path(path)
        if not path.exists():
            logger.warning("재생할 파일 없음: %s", path)
            return
        try:
            import soundfile as sf
            wav_array, sr = sf.read(str(path), dtype="float32")
            self._play(wav_array, int(sr))
        except Exception as e:
            logger.warning("파일 재생 실패 %s: %s", path, e)
