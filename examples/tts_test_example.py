"""
Qwen3-TTS 변환 테스트

텍스트를 음성으로 변환하는지만 확인합니다. 채팅 응답 연동은 하지 않습니다.
실행: python examples/tts_test_example.py  (프로젝트 루트에서)

필요: NVIDIA GPU (CUDA), qwen-tts, soundfile 설치
  pip install -r requirements.txt

속도: Qwen3-TTS 0.6B가 공식 최소 모델. flash-attn은 선택(Windows 빌드 어려움 많음). 더 가벼운 대안: Piper TTS.
"""

import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    try:
        import torch
        import soundfile as sf
        from qwen_tts import Qwen3TTSModel
    except ImportError as e:
        print(f"오류: 필요한 패키지가 없습니다. ({e})")
        print("  pip install -r requirements.txt 후 다시 실행하세요.")
        print("  AutoProcessor 오류 시: pip install sentencepiece")
        sys.exit(1)

    # 0.6B 모델 (VRAM 약 2GB). 1.7B는 약 4GB 필요
    model_id = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        print("경고: CUDA가 없어 CPU로 실행합니다. 매우 느릴 수 있습니다.")

    print(f"모델 로딩 중: {model_id} ...")
    load_kwargs = {
        "device_map": device,
        "dtype": torch.bfloat16 if device != "cpu" else torch.float32,
    }
    # FlashAttention 2 있으면 사용 (VRAM 절약). 없으면 기본 attention
    try:
        import flash_attn  # noqa: F401
        load_kwargs["attn_implementation"] = "flash_attention_2"
    except ImportError:
        pass
    model = Qwen3TTSModel.from_pretrained(model_id, **load_kwargs)

    # 테스트 문장 (한국어, Sohee 스피커)
    test_text = "간장 공장 공장장은 강 공장장이고, 된장 공장 공장장은 장 공장장이다."
    language = "Korean"
    speaker = "Sohee"

    print(f"TTS 생성 중: '{test_text}' (language={language}, speaker={speaker})")
    wavs, sr = model.generate_custom_voice(
        text=test_text,
        language=language,
        speaker=speaker,
    )
    print(f"샘플레이트: {sr}, 샘플 수: {len(wavs[0])}")

    out_dir = Path(__file__).resolve().parent.parent / "assets" / "voice_samples"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "tts_test_output.wav"
    sf.write(str(out_path), wavs[0], sr)
    print(f"저장 완료: {out_path}")
    print("Qwen3-TTS 변환 테스트 성공.")


if __name__ == "__main__":
    main()
