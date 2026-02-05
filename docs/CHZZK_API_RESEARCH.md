# 치지직 API 정보 가이드

**✅ 공식 문서 발견!**: https://chzzk.gitbook.io/chzzk/chzzk-api/session

치지직은 **Socket.IO**를 사용하며, 공식 API 문서가 있습니다.

## 1. 공식 개발자 문서 ✅

### 치지직 API 문서
- **URL**: https://chzzk.gitbook.io/chzzk/chzzk-api/session
- **주요 내용**:
  - Socket.IO 기반 연결 (WebSocket 아님!)
  - 세션 생성 API: `/open/v1/sessions/auth` 또는 `/open/v1/sessions/auth/client`
  - 인증 방식: Access Token 또는 Client 인증
  - 채팅 메시지 구조 명시

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
GET https://open-api.chzzk.naver.com/open/v1/sessions/auth
Headers: Authorization: Bearer {access_token}

# Client 인증
GET https://open-api.chzzk.naver.com/open/v1/sessions/auth/client
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

### 채널 구독 요청
```python
# 연결 완료 후 sessionKey 획득
# SYSTEM 메시지의 "connected" 타입에서 sessionKey 추출

subscribe_data = {
    "sessionKey": "세션키",
    "eventType": "CHAT",
    "channelId": "채널ID"
}
sio.emit("subscribe", subscribe_data)
```

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
