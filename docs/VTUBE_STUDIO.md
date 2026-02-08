# VTube Studio 연동

채팅 → Groq 감정 → TTS 재생과 함께, **감정에 맞는 포즈**를 VTube Studio에 파라미터로 전달합니다.

## 1. 연결 방법

### 1) VTube Studio 실행

- **PC**: Steam에서 VTube Studio 실행 (또는 스마트폰 앱 + PC 스트리밍).
- **모델 로드**: 사용할 Live2D 모델을 로드해 두세요.

### 2) 플러그인 API 사용 허용

- VTube Studio 설정에서 **플러그인/외부 연동**이 켜져 있어야 합니다.
- 기본 포트: **8001** (로컬 WebSocket).

### 3) 우리 스크립트 실행

- `python examples/chzzk_groq_example.py` 등으로 실행.
- **최초 1회**: VTube Studio에 **플러그인 연결 요청** 창이 뜨면 **허용**을 누릅니다.
- 토큰이 `config/vts_token.txt`에 저장되며, 다음부터는 자동 인증됩니다.

### 4) 연결 실패 시

- VTube Studio가 **실행 중**인지 확인.
- 방화벽에서 **localhost:8001** 허용 여부 확인.
- 토큰 만료 시 `config/vts_token.txt`를 지우고 다시 실행한 뒤 VTS에서 허용.

---

## 2. 포즈 설정 (config/pose_mapping.json)

감정별로 **어떤 파라미터를 얼마로 보낼지** JSON으로 정의합니다.

### 파일 준비

```bash
copy config\pose_mapping.json.example config\pose_mapping.json
```

(또는 `pose_mapping.json.example` 내용을 복사해 `config/pose_mapping.json`으로 저장)

### 파라미터 이름 확인

- VTube Studio에서 **모델 설정** → **파라미터** 목록을 엽니다.
- 사용할 파라미터의 **정확한 이름**(예: `ParamBodyAngleZ`, `ParamAngleX`)을 확인합니다.
- `pose_mapping.json`의 **parameter_mapping**과 **emotions** 안의 키를, 이 이름에 맞게 수정합니다.

### 구조 요약

| 항목 | 설명 |
|------|------|
| **parameter_mapping** | 우리가 쓰는 짧은 이름 → VTS 실제 파라미터 이름. 모델에 없는 이름은 제거하거나 모델 이름으로 바꾸세요. |
| **emotions** | happy, sad, angry, surprised, neutral, excited 등 감정 키 → 그 감정일 때 쓸 파라미터 이름·값 딕셔너리. |
| **default** | 매칭되는 감정이 없을 때 쓸 감정. |

### 파라미터 값 범위 (참고)

모델마다 다를 수 있으며, 아래는 기본 예시 모델 기준입니다. VTS **모델 설정 → 파라미터**에서 min/max를 확인해 조정하세요.

| 구분 | 파라미터 예시 | 범위 |
|------|----------------|------|
| 얼굴 각도 | ParamAngleX, ParamAngleY, ParamAngleZ | -30 ~ 30 |
| 몸 회전 | ParamBodyAngleY, ParamBodyAngleZ | -10 ~ 10 |
| 다리 | ParamRightLeg, ParamLeftLeg | -30 ~ 30 |
| 눈 열림 | ParamEyeLOpen, ParamEyeROpen | -1 ~ 1 |
| 눈썹/눈 각도 | ParamBrowLY, ParamBrowRY, ParamBrowLAngle, ParamBrowRAngle | -1 ~ 1 |
| 입 벌림 | ParamMouthOpenY | 0 ~ 1 |
| 호흡 | ParamBreath | 0 ~ 1 |

---

## 3. 동작 흐름

1. 채팅 수신 → Groq에서 **답변 + 감정** 수신.
2. **VTS**: `set_emotion(emotion)` 호출 → `pose_mapping.json` 값을 **VTS 입력 파라미터**에 넣음(InjectParameterDataRequest).
3. **TTS**: 같은 답변을 음성으로 합성 후 저장·재생.

포즈는 감정이 정해지는 시점에 바로 적용되고, 그 다음 TTS가 재생됩니다.

---

## 4. 입력 파라미터로 보내기 (필수 설정)

VTS API는 **Live2D(출력) 파라미터에 직접 값을 넣지 않습니다.**  
값을 넣는 대상은 **입력(INPUT) 파라미터**뿐입니다.  
([공식 API](https://github.com/DenchiSoft/VTubeStudio) – "Feeding in data for default or custom parameters")

이 프로젝트는 다음처럼 동작합니다.

- **기본 입력**: FaceAngleX, FaceAngleY, FaceAngleZ, EyeOpenLeft, EyeOpenRight, MouthOpen, BrowLeftY, BrowRightY 에 값을 전송.
- **커스텀 입력**: AIsChocoBodyY, AIsChocoBodyZ, AIsChocoBreath, AIsChocoBrowLAngle, AIsChocoBrowRAngle, AIsChocoLegR, AIsChocoLegL 은 스크립트 연결 시 자동 생성 후 여기에 값을 전송.

따라서 **모델 설정에서 "입력 → Live2D(출력)" 매핑**을 해 줘야 포즈가 보입니다.

### 모델 설정에서 할 일

1. **VTS** → **모델 설정** 탭 → **VTS Parameter Setup**(파라미터 설정).
2. **INPUT**으로 아래 이름들을 선택하고, 각각 원하는 **OUTPUT(Live2D 파라미터)** 에 매핑합니다.

| 우리가 보내는 입력 (INPUT) | 예시 매핑 대상 (OUTPUT) |
|---------------------------|--------------------------|
| FaceAngleX, FaceAngleY, FaceAngleZ | ParamAngleX, ParamAngleY, ParamAngleZ |
| EyeOpenLeft, EyeOpenRight | ParamEyeLOpen, ParamEyeROpen |
| BrowLeftY, BrowRightY | ParamBrowLY, ParamBrowRY |
| AIsChocoBrowLAngle, AIsChocoBrowRAngle | ParamBrowLAngle, ParamBrowRAngle |
| MouthOpen | ParamMouthOpenY |
| AIsChocoBodyY, AIsChocoBodyZ | ParamBodyAngleY, ParamBodyAngleZ |
| AIsChocoBreath | ParamBreath |
| AIsChocoLegR, AIsChocoLegL | ParamRightLeg, ParamLeftLeg |

3. **플러그인 포즈만 쓰고 싶을 때**: 위 입력들은 우리 스크립트가 제어하므로, 해당 OUTPUT에는 **다른 입력(얼굴 트래킹 등)을 매핑하지 않으면** 됩니다.  
   **얼굴 트래킹과 같이 쓰고 싶을 때**: 같은 OUTPUT에 FaceAngleX와 트래킹을 둘 다 쓰면 안 되고, 포즈용 OUTPUT에는 위 입력만 매핑하고, 나머지 OUTPUT에는 트래킹만 매핑하는 식으로 나누면 됩니다.

연결 후 플러그인 설정 화면에 **사용자 지정 파라미터: 7**처럼 표시되면 커스텀 입력이 생성된 것입니다.

---

## 5. 포즈가 안 바뀔 때

- **입력 → 출력 매핑 확인**: 위 표대로 모델 설정에서 INPUT을 OUTPUT에 매핑했는지 확인하세요.
- **1초마다 재전송**: VTS는 "플러그인이 제어하는 파라미터는 **최소 1초에 한 번** 값을 보내야 한다"고 합니다. 감정이 바뀔 때만 보내면 1초 지나면 다시 트래킹 등으로 돌아갈 수 있으니, 포즈를 유지하려면 주기적으로 같은 값을 다시 보내는 방식이 필요할 수 있습니다.

공식 문서: [VTS Model Settings](https://github.com/DenchiSoft/VTubeStudio/wiki/VTS-Model-Settings), [Plugins / Custom Parameters](https://github.com/DenchiSoft/VTubeStudio/wiki/Plugins)
