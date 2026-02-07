"""
Qwen3-TTS Base 모델 제로샷 음성 클로닝 테스트

참조 음성(약 3초) + 원문을 파일 안에 두고, 실행만 하면 클로닝 합성합니다.
실행: python examples/tts_clone_example.py  (프로젝트 루트에서)

필요: NVIDIA GPU (CUDA), qwen-tts, soundfile
  pip install -r requirements.txt
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
# 참조 음성: assets/voice_samples/ref.wav (약 3초 wav 넣고, 아래에 그 원문 적기)
REF_AUDIO = ROOT / "assets" / "voice_samples" / "ref.wav"
REF_TEXT = "지금 들으시는 목소리는 클로닝된 목소리입니다"  # 참조 음성(ref.wav)에 들어 있는 말을 그대로 적어주세요.

# 이 목소리로 합성할 문장
TEXT = "감정표현을 하면서도 보이스클로닝까지 하는 방법은 없을까"
LANGUAGE = "Korean"

# Base(클로닝) 모델은 공식 API에 감정(instruct) 파라미터가 없음. 감정 표현은 CustomVoice(instruct) 또는
# Voice Design으로 참조 음성 만든 뒤 클로닝하는 2단계로 가능.


def main():
    try:
        import torch
        import soundfile as sf
        from qwen_tts import Qwen3TTSModel
    except ImportError as e:
        print(f"오류: 필요한 패키지가 없습니다. ({e})")
        print("  pip install -r requirements.txt")
        sys.exit(1)

    model_id = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        print("경고: CUDA 없음. CPU로 실행하면 매우 느립니다.")

    print(f"모델 로딩 중: {model_id} ...")
    load_kwargs = {
        "device_map": device,
        "dtype": torch.bfloat16 if device != "cpu" else torch.float32,
    }
    try:
        import flash_attn  # noqa: F401
        load_kwargs["attn_implementation"] = "flash_attention_2"
    except ImportError:
        pass
    model = Qwen3TTSModel.from_pretrained(model_id, **load_kwargs)

    if not REF_AUDIO.exists():
        print(f"오류: 참조 음성이 없습니다. {REF_AUDIO}")
        print("  assets/voice_samples/ref.wav 에 참조용 wav(약 3초)를 넣고, REF_TEXT에 그 원문을 적어주세요.")
        sys.exit(1)
    if not REF_TEXT.strip():
        print("오류: REF_TEXT가 비어 있습니다. 참조 음성(ref.wav)에 들어 있는 말을 적어주세요.")
        sys.exit(1)

    print(f"클로닝 합성: text={TEXT!r}, language={LANGUAGE}")
    wavs, sr = model.generate_voice_clone(
        text=TEXT,
        language=LANGUAGE,
        ref_audio=str(REF_AUDIO),
        ref_text=REF_TEXT,
    )
    print(f"샘플레이트: {sr}, 샘플 수: {len(wavs[0])}")

    out_dir = Path(__file__).resolve().parent.parent / "assets" / "voice_samples"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "tts_clone_output.wav"
    sf.write(str(out_path), wavs[0], sr)
    print(f"저장: {out_path}")
    print("제로샷 클로닝 테스트 완료.")


if __name__ == "__main__":
    main()
