# AIsChoco - 치지직 연동 실시간 AI 버튜버 시스템

치지직 라이브 방송의 채팅을 실시간 분석하여, 고속 LLM(Groq)이 답변과 감정을 생성하고, 로컬 구동 TTS(Qwen3-TTS)와 캐릭터 제어 API(VTube Studio)를 통해 반응하는 지능형 버튜버 시스템입니다.

## 🚀 주요 기능

- **실시간 채팅 수집**: 치지직 Socket.IO API를 통한 지연 없는 채팅 데이터 수집
- **고속 AI 추론**: Groq API(기본: gpt-oss-120b, .env GROQ_MODEL로 변경 가능)를 사용하여 1초 미만의 응답 생성
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
   - **GPU 사용 시 (TTS 등)**: PyTorch CUDA를 먼저 설치한 뒤 나머지 의존성 설치
   ```bash
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
   pip install -r requirements.txt
   ```
   - **CPU만 사용 시**: 아래만 실행
   ```bash
   pip install -r requirements.txt
   ```
   CUDA 버전(cu118/cu126/cu128)은 [pytorch.org/get-started/locally](https://pytorch.org/get-started/locally/)에서 본인 환경에 맞게 선택.

4. 치지직 애플리케이션 등록 및 인증 설정
   - [치지직 개발자 센터](https://developers.chzzk.naver.com/) 접속
   - 애플리케이션 등록 (자세한 방법은 [docs/CHZZK_API_RESEARCH.md](docs/CHZZK_API_RESEARCH.md) 참고)
   - Client ID와 Client Secret 발급
   - 로그인 리디렉션 URL 등록 (예: `http://localhost:8080/callback`)

5. 환경 변수 설정
- 프로젝트 루트에 `.env` 파일을 생성하고 아래 항목을 입력하세요.
- **필수**: CHZZK_CLIENT_ID, CHZZK_CLIENT_SECRET, CHZZK_REDIRECT_URI, CHZZK_CHANNEL_ID, CHZZK_ACCESS_TOKEN(인증 후), GROQ_API_KEY
- **선택**: GROQ_MODEL(기본 openai/gpt-oss-120b), TTS_REMOTE_URL(Colab TTS 사용 시). 자세한 예시는 [docs/QUICK_START.md](docs/QUICK_START.md) 참고.

6. Qwen3-TTS 모델 다운로드
- Hugging Face 또는 공식 저장소에서 모델 다운로드
- `models/qwen3-tts/` 디렉토리에 저장

7. VB-Cable 설치 및 설정
- VB-Cable 다운로드 및 설치
- VTube Studio의 오디오 입력을 VB-Cable로 설정

## ⚙️ 설정

- **캐릭터 성격**: `config/character.txt`에 작성 시 Groq 시스템 프롬프트 앞에 붙어 적용됩니다. (예: `character.txt.example` 참고)
- **VTS 포즈**: `config/pose_mapping.json`으로 감정별 파라미터 설정. 최초 연결 시 토큰은 `config/vts_token.txt`에 저장됩니다. ([docs/VTUBE_STUDIO.md](docs/VTUBE_STUDIO.md))
- **원격 TTS**: Colab에서 TTS 서버를 띄우고 `.env`에 `TTS_REMOTE_URL`을 설정하면 로컬 대신 원격 TTS를 사용합니다. ([docs/COLAB_TTS.md](docs/COLAB_TTS.md))
- 자세한 요구사항은 [PRD.md](PRD.md)를 참고하세요.

## 🎮 사용법

### 전체 시스템 실행 (치지직 + Groq + TTS + VTS)
```bash
# 가상환경 활성화 후 프로젝트 루트에서
python examples/chzzk_groq_example.py
```

### 치지직 예제만 실행 (가상환경 활성화 후, 프로젝트 루트에서)
```bash
# 1) Access Token 발급 (한 번만)
python examples/chzzk_auth_example.py

# 2) .env에 CHZZK_ACCESS_TOKEN 추가 후 채팅 수신 테스트
python examples/chzzk_chat_example.py
```

### TTS 예제 (프로젝트 루트에서)
```bash
# CustomVoice: 프리셋 목소리(Sohee 등) + 감정 instruct
python examples/tts_test_example.py

# Base 제로샷 클로닝: 참조 음성(파일 내 REF_AUDIO, REF_TEXT)으로 그 목소리 합성
python examples/tts_clone_example.py

# Voice Design then Clone: 16세 여성 중립 톤 등 목소리 설계 후 클로닝 (참조는 AI 생성)
python examples/tts_design_then_clone_example.py
```

**⚠️ 중요**: 실제 사용 전에 다음을 설정해야 합니다:
1. 가상환경 활성화 후 `pip install -r requirements.txt`
2. 치지직 개발자 센터에서 애플리케이션 등록 및 Client ID/Secret 발급
3. `.env` 파일에 발급받은 정보 및 API 키 설정
4. Access Token 발급 (`python examples/chzzk_auth_example.py`) 후 `.env`에 `CHZZK_ACCESS_TOKEN` 추가
5. 치지직 채널 ID 확인 및 `.env`에 `CHZZK_CHANNEL_ID` 설정

자세한 설정 방법은 [docs/CHZZK_API_RESEARCH.md](docs/CHZZK_API_RESEARCH.md)를 참고하세요.

## 📁 프로젝트 구조

```
aischoco/
├── src/
│   ├── chat/          # 치지직 채팅 수집
│   ├── ai/            # Groq API 연동, 채팅 히스토리(토큰 기반 요약)
│   ├── tts/           # Qwen3-TTS 음성 생성
│   ├── vtuber/        # VTube Studio 제어 (vts_client)
│   ├── core/          # (예제는 examples/ 에서 실행)
│   └── utils/         # 유틸리티
├── examples/         # 실행 진입점 (chzzk_groq_example.py 등)
├── models/            # TTS 모델 저장
├── assets/            # 음성 샘플 등
├── config/            # character.txt, pose_mapping.json 등
└── history/           # summary.json, summaries/, backups/
```

## 📚 문서

- [docs/QUICK_START.md](docs/QUICK_START.md) - **빠른 시작 가이드** (처음 사용하는 분 추천)
- [PRD.md](PRD.md) - 상세한 제품 요구사항 문서
- [docs/CHZZK_API_RESEARCH.md](docs/CHZZK_API_RESEARCH.md) - 치지직 API 사용 가이드 (애플리케이션 등록, Access Token 발급 등)
- [docs/VTUBE_STUDIO.md](docs/VTUBE_STUDIO.md) - VTube Studio 연결 및 감정 포즈 설정 (pose_mapping.json)
- [docs/COLAB_TTS.md](docs/COLAB_TTS.md) - Colab 원격 TTS 사용 (TTS_REMOTE_URL)

## 🔗 참고 자료

- [Groq API Documentation](https://console.groq.com/docs)
- [VTube Studio API Documentation](https://github.com/DenchiSoft/VTubeStudio)
- [Qwen3-TTS Documentation](https://github.com/QwenLM/Qwen3-TTS)
- [치지직 API Documentation](https://developers.chzzk.naver.com/)

## 📝 라이선스

[라이선스 정보 추가 예정]

## 🤝 기여

이슈 및 Pull Request를 환영합니다!
