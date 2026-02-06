# 채팅 모듈 구조

다양한 플랫폼의 채팅을 수집하기 위한 확장 가능한 구조입니다.

## 구조

```
src/chat/
├── base_client.py          # 추상 기본 클래스 (ChatClient)
├── chzzk_client.py         # 치지직 구현체
├── youtube_client.py       # 유튜브 구현체 (추가 예정)
├── chat_parser.py          # 메시지 파싱 및 필터링
├── client_factory.py       # 플랫폼별 클라이언트 팩토리
└── example_usage.py        # 사용 예제
```

## 새로운 플랫폼 추가하기

### 1. 클라이언트 클래스 생성

`base_client.py`의 `ChatClient`를 상속하여 구현:

```python
# src/chat/youtube_client.py
from .base_client import ChatClient, ChatMessage

class YouTubeChatClient(ChatClient):
    @property
    def platform_name(self) -> str:
        return "youtube"
    
    async def connect(self):
        # 유튜브 API 연결 로직
        pass
    
    async def disconnect(self):
        # 연결 종료 로직
        pass
    
    async def listen(self):
        # 메시지 수신 루프
        pass
```

### 2. 팩토리에 등록

`client_factory.py`에 추가:

```python
from .youtube_client import YouTubeChatClient

_platforms = {
    "chzzk": ChzzkSocketIOClient,
    "youtube": YouTubeChatClient,  # 추가
}
```

### 3. 사용

```python
from chat import ChatClientFactory

# 플랫폼만 변경하면 됨!
client = ChatClientFactory.create(
    platform="youtube",  # 또는 "chzzk"
    channel_id="YOUR_CHANNEL_ID"
)
```

## 공통 인터페이스

모든 플랫폼 클라이언트는 다음 메서드를 구현해야 합니다:

- `platform_name`: 플랫폼 이름 반환
- `connect()`: 연결
- `disconnect()`: 연결 종료
- `listen()`: 메시지 수신 루프

## ChatMessage 구조

모든 플랫폼은 동일한 `ChatMessage` 형식을 사용:

```python
@dataclass
class ChatMessage:
    user: str
    message: str
    timestamp: datetime
    emoticons: list[str]
    channel_id: str
    platform: str  # 자동 설정됨
    message_id: Optional[str] = None
    user_id: Optional[str] = None
    user_badge: Optional[str] = None
```
