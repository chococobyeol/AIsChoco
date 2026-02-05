# AIsChoco - 치지직 연동 실시간 AI 버튜버 시스템

치지직 라이브 방송의 채팅을 실시간 분석하여, 고속 LLM(Groq)이 답변과 감정을 생성하고, 로컬 구동 TTS(Qwen3-TTS)와 캐릭터 제어 API(VTube Studio)를 통해 반응하는 지능형 버튜버 시스템입니다.

## 🚀 주요 기능

- **실시간 채팅 수집**: 치지직 WebSocket API를 통한 지연 없는 채팅 데이터 수집
- **고속 AI 추론**: Groq API(Llama 3 70B)를 사용하여 1초 미만의 응답 생성
- **로컬 음성 생성**: Qwen3-TTS 모델을 로컬 GPU 환경에서 구동하여 저지연 고음질 음성 출력
- **멀티모달 반응**: 답변 내용에 맞춘 포즈, 립싱크 동시 수행
- **정밀 캐릭터 제어**: VTube Studio API를 통한 부드러운 움직임 구현

## 📋 요구사항

- Python 3.10+
- NVIDIA GPU (CUDA 지원)
  - Qwen3-TTS 1.7B 모델: 최소 4GB VRAM
  - Qwen3-TTS 0.6B 모델: 최소 2GB VRAM
- Windows 10/11 (VB-Cable 지원)
- VTube Studio 설치 및 실행

## 🛠️ 설치

1. 저장소 클론
```bash
git clone https://github.com/chococobyeol/AIsChoco.git
cd AIsChoco
```

2. 가상 환경 생성 및 활성화
```bash
python -m venv venv
venv\Scripts\activate  # Windows
```

3. 의존성 설치
```bash
pip install -r requirements.txt
```

4. 환경 변수 설정
```bash
cp .env.example .env
# .env 파일을 열어 API 키 등을 설정
```

5. Qwen3-TTS 모델 다운로드
- Hugging Face 또는 공식 저장소에서 모델 다운로드
- `models/qwen3-tts/` 디렉토리에 저장

6. VB-Cable 설치 및 설정
- VB-Cable 다운로드 및 설치
- VTube Studio의 오디오 입력을 VB-Cable로 설정

## ⚙️ 설정

자세한 설정 방법은 [PRD.md](PRD.md) 문서를 참고하세요.

## 🎮 사용법

```bash
python src/core/pipeline.py
```

## 📁 프로젝트 구조

```
aischoco/
├── src/
│   ├── chat/          # 치지직 채팅 수집
│   ├── ai/            # Groq API 연동
│   ├── tts/           # Qwen3-TTS 음성 생성
│   ├── vtuber/        # VTube Studio 제어
│   ├── core/           # 메인 파이프라인
│   └── utils/          # 유틸리티
├── models/             # TTS 모델 저장
├── assets/             # 음성 샘플 등
├── config/             # 설정 파일
└── history/            # 채팅 히스토리
```

## 📚 문서

- [PRD.md](PRD.md) - 상세한 제품 요구사항 문서

## 🔗 참고 자료

- [Groq API Documentation](https://console.groq.com/docs)
- [VTube Studio API Documentation](https://github.com/DenchiSoft/VTubeStudio)
- [Qwen3-TTS Documentation](https://github.com/QwenLM/Qwen3-TTS)
- [치지직 API Documentation](https://developers.chzzk.naver.com/)

## 📝 라이선스

[라이선스 정보 추가 예정]

## 🤝 기여

이슈 및 Pull Request를 환영합니다!
