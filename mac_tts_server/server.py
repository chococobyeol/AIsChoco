"""
맥용 TTS API 서버 (Qwen3-TTS MLX, Voice Cloning).
aischoco 원격 TTS 규격: POST /synthesize { "text", "emotion" } → WAV 바이너리.

실행: macOS에서만 동작. python server.py 또는 uvicorn server:app --host 0.0.0.0 --port 5001
"""

from __future__ import annotations

import os
import shutil
import tempfile
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import Response
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# 환경 변수 (refs 기본값: server.py 기준 refs/ 폴더)
_SERVER_DIR = Path(__file__).resolve().parent
_DEFAULT_REF_DIR = str(_SERVER_DIR / "refs")

MODELS_DIR = os.environ.get("MODELS_DIR", os.path.join(os.getcwd(), "models"))
MODEL_FOLDER = os.environ.get("MODEL_FOLDER", "Qwen3-TTS-12Hz-1.7B-Base-8bit")
REF_MODEL_PATH = os.environ.get("REF_MODEL_PATH", "").strip() or None
REF_AUDIO_PATH = os.environ.get("REF_AUDIO_PATH", "").strip() or None
REF_TEXT_PATH = os.environ.get("REF_TEXT_PATH", "").strip() or None
REF_AUDIO_DIR = os.environ.get("REF_AUDIO_DIR", "").strip() or _DEFAULT_REF_DIR

app = FastAPI(title="Mac TTS API (Qwen3-TTS MLX)")


def get_model_path() -> str | None:
    """모델 디렉터리 경로 (qwen3-tts-apple-silicon get_smart_path 동일 로직)."""
    if REF_MODEL_PATH and os.path.isdir(REF_MODEL_PATH):
        return REF_MODEL_PATH
    full = os.path.join(MODELS_DIR, MODEL_FOLDER)
    if not os.path.isdir(full):
        return None
    snapshots = os.path.join(full, "snapshots")
    if os.path.isdir(snapshots):
        subs = [f for f in os.listdir(snapshots) if not f.startswith(".")]
        if subs:
            return os.path.join(snapshots, subs[0])
    return full


def get_ref_audio_and_text() -> tuple[str | None, str | None]:
    """ref.wav 경로와 ref_text 문자열 반환."""
    ref_audio = REF_AUDIO_PATH
    ref_text_path = REF_TEXT_PATH
    if REF_AUDIO_DIR:
        d = Path(REF_AUDIO_DIR)
        if not ref_audio and (d / "ref.wav").exists():
            ref_audio = str(d / "ref.wav")
        if not ref_text_path and (d / "ref_text.txt").exists():
            ref_text_path = str(d / "ref_text.txt")
    if not ref_audio or not os.path.isfile(ref_audio):
        return None, None
    if ref_text_path and os.path.isfile(ref_text_path):
        ref_text = Path(ref_text_path).read_text(encoding="utf-8").strip()
    else:
        ref_text = "."
    return ref_audio, ref_text


class SynthesizeRequest(BaseModel):
    text: str = ""
    emotion: str = "neutral"


_model = None


def get_model():
    global _model
    if _model is not None:
        return _model
    from mlx_audio.tts.utils import load_model

    path = get_model_path()
    if not path:
        raise FileNotFoundError(
            f"모델을 찾을 수 없습니다. MODELS_DIR={MODELS_DIR}, MODEL_FOLDER={MODEL_FOLDER} 또는 REF_MODEL_PATH 설정."
        )
    logger.info("모델 로드 중: %s", path)
    _model = load_model(path)
    return _model


@app.post("/synthesize")
def synthesize(req: SynthesizeRequest):
    """텍스트 → 클론 음성 WAV 반환. aischoco 원격 TTS 규격."""
    text = (req.text or "").strip()
    if not text:
        return Response(content=b"", status_code=400, media_type="text/plain")

    ref_audio, ref_text = get_ref_audio_and_text()
    if not ref_audio or not ref_text:
        logger.warning(
            "503: ref 미설정. REF_AUDIO_DIR=%s, ref.wav 존재=%s, ref_text.txt 존재=%s",
            REF_AUDIO_DIR,
            (Path(REF_AUDIO_DIR) / "ref.wav").exists() if REF_AUDIO_DIR else False,
            (Path(REF_AUDIO_DIR) / "ref_text.txt").exists() if REF_AUDIO_DIR else False,
        )
        return Response(
            content=b"ref.wav / ref_text not configured. Set REF_AUDIO_PATH, REF_TEXT_PATH or REF_AUDIO_DIR.",
            status_code=503,
            media_type="text/plain",
        )

    try:
        model = get_model()
    except FileNotFoundError as e:
        logger.warning("503: 모델 없음 - %s", e)
        return Response(content=str(e).encode("utf-8"), status_code=503, media_type="text/plain")
    except Exception as e:
        logger.exception("모델 로드 실패: %s", e)
        return Response(content=str(e).encode("utf-8"), status_code=500, media_type="text/plain")

    from mlx_audio.tts.generate import generate_audio

    tmp = tempfile.mkdtemp(prefix="tts_")
    try:
        generate_audio(
            model=model,
            text=text,
            ref_audio=ref_audio,
            ref_text=ref_text,
            output_path=tmp,
        )
        wav_path = os.path.join(tmp, "audio_000.wav")
        if not os.path.isfile(wav_path):
            return Response(content=b"generate_audio did not produce audio_000.wav", status_code=500)
        with open(wav_path, "rb") as f:
            wav_bytes = f.read()
        return Response(content=wav_bytes, media_type="audio/wav")
    except Exception as e:
        logger.exception("TTS 생성 실패: %s", e)
        return Response(content=str(e).encode("utf-8"), status_code=500, media_type="text/plain")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@app.get("/health")
def health():
    ref_audio, ref_text = get_ref_audio_and_text()
    ref_dir = REF_AUDIO_DIR
    ref_ok = ref_audio is not None and ref_text is not None
    return {
        "status": "ok",
        "model_path": get_model_path() or "not set",
        "ref_audio_dir": ref_dir,
        "ref_wav_exists": (Path(ref_dir) / "ref.wav").exists() if ref_dir else False,
        "ref_txt_exists": (Path(ref_dir) / "ref_text.txt").exists() if ref_dir else False,
        "ref_ready": ref_ok,
    }


if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("TTS_SERVER_HOST", "0.0.0.0")
    port = int(os.environ.get("TTS_SERVER_PORT", "5001"))
    logger.info("Mac TTS API 서버 시작: http://%s:%s", host, port)
    model_path = get_model_path()
    if model_path:
        logger.info("모델 경로: %s", model_path)
    else:
        expected = os.path.join(MODELS_DIR, MODEL_FOLDER)
        logger.warning(
            "모델을 찾을 수 없습니다. 다음 중 하나를 하세요:\n"
            "  1) 이 경로에 모델 폴더 두기: %s\n"
            "  2) qwen3-tts-apple-silicon 사용 중이면: export REF_MODEL_PATH=해당경로/models/Qwen3-TTS-12Hz-1.7B-Base-8bit",
            expected,
        )
    uvicorn.run(app, host=host, port=port)
