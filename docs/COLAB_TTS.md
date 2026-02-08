# Colab TTS 서버 가이드

로컬 PC가 느려서 TTS가 오래 걸릴 때, Google Colab의 GPU에서 TTS를 돌리고 로컬 앱이 API로 호출하는 방식입니다.

## 사용 흐름

1. **Colab**: TTS 모델 + Flask API 실행, ngrok으로 공개 URL 노출
2. **로컬**: `.env`에 `TTS_REMOTE_URL` 설정 → TTS 호출 시 Colab API로 전송

## Colab 설정

### 1. 새 노트북 생성

- [colab.research.google.com](https://colab.research.google.com) 접속
- **파일 → 새 노트북** 또는 **런타임 → 런타임 유형 변경 → GPU** 선택

### 2. ngrok authtoken 설정

- [ngrok 대시보드](https://dashboard.ngrok.com/signup)에서 무료 가입
- [Your Authtoken](https://dashboard.ngrok.com/get-started/your-authtoken) 페이지에서 토큰 복사
- Colab에서 **별도 셀** 실행:
  ```python
  import os
  os.environ["NGROK_AUTHTOKEN"] = "여기에_발급받은_토큰_붙여넣기"
  ```

### 3. ref 파일 업로드

- 왼쪽 **파일** 아이콘 클릭
- `ref.wav`, `ref_text.txt` 업로드 (로컬 `assets/voice_samples/` 와 동일한 파일)

### 4. TTS 서버 코드 실행

- `examples/colab_tts_server.py` 전체 내용을 Colab 셀에 붙여넣고 실행
- 모델 로드 + 서버 시작 + ngrok URL 출력까지 완료될 때까지 대기

### 5. URL 복사

출력 예시:
```
============================================================
TTS 서버가 실행되었습니다.
.env에 다음을 추가하세요:
TTS_REMOTE_URL=https://xxxx.ngrok-free.app
============================================================
```

이 `TTS_REMOTE_URL` 값을 복사합니다.

## 로컬 설정

### .env 수정

```
TTS_REMOTE_URL=https://xxxx.ngrok-free.app
```

- `https://` 로 시작하는 URL만 넣고, 끝의 `/` 는 넣지 않아도 됩니다.
- Colab 세션이 끊기거나 URL이 바뀌면, 다시 Colab 실행 후 출력된 새 URL로 교체해야 합니다.

### 실행

```bash
python examples/chzzk_groq_example.py
```

로그에 `TTS 원격 API 사용: https://...` 가 보이면 정상입니다.

## 주의사항

- **Colab 세션 제한**: 무료 Colab은 90분 후 등으로 끊길 수 있음. 끊기면 다시 Colab을 실행하고 새 ngrok URL을 `.env`에 넣어야 함.
- **동일 ref 사용**: Colab에 업로드한 `ref.wav`, `ref_text.txt`는 로컬 `assets/voice_samples/` 와 동일해야 목소리가 맞음.
- **네트워크**: Colab은 해외 서버라 한국에서는 50~200ms RTT 정도 예상. TTS 추론 시간이 수 초이므로 전체 지연은 추론 시간이 지배적임.
