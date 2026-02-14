# AIsChoco - 치지직 연동 실시간 AI 버튜버 시스템

치지직 라이브 방송의 채팅을 실시간 분석하여, 고속 LLM(Groq)이 답변과 감정을 생성하고, 로컬 구동 TTS(Qwen3-TTS)와 캐릭터 제어 API(VTube Studio)를 통해 반응하는 지능형 버튜버 시스템입니다.

## 🚀 주요 기능

- **실시간 채팅 수집**: 치지직 Socket.IO API를 통한 지연 없는 채팅 데이터 수집
- **고속 AI 추론**: Groq API(기본: gpt-oss-120b, .env GROQ_MODEL로 변경 가능)를 사용하여 1초 미만의 응답 생성
- **로컬 음성 생성**: Qwen3-TTS 모델을 로컬 GPU 환경에서 구동하여 저지연 고음질 음성 출력
- **멀티모달 반응**: 답변 내용에 맞춘 포즈, 립싱크 동시 수행
- **정밀 캐릭터 제어**: VTube Studio API를 통한 부드러운 움직임 구현
- **방송 오버레이**: OBS 브라우저 소스로 시청자 채팅 / AI 답변 표시 (클리어·방장 채팅 숨김 토글)
- **분리 로깅**: 통합/에러/카테고리 로그 파일 자동 저장 (`logs/`)

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
- 프로젝트 루트에서 `.env.example`을 복사해 `.env`를 만드세요.
  - 예: `cp .env.example .env` (Windows PowerShell: `Copy-Item .env.example .env`)
- **실행 시 필수**: CHZZK_CHANNEL_ID, CHZZK_ACCESS_TOKEN, GROQ_API_KEY
- **토큰 발급 시 필요** (한 번만): CHZZK_CLIENT_ID, CHZZK_CLIENT_SECRET, CHZZK_REDIRECT_URI ([docs/CHZZK_API_RESEARCH.md](docs/CHZZK_API_RESEARCH.md) 참고)
- **선택**: GROQ_MODEL(기본 openai/gpt-oss-120b), TTS_REMOTE_URL(원격 TTS 사용 시), OVERLAY_PORT(기본 8765), TTS_OUTPUT_DEVICE(VB-Cable 등). 자세한 예시는 [docs/QUICK_START.md](docs/QUICK_START.md) 참고.

6. TTS (로컬 사용 시)
- **로컬 GPU**: Qwen3-TTS는 Hugging Face 캐시에 자동 다운로드됩니다. `.env`의 `HF_HOME` 또는 기본 `cache/huggingface` 사용. 참조 음성은 `assets/voice_samples/ref.wav`, `ref_text.txt`에 두세요.
- **원격 TTS**: GPU 없이 쓰려면 Colab 또는 맥(Apple Silicon)에서 TTS API 서버를 띄우고 `.env`에 `TTS_REMOTE_URL` 설정. Colab은 [docs/COLAB_TTS.md](docs/COLAB_TTS.md), 맥은 [mac_tts_server/README.md](mac_tts_server/README.md) 참고.

7. VB-Cable 설치 및 설정
- VB-Cable 다운로드 및 설치
- VTube Studio의 오디오 입력을 VB-Cable로 설정

## ⚙️ 설정

- **캐릭터 성격**: `config/character.txt`에 작성 시 Groq 시스템 프롬프트 앞에 붙어 적용됩니다. (예: `character.txt.example` 참고)
- **VTS 포즈**: `config/pose_mapping.json`으로 감정별 파라미터 설정. 최초 연결 시 토큰은 `config/vts_token.txt`에 저장됩니다. ([docs/VTUBE_STUDIO.md](docs/VTUBE_STUDIO.md))
- **원격 TTS**: Colab 또는 맥(MLX)에서 TTS 서버를 띄운 뒤 `.env`에 `TTS_REMOTE_URL` 설정 시 로컬 대신 원격 TTS 사용. ([docs/COLAB_TTS.md](docs/COLAB_TTS.md), [mac_tts_server/README.md](mac_tts_server/README.md))
- **방송 오버레이**: `chzzk_groq_example.py` 실행 시 같은 프로세스에서 오버레이 서버가 백그라운드로 뜹니다. OBS에서 브라우저 소스 추가 → URL에 `http://127.0.0.1:8765/` (포트 변경 시 `.env`에 `OVERLAY_PORT` 설정). 화면에 시청자 채팅 / AI 답변 컬럼, 클리어·방장 채팅 숨김 토글 제공.
- **로깅**: 실행 시 `logs/` 폴더에 통합/에러/카테고리 로그가 자동 저장됩니다. noisy 로그(`engineio.client`)는 `.env`의 `ENGINEIO_LOG_LEVEL`로 조절할 수 있습니다. ([docs/LOGGING.md](docs/LOGGING.md))
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

### 방송 오버레이 (OBS)
- `python examples/chzzk_groq_example.py` 실행 시 오버레이 서버가 `http://127.0.0.1:8765/` (또는 OVERLAY_PORT)에서 자동 기동됩니다.
- OBS에서 **브라우저 소스** 추가 후 URL에 위 주소 입력하면 시청자 채팅(오른쪽)과 AI 답변(왼쪽)이 표시됩니다. 페이지의 **클리어** 버튼으로 수동 클리어, **방장 숨김** 토글로 방장 채팅 표시/무시 가능.

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
│   ├── tts/           # Qwen3-TTS 음성 생성 (로컬/원격 TTS_REMOTE_URL)
│   ├── vtuber/        # VTube Studio 제어 (vts_client, 감정·아이들 포즈)
│   ├── overlay/       # 방송 오버레이 (상태·HTTP 서버, OBS 브라우저 소스용)
│   ├── core/          # (예제는 examples/ 에서 실행)
│   └── utils/         # 유틸리티
├── examples/         # 실행 진입점 (chzzk_groq_example.py 등)
├── mac_tts_server/   # 맥(Apple Silicon)용 TTS API 서버 (원격 TTS 옵션)
├── assets/            # 음성 샘플(voice_samples), 이미지 등
├── config/            # character.txt, pose_mapping.json, vts_token.txt
└── history/           # summary.json, summaries/, backups/
```

로컬 TTS 모델은 Hugging Face 캐시(기본 `cache/huggingface` 또는 `.env` HF_HOME)에 저장됩니다.

## 📚 문서

- [docs/QUICK_START.md](docs/QUICK_START.md) - **빠른 시작 가이드** (처음 사용하는 분 추천)
- [PRD.md](PRD.md) - 상세한 제품 요구사항 문서
- [docs/CHZZK_API_RESEARCH.md](docs/CHZZK_API_RESEARCH.md) - 치지직 API 사용 가이드 (애플리케이션 등록, Access Token 발급 등)
- [docs/VTUBE_STUDIO.md](docs/VTUBE_STUDIO.md) - VTube Studio 연결 및 감정 포즈 설정 (pose_mapping.json)
- [docs/COLAB_TTS.md](docs/COLAB_TTS.md) - Colab 원격 TTS 사용 (TTS_REMOTE_URL)
- [docs/TAROT_OVERLAY.md](docs/TAROT_OVERLAY.md) - 타로 오버레이 설계·구현 정리 (카드 시각화, 질문 유형별 JSON)
- [docs/LOGGING.md](docs/LOGGING.md) - 로그 파일 구조, 레벨, 회전 설정
- [mac_tts_server/README.md](mac_tts_server/README.md) - 맥(Apple Silicon) TTS API 서버 (MLX, 원격 TTS)

## 🔗 참고 자료

- [Groq API Documentation](https://console.groq.com/docs)
- [VTube Studio API Documentation](https://github.com/DenchiSoft/VTubeStudio)
- [Qwen3-TTS Documentation](https://github.com/QwenLM/Qwen3-TTS)
- [치지직 API Documentation](https://developers.chzzk.naver.com/)

## 📝 라이선스

[라이선스 정보 추가 예정]

## 🤝 기여

이슈 및 Pull Request를 환영합니다!
