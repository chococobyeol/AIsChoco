"""
Qwen3-TTS Voice Design then Clone 예제

(1) Voice Design 모델로 "16세 여성, 중립 톤" 참조 음성을 생성
(2) 그 음성을 Base 모델로 클로닝해 여러 문장 합성

참조 음성은 사용자 녹음이 아니라 AI가 만든 목소리입니다.
실행: python examples/tts_design_then_clone_example.py  (프로젝트 루트에서)

필요: NVIDIA GPU (CUDA), qwen-tts, soundfile. VoiceDesign 1.7B + Base 0.6B 사용.
  pip install -r requirements.txt
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "voice_samples"

# 1단계: Voice Design으로 참조 음성 만들 때 쓸 문장 + 목소리 지시
REF_TEXT = "안녕하세요. 오늘 날씨가 좋네요. 이 목소리는 디자인된 참조 음성입니다."
REF_INSTRUCT = "16세 여성, 중립적인 톤으로 차분하게 말해줘."

# 2단계: 이 목소리로 합성할 문장들
SENTENCES = [
    "오늘 뭐 할 거예요?",
    "저는 그렇게 생각하지 않아요. 다시 한번 말해 주세요.",
]
LANGUAGE = "Korean"


def main():
    try:
        import torch
        import soundfile as sf
        from qwen_tts import Qwen3TTSModel
    except ImportError as e:
        print(f"오류: 필요한 패키지가 없습니다. ({e})")
        print("  pip install -r requirements.txt")
        sys.exit(1)

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        print("경고: CUDA 없음. CPU로 실행하면 매우 느립니다.")
    load_kwargs = {
        "device_map": device,
        "dtype": torch.bfloat16 if device != "cpu" else torch.float32,
    }
    try:
        import flash_attn  # noqa: F401
        load_kwargs["attn_implementation"] = "flash_attention_2"
    except ImportError:
        pass

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- 1단계: Voice Design으로 참조 음성 생성 (16세 여성, 중립 톤)
    design_id = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
    print(f"모델 로딩 중: {design_id} ...")
    design_model = Qwen3TTSModel.from_pretrained(design_id, **load_kwargs)
    print(f"Voice Design 생성: instruct={REF_INSTRUCT!r}")
    ref_wavs, sr = design_model.generate_voice_design(
        text=REF_TEXT,
        language=LANGUAGE,
        instruct=REF_INSTRUCT,
    )
    design_ref_path = OUT_DIR / "design_ref.wav"
    sf.write(str(design_ref_path), ref_wavs[0], sr)
    print(f"참조 음성 저장: {design_ref_path}")

    del design_model
    if device != "cpu":
        torch.cuda.empty_cache()

    # --- 2단계: Base로 클로닝 프롬프트 만들고 문장들 합성
    base_id = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
    print(f"모델 로딩 중: {base_id} ...")
    clone_model = Qwen3TTSModel.from_pretrained(base_id, **load_kwargs)

    voice_clone_prompt = clone_model.create_voice_clone_prompt(
        ref_audio=(ref_wavs[0], sr),
        ref_text=REF_TEXT,
    )

    print(f"클로닝 합성: {len(SENTENCES)}문장")
    lang_list = [LANGUAGE] * len(SENTENCES)
    wavs, sr = clone_model.generate_voice_clone(
        text=SENTENCES,
        language=lang_list,
        voice_clone_prompt=voice_clone_prompt,
    )

    for i, w in enumerate(wavs):
        path = OUT_DIR / f"design_clone_{i}.wav"
        sf.write(str(path), w, sr)
        print(f"  저장: {path}")

    print("Voice Design then Clone 완료.")


if __name__ == "__main__":
    main()
