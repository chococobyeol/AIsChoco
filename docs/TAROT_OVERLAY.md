# 타로 오버레이 구현 정리

AI가 타로 점괘를 조작하고, 결과를 웹 오버레이로 실시간 표시하기 위한 설계·구현 가이드.

---

## 1. 개요

- **목적**: **AI(Groq 응답)**가 상황을 보고 타로를 호출할 때 오버레이에 카드 + 해석 + 시각화를 띄운다. 키워드로 무조건 타로를 켜지 않고, AI가 "지금 운세 볼 상황이다"라고 판단한 경우에만 진행한다. 순서: AI가 먼저 "뭐에 대해 보고 싶어요?"라고 묻고, 시청자가 주제를 말한 뒤 1~78번 카드 선택 → 해석.
- **위치**: 기존 오버레이 서버(`src/overlay/`)에 **타로 전용 상태**와 **`/tarot` 페이지**를 추가. OBS 브라우저 소스로 `http://127.0.0.1:8765/tarot` 사용.

---

## 2. 데이터 흐름

타로는 **Groq API 응답**으로만 시작한다. AI가 채팅 맥락을 보고 타로를 진행할 때 `action: "tarot_ask_question"` 또는 `action: "tarot"`를 반환하고, **먼저 뭐에 대해 볼지 묻는 것**이 기본 순서다.

```
[시청자] "타로 봐줘" 등
    → [Groq] 상황 판단 후 action "tarot_ask_question" + response "뭐에 대해 보고 싶어요?"
    → [백엔드] overlay_state["tarot"] = { phase: "asking_question", requester_id }
[시청자] "내일 면접" 등 주제 답장
    → [백엔드] 질문 확정, 78장 셔플, phase: "selecting", 덱 표시
    → [오버레이] "1~78번 중 번호로 골라주세요" 안내
[시청자] 채팅으로 번호 선택 (예: "23번" 또는 "7번, 23번, 45번")
    → [백엔드] 선택한 번호에 해당하는 카드만 앞면으로 공개, 해당 카드 id 목록을 Groq에 전달
    → [Groq] 전달받은 카드만으로 해석 + visual_data(JSON) 생성
    → [overlay_state["tarot"]] 갱신 → [/tarot 페이지] 앞면 카드 이미지 + 해석 + 시각화 렌더
```

- 타로 전용 응답은 **기존 채팅 응답과 별도**로, `overlay_state["tarot"]`를 두 단계(선택 대기 / 공개·해석)에 맞게 갱신하고, `/tarot` 페이지는 이 상태만 보고 그린다.

---

## 3. 타로 진행 흐름 (시청자 카드 선택)

시청자가 **직접 뽑는 느낌**을 주기 위해, 78장 전체를 한 덱(뭉탱이)으로 두고 **1~78번** 중 번호로만 선택하게 한 뒤, 선택한 카드만 공개한다.

### 3.1 1단계: 덱 표시 및 번호 선택

- 타로 요청이 들어오면 **78장 전체**를 한 덱으로 두고, 백엔드가 78장을 셔플해 **1~78번**에 각각 카드 id와 정/역을 배정해 둔다. (선택지는 시청자, 카드 구성은 시스템.)
- 오버레이에는 덱(뭉탱이) 이미지 하나 또는 "1~78번 중 번호로 골라주세요" 문구를 띄운다.
- AI 또는 고정 멘트로 "몇 번 카드를 뽑을까요?" 또는 스프레드에 따라 "3장 뽑아주세요. 1~78 중 번호로 말해주세요" 등 안내.

**필요 리소스**

- **카드 뒷면/덱 이미지 1종**: 덱 전체를 나타낼 이미지. 예: `assets/tarot/tarot_back.png`. 없으면 추가하거나 기존 이미지 중 하나 사용.

### 3.2 여러 장 뽑기 (스프레드)

- **1장만**: "1~78 중 한 번호만 골라주세요" → 시청자 "23번".
- **3장 (과거·현재·미래 등)**: "1~78 중 번호 3개 골라주세요" → 시청자 "7번, 23번, 45번"처럼 채팅으로 선택. (같은 번호 중복 허용 여부는 구현 시 결정.)
- 스프레드 종류(몇 장 뽑을지)는 프롬프트·규칙으로 정하거나, 질문에 따라 AI가 "이번엔 3장 뽑아주세요"처럼 멘트로 지정하게 할 수 있다.

### 3.3 2단계: 선택한 카드만 공개 후 해석

- 시청자가 채팅으로 번호를 보내면(예: "23번" 또는 "7번, 23번, 45번"), 해당 번호에 매핑된 카드 id(+ reversed)만 앞면 이미지로 오버레이에 표시한다.
- 이 카드 목록을 Groq에 넘겨 "이 카드들로 질문에 대해 해석하고 visual_data를 생성해라"고 요청한다.
- Groq 응답(해석문 + visual_data)으로 `overlay_state["tarot"]`를 갱신하면, 오버레이에 해석문 + 시각화가 함께 나온다.
- Groq가 타임아웃·에러로 해석을 반환하지 못하면 재시도하거나, "이번에는 해석을 불러오지 못했어요" 멘트 후 타로 상태 초기화해 일반 채팅으로 복귀.

**요약**: 뒷면 번호로 선택 → 선택한 번호만 앞면 공개 → 공개된 카드만으로 AI 해석. 해석문이 핵심이고, 시각화(레이더·게이지 등)는 보조.

### 3.4 타임아웃 및 시청자 일치

**응답 타임아웃**

- 선택 단계(phase `"selecting"`)에서 시청자가 번호를 고르지 않고 떠나거나 조용히 있으면 방송이 그대로 멈춰 있을 수 있다.
- **일정 시간(예: 5분~10분) 내에 유효한 번호 채팅이 없으면** 타로를 취소하고 `overlay_state["tarot"]`를 초기화(또는 `visible: false`)한다. 필요하면 "시간이 지나서 이번 타로는 마무리할게요" 멘트 후 일반 채팅 흐름으로 복귀.
- 타임아웃 값은 설정(예: `.env` 또는 config)으로 두고 5분·10분 등에서 선택 가능하게 하면 좋다.

**당일 타로 비활성화**

- 타로 방송을 하지 않을 날에는 `.env`에 `TAROT_ENABLED=0` 또는 `TAROT_ENABLED=false` 로 두면 된다. 이때 시청자가 "타로 봐줘"라고 해도 AI가 거절만 하고 타로 플로우는 시작되지 않는다.

**시청자(요청자) 일치**

- 타로를 **요청한 시청자**와 **번호를 채팅으로 보낸 시청자**가 같아야만 선택으로 인정한다.
- 치지직 채팅에서 user_id(또는 고유 식별자)·닉네임을 함께 저장해 두고, 타로 요청 시점에 "이번 타로 요청자 = user_id/닉네임"을 기록. 선택 단계에서 들어오는 채팅이 **같은 user_id/닉네임**에서 온 번호일 때만 파싱·적용.
- 다른 시청자가 "23번"이라고 먼저 쳐도 무시하고, 요청자만의 메시지를 기다린다. (필요하면 오버레이에 "OO님, 1~78 중 번호로 골라주세요"처럼 요청자 닉네임을 노출해 혼선을 줄인다.)

**한 번에 한 타로**

- 이미 선택 단계 또는 공개·해석 표시 중인 타로가 있으면, 다른 시청자의 새 타로 요청은 무시하거나 "지금은 OO님 타로 진행 중이에요" 안내. 해당 타로가 타임아웃·완료·클리어된 뒤에만 새 타로 요청을 받는다.

**잘못된 번호**

- 시청자가 "0번", "79번", "백번" 등 1~78 범위 밖이나 비숫자를 보내면 해당 메시지는 무시하고, 요청자에게만 "1부터 78 사이 번호로 골라주세요" 등으로 다시 안내.

---

## 4. overlay_state 확장 (tarot 상태)

`src/overlay/state.py`의 `overlay_state`에 다음 키를 추가한다.

| 키 | 타입 | 설명 |
|----|------|------|
| `tarot` | `dict \| None` | `None`이면 타로 미표시. 있으면 아래 구조. |

**`tarot` 객체 구조**

| 필드 | 타입 | 설명 |
|------|------|------|
| `visible` | bool | 타로 오버레이 표시 여부 |
| `phase` | str | `"asking_question"` (뭐에 대해 볼지 대기) \| `"selecting"` (번호 대기) \| `"revealed"` (공개·해석 완료) |
| `requester_id` | str (선택) | 타로를 요청한 시청자 식별자 (user_id 등). 선택 단계에서 이 사람의 채팅만 번호로 인정 |
| `select_deadline_ts` | float (선택) | 선택 마감 시각 (Unix timestamp). 이 시각까지 번호가 없으면 타임아웃 처리 |
| `question` | str | 시청자 질문 (선택) |
| `cards` | list | `[{ "id": str, "reversed": bool }, ...]` — 카드 id는 파일명과 일치 (예: `wheel_of_fortune`) |
| `interpretation` | str | AI 해석 전문 |
| `visual_data` | dict | 시각화용 데이터. 아래 `visual_type`에 따라 구조 상이 |
| `soul_color` | str (선택) | 분위기 색. 예: `gold`, `purple`, `black` — 오버레이 테두리/배경 톤 |
| `danger_alert` | bool (선택) | Death/Tower 등일 때 true → 경고 비네팅/문구 |

**카드 id 규칙**

- 파일명이 `tarot_fool.png` → id는 `fool`
- 파일명이 `tarot_wheel_of_fortune.png` → id는 `wheel_of_fortune`
- 역방은 `reversed: true` → `/tarot-assets/reverse/tarot_<id>_r.png` 로 매핑

**선택 대기 단계**

- 시청자가 번호를 고르기 전에는 `tarot`에 `phase: "selecting"`(또는 동일 목적 필드)와 **1~78 번호→카드 매핑**을 넣어 두고, 오버레이에서는 덱(뭉탱이) 이미지와 "1~78번 중 선택" 안내를 그린다. 시청자 선택 후 공개·해석 단계로 넘어가면 `phase: "revealed"`(또는 해석문·cards 확정)로 바꾸고, 앞면 + 해석 + 시각화를 그린다. (매핑 구조는 구현 시 정의.)

---

## 5. 시각화 유형 (visual_type) 및 JSON 구조

LLM은 해석과 함께 **하나의** `visual_data` 객체를 출력한다. `visual_type`으로 어떤 UI를 쓸지 결정하고, 나머지 필드는 타입별로 채운다.

---

### 5.1 radar_fixed — 고정 5각 레이더 (종합 운세)

**용도**: "오늘의 운세 봐줘"처럼 질문이 일반적일 때.

```json
{
  "visual_type": "radar_fixed",
  "labels": ["애정", "금전", "사업/학업", "건강", "행운"],
  "scores": [80, 40, 60, 90, 50]
}
```

- `labels`는 고정 5개, 순서 통일.
- 프론트: 5각 방사형 차트(Chart.js 등), 점수에 따라 영역 애니메이션.

---

### 5.2 radar_dynamic — 가변 3축 (질문 맞춤)

**용도**: "내일 떡볶이 먹어도 될까?"처럼 **질문에 맞는 기준**을 AI가 정할 때.

```json
{
  "visual_type": "radar_dynamic",
  "labels": ["만족도", "칼로리 위험도", "소화 가능성"],
  "scores": [95, 85, 40]
}
```

- 라벨 개수는 3개 권장(그래프 가독성). 라벨 이름은 질문 맥락에 따라 AI가 자유로이 생성.
- 프론트: 3각 레이더 또는 바 차트, 라벨 텍스트 실시간 표시.

---

### 5.3 yes_no — 찬성/반대 게이지

**용도**: "해도 될까?", "갈까?" 등 Yes/No·Go/Stop 질문.

```json
{
  "visual_type": "yes_no",
  "recommendation": "YES",
  "score": 75
}
```

- `recommendation`: `"YES"` | `"NO"` (또는 `"GO"` / `"STOP"` 등 통일 규칙).
- `score`: 0~100. Yes 방향이면 50~100, No 방향이면 0~50으로 해석 가능.
- 프론트: 좌(No)~우(Yes) 그라데이션 바, 눈금이 `score` 위치로 이동 + "타로의 결론: YES 75%" 문구.

---

### 5.4 keywords — 키워드 태그 3개

**용도**: 수치보다 **분위기/핵심어** 전달. 모든 질문 유형에 보조로 사용 가능.

```json
{
  "visual_type": "keywords",
  "keywords": ["#스트레스해소", "#매운맛경보", "#행복한_지출"]
}
```

- AI가 해석문에서 핵심 단어 3개 추출.
- 프론트: 해석문 옆 또는 카드 아래 태그/말풍선 형태로 표시.

---

### 5.5 candidates — 후보 + 매칭 점수 (선택 질문)

**용도**: "내일 점심 뭐 먹지?"처럼 **선택지가 열린** 질문.

```json
{
  "visual_type": "candidates",
  "candidates": [
    { "label": "제육볶음", "score": 88, "reason": "태양 카드와 잘 맞아요" },
    { "label": "초밥", "score": 72 },
    { "label": "샐러드", "score": 45 }
  ],
  "recommended_index": 0
}
```

- `recommended_index`: 슬롯/룰렛에서 최종으로 멈출 인덱스.
- 프론트: 룰렛 또는 슬롯 연출 후 `candidates[recommended_index]` 강조, 각 후보 옆에 점수(선택적으로 reason) 표시.

---

### 5.6 decision_map — 운명의 좌표 (2축 맵)

**용도**: "무엇을 할까?"에 대해 **선택의 성격**을 2축으로 제시할 때.

```json
{
  "visual_type": "decision_map",
  "axis_x": "가벼운 식사 ↔ 든든한 식사",
  "axis_y": "익숙한 맛 ↔ 새로운 도전",
  "point": [0.7, 0.3],
  "hint": "이 구역의 음식을 추천해요"
}
```

- `point`: [x, y] 0~1 정규화. (0.7, 0.3)이면 "든든한 쪽 + 익숙한 쪽".
- 프론트: 2축 평면에 점 찍고, `hint` 텍스트 표시. (메뉴 아이콘은 선택 구현.)

---

### 5.7 danger_alert / soul_color

- **danger_alert**: Death, Tower 등 특정 카드가 포함되면 `tarot.danger_alert: true`. 프론트에서 붉은 비네팅 또는 "WARNING: 조심해야 할 시기" 깜빡임.
- **soul_color**: `tarot.soul_color` 값에 따라 오버레이 테두리·배경 톤 변경 (예: gold / purple / black). 텍스트만으로 지정하므로 별도 이미지 불필요.

---

## 6. LLM 출력 통합 예시

Groq에 타로 전용 프롬프트를 줄 때, **한 번에** 아래 형태의 JSON을 생성하게 한다.

```json
{
  "response": "내일 떡볶이를 드시는 것은...",
  "emotion": "happy",
  "action": "tarot",
  "tarot": {
    "cards": [
      { "id": "sun", "reversed": false },
      { "id": "cups_3", "reversed": true }
    ],
    "interpretation": "해석 전문 텍스트...",
    "visual_data": {
      "visual_type": "radar_dynamic",
      "labels": ["만족도", "칼로리 위험도", "소화 가능성"],
      "scores": [95, 85, 40]
    },
    "soul_color": "gold",
    "danger_alert": false
  }
}
```

- 일반 채팅일 때는 `action` 없거나 `"chat"`, `tarot` 필드 없음.
- **선택→공개 흐름**에서는 카드는 백엔드가 시청자 선택 결과로 이미 가지고 있으므로, Groq에는 카드 목록을 **입력**으로 넘기고 Groq는 **interpretation + visual_data + soul_color + danger_alert**만 출력하면 된다. `overlay_state["tarot"]`의 `cards`는 백엔드가 채우고, 해석·시각화만 Groq 응답으로 갱신.
- TTS에는 `response`(해석문 또는 요약) 전달. 해석문이 길면 전부 읽을지 요약만 읽을지는 구현 시 결정.

---

## 7. 정적 리소스 (카드 이미지)

| 경로 | 설명 |
|------|------|
| `assets/tarot/tarot_<id>.png` | 정방 카드 |
| `assets/tarot/reverse/tarot_<id>_r.png` | 역방 카드 |
| `assets/tarot/tarot_back.png` | 카드 뒷면/덱 뭉탱이 (선택 단계에서 1~78 안내와 함께 표시) |

- id 예: `fool`, `wheel_of_fortune`, `cups_3`, `swords_king`. **78장 덱**에는 타로 카드 파일만 포함하고, `tarot_milk_tea`, `tarotcards.png` 등 비덱 이미지는 제외. (구현 시 `tarot_<id>.png` / `tarot_<id>_r.png` 패턴으로 78장 id 목록 생성.)
- 오버레이 서버에서 `assets/tarot`를 `/tarot-assets` 등으로 마운트하면, 프론트에서 `src="/tarot-assets/tarot_fool.png"`, `src="/tarot-assets/reverse/tarot_fool_r.png"` 로 참조.

---

## 8. 구현 체크리스트

### 백엔드 (overlay)

- [ ] `state.py`: `overlay_state`에 `"tarot": None` 초기값 추가.
- [ ] `server.py`:
  - [ ] `StaticFiles`로 `assets/tarot` → `/tarot-assets` 마운트 (프로젝트 루트 기준 경로 처리).
  - [ ] `GET /tarot`: 타로 전용 HTML 페이지 응답 (기존 `OVERLAY_HTML` 참고).
  - [ ] `GET /api/state`: 응답에 `tarot` 필드 포함 (`overlay_state.get("tarot")`).
- [ ] (선택) 타로 클리어용 `POST /api/tarot/clear` → `overlay_state["tarot"] = None`.

### 메인 파이프라인 (examples)

- [ ] 타로 요청 시: 78장 셔플 → 1~78번 매핑 저장 → `overlay_state["tarot"]`에 phase `"selecting"`, `requester_id`(요청자 식별), `select_deadline_ts`(현재 시각 + 5분 또는 10분) 및 덱 표시용 데이터 설정. "1~78번 중 번호로 골라주세요" 등 안내 멘트.
- [ ] **시청자 일치**: 선택 단계에서 들어오는 채팅은 **요청자(requester_id)와 같은 사람**에서 온 것만 번호로 인정. 다른 시청자 메시지는 무시.
- [ ] **타임아웃**: 주기적으로(또는 채팅 처리 시) `select_deadline_ts`와 현재 시각 비교. 초과 시 타로 취소·상태 초기화, 필요 시 멘트 후 일반 흐름 복귀.
- [ ] 시청자(요청자) 채팅에서 **1~78 범위** 번호만 파싱(예: "23번" 또는 "7번, 23번, 45번"). 범위 밖·비숫자면 무시하고 재안내.
- [ ] 선택 번호에 해당하는 카드만 추려 Groq에 전달 → 해석 + visual_data 수신 후 `overlay_state["tarot"]`를 phase `"revealed"`·cards·interpretation·visual_data로 갱신. Groq 실패 시 재시도 또는 멘트 후 타로 초기화.
- [ ] **동시에 한 타로만**: 이미 타로 진행 중이면 새 타로 요청 무시 또는 안내.
- [ ] Groq 응답에서 해석 단계는 카드 목록을 **입력**으로만 쓰고, Groq는 interpretation·visual_data·soul_color·danger_alert만 반환. overlay_state["tarot"]의 cards는 백엔드가 선택 결과로 설정.
- [ ] TTS에는 `response`만 전달. (필요하면 "타로 결과를 알려드릴게요" 등 짧은 멘트 후 해석 읽기.)

### Groq 프롬프트

- [ ] 시스템 프롬프트: **시청자가 타로를 요청했을 때만** 타로 응답. 판단 기준("타로 봐줘", "타로로 봐줘", "점 괘", "운세" 등) 및 카드 id 목록(메이저+마이너 파일명 규칙) 명시.
- [ ] 응답 형식: 위 통합 JSON 구조 고정. `visual_type`은 질문 성격에 따라 선택:
  - 일반 운세 → `radar_fixed`
  - 구체적 질문(할까?/될까?) → `radar_dynamic` 또는 `yes_no`
  - 선택 질문(뭐 먹지? 등) → `candidates` 또는 `decision_map`
  - 키워드는 모든 경우 선택적으로 추가 가능.

### 프론트 (/tarot 페이지)

- [ ] `/api/state` 폴링(또는 WebSocket)으로 `tarot` 구독.
- [ ] `tarot.phase === "selecting"`: 덱(뭉탱이) 이미지 + "1~78번 중 번호로 골라주세요" 안내 + (선택) 요청자 닉네임.
- [ ] `tarot.phase === "revealed" && tarot.cards`: 앞면 카드 이미지 표시 (id, reversed → URL 매핑).
- [ ] `tarot.interpretation`: 해석문 표시.
- [ ] `tarot.visual_data.visual_type` 분기:
  - [ ] radar_fixed / radar_dynamic: 레이더 차트 (Chart.js 등, CDN).
  - [ ] yes_no: 게이지 바 + recommendation + score 텍스트.
  - [ ] keywords: 태그 3개 표시.
  - [ ] candidates: 룰렛/슬롯 연출 + 후보 목록 + 점수.
  - [ ] decision_map: 2축 + point + hint.
- [ ] `tarot.danger_alert === true`: 경고 비네팅/문구.
- [ ] `tarot.soul_color`: CSS 변수로 테두리/배경 색 적용.
- [ ] 배경 투명 처리해 OBS 오버레이로 사용 가능하게.

---

## 9. 참고

- 기존 오버레이: [README 오버레이 섹션](../README.md), `src/overlay/server.py`, `src/overlay/state.py`
- 카드 이미지: `assets/tarot/`, `assets/tarot/reverse/`
- PRD: [PRD.md](../PRD.md) — 오버레이·히스토리·Groq 연동 전제
