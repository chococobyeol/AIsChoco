# 로깅 가이드

`examples/chzzk_groq_example.py`, `examples/chzzk_chat_example.py` 실행 시 공통 로깅 설정이 자동 적용됩니다.
`examples/chzzk_groq_example.py`의 AI/TTS 파이프라인 로그에는 `rid=<request_id>`가 포함되어 한 턴을 추적할 수 있습니다.

## 기본 동작

- 콘솔 출력: `WARNING` 이상
- 통합 로그: `logs/app.log` (`INFO` 이상)
- 에러 전용: `logs/error.log` (`ERROR` 이상)
- 카테고리 로그:
  - `logs/chat.log`: `src.chat`, `engineio`, `socketio`
  - `logs/ai.log`: `src.ai` (시청자 입력/AI 답변 대화 로그 포함)
  - `logs/tts.log`: `src.tts` (TTS 합성 시작/완료, 재생 시작/완료 포함)
  - `logs/vtuber.log`: `src.vtuber`, `src.overlay`
- 로그 파일은 크기 기반으로 자동 회전됩니다.

`chat.log`에는 연결/구독 로그와 함께 **실제 채팅 수신 로그(DEBUG)**가 기록됩니다.
실시간 채팅이 없으면 구독 로그만 보일 수 있습니다.

## Engine.IO / Socket.IO 로그 소음 줄이기

치지직 연결 로그(`engineio.client`)가 너무 많으면 `.env`에 아래를 추가하세요.

```bash
# 기본값: WARNING
ENGINEIO_LOG_LEVEL=ERROR
```

권장 값:
- `WARNING`: 중요한 경고는 보고 싶을 때
- `ERROR`: 연결 디버그 로그를 거의 숨기고 싶을 때

## 로그 회전(파일 크기/보관 개수)

```bash
# 기본값: 10MB
LOG_MAX_MB=20

# 기본값: 5개
LOG_BACKUP_COUNT=10
```

## 콘솔 로그 레벨

```bash
# 기본값: WARNING
LOG_CONSOLE_LEVEL=INFO
```

가능 값: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

## 운영 팁

- 평소 방송: `ENGINEIO_LOG_LEVEL=ERROR`, `LOG_CONSOLE_LEVEL=WARNING`
- 문제 분석: `ENGINEIO_LOG_LEVEL=WARNING`, `LOG_CONSOLE_LEVEL=INFO`
- 디스크 관리: 로그 폴더(`logs/`)를 주기적으로 정리하거나 `LOG_BACKUP_COUNT`를 낮추세요.
