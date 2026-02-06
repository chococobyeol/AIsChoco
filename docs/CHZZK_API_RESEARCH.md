# 치지직 API 정보 가이드

**✅ 공식 문서 발견!**: https://chzzk.gitbook.io/chzzk/chzzk-api/session

치지직은 **Socket.IO**를 사용하며, 공식 API 문서가 있습니다.

## 1. 공식 개발자 문서 ✅

### 치지직 API 문서
- **세션 문서**: https://chzzk.gitbook.io/chzzk/chzzk-api/session
- **인증 문서**: https://chzzk.gitbook.io/chzzk/chzzk-api/authorization
- **주요 내용**:
  - Socket.IO 기반 연결 (WebSocket 아님!)
  - 세션 생성 API: `/open/v1/sessions/auth` 또는 `/open/v1/sessions/auth/client`
  - 인증 방식: Access Token 또는 Client 인증
  - 채팅 메시지 구조 명시

### Access Token 발급 절차

치지직 API를 사용하려면 먼저 **Access Token**을 발급받아야 합니다.

#### 1단계: 애플리케이션 등록

[치지직 개발자 센터](https://developers.chzzk.naver.com/)에서 애플리케이션을 등록하여 `clientId`와 `clientSecret`을 발급받습니다.

##### 1.1 개발자 센터 접속
1. [치지직 개발자 센터](https://developers.chzzk.naver.com/) 접속
2. 로그인 (네이버 계정 필요)
3. 상단 메뉴에서 **"Application"** 클릭
4. **"애플리케이션 등록"** 버튼 클릭

##### 1.2 애플리케이션 정보 입력

**애플리케이션 ID** (필수):
- **규칙**:
  - 영문 대소문자, 숫자, 하이픈(`-`), 언더스코어(`_`)만 사용 가능
  - 최대 50자까지 입력 가능
  - 기존 클라이언트와 중복 불가
  - `naver`, `chzzk` 등 공식 서비스명 포함 불가
- **예시**: `aischoco-vtuber`, `my-chat-bot`, `test_app_001`
- **중복 확인**: 입력 후 "중복 확인" 버튼으로 사용 가능 여부 확인

**애플리케이션 이름** (필수):
- **규칙**:
  - 한글, 영문 대소문자, 숫자, 띄어쓰기만 사용 가능
  - 최대 50자까지 입력 가능
  - 기존 클라이언트와 중복 불가
  - `naver`, `네이버`, `chzzk`, `치지직` 등 공식 서비스명 포함 불가
- **예시**: `AI 버튜버`, `Chat Bot`, `My Application`
- **중복 확인**: 입력 후 "중복 확인" 버튼으로 사용 가능 여부 확인

**로그인 리디렉션 URL** (필수):
- OAuth 2.0 인증 후 사용자를 리다이렉트할 URL
- **로컬 개발 환경 예시**: `http://localhost:8080/callback`
- **프로덕션 환경 예시**: `https://yourdomain.com/callback`
- ⚠️ **중요**: 이 URL은 나중에 인증 코드 요청 시 사용하는 `redirectUri`와 **정확히 일치**해야 합니다
- 여러 URL 등록 가능 여부는 개발자 센터에서 확인 필요

**API Scopes** (필수):
- "선택" 버튼을 클릭하여 필요한 권한 선택
- **채팅 메시지 수신에 필요한 스코프**:
  - `채팅 메시지 조회` (또는 유사한 이름)
- **후원/구독 이벤트 수신에 필요한 스코프**:
  - `후원 조회`
  - `구독 조회`
- ⚠️ **주의**: 스코프 이름은 실제 개발자 센터에서 확인하세요

##### 1.3 등록 완료
1. 모든 필수 항목 입력 후 **"등록"** 버튼 클릭
2. 등록 완료 시 **Client ID**와 **Client Secret** 발급
3. ⚠️ **중요**: Client Secret은 **한 번만 표시**되므로 반드시 안전하게 저장하세요

##### 1.4 발급받은 정보 저장
```python
# .env 파일 또는 config.yaml에 저장
CHZZK_CLIENT_ID=your-client-id-here
CHZZK_CLIENT_SECRET=your-client-secret-here
CHZZK_REDIRECT_URI=http://localhost:8080/callback
```

**⚠️ 보안 주의사항**:
- Client Secret은 절대 공개 저장소(GitHub 등)에 업로드하지 마세요
- `.env` 파일은 `.gitignore`에 추가되어 있는지 확인하세요
- 프로덕션 환경에서는 환경 변수나 보안 저장소 사용을 권장합니다

#### 2단계: 인증 코드 요청
```
GET https://chzzk.naver.com/account-interlock
```

**파라미터**:
- `clientId`: 애플리케이션 Client ID
- `redirectUri`: 등록한 리디렉션 URL (반드시 등록한 URL과 일치해야 함)
- `state`: CSRF 방지를 위한 랜덤 문자열

**예시**:
```
https://chzzk.naver.com/account-interlock?
  clientId=fefb6bbb-00c2-497c-afc2-XXXXXXXXXXXX&
  redirectUri=http://localhost:8080/callback&
  state=zxclDasdfA25
```

사용자가 로그인하면 `redirectUri`로 리다이렉트되며 `code`와 `state`가 전달됩니다:
```
http://localhost:8080/callback?code=ygKEQQk3p0DjUsBjJradJmXXXXXXXX&state=zxclDasdfA25
```

#### 3단계: Access Token 발급
```
POST https://openapi.chzzk.naver.com/auth/v1/token
```

**Request Body**:
```json
{
  "grantType": "authorization_code",
  "clientId": "fefb6bbb-00c2-497c-afc2-XXXXXXXXXXXX",
  "clientSecret": "VeIMuc9XGle7PSxIVYNwPpI2OEk_9gXoW_XXXXXXXXX",
  "code": "ygKEQQk3p0DjUsBjJradJmXXXXXXXX",
  "state": "zxclDasdfA25"
}
```

**Response**:
```json
{
  "accessToken": "FFok65zQFQVcFvH2eJ7SS7SBFlTXt0EZ10L5XXXXXXXX",
  "refreshToken": "NWG05CKHAsz4k4d3PB0wQUV9ugGlp0YuibQ4XXXXXXXX",
  "tokenType": "Bearer",
  "expiresIn": "86400"
}
```

- **Access Token**: 1일 만료 (86400초)
- **Refresh Token**: 30일 만료
- **tokenType**: 항상 `Bearer`

#### 4단계: Access Token 갱신 (만료 시)
```
POST https://openapi.chzzk.naver.com/auth/v1/token
```

**Request Body**:
```json
{
  "grantType": "refresh_token",
  "refreshToken": "NWG05CKHAsz4k4d3PB0wQUV9ugGlp0YuibQ4XXXXXXXX",
  "clientId": "fefb6bbb-00c2-497c-afc2-XXXXXXXXXXXX",
  "clientSecret": "VeIMuc9XGle7PSxIVYNwPpI2OEk_9gXoW_XXXXXXXXX"
}
```

**Response**: 새로운 `accessToken`과 `refreshToken` 발급

#### 5단계: Access Token 사용
발급받은 Access Token을 사용하여 세션 생성 API 호출:
```
GET https://openapi.chzzk.naver.com/open/v1/sessions/auth
Headers: Authorization: Bearer {accessToken}
```

**참고**: [치지직 인증 문서](https://chzzk.gitbook.io/chzzk/chzzk-api/authorization)

### 핵심 정보
1. **연결 방식**: Socket.IO (WebSocket 아님)
2. **세션 생성**: 먼저 REST API로 세션 URL 획득 필요
3. **인증**: Access Token 또는 Client ID/Secret
4. **메시지 포맷**: JSON 구조 명확히 정의됨

## 2. 기존 오픈소스 프로젝트 분석

### 추천 프로젝트
1. **chzzk-tts** (GitHub)
   - URL: https://github.com/leinnesw/chzzk-tts
   - 치지직 채팅을 수집하는 실제 구현 사례
   - WebSocket 연결 코드 참고 가능

2. **chzzk-py** (GitHub에서 검색)
   - Python 기반 치지직 API 래퍼
   - WebSocket 구현 예시

### 분석 방법
```bash
# GitHub에서 프로젝트 클론
git clone https://github.com/leinnesw/chzzk-tts.git
cd chzzk-tts

# WebSocket 관련 코드 확인
# - WebSocket 엔드포인트 URL
# - 연결 헤더/인증 방식
# - 메시지 포맷
```

## 3. 브라우저 DevTools를 통한 역엔지니어링

### 단계별 방법

1. **치지직 라이브 방송 페이지 열기**
   - https://chzzk.naver.com/live/{channelId}

2. **브라우저 DevTools 열기** (F12)

3. **Network 탭 → WS (WebSocket) 필터**
   - WebSocket 연결 확인
   - 연결 URL 확인 (엔드포인트)

4. **WebSocket 메시지 모니터링**
   - Messages 탭에서 송수신 메시지 확인
   - 메시지 포맷 분석
   - 인증 토큰/헤더 확인

5. **Headers 탭 확인**
   - Request Headers: 인증 토큰, 쿠키 등
   - Response Headers: 서버 응답 정보

### 확인할 정보
- **WebSocket URL**: `wss://...` 형식의 엔드포인트
- **인증 헤더**: Authorization, Cookie 등
- **초기 메시지**: 연결 후 전송하는 구독 메시지
- **채팅 메시지 포맷**: JSON 구조

## 4. 실제 구현 시 확인 사항

### 세션 생성 API
```python
# 유저 인증 (Access Token)
GET https://openapi.chzzk.naver.com/open/v1/sessions/auth
Headers: Authorization: Bearer {access_token}

# Client 인증
GET https://openapi.chzzk.naver.com/open/v1/sessions/auth/client
# Client 인증 헤더 필요 (문서 참고)

# 응답
{
  "url": "https://ssio08.nchat.naver.com:443?auth=TOKEN"
}
```

### Socket.IO 연결
```python
import socketio

sio = socketio.AsyncClient()
await sio.connect(session_url, transports=['websocket'])

# 이벤트 핸들러 등록
sio.on("SYSTEM", on_system_message)  # 시스템 메시지
sio.on("CHAT", on_chat_message)     # 채팅 메시지
```

### 채팅 메시지 포맷 (실제 API 구조)
```json
{
  "channelId": "채널ID",
  "senderChannelId": "작성자 채널ID",
  "profile": {
    "nickname": "사용자명",
    "badges": [],
    "verifiedMark": false
  },
  "userRoleCode": "common_user",
  "content": "채팅 내용",
  "emojis": {
    "key": "이모티콘ID",
    "value": "이모티콘URL"
  },
  "messageTime": 1707216000000
}
```

### 채널 구독 요청 (문서: REST API)
문서 기준 구독은 소켓 emit이 아니라 **REST API** 호출입니다.
- **POST** `/open/v1/sessions/events/subscribe/chat`
- Request Param: `sessionKey` (필수), 채널 지정 시 `channelId`
- Header: `Authorization: Bearer {access_token}`

```python
# 연결 완료 후 SYSTEM "connected"에서 sessionKey 획득 후
POST https://openapi.chzzk.naver.com/open/v1/sessions/events/subscribe/chat
  ?sessionKey=세션키&channelId=채널ID
  Authorization: Bearer {access_token}
```
Socket.IO 클라이언트는 문서상 **Socket.IO-client 2.0.3 버전까지 지원**이므로, python-socketio는 **4.x + python-engineio 3.x** 사용 (5.x는 프로토콜 불일치).

## 5. 커뮤니티 리소스

### GitHub 검색
```
검색어:
- "chzzk websocket"
- "chzzk chat api"
- "치지직 채팅"
```

### 참고할 수 있는 라이브러리
- Python: `chzzk-py`, `chzzk-api` 등
- JavaScript: 브라우저 확장 프로그램 소스 코드

## 6. 구현 체크리스트

실제 구현 전에 다음을 확인하세요:

- [ ] WebSocket 엔드포인트 URL
- [ ] 인증 방식 (쿠키/토큰/세션)
- [ ] 채널 구독 메시지 포맷
- [ ] 채팅 메시지 수신 포맷
- [ ] 에러 메시지 포맷
- [ ] 재연결 로직
- [ ] Rate Limiting 정책

## 7. 주의사항

1. **API 변경**: 공식 문서가 없으므로 언제든 변경될 수 있음
2. **에러 핸들링**: 연결 실패, 인증 실패 등 다양한 상황 대비
3. **법적 고려**: ToS(이용약관) 확인 필요
4. **테스트**: 실제 환경에서 충분히 테스트 후 사용

## 8. 빠른 시작 (기존 프로젝트 참고)

가장 빠른 방법은 기존 오픈소스 프로젝트의 코드를 분석하는 것입니다:

```bash
# chzzk-tts 프로젝트 분석
git clone https://github.com/leinnesw/chzzk-tts.git
# WebSocket 클라이언트 코드 확인
```

## 9. 다음 단계

1. DevTools로 실제 연결 확인
2. 기존 프로젝트 코드 분석
3. 테스트 환경에서 연결 시도
4. 메시지 포맷 검증
5. 코드에 반영

---

**참고**: 이 정보는 2026년 2월 기준이며, 치지직 API 정책 변경에 따라 달라질 수 있습니다.
