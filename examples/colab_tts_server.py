"""
Colab TTS 서버 - Google Colab에서 실행하여 로컬 앱이 원격 TTS API를 호출하도록 함.

사용법:
1. Google Colab (colab.research.google.com) 새 노트북 생성
2. 런타임 → 런타임 유형 변경 → GPU 선택
3. ngrok 계정 생성 후 authtoken 발급: https://dashboard.ngrok.com/get-started/your-authtoken
4. 아래 코드 실행 전, 별도 셀에서 authtoken 설정:
   import os
   os.environ["NGROK_AUTHTOKEN"] = "여기에_발급받은_토큰_붙여넣기"
5. 왼쪽 파일 아이콘에서 ref.wav, ref_text.txt 업로드 (assets/voice_samples/ 와 동일)
6. 아래 전체 코드를 한 셀에 붙여넣고 실행
7. 출력된 TTS_REMOTE_URL 을 복사해 로컬 .env 에 추가
8. 로컬에서 chzzk_groq_example.py 실행
"""

import io
import subprocess
import sys

# Colab용 의존성 설치 (최초 1회)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "flask", "pyngrok", "qwen-tts", "soundfile", "sentencepiece"], check=True)
import os
from pathlib import Path

from flask import Flask, request, send_file

app = Flask(__name__)

# Colab 기본 경로 (업로드한 ref 파일 위치)
CONTENT = Path("/content")
REF_AUDIO = CONTENT / "ref.wav"
REF_TEXT_FILE = CONTENT / "ref_text.txt"

_model = None
_ref_text = ""


def get_model():
    global _model
    if _model is not None:
        return _model
    import torch
    from qwen_tts import Qwen3TTSModel
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    load_kwargs = {"device_map": device, "dtype": torch.bfloat16 if device != "cpu" else torch.float32}
    try:
        import flash_attn  # noqa: F401
        load_kwargs["attn_implementation"] = "flash_attention_2"
    except ImportError:
        pass
    _model = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-Base", **load_kwargs)
    return _model


@app.route("/synthesize", methods=["POST"])
def synthesize():
    global _ref_text
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get("text") or "").strip()
    emotion = (data.get("emotion") or "neutral").strip().lower()

    if not text:
        return "text required", 400

    ref_path = REF_AUDIO
    if not ref_path.exists():
        return "ref.wav not found. Upload ref.wav to /content/", 503

    if _ref_text:
        ref_text = _ref_text
    else:
        if REF_TEXT_FILE.exists():
            _ref_text = REF_TEXT_FILE.read_text(encoding="utf-8").strip()
            ref_text = _ref_text
        else:
            return "ref_text.txt not found. Upload ref_text.txt to /content/", 503

    try:
        model = get_model()
        wavs, sr = model.generate_voice_clone(
            text=text,
            language="Korean",
            ref_audio=str(ref_path),
            ref_text=ref_text,
        )
    except Exception as e:
        return str(e), 500

    buf = io.BytesIO()
    import soundfile as sf
    sf.write(buf, wavs[0], sr, format="WAV")
    buf.seek(0)
    return send_file(buf, mimetype="audio/wav", as_attachment=False)


@app.route("/health", methods=["GET"])
def health():
    return "ok", 200


if __name__ == "__main__":
    from pyngrok import ngrok
    port = 5000
    token = os.environ.get("NGROK_AUTHTOKEN") or os.environ.get("NGROK_AUTH_TOKEN")
    if token:
        ngrok.set_auth_token(token)
    else:
        print("ngrok authtoken이 없습니다. 아래 셀을 먼저 실행하세요:")
        print('  import os')
        print('  os.environ["NGROK_AUTHTOKEN"] = "발급받은_토큰"')
        raise SystemExit("NGROK_AUTHTOKEN 또는 NGROK_AUTH_TOKEN 환경변수를 설정하세요.")
    public_url = ngrok.connect(port).public_url
    print("=" * 60)
    print("TTS 서버가 실행되었습니다.")
    print(".env에 다음을 추가하세요:")
    print(f"TTS_REMOTE_URL={public_url.rstrip('/')}")
    print("=" * 60)
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
