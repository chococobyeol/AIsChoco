# Mac TTS API 서버 (Qwen3-TTS MLX)

Apple Silicon 맥에서 Qwen3-TTS(Voice Cloning)를 돌리고, aischoco가 **원격 TTS**로 호출할 수 있게 해주는 HTTP API 서버입니다.

- **규격**: `POST /synthesize` — Body `{"text": "문장", "emotion": "neutral"}` → 응답: WAV 바이너리
- **동작**: [qwen3-tts-apple-silicon](https://github.com/kapi2800/qwen3-tts-apple-silicon)과 동일한 MLX 모델·`mlx_audio` 사용 (Voice Cloning만 사용)

---

## 요구사항

- **macOS** (Apple Silicon M1/M2/M3/M4)
- **Python 3.10+**
- **ffmpeg**: `brew install ffmpeg`
- **모델**: Qwen3-TTS Base(Voice Cloning) MLX 8bit 모델이 `models/` 아래에 있어야 함 (아래 “모델 준비” 참고)
- **참조 음성**: `ref.wav` + `ref_text.txt` (aischoco의 `assets/voice_samples/` 와 동일한 파일 사용 권장)

---

## 1. 모델 다운로드 (필수, 최초 1회)

Voice Cloning용 **Base** 모델이 없으면 서버가 503을 반환합니다. 아래 중 한 가지 방법으로 받으세요.

### 방법 A: HuggingFace에서 직접 받기

1. 브라우저에서 열기:
   - **Pro (품질 좋음, 약 3GB)**: [mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit)
   - **Lite (가벼움, 약 1GB)**: [mlx-community/Qwen3-TTS-12Hz-0.6B-Base-8bit](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-0.6B-Base-8bit)
2. 페이지에서 **Files and versions** → **Clone repository** 옆 `↓` 또는 **Download** 로 전체 저장소 받기.
3. 압축 해제한 **폴더 이름**이 `Qwen3-TTS-12Hz-1.7B-Base-8bit` 또는 `Qwen3-TTS-12Hz-0.6B-Base-8bit` 인지 확인.
4. 이 서버 폴더 안에 `models` 디렉터리를 만들고, 그 안에 위 폴더를 넣기:

   ```bash
   cd mac_tts_server
   mkdir -p models
   # 다운로드한 폴더를 models/ 안으로 이동 (이름 그대로)
   # 결과: mac_tts_server/models/Qwen3-TTS-12Hz-1.7B-Base-8bit/ (또는 0.6B)
   ```

### 방법 B: Python 한 줄로 받기 (권장)

`huggingface_hub`만 설치돼 있으면 되고, `huggingface-cli`가 없어도 동작합니다. **mac_tts_server** 폴더에서 실행하세요.

**Lite (0.6B, 약 1GB):**
```bash
python -c "from huggingface_hub import snapshot_download; snapshot_download('mlx-community/Qwen3-TTS-12Hz-0.6B-Base-8bit', local_dir='models/Qwen3-TTS-12Hz-0.6B-Base-8bit')"
```

**Pro (1.7B, 약 3GB):**
```bash
python -c "from huggingface_hub import snapshot_download; snapshot_download('mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit', local_dir='models/Qwen3-TTS-12Hz-1.7B-Base-8bit')"
```

둘 다 받을 수도 있고, 하나만 써도 됩니다. 서버 기본값은 1.7B (`MODEL_FOLDER`). 0.6B만 쓸 경우 실행 전에 `export MODEL_FOLDER=Qwen3-TTS-12Hz-0.6B-Base-8bit` 로 지정하면 됩니다.

### 방법 C: huggingface-cli / hf (가능한 경우)

```bash
pip install "huggingface_hub[cli]"
hf download mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit --local-dir models/Qwen3-TTS-12Hz-1.7B-Base-8bit
# 또는 0.6B: --local-dir models/Qwen3-TTS-12Hz-0.6B-Base-8bit
```

### 최종 구조

```
mac_tts_server/
├── models/
│   └── Qwen3-TTS-12Hz-1.7B-Base-8bit/   # 또는 0.6B
│       └── (모델 파일들: config.json, *.safetensors 등)
├── refs/
│   ├── ref.wav
│   └── ref_text.txt
├── server.py
└── ...
```

**이미 [qwen3-tts-apple-silicon](https://github.com/kapi2800/qwen3-tts-apple-silicon)으로 모델을 받아 두었다면** 그 경로를 쓰면 됩니다:  
`export REF_MODEL_PATH=~/qwen3-tts-apple-silicon/models/Qwen3-TTS-12Hz-1.7B-Base-8bit`

---

## 2. 설치 및 ref 설정

```bash
cd mac_tts_server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

참조 음성은 아래 중 하나로 맞추면 됩니다.

- **방법 A (기본)**: 이 폴더 안에 `refs/` 만들고 `ref.wav`, `ref_text.txt` 넣기  
  → 환경 변수 없이 `python server.py` 만 실행하면 자동으로 `refs/` 를 참조합니다.
- **방법 B**: aischoco 쪽 `assets/voice_samples/` 경로를 쓰려면  
  → `REF_AUDIO_DIR=/path/to/aischoco/assets/voice_samples` 지정 후 실행

---

## 3. 환경 변수 (선택)

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `MODELS_DIR` | 모델이 들어 있는 디렉터리 | `./models` (현재 디렉터리 기준) |
| `MODEL_FOLDER` | 모델 폴더 이름 | `Qwen3-TTS-12Hz-1.7B-Base-8bit` |
| `REF_MODEL_PATH` | 모델 전체 경로 (지정 시 `MODELS_DIR` 무시) | (없음) |
| `REF_AUDIO_DIR` | `ref.wav` / `ref_text.txt` 가 있는 디렉터리 | `refs/` (server.py 기준) |
| `REF_AUDIO_PATH` | ref 음성 파일 경로 | (없음) |
| `REF_TEXT_PATH` | ref 원문 텍스트 파일 경로 | (없음) |
| `TTS_SERVER_HOST` | 서버 바인드 주소 | `0.0.0.0` |
| `TTS_SERVER_PORT` | 서버 포트 | `5000` |

---

## 4. 실행 방법

### 4-1. 같은 맥에서만 쓰기 (로컬)

```bash
source .venv/bin/activate
python server.py
```

(`refs/ref.wav`, `refs/ref_text.txt` 가 있으면 별도 설정 없이 사용됩니다.)

aischoco를 **같은 맥**에서 돌릴 때는 `.env`에:

```
TTS_REMOTE_URL=http://127.0.0.1:5001

---

### 4-2. 같은 Wi‑Fi(같은 네트워크)에서 다른 PC가 접속

서버를 **모든 인터페이스**에 바인드해 두었으므로(`0.0.0.0`) 그대로 실행하면 됩니다.

```bash
source .venv/bin/activate
python server.py
```

- 맥 IP 확인: **시스템 설정 → 네트워크** 또는 터미널에서 `ipconfig getifaddr en0` (Wi‑Fi)
- aischoco를 **다른 PC(Windows 등)**에서 돌릴 때 그 PC의 `.env`에:

```
TTS_REMOTE_URL=http://맥북IP:5001
```

예: `TTS_REMOTE_URL=http://192.168.0.10:5001`

---

### 4-3. 다른 네트워크(집 밖 등)에서 접속 — ngrok

1. [ngrok](https://ngrok.com) 가입 후 [Authtoken](https://dashboard.ngrok.com/get-started/your-authtoken) 발급.
2. 맥에 ngrok 설치: `brew install ngrok` (또는 공식 다운로드).
3. 토큰 설정: `ngrok config add-authtoken YOUR_TOKEN`
4. TTS 서버 실행 후 **다른 터미널**에서:

   ```bash
   ngrok http 5000
   ```

5. 화면에 나오는 **Forwarding** URL 복사 (예: `https://xxxx.ngrok-free.app`).
6. aischoco를 **어디서든** 돌리는 PC의 `.env`에:

   ```
   TTS_REMOTE_URL=https://xxxx.ngrok-free.app
   ```

   (끝에 `/` 없이, `https://` 포함)

ngrok을 끄면 URL이 바뀔 수 있으므로, 다시 켤 때마다 새 URL을 `.env`에 반영해야 합니다.

---

## 5. 동작 확인

- 서버 실행 후 브라우저 또는 curl:
  - `http://맥IP:5001/health` → `{"status":"ok", "model_path": "..."}` 이 나오면 준비된 것.
- aischoco 실행 시 로그에 `TTS 원격 API 사용: http://...` 가 보이면 원격 TTS로 연결된 것입니다.

---

## 6. 요약

| 사용처 | 맥에서 실행 | aischoco .env |
|--------|-------------|----------------|
| 같은 맥 | `python server.py` | `TTS_REMOTE_URL=http://127.0.0.1:5001` |
| 같은 Wi‑Fi 다른 PC | `python server.py` | `TTS_REMOTE_URL=http://맥IP:5001` |
| 다른 네트워크 | `python server.py` + `ngrok http 5001` | `TTS_REMOTE_URL=https://xxxx.ngrok-free.app` |
