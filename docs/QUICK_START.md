# 빠른 시작 가이드

치지직 AI 버튜버 시스템을 처음 사용하는 분을 위한 단계별 가이드입니다.

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

프로젝트 루트에 `.env` 파일을 생성하고 다음 내용을 입력하세요:

```bash
# 치지직 API 인증 정보
CHZZK_CLIENT_ID=your-client-id-here
CHZZK_CLIENT_SECRET=your-client-secret-here
CHZZK_REDIRECT_URI=http://localhost:8080/callback

# 치지직 채널 ID (라이브 방송 채널 ID)
CHZZK_CHANNEL_ID=your-channel-id-here

# Groq API 키
GROQ_API_KEY=your-groq-api-key-here

# VTube Studio 설정
VTUBE_STUDIO_HOST=localhost
VTUBE_STUDIO_PORT=8001
VTUBE_STUDIO_TOKEN=your-vtube-studio-token-here

# Qwen3-TTS 모델 경로
QWEN3_TTS_MODEL_PATH=models/qwen3-tts

# 로깅 레벨
LOG_LEVEL=INFO
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

### 5.1 채팅 클라이언트 테스트
```bash
python src/chat/example_usage.py
```

### 5.2 전체 시스템 실행
```bash
python src/core/pipeline.py
```

## 다음 단계

- [PRD.md](../PRD.md) - 상세한 제품 요구사항 문서
- [docs/CHZZK_API_RESEARCH.md](CHZZK_API_RESEARCH.md) - 치지직 API 상세 가이드

## 문제 해결

### "Client Secret이 없습니다" 오류
- 치지직 개발자 센터에서 애플리케이션을 다시 등록하거나, Client Secret을 재발급 받으세요

### "리디렉션 URL이 일치하지 않습니다" 오류
- 개발자 센터에 등록한 리디렉션 URL과 `.env`의 `CHZZK_REDIRECT_URI`가 정확히 일치하는지 확인하세요

### "토큰이 만료되었습니다" 오류
- Refresh Token으로 자동 갱신되지만, Refresh Token도 만료된 경우 인증 과정을 다시 진행하세요
