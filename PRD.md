# [PRD] 치지직 연동 실시간 AI 버튜버 시스템 - aischoco

## 문서 정보
- **프로젝트명**: aischoco
- **버전**: 1.0.0
- **작성일**: 2026-02-06
- **최종 수정일**: 2026-02-06
- **문서 상태**: 최종안

---

## 1. 프로젝트 개요

### 1.1 프로젝트 목적
치지직 라이브 방송의 채팅을 실시간 분석하여, 고속 LLM(Groq)이 답변과 감정을 생성하고, 로컬 구동 TTS(Qwen3-TTS)와 캐릭터 제어 API(VTube Studio)를 통해 반응하는 지능형 버튜버 시스템을 구축합니다.

### 1.2 프로젝트 범위
- 치지직 Socket.IO API를 통한 실시간 채팅 수집
- Groq API를 활용한 고속 텍스트 생성 및 감정 분석
- 로컬 또는 원격 Qwen3-TTS를 통한 음성 합성 (원격 시 TTS_REMOTE_URL)
- VTube Studio API를 통한 실시간 캐릭터 제어
- 멀티모달 반응 시스템 (표정, 포즈, 립싱크)
- 방송 오버레이: OBS 브라우저 소스용 시청자 채팅 / AI 답변 표시 (클리어·방장 채팅 숨김 토글)

### 1.3 목표 사용자
- 치지직 스트리머
- AI 버튜버 운영자
- 실시간 인터랙티브 콘텐츠 제작자

---

## 2. 핵심 기능 (Core Features)

### 2.1 실시간 채팅 수집 및 분석
- **기능**: 치지직 Socket.IO API를 통해 지연 없는 채팅 데이터 수집
- **요구사항**:
  - 채팅 메시지 실시간 수신 (지연 < 100ms)
  - 사용자명, 메시지 내용, 이모티콘 파싱
  - 스팸/부적절 메시지 필터링 옵션
  - 채팅 히스토리 관리 (최근 N개 메시지 유지)

### 2.2 고속 AI 추론 엔진
- **기능**: Groq API(기본: openai/gpt-oss-120b, .env GROQ_MODEL로 변경 가능)를 사용하여 1초 미만의 응답 생성
- **요구사항**:
  - 응답 생성 시간: < 1초
  - 감정 분석 정확도: > 85%
  - 컨텍스트 이해 및 적절한 답변 생성
  - 감정/동작 파라미터 수치 자동 생성

### 2.3 로컬 음성 생성 시스템
- **기능**: Qwen3-TTS 모델을 로컬 GPU 환경에서 구동하여 저지연 고음질 음성 출력
- **요구사항**:
  - 첫 패킷 지연율(First-chunk Latency): < 100ms
  - 음성 품질: 자연스러운 한국어 발음
  - 음성 복제: 3초 샘플 기반 일관된 목소리
  - 실시간 스트리밍 출력 지원

### 2.4 멀티모달 캐릭터 반응
- **기능**: 답변 내용에 맞춘 표정, 포즈, 립싱크 동시 수행
- **요구사항**:
  - 감정별 표정 자동 전환
  - 자연스러운 신체 움직임 (보간 알고리즘 적용)
  - 오디오 기반 립싱크 동기화
  - 반응 지연: < 200ms

### 2.5 정밀 캐릭터 제어
- **기능**: VTube Studio API의 파라미터 주입 기능을 통한 부드러운 움직임 구현
- **요구사항**:
  - 실시간 파라미터 제어 (BodyAngleZ, AngleX 등)
  - 선형 보간(Lerp)을 통한 부드러운 전환 (0.1~0.5초)
  - 핫키 기반 표정 제어
  - API 연결 안정성 유지

---

## 3. 기술 스택 (Technical Stack)

### 3.1 개발 환경
| 구분 | 선택 기술 | 버전 | 비고 |
| --- | --- | --- | --- |
| **언어** | Python | 3.10+ | 시스템 통합 및 비동기 처리 |
| **프레임워크** | asyncio | - | 비동기 이벤트 처리 |
| **Socket.IO** | python-socketio | 4.x | 치지직 API 통신 (공식: Socket.IO 2.0.3 호환) |
| **HTTP 클라이언트** | httpx / aiohttp | latest | Groq API 통신 |

### 3.2 AI/ML 스택
| 구분 | 선택 기술 | 버전 | 비고 |
| --- | --- | --- | --- |
| **LLM** | Groq API | - | 기본 openai/gpt-oss-120b (.env GROQ_MODEL로 변경 가능) |
| **TTS** | Qwen3-TTS | 12Hz/1.7B | 로컬 GPU 구동 (0.6B 대체 가능) |
| **최적화** | FlashAttention | latest | TTS 추론 속도 향상 |
| **오디오 처리** | torchaudio | latest | 오디오 스트리밍 |

### 3.3 VTuber 제어
| 구분 | 선택 기술 | 버전 | 비고 |
| --- | --- | --- | --- |
| **VTS API** | pyvts | latest | VTube Studio API 래퍼 |
| **오디오 라우팅** | VB-Cable | - | Virtual Audio 장치 |

### 3.4 개발 도구
| 구분 | 선택 기술 | 비고 |
| --- | --- | --- |
| **의존성 관리** | requirements.txt | Python 패키지 관리 |
| **환경 변수** | .env | API 키 및 설정 관리 |
| **로깅** | logging | 시스템 로그 관리 |
| **설정 관리** | .env, config/character.txt, pose_mapping.json, vts_token.txt | config.yaml.example은 참고용 |

---

## 4. 상세 요구사항 (Detailed Requirements)

### 4.1 Qwen3-TTS 로컬 환경 구축

#### 4.1.1 모델 구성
- **기본 모델**: `Qwen3-TTS-12Hz-1.7B-Base`
- **대체 모델**: `Qwen3-TTS-12Hz-0.6B-Base` (GPU 메모리 부족 시)
- **모델 다운로드**: Hugging Face 또는 공식 저장소에서 자동/수동 다운로드
- **모델 경로 (로컬 TTS)**: Hugging Face 캐시 사용. `.env`의 `HF_HOME` 또는 프로젝트 `cache/huggingface`에 qwen-tts 패키지가 자동 다운로드. 수동 지정 시 해당 경로에 모델 배치.
- **원격 TTS**: `TTS_REMOTE_URL` 설정 시 Colab 또는 맥(Apple Silicon) TTS API 서버 사용 가능. 로컬 GPU 불필요. (mac_tts_server 참고)

#### 4.1.2 성능 최적화
- **FlashAttention 설치**: 추론 속도 극대화
- **첫 패킷 지연율**: < 100ms 목표 (97ms 달성)
- **GPU 메모리 관리**: 
  - 1.7B 모델: 최소 4GB VRAM
  - 0.6B 모델: 최소 2GB VRAM
- **배치 처리**: 실시간 스트리밍을 위한 배치 크기 최적화

#### 4.1.3 음성 복제 설정
- **샘플 요구사항**: 3초 분량의 캐릭터 원본 음성 샘플 (WAV/MP3)
- **샘플 경로**: `assets/voice_samples/` 디렉토리
- **음성 일관성**: 동일한 샘플 기반 일관된 목소리 출력
- **샘플 전처리**: 16kHz, 모노 채널로 변환

#### 4.1.4 한국어 지원
- **언어 설정**: 한국어 텍스트 입력 지원
- **발음 품질**: 자연스러운 한국어 발음 및 억양
- **사전 테스트**: 한국어 음성 품질 사전 검증 필수

### 4.2 캐릭터 애니메이션 제어

#### 4.2.1 감정 분석 (표현 제어 없음)
- **감정 타입**: 
  - happy (기쁨)
  - sad (슬픔)
  - angry (화남)
  - surprised (놀람)
  - neutral (중립)
  - excited (흥분)
- **용도**: Groq에서 수신된 `emotion` 값은 포즈 제어 로직의 입력으로만 사용
- **주의사항**: 모델에 감정 표현(표정) 기능이 없으므로, 감정은 포즈 파라미터 계산에만 활용

#### 4.2.2 포즈 제어 시스템
- **목적**: AI 응답의 감정과 내용에 맞춰 캐릭터의 포즈를 파라미터로 직접 제어
- **제어 방식**: VTS API의 `InjectParameterDataRequest`를 통한 실시간 파라미터 주입
- **현재 구현**: `src/vtuber/vts_client.py`에서 감정→파라미터 계산 및 VTS 전송을 통합. `config/pose_mapping.json`에 감정별 기본 포즈 값 정의. 별도 `pose_controller.py`/`parameter_controller.py` 파일은 없음.
- **입력 데이터**:
  - `emotion`: Groq에서 생성된 감정 타입 (string)
  - (선택) 응답 텍스트·타임스탬프 기반 미세 조정
- **주요 파라미터**: pose_mapping.json의 키를 VTS 입력 파라미터(MousePositionX/Y, AIsChocoBrowLAngle 등)에 매핑
- **포즈 계산 로직**:
  1. **감정 기반 기본 포즈**: pose_mapping.json에 따른 감정별 파라미터 값 (구현됨)
  2. **Idle 애니메이션**: 응답이 없을 때 자연스러운 미세 움직임 (구현됨: 예제의 idle_worker에서 마우스 좌우 이동·다리 주기 동작, 말하기 중에는 미동작)
  3. **랜덤 요소**: Idle 구간에서 주기·값에 랜덤 보정 적용 (구현됨)
- **설정 파일**: `config/pose_mapping.json`

#### 4.2.3 실시간 파라미터 제어
- **기능**: vts_client에서 계산된 파라미터 값을 VTS API로 전송
- **전송 방식**: WebSocket을 통한 `InjectParameterDataRequest`
- **값 범위**: -1.0 ~ 1.0 (VTS 표준)
- **에러 핸들링**: 파라미터 값 유효성 검증 및 범위 제한

#### 4.2.4 보간 알고리즘
- **알고리즘**: 선형 보간(Lerp)
- **보간 시간**: 0.1~0.5초 (파라미터별 조정 가능)
- **목적**: 순간 이동 방지 및 부드러운 움직임 구현
- **현재 구현**: 시선 복귀(`_animate_look_back_to_center`)에서만 스텝별 보간 적용. 감정/포즈 전환은 즉시 주입. 전역 Lerp(모든 파라미터 전환 시 0.1~0.5초 보간)는 미적용.

### 4.3 입모양(Lip-sync) 동기화

#### 4.3.1 오디오 라우팅
- **가상 오디오 장치**: VB-Cable 설치 및 설정
- **출력 장치**: Qwen3-TTS 오디오를 VB-Cable로 출력
- **VTS 연결**: VTube Studio의 오디오 입력을 VB-Cable로 설정
- **지연 최소화**: 오디오 버퍼 크기 최적화

#### 4.3.2 립싱크 파라미터
- **주요 파라미터**: `ParamMouthOpenY`
- **동기화 방식**: VTS 오디오 기반 자동 립싱크
- **지연 보정**: 오디오 지연 시간 측정 및 보정
- **품질**: 자연스러운 입 모양 움직임

### 4.4 치지직 API 연동

**⚠️ 중요**: 아래 내용은 예상 구조이며, 실제 치지직 공식 API 문서 확인 후 수정 필요

#### 4.4.1 Socket.IO 연결
- **연결 방식**: Socket.IO 프로토콜 (세션 URL은 REST API `/open/v1/sessions/auth` 등으로 획득, 공식 문서 참고)
- **인증**: OAuth 2.0 또는 API 토큰 (실제 인증 방식 확인 필요)
- **재연결 로직**: 연결 끊김 시 자동 재연결 (지수 백오프)
- **에러 핸들링**: 네트워크 오류 처리 및 로깅
- **참고 문서**: [치지직 개발자 문서](https://developers.chzzk.naver.com/) 확인 필수

#### 4.4.2 채팅 데이터 파싱
- **⚠️ 주의**: 아래 데이터 구조는 예시이며, 실제 API 응답 구조와 다를 수 있음
- **실제 구현 전 필수 확인 사항**:
  1. 치지직 공식 API 문서에서 채팅 메시지 데이터 구조 확인
  2. 실제 Socket.IO 메시지 포맷 및 필드명 검증
  3. 인증 토큰 발급 및 사용 방법 확인
  4. Rate Limiting 정책 확인
- **예상 데이터 구조** (실제 구조로 수정 필요):
  ```json
  {
    "user": "사용자명",
    "message": "채팅 내용",
    "timestamp": "2026-02-06T12:00:00Z",
    "emoticons": ["이모티콘1", "이모티콘2"]
  }
  ```
- **실제 구현 시 확인할 사항**:
  - 필드명이 실제 API와 일치하는지 (예: `user` vs `username` vs `nickname`)
  - 타임스탬프 형식 (ISO 8601, Unix timestamp 등)
  - 이모티콘/이미지 데이터 구조
  - 채널 ID, 메시지 ID 등 추가 필드 존재 여부
- **필터링**: 
  - 스팸 메시지 필터
  - 부적절 언어 필터 (옵션)
  - 최소 길이 제한
- **히스토리 관리**: 토큰 기반 슬라이딩 윈도우(기본 최근 5K 토큰, 7K 도달 시 요약, 8K 제한)로 컨텍스트 유지

### 4.5 Groq API 연동

#### 4.5.1 API 설정
- **엔드포인트**: Groq API 엔드포인트
- **모델**: 기본 openai/gpt-oss-120b (.env GROQ_MODEL로 변경 가능)
- **인증**: API 키 기반 인증
- **요청 제한**: Rate limiting 처리

#### 4.5.2 프롬프트 엔지니어링
- **시스템 프롬프트**: 캐릭터 성격 및 역할 정의
- **컨텍스트 관리**: **매 요청마다 이전 채팅 히스토리를 포함해야 맥락 이해 가능**
  - **중요**: Groq API는 stateless이므로, 이전 대화 내용을 자동으로 기억하지 않음
  - **히스토리 관리 전략: 토큰 기반 슬라이딩 윈도우 + 요약 (현재 구현)**
    - **구현 구조**:
      - 메모리: 최근 대화를 토큰 수로 관리 (기본 최대 5,000 토큰 유지)
      - 요약: 누적 토큰이 7,000 도달 시 오래된 분량 요약 후 `history/summary.json` 저장, `history/summaries/`에 타임스탬프 백업
      - 수동 백업: `history/backups/` (DO_BACKUP 등)
    - **참고: 아래 "동작 방식"은 메시지 개수 기반 설명이며, 실제 코드는 토큰 기반으로 동작함**
    - **기본 구조 (개념)**:
      - 메모리: 최근 N개 대화 (user + assistant 쌍) 유지
      - 파일: 요약된 이전 대화 히스토리 저장 (`history/summary.json`)
    - **동작 방식**:
      1. **1~10번째 대화**: 메모리의 최근 대화만 사용
      2. **11번째 대화 진입 시**:
         - 현재 메모리의 10개 대화를 Groq API로 요약
         - 요약 결과를 `history/summary.json`에 저장
         - 메모리에서 가장 오래된 1개 대화 제거 (9개 남음)
      3. **12번째 이후 대화**:
         - 요청 시: `요약 히스토리 + 메모리의 최근 10개 대화` 조합하여 사용
         - 11번째 대화마다: `이전 요약 + 메모리에서 가장 오래된 1개`를 합쳐서 새 요약 생성
         - 새 요약으로 파일 업데이트 후, 가장 오래된 1개 대화를 메모리에서 제거
    - **요약 생성 방법**:
      - **첫 요약 (11번째 대화 시)**:
        - 현재 메모리의 10개 대화를 Groq API로 요약
        - 프롬프트: "다음 대화 내용을 간결하게 요약해주세요. 중요한 맥락과 주제는 유지하세요."
      - **이후 요약 (22번째, 33번째... 대화 시)**:
        - 이전 요약 + 메모리에서 가장 오래된 1개 대화를 합쳐서 새 요약 생성
        - 프롬프트: "다음 이전 요약과 새로운 대화를 합쳐서 하나의 간결한 요약으로 만들어주세요."
        - 예시 구조:
          ```
          [이전 요약] 사용자가 게임에 대해 이야기하고 있었고...
          [새 대화] 사용자: "그 게임 재밌었어"
          [새 요약] 사용자가 게임에 대해 이야기하며 재미있었다고 언급...
          ```
      - 요약 결과는 JSON 형식으로 저장: `{"summary": "...", "timestamp": "...", "message_count": 10}`
    - **장점**:
      - 토큰 사용량 최적화 (항상 최근 10개 + 요약만 사용)
      - 긴 대화에서도 초반 맥락 유지 가능
      - 파일 기반 저장으로 재시작 후에도 히스토리 유지 가능
    - **단점 및 개선 방안**:
      - **문제점 1: 요약 품질 저하**
        - 요약을 거듭할수록 정보 손실 누적 (요약의 요약)
        - **개선안**: 요약을 여러 단계로 나누어 저장 (계층적 요약)
      - **문제점 2: 고정된 메시지 개수**
        - 메시지 길이와 무관하게 10개로 고정 → 토큰 사용 불균형
        - **개선안**: 토큰 수 기반으로 관리 (예: 최근 4,000 토큰 유지)
      - **문제점 3: 요약 비용/지연**
        - 매 11번째마다 Groq API 호출로 비용 및 지연 발생
        - **개선안**: 백그라운드에서 비동기 요약 또는 배치 요약
      - **문제점 4: 가장 오래된 1개만 합치는 비효율**
        - 중요한 정보가 여러 개에 분산되어 있을 수 있음
        - **개선안**: 여러 개를 묶어서 요약하거나, 중요도 기반 선택
  - **요청 구조 예시** (12번째 대화 이후):
    ```json
    {
      "model": "openai/gpt-oss-120b",
      "messages": [
        {"role": "system", "content": "당신은 친근한 AI 버튜버입니다..."},
        {"role": "system", "content": "[이전 대화 요약] 사용자가 게임에 대해 이야기하고 있었고..."},
        {"role": "user", "content": "메모리의 대화 1"},
        {"role": "assistant", "content": "메모리의 답변 1"},
        ...
        {"role": "user", "content": "메모리의 대화 10"},
        {"role": "assistant", "content": "메모리의 답변 10"},
        {"role": "user", "content": "현재 채팅 메시지"}
      ],
      "response_format": {"type": "json_object"}
    }
    ```
  - **토큰 제한 고려**: 
    - Groq 모델 컨텍스트 제한에 맞춰 최근 5K 토큰 유지, 7K 도달 시 요약 (8K 제한 전제)
    - 요약 히스토리 + 최근 대화가 토큰 제한 내에 들어가도록 조정
    - 요약 길이도 토큰 제한 내에서 관리
  - **개선된 히스토리 관리 전략 (권장)**:
    - **방법 1: 토큰 기반 슬라이딩 윈도우** (가장 권장)
      - 메시지 개수 대신 토큰 수로 관리 (예: 최근 4,000 토큰 유지)
      - 긴 메시지와 짧은 메시지를 균형있게 처리
      - 토큰 제한에 도달하면 가장 오래된 메시지부터 제거
      - 장점: 토큰 사용량 정확히 제어, 메시지 길이에 관계없이 효율적
    - **방법 2: 계층적 요약 (Hierarchical Summarization)**
      - 요약을 여러 단계로 나누어 저장 (예: 10개 → 50개 → 200개 단위)
      - 각 단계별로 별도 요약 파일 유지
      - 장점: 정보 손실 최소화, 더 긴 맥락 유지 가능
    - **방법 3: 하이브리드 접근**
      - 최근 대화: 상세히 유지 (예: 최근 5,000 토큰)
      - 중간 대화: 요약으로 유지 (예: 5,000~10,000 토큰 구간)
      - 오래된 대화: 더 압축된 요약으로 유지
      - 장점: 최근 맥락은 정확히, 오래된 맥락은 요약으로
    - **방법 4: 중요도 기반 선택** (고급)
      - 각 메시지에 중요도 점수 부여 (키워드, 감정 강도 등)
      - 중요도가 높은 메시지는 요약하지 않고 보존
      - 장점: 중요한 정보 손실 방지
  - **최종 권장 방식: 토큰 기반 슬라이딩 윈도우 + 간단한 요약**
    - **구현 방법**:
      1. 최근 대화를 토큰 수로 관리 (예: 최근 4,000 토큰 유지)
      2. 토큰 제한(예: 6,000 토큰)에 도달하면:
         - 가장 오래된 메시지들을 묶어서 요약 (예: 2,000 토큰 분량)
         - 요약 결과를 파일에 저장
         - 메모리에서 요약한 메시지들 제거
      3. 요청 시: 요약 + 최근 대화(4,000 토큰) 조합
    - **장점**:
      - 토큰 사용량 정확히 제어 (항상 일정한 토큰 수 유지)
      - 메시지 길이에 관계없이 효율적
      - 요약 빈도가 줄어서 비용/지연 감소
      - 구현이 상대적으로 간단
    - **구현 예시**:
      ```python
      class TokenBasedHistory:
          max_tokens: int = 4000  # 최근 대화 토큰 수
          summary_threshold: int = 6000  # 요약 시작 임계값
          
          def add_message(self, message: str):
              tokens = count_tokens(message)
              if self.current_tokens + tokens > self.summary_threshold:
                  # 오래된 메시지들을 요약
                  messages_to_summarize = self.get_oldest_messages(2000)  # 2000 토큰 분량
                  summary = self.create_summary(messages_to_summarize)
                  self.save_summary(summary)
                  self.remove_messages(messages_to_summarize)
              
              self.recent_messages.append(message)
              self.current_tokens += tokens
      ```
- **요청 구조 예시**:
  ```json
  {
    "model": "openai/gpt-oss-120b",
    "messages": [
      {"role": "system", "content": "당신은 친근한 AI 버튜버입니다..."},
      {"role": "user", "content": "이전 채팅 메시지 1"},
      {"role": "assistant", "content": "이전 답변 1"},
      {"role": "user", "content": "이전 채팅 메시지 2"},
      {"role": "assistant", "content": "이전 답변 2"},
      {"role": "user", "content": "현재 채팅 메시지"}
    ],
    "response_format": {"type": "json_object"}
  }
  ```
- **출력 형식**: JSON 형식으로 구조화된 응답
  ```json
  {
    "response": "답변 텍스트",
    "emotion": "happy"
  }
  ```
- **주의**: Groq 응답에는 파라미터 값이 포함되지 않음. 포즈 제어 모듈에서 감정과 응답 텍스트를 기반으로 파라미터를 계산

#### 4.5.3 성능 최적화
- **스트리밍**: 스트리밍 응답 지원 (옵션)
- **캐싱**: 자주 사용되는 응답 캐싱
- **타임아웃**: 5초 타임아웃 설정
- **재시도**: 실패 시 최대 3회 재시도

---

## 5. 시스템 아키텍처

### 5.1 전체 구조도
```
[치지직 Socket.IO]
    ↓
[채팅 수집 모듈] → [채팅 큐] ──────────────────→ [오버레이 상태] → [OBS 브라우저 소스]
    ↓
[Groq API 클라이언트] → [LLM 추론] → [응답 파싱]
    ↓                                    ↓
[응답 큐]                    [감정/응답] → [vts_client 포즈·아이들]
    ↓                                    ↓
[Qwen3-TTS (로컬/원격)]      [VTS API 파라미터 주입]
    ↓                                    ↓
[VB-Cable 오디오 출력]        [VTS 립싱크]
    ↓
[OBS 송출]
```

### 5.2 모듈 구조 (현재 구현 기준)
```
aischoco/
├── src/
│   ├── chat/
│   │   ├── chzzk_client.py      # 치지직 Socket.IO 클라이언트
│   │   ├── chat_parser.py       # 채팅 파싱 및 필터링
│   │   ├── base_client.py, client_factory.py
│   │   └── (chat_history는 ai/ 에 있음)
│   ├── ai/
│   │   ├── groq_client.py       # Groq API 클라이언트 (응답 파싱 포함)
│   │   ├── chat_history.py      # 채팅 히스토리 (토큰 기반 슬라이딩 윈도우 + 요약)
│   │   └── models.py            # 응답/감정 모델 정의
│   ├── tts/
│   │   └── tts_service.py       # Qwen3-TTS 연동 (로컬/원격 TTS_REMOTE_URL)
│   ├── vtuber/
│   │   └── vts_client.py        # VTS API 클라이언트 (감정→포즈 주입, set_leg_idle 등)
│   │       # 포즈 계산·전송 통합. Idle은 예제 idle_worker에서 마우스/다리 주기 동작.
│   │       # 전역 Lerp(모든 파라미터 보간) 미적용. 시선 복귀만 스텝 보간.
│   ├── overlay/
│   │   ├── state.py             # 시청자/AI 메시지, ignore_streamer_chat 등 공유 상태
│   │   └── server.py            # FastAPI (/, /api/state, /api/clear, /api/toggle_streamer_chat)
│   ├── core/                    # (메인 진입점은 examples/chzzk_groq_example.py)
│   └── utils/
│       └── chzzk_auth.py        # 치지직 인증
├── examples/                    # 실행 진입점
│   ├── chzzk_groq_example.py   # 전체 파이프라인 (채팅+Groq+TTS+VTS+오버레이+Idle)
│   ├── chzzk_auth_example.py, chzzk_chat_example.py
│   └── tts_*_example.py, colab_tts_server.py
├── mac_tts_server/             # 맥(Apple Silicon) TTS API 서버 (MLX, 원격 TTS 옵션)
├── assets/voice_samples/       # 음성 샘플 (ref.wav, ref_text.txt)
├── config/
│   ├── character.txt           # 캐릭터 성격 (Groq 시스템 프롬프트 보강)
│   ├── pose_mapping.json       # 감정-포즈 매핑
│   └── vts_token.txt           # VTS 연결 토큰 (자동 저장)
├── history/
│   ├── summary.json            # 요약 히스토리
│   ├── summaries/              # 요약 타임스탬프 백업
│   └── backups/                # 수동 백업
├── requirements.txt
├── README.md
└── PRD.md
```
로컬 TTS 모델은 Hugging Face 캐시(기본 `cache/huggingface` 또는 HF_HOME)에 저장됨.

### 5.3 데이터 흐름
1. **채팅 수집**: 치지직 Socket.IO → 채팅 파서 → (예제에서 큐/배치 처리). 시청자 메시지는 overlay_state에 즉시 추가(오버레이 표시). ignore_streamer_chat 시 방장(user_id==channel_id) 메시지는 제외.
2. **AI 처리**:
   - 말하기 시점에 큐에서 꺼낸 메시지들 → 채팅 히스토리에 user 추가
   - **토큰 임계치(7K) 도달 시**: 오래된 분량 요약 후 summary.json 및 history/summaries/에 저장, 메모리에서 제거
   - groq_client가 요약 히스토리 + 최근 대화(토큰 기준) + 새 메시지로 Groq API 요청
   - JSON 파싱 후 응답·감정 반환, 채팅 히스토리에 assistant 메시지 추가, overlay_state에 assistant_messages 추가
3. **음성 생성**: 응답 → Qwen3-TTS(로컬 또는 TTS_REMOTE_URL) → 오디오 → VB-Cable
4. **캐릭터 제어**: 감정 → vts_client(pose_mapping.json) → VTS API 파라미터 주입. 말하기 전 시선 연출, 말하는 중 시선 복귀(스텝 보간). Idle은 idle_worker에서 마우스/다리 주기 동작.
5. **동기화**: 오디오 스트림 → VTS 립싱크
6. **방송 오버레이**: overlay 서버가 /api/state로 시청자·AI 메시지 제공. OBS 브라우저 소스에서 표시. 10분 경과 메시지 페이드아웃, 클리어·방장 숨김 토글 지원.

---

## 6. 데이터 모델

### 6.1 채팅 메시지
```python
@dataclass
class ChatMessage:
    user: str              # 사용자명
    message: str           # 메시지 내용
    timestamp: datetime    # 타임스탬프
    emoticons: List[str]   # 이모티콘 리스트
    channel_id: str        # 채널 ID
    # 구현 확장: message_id, user_id, user_badge (방장 판별: user_id == channel_id)
```

### 6.2 AI 응답
```python
@dataclass
class AIResponse:
    response: str          # 답변 텍스트
    emotion: str           # 감정 타입 (포즈 계산용)
    confidence: float     # 신뢰도 (0.0 ~ 1.0)
    processing_time: float # 처리 시간 (초)
```

### 6.2.1 채팅 히스토리 관리
실제 구현은 **토큰 기반** 슬라이딩 윈도우(예: 7K 토큰 임계치)와 요약으로 오래된 분량을 정리함.
```python
@dataclass
class ChatHistory:
    # 메모리: 토큰 기준 최근 대화 유지
    recent_messages: List[Dict[str, str]]  # [{"role": "user", "content": "..."}, ...]
    max_recent_count: int = 10             # 참고용; 실제는 토큰 수로 제한
    
    # 파일: 요약 히스토리
    summary_file: str = "history/summary.json"
    summary_content: str = ""               # 현재 요약 내용
    
    def add_user_message(self, content: str)
    def add_assistant_message(self, content: str)
    
    def get_context_messages(self) -> List[Dict]:
        """요약 히스토리 + 최근 대화를 조합하여 반환"""
        messages = []
        if self.summary_content:
            messages.append({
                "role": "system",
                "content": f"[이전 대화 요약] {self.summary_content}"
            })
        messages.extend(self.recent_messages)
        return messages
    
    def should_summarize(self) -> bool:
        """11번째 대화인지 확인 (user+assistant 쌍 기준)"""
        return len(self.recent_messages) >= self.max_recent_count * 2
    
    def create_summary(self, groq_client) -> str:
        """현재 10개 대화를 요약하여 반환 (첫 요약)"""
        # Groq API로 요약 요청
        # messages: 현재 10개 대화
        pass
    
    def update_summary(self, groq_client):
        """요약 히스토리 업데이트 (이전 요약 + 가장 오래된 1개 합쳐서 새 요약)"""
        # 이전 요약 + 메모리에서 가장 오래된 1개 대화를 합쳐서 새 요약 생성
        # messages: [이전 요약, 가장 오래된 1개 대화]
        # 새 요약으로 파일 업데이트
        pass
    
    def save_summary(self, summary: str):
        """요약을 파일에 저장"""
        pass
    
    def load_summary(self):
        """파일에서 요약 로드"""
        pass
```

### 6.3 포즈 계산 결과
```python
@dataclass
class PoseCalculation:
    emotion: str                    # 입력 감정
    parameters: Dict[str, float]    # 계산된 파라미터 값
    interpolation_time: float       # 보간 시간 (초)
    timestamp: datetime              # 계산 시점
```

### 6.4 캐릭터 파라미터
```python
@dataclass
class CharacterParameters:
    body_angle_z: float   # -1.0 ~ 1.0
    angle_x: float        # -1.0 ~ 1.0
    angle_y: float        # -1.0 ~ 1.0
    eye_open_left: float  # 0.0 ~ 1.0
    eye_open_right: float # 0.0 ~ 1.0
    mouth_open_y: float   # 0.0 ~ 1.0
    # ... 기타 파라미터
```

---

## 7. API 명세

### 7.1 VTube Studio API
- **연결**: WebSocket (ws://localhost:8001)
- **인증**: 토큰 기반 (최초 연결 시 플러그인 허용 필요)
- **주요 엔드포인트**:
  - `TriggerHotkeyRequest`: 핫키 실행 (표정 변경)
  - `InjectParameterDataRequest`: 파라미터 주입
  - `GetCurrentModelRequest`: 현재 모델 정보

### 7.2 Groq API
- **엔드포인트**: `https://api.groq.com/openai/v1/chat/completions`
- **인증**: Bearer Token
- **요청 형식**: OpenAI 호환 형식
- **모델**: 기본 `openai/gpt-oss-120b` (.env GROQ_MODEL로 변경 가능)

### 7.3 치지직 API
- **⚠️ 중요**: 실제 API 스펙은 공식 문서 확인 필수
- **공식 문서**: [치지직 개발자 문서](https://developers.chzzk.naver.com/)
- **Socket.IO**: 치지직은 Socket.IO 사용 (세션 URL은 REST API로 획득, [chzzk API 문서](https://chzzk.gitbook.io/chzzk/chzzk-api/session) 참고)
- **인증**: OAuth 2.0 또는 API 토큰 (실제 인증 방식 확인 필요)
- **이벤트 타입**: 채팅 메시지, 구독, 후원 등 (실제 지원 이벤트 확인 필요)
- **구현 전 체크리스트**:
  - [ ] API 엔드포인트 URL 확인
  - [ ] 인증 토큰 발급 방법 확인
  - [ ] 채팅 메시지 데이터 구조 확인
  - [ ] Rate Limiting 정책 확인
  - [ ] 에러 응답 형식 확인

---

## 8. 성능 요구사항

### 8.1 지연 시간 (Latency)
- **채팅 수집**: < 100ms
- **AI 응답 생성**: < 1000ms (1초)
- **TTS 첫 패킷**: < 100ms
- **캐릭터 반응**: < 200ms
- **전체 파이프라인**: < 2초

### 8.2 처리량 (Throughput)
- **동시 채팅 처리**: 최대 10개/초
- **응답 생성**: 최대 5개/초
- **오디오 스트리밍**: 실시간 (44.1kHz)

### 8.3 리소스 사용량
- **CPU**: 중간 수준 (멀티코어 활용)
- **GPU**: 
  - 1.7B 모델: 최소 4GB VRAM
  - 0.6B 모델: 최소 2GB VRAM
- **RAM**: 최소 8GB (16GB 권장)
- **디스크**: 모델 저장용 5GB 이상

---

## 9. 보안 요구사항

### 9.1 API 키 관리
- **환경 변수**: `.env` 파일에 저장 (Git 제외)
- **암호화**: 민감 정보 암호화 저장 (옵션)
- **접근 제어**: 설정 파일 읽기 전용 권한

### 9.2 네트워크 보안
- **HTTPS**: 외부 API 통신 시 HTTPS 사용
- **로컬 연결**: VTS API는 로컬호스트만 허용
- **방화벽**: 불필요한 포트 차단

### 9.3 데이터 보안
- **채팅 로그**: 개인정보 보호를 위한 로그 관리
- **음성 샘플**: 저작권 보호 및 개인정보 관리
- **설정 파일**: 민감 정보 제외

---

## 10. 사용자 스토리 (User Stories)

### US-1: 실시간 채팅 반응
**As a** 스트리머  
**I want to** 채팅에 실시간으로 반응하는 AI 버튜버  
**So that** 시청자와 자연스러운 대화를 할 수 있다

**Acceptance Criteria**:
- 채팅 메시지 수신 후 2초 이내 응답
- 자연스러운 답변 생성
- 적절한 감정 표현

### US-2: 음성 출력
**As a** 스트리머  
**I want to** AI가 생성한 답변을 음성으로 출력  
**So that** 시청자가 들을 수 있다

**Acceptance Criteria**:
- 자연스러운 한국어 발음
- 일관된 목소리 톤
- 저지연 음성 출력 (< 100ms)

### US-3: 캐릭터 애니메이션
**As a** 스트리머  
**I want to** 답변에 맞는 표정과 동작  
**So that** 더 생동감 있는 버튜버를 제공할 수 있다

**Acceptance Criteria**:
- 감정과 응답에 맞는 포즈 자동 계산
- 부드러운 움직임 (보간 적용)
- 립싱크 동기화

### US-4: 설정 관리
**As a** 개발자/운영자  
**I want to** 쉽게 설정을 변경할 수 있다  
**So that** 다양한 상황에 맞춰 조정할 수 있다

**Acceptance Criteria**:
- YAML/JSON 설정 파일 지원
- 환경 변수 지원
- 런타임 설정 변경 (옵션)

---

## 11. 제약 및 주의사항

### 11.1 기술적 제약
- **GPU 메모리**: 로컬 TTS 구동 시 VRAM 점유율 고려 필요
- **모델 크기**: GPU 사양에 따라 1.7B 또는 0.6B 모델 선택
- **네트워크**: 안정적인 인터넷 연결 필요 (Groq API)
- **플랫폼**: Windows 환경 최적화 (VB-Cable)

### 11.2 운영 제약
- **VTS 연결**: 최초 연결 시 '플러그인 허용' 수동 승인 필수
- **API 제한**: Groq API Rate Limiting 고려
- **언어 지원**: Qwen3-TTS 한국어 지원 여부 사전 테스트 필요
- **라이선스**: 각 라이브러리 및 모델의 라이선스 확인

### 11.3 성능 제약
- **동시 처리**: 다수의 채팅 동시 수신 시 큐 관리 필요
- **메모리 누수**: 장시간 운영 시 메모리 관리 중요
- **CPU/GPU 부하**: 다른 애플리케이션과의 리소스 경쟁 고려

---

## 12. 개발 일정 (예상)

### Phase 1: 기반 구축 (2주)
- 프로젝트 구조 설정
- 치지직 Socket.IO 클라이언트 개발
- 기본 설정 시스템 구축

### Phase 2: AI 연동 (2주)
- Groq API 클라이언트 개발
- 프롬프트 엔지니어링
- 응답 파싱 시스템

### Phase 3: TTS 구축 (2주)
- Qwen3-TTS 로컬 환경 구축
- 음성 복제 시스템
- 오디오 스트리밍 구현

### Phase 4: VTS 연동 (2주)
- VTS API 클라이언트 개발
- 포즈 제어 모듈 개발 (별도 구현)
- 파라미터 계산 로직 구현
- 파라미터 제어 및 보간

### Phase 5: 통합 및 최적화 (2주)
- 전체 파이프라인 통합
- 성능 최적화
- 에러 핸들링 및 로깅

### Phase 6: 테스트 및 배포 (1주)
- 통합 테스트
- 문서화
- 배포 준비

**총 예상 기간**: 11주 (약 3개월)

---

## 13. 테스트 계획

### 13.1 단위 테스트
- 각 모듈별 단위 테스트 작성
- 테스트 커버리지: > 70%
- 주요 테스트 대상:
  - 채팅 파싱
  - 응답 파싱
  - 파라미터 보간
  - 오디오 처리

### 13.2 통합 테스트
- 모듈 간 통합 테스트
- API 연동 테스트
- 전체 파이프라인 테스트

### 13.3 성능 테스트
- 지연 시간 측정
- 처리량 테스트
- 리소스 사용량 모니터링
- 장시간 운영 테스트 (스트레스 테스트)

### 13.4 사용자 테스트
- 실제 스트리밍 환경 테스트
- 사용자 피드백 수집
- 버그 수정 및 개선

---

## 14. 배포 및 운영

### 14.1 배포 환경
- **OS**: Windows 10/11
- **Python**: 3.10 이상
- **GPU**: NVIDIA GPU (CUDA 지원)
- **의존성**: requirements.txt 기반 설치

### 14.2 설치 절차
1. Python 환경 설정
2. 의존성 패키지 설치
3. Qwen3-TTS 모델 다운로드
4. VB-Cable 설치 및 설정
5. 환경 변수 설정 (.env)
6. VTS 플러그인 연결 설정

### 14.3 운영 모니터링
- 로그 파일 관리
- 에러 알림 시스템 (옵션)
- 성능 메트릭 수집
- 리소스 사용량 모니터링

### 14.4 유지보수
- 정기적인 의존성 업데이트
- 모델 업데이트 (필요 시)
- 버그 수정 및 기능 개선
- 사용자 피드백 반영

---

## 15. 향후 개선 사항 (Future Enhancements)

### 15.1 기능 개선
- 다중 언어 지원 확대
- 커스텀 감정 추가
- 더 많은 캐릭터 파라미터 제어
- 음성 스타일 변환 (속도, 톤 등)

### 15.2 성능 개선
- 모델 최적화 (양자화, 프루닝)
- 캐싱 시스템 고도화
- 병렬 처리 최적화

### 15.3 사용자 경험
- GUI 설정 도구
- 실시간 모니터링 대시보드
- 자동 설정 최적화

---

## 16. 참고 자료

### 16.1 공식 문서
- [Groq API Documentation](https://console.groq.com/docs)
- [VTube Studio API Documentation](https://github.com/DenchiSoft/VTubeStudio)
- [Qwen3-TTS Documentation](https://github.com/QwenLM/Qwen3-TTS)
- [치지직 API Documentation](https://developers.chzzk.naver.com/) ⚠️ **실제 API 구조 확인 필수**

### 16.2 관련 라이브러리
- pyvts: VTube Studio Python 라이브러리
- python-socketio: 치지직 Socket.IO 클라이언트 (치지직 API 통신)
- websockets: Python WebSocket 라이브러리 (VTube Studio 등)
- torch: PyTorch (TTS 모델용)

---

## 부록 A: 용어 정의

- **버튜버**: 가상 유튜버/스트리머
- **립싱크**: 음성에 맞춘 입 모양 동기화
- **보간(Interpolation)**: 두 값 사이를 부드럽게 전환하는 기법
- **First-chunk Latency**: 첫 오디오 패킷 생성까지의 지연 시간
- **VRAM**: 비디오 랜덤 액세스 메모리 (GPU 메모리)

---

## 부록 B: 변경 이력

| 버전 | 날짜 | 변경 내용 | 작성자 |
| --- | --- | --- | --- |
| 1.0.0 | 2026-02-06 | 초안 작성 | - |

---

**문서 끝**

