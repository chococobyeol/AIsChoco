# 빠른 시작 가이드

치지직 AI 버튜버 시스템을 처음 사용하는 분을 위한 단계별 가이드입니다.

## 0. 설치 (실행 순서)

1. 저장소 클론 후 가상환경 생성 및 활성화
2. **GPU 사용 시**: PyTorch CUDA 먼저 설치 후 의존성 설치
   ```bash
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
   pip install -r requirements.txt
   ```
3. **CPU만 사용 시**: 의존성만 설치
   ```bash
   pip install -r requirements.txt
   ```
   (CUDA 버전은 [pytorch.org/get-started/locally](https://pytorch.org/get-started/locally/)에서 확인)

## 1. 치지직 애플리케이션 등록

### 1.1 개발자 센터 접속
1. [치지직 개발자 센터](https://developers.chzzk.naver.com/) 접속
2. 네이버 계정으로 로그인
3. 상단 메뉴에서 **"Application"** 클릭
4. **"애플리케이션 등록"** 버튼 클릭

### 1.2 애플리케이션 정보 입력

#### 애플리케이션 ID
- **규칙**: 영문 대소문자, 숫자, `-`, `_`만 사용 가능 (최대 50자)
- **예시**: `aischoco-vtuber`, `my-chat-bot`
- ⚠️ `naver`, `chzzk` 등 공식 서비스명 포함 불가
- 입력 후 **"중복 확인"** 버튼 클릭

#### 애플리케이션 이름
- **규칙**: 한글, 영문, 숫자, 띄어쓰기만 사용 가능 (최대 50자)
- **예시**: `AI 버튜버`, `Chat Bot`
- ⚠️ `naver`, `네이버`, `chzzk`, `치지직` 등 공식 서비스명 포함 불가
- 입력 후 **"중복 확인"** 버튼 클릭

#### 로그인 리디렉션 URL
- **로컬 개발**: `http://localhost:8080/callback`
- **프로덕션**: `https://yourdomain.com/callback`
- ⚠️ 이 URL은 나중에 인증 코드 요청 시 사용하는 `redirectUri`와 **정확히 일치**해야 합니다

#### API Scopes
- **"선택"** 버튼 클릭하여 필요한 권한 선택:
  - ✅ `채팅 메시지 조회` (필수)
  - ✅ `후원 조회` (후원 이벤트 수신 시)
  - ✅ `구독 조회` (구독 이벤트 수신 시)

### 1.3 등록 완료
1. 모든 필수 항목 입력 후 **"등록"** 버튼 클릭
2. **Client ID**와 **Client Secret** 발급
3. ⚠️ **중요**: Client Secret은 **한 번만 표시**되므로 반드시 안전하게 저장하세요!

## 2. 환경 변수 설정

프로젝트 루트에서 `.env.example`을 복사해 `.env`를 만들고 값을 채우세요.

```bash
# macOS / Linux
cp .env.example .env

# Windows PowerShell
Copy-Item .env.example .env
```

기본 템플릿:

```bash
# 치지직 API 인증 정보
CHZZK_CLIENT_ID=your-client-id-here
CHZZK_CLIENT_SECRET=your-client-secret-here
CHZZK_REDIRECT_URI=http://localhost:8080/callback

# 치지직 채널 ID (라이브 방송 채널 ID)
CHZZK_CHANNEL_ID=your-channel-id-here

# 치지직 Access Token (chzzk_auth_example.py 실행 후 발급받아 추가)
CHZZK_ACCESS_TOKEN=your-access-token-here

# Groq API 키 (기본 모델: openai/gpt-oss-120b, 변경 시 아래 추가)
GROQ_API_KEY=your-groq-api-key-here
# GROQ_MODEL=openai/gpt-oss-120b

# VTube Studio: 앱 실행 후 chzzk_groq_example.py 최초 실행 시 연결 허용하면
# 토큰이 config/vts_token.txt 에 자동 저장됩니다. .env에 VTS_* 는 선택.

# (선택) Colab TTS 사용 시
# TTS_REMOTE_URL=https://xxxx.ngrok.io

# (선택) 로그 설정
# ENGINEIO_LOG_LEVEL=ERROR      # 기본 WARNING, engineio/client 로그 줄이기
# LOG_CONSOLE_LEVEL=WARNING     # 콘솔 출력 레벨
# LOG_MAX_MB=10                 # 파일당 최대 크기(MB)
# LOG_BACKUP_COUNT=5            # 로그 파일 보관 개수
```

⚠️ **보안 주의사항**:
- `.env` 파일은 절대 Git에 커밋하지 마세요 (`.gitignore`에 포함되어 있음)
- Client Secret은 공개 저장소에 업로드하지 마세요

## 3. Access Token 발급

### 3.1 인증 URL 생성 및 로그인
```bash
python examples/chzzk_auth_example.py
```

스크립트가 인증 URL을 생성하면:
1. 브라우저에서 해당 URL 열기
2. 치지직 계정으로 로그인
3. 권한 승인
4. 리디렉션 URL에서 `code`와 `state` 파라미터 복사

### 3.2 토큰 발급
스크립트에 `code`와 `state`를 입력하면 Access Token이 발급됩니다.

발급받은 토큰은 자동으로 저장되며, 만료 시 Refresh Token으로 자동 갱신됩니다.

## 4. 채널 ID 확인

치지직 라이브 방송 페이지 URL에서 채널 ID를 확인할 수 있습니다:
```
https://chzzk.naver.com/live/{CHANNEL_ID}
```

예: `https://chzzk.naver.com/live/abc123def456` → 채널 ID는 `abc123def456`

## 5. 테스트 실행

### 5.1 채팅만 수신 테스트
```bash
python examples/chzzk_chat_example.py
```

실행 후 프로젝트 루트에 `logs/` 폴더가 생성되고 아래 파일이 저장됩니다:
- `logs/app.log` (통합)
- `logs/error.log` (에러 전용)
- `logs/chat.log`, `logs/ai.log`, `logs/tts.log`, `logs/vtuber.log` (카테고리별)

### 5.2 전체 시스템 실행 (채팅 + Groq + TTS + VTS)
```bash
python examples/chzzk_groq_example.py
```

## 다음 단계

- [PRD.md](../PRD.md) - 상세한 제품 요구사항 문서
- [docs/CHZZK_API_RESEARCH.md](CHZZK_API_RESEARCH.md) - 치지직 API 상세 가이드
- [docs/LOGGING.md](LOGGING.md) - 로그 파일 구조/레벨/회전 설정

## 문제 해결

### "Client Secret이 없습니다" 오류
- 치지직 개발자 센터에서 애플리케이션을 다시 등록하거나, Client Secret을 재발급 받으세요

### "리디렉션 URL이 일치하지 않습니다" 오류
- 개발자 센터에 등록한 리디렉션 URL과 `.env`의 `CHZZK_REDIRECT_URI`가 정확히 일치하는지 확인하세요

### "토큰이 만료되었습니다" 오류
- Refresh Token으로 자동 갱신되지만, Refresh Token도 만료된 경우 인증 과정을 다시 진행하세요
