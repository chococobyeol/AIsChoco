"""
방송 오버레이용 로컬 HTTP 서버. /api/state JSON, / 오버레이 HTML.
반드시 chzzk_groq_example.py 안에서만 실행 (같은 프로세스에서 state 공유).
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.overlay.state import overlay_state

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_TAROT_ASSETS = _PROJECT_ROOT / "assets" / "tarot"

logger = logging.getLogger(__name__)
app = FastAPI(title="AIsChoco Overlay", docs_url=None, redoc_url=None)
if _TAROT_ASSETS.is_dir():
    app.mount("/tarot-assets", StaticFiles(directory=str(_TAROT_ASSETS)), name="tarot_assets")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
)


@app.get("/api/state")
def get_state():
    """오버레이: 시청자 채팅 컬럼 / AI 답변 컬럼, 방장채팅 숨김 설정, 타로 상태 반환."""
    viewer = list(overlay_state.get("viewer_messages") or [])
    assistant = list(overlay_state.get("assistant_messages") or [])
    ignore = bool(overlay_state.get("ignore_streamer_chat"))
    tarot = overlay_state.get("tarot")
    return JSONResponse({
        "viewer_messages": viewer,
        "assistant_messages": assistant,
        "ignore_streamer_chat": ignore,
        "tarot": tarot,
    })


@app.post("/api/toggle_streamer_chat")
def toggle_streamer_chat():
    """방장 채팅 무시 토글. ON이면 방장 채팅 미표시·AI 미반응."""
    cur = bool(overlay_state.get("ignore_streamer_chat"))
    overlay_state["ignore_streamer_chat"] = not cur
    logger.info("Overlay API: ignore_streamer_chat=%s", overlay_state["ignore_streamer_chat"])
    return JSONResponse({"ignore_streamer_chat": overlay_state["ignore_streamer_chat"]})


@app.post("/api/clear")
def clear_chat():
    """채팅/답변 오버레이 수동 클리어."""
    overlay_state["viewer_messages"] = []
    overlay_state["assistant_messages"] = []
    overlay_state["_next_id"] = 0
    logger.info("Overlay API: clear")
    return JSONResponse({"ok": True})


@app.post("/api/tarot/clear")
def clear_tarot():
    """타로 오버레이 상태 초기화."""
    overlay_state["tarot"] = None
    logger.info("Overlay API: tarot clear")
    return JSONResponse({"ok": True})

OVERLAY_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Chat Overlay Final v3</title>
  <link href="https://fonts.googleapis.com/css2?family=Gowun+Dodum&display=swap" rel="stylesheet">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    ::-webkit-scrollbar { display: none; }
    
    body {
      font-family: "Gowun Dodum", sans-serif;
      background-color: transparent;
      height: 100vh;
      width: 100vw;
      padding: 15px;
      display: flex;
      gap: 20px;
      overflow: hidden;
    }

    /* OBS 모드일 때 버튼 숨김 */
    body.obs-mode .btn-area { display: none !important; }

    /* [컬럼 설정] */
    .col {
      flex: 1;
      display: flex;
      flex-direction: column;
      justify-content: flex-end; /* 아래에서 위로 쌓임 */
      min-width: 0;
      padding-bottom: 5px;
    }

    /* [메시지 공통 디자인] */
    .row {
      margin-bottom: 12px;
      padding: 14px 18px;
      border-radius: 16px;
      font-size: 17px;
      line-height: 1.5;
      word-break: break-word;
      box-shadow: 0 4px 10px rgba(0,0,0,0.25);
      backdrop-filter: blur(8px);
      border: 1px solid rgba(255,255,255,0.1);
      
      /* 등장 애니메이션 (부드럽게 스윽) */
      opacity: 0;
      transform: translateY(20px);
      animation: slideUp 0.4s cubic-bezier(0.2, 0.8, 0.2, 1) forwards;
      transition: all 0.5s ease; /* 상태 변화 부드럽게 */
    }

    @keyframes slideUp {
      to { opacity: 1; transform: translateY(0); }
    }

    /* -----------------------------------------------------------
       [왼쪽: AI/방송인] 
       ----------------------------------------------------------- */
    .row.assistant {
      align-self: flex-start;
      text-align: left;
      background: rgba(60, 55, 50, 0.9);
      color: #fff8e1;
      max-width: 95%;
      border-left: 5px solid #e2b088;
    }

    /* [AI 이전 답변] - 흐리게 */
    .row.assistant.previous {
      background: rgba(40, 35, 30, 0.6);
      color: #d6d3d1;
      border-left-color: #78716c;
      transform: scale(0.98);
      box-shadow: none;
    }

    /* -----------------------------------------------------------
       [오른쪽: 시청자]
       ----------------------------------------------------------- */
    .row.viewer {
      align-self: flex-end;
      text-align: right;
      background: rgba(40, 45, 60, 0.9);
      color: #f1f5f9;
      max-width: 95%;
      border-right: 5px solid #94a3b8;
    }

    .row.viewer .name {
      display: block;
      font-size: 13px;
      font-weight: bold;
      color: #bae6fd;
      margin-bottom: 5px;
    }

    /* [답변 완료된 시청자 채팅] - 흐리게 */
    .row.viewer.processed {
      background: rgba(20, 25, 35, 0.65);
      color: #94a3b8;
      border-right-color: #475569;
      transform: scale(0.98);
      box-shadow: none;
      filter: grayscale(0.8);
    }

    /* [버튼 영역] */
    .btn-area {
      position: fixed;
      top: 15px;
      right: 15px;
      display: flex;
      gap: 8px;
      z-index: 9999;
    }

    .btn-common {
      padding: 8px 14px;
      font-size: 13px;
      border-radius: 8px;
      border: 1px solid rgba(255,255,255,0.3);
      background: rgba(0, 0, 0, 0.7);
      color: #e2e8f0;
      cursor: pointer;
      font-family: "Gowun Dodum", sans-serif;
    }
    .btn-common:hover { background: rgba(255,255,255,0.2); color: white; }
    .btn-common.on { background: rgba(239, 68, 68, 0.6); border-color: #f87171; }

  </style>
</head>
<body>
  <div class="btn-area">
    <button type="button" class="btn-common" id="btn-streamer">방장 숨김</button>
    <button type="button" class="btn-common" id="btn-clear">지우기</button>
  </div>

  <div class="col" id="col-assistant"></div>
  <div class="col" id="col-viewer"></div>

  <script>
    // URL 파라미터 확인 (?obs=1)
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('obs')) {
      document.body.classList.add('obs-mode');
    }

    const MAX_AGE = 600; // 10분 (초 단위)

    function escapeHtml(text) {
      if (!text) return "";
      return text.replace(/&/g, "&amp;")
                 .replace(/</g, "&lt;")
                 .replace(/>/g, "&gt;")
                 .replace(/"/g, "&quot;")
                 .replace(/'/g, "&#039;");
    }

    function render() {
      var base = window.location.origin || (window.location.protocol + "//" + window.location.host);
      
      fetch(base + "/api/state")
        .then(function(r) { return r.json(); })
        .then(function(data) {
          // 1. 버튼 상태 업데이트
          var ignore = data.ignore_streamer_chat || false;
          var btn = document.getElementById("btn-streamer");
          if(btn) {
             btn.className = "btn-common" + (ignore ? " on" : "");
             btn.innerText = ignore ? "방장 숨김: ON" : "방장 숨김: OFF";
          }

          var now = Date.now() / 1000;

          // 2. 10분 지난 메시지 필터링 (빼먹었던 부분 복구!)
          var viewerList = (data.viewer_messages || []).filter(function(m) {
             return (now - (m.ts || now)) <= MAX_AGE;
          });
          var assistantList = (data.assistant_messages || []).filter(function(m) {
             return (now - (m.ts || now)) <= MAX_AGE;
          });

          // 3. 스마트 업데이트 (깜빡임 해결의 핵심)
          updateColumn("col-viewer", viewerList, "viewer");
          updateColumn("col-assistant", assistantList, "assistant");

        })
        .catch(function(err) { console.error(err); });
    }

    // 컬럼 업데이트 함수 (기존 내용을 덮어쓰지 않고 비교해서 수정함)
    function updateColumn(colId, messages, type) {
      var col = document.getElementById(colId);
      var validIds = new Set();

      messages.forEach(function(msg, index) {
        // 메시지 고유 ID 생성 (타임스탬프 활용)
        var msgId = type + "-" + (msg.ts || 0) + "-" + index; 
        validIds.add(msgId);

        var el = document.getElementById(msgId);

        // A. 새로운 메시지면? -> 만든다 (append)
        if (!el) {
          el = document.createElement("div");
          el.id = msgId;
          el.className = "row " + type;
          
          var html = "";
          if (type === "viewer") {
             html += '<span class="name">' + escapeHtml(msg.user) + '</span>';
          }
          html += '<div class="text">' + escapeHtml(msg.message) + '</div>';
          
          el.innerHTML = html;
          col.appendChild(el); // 톡! 추가 (전체 갱신 X)
          
          // 새 메시지 왔으니 스크롤 내리기
          // col.scrollTop = col.scrollHeight; 
        }

        // B. 상태 업데이트 (답변 완료 / 이전 답변 처리)
        // 시청자: processed 체크
        if (type === "viewer") {
           if (msg.processed && !el.classList.contains("processed")) {
              el.classList.add("processed");
           }
        }
        // AI: 마지막 답변이 아니면 previous 처리
        if (type === "assistant") {
           var isLast = (index === messages.length - 1);
           if (!isLast && !el.classList.contains("previous")) {
              el.classList.add("previous");
           } else if (isLast && el.classList.contains("previous")) {
              el.classList.remove("previous"); // 혹시 순서 꼬임 방지
           }
        }
      });

      // C. 삭제된 메시지 정리 (10분 지난거 지우기)
      // 현재 화면에는 있는데, API 리스트(validIds)에는 없는 애들을 찾아서 제거
      var children = Array.from(col.children);
      children.forEach(function(child) {
        if (!validIds.has(child.id)) {
           child.style.opacity = "0"; // 부드럽게 사라지기
           setTimeout(function() { 
             if(child.parentNode) child.parentNode.removeChild(child); 
           }, 500); 
        }
      });
    }

    document.getElementById("btn-clear").onclick = function() {
      fetch("/api/clear", { method: "POST" }).then(function() { 
        document.getElementById("col-viewer").innerHTML = "";
        document.getElementById("col-assistant").innerHTML = "";
        render(); 
      });
    };
    document.getElementById("btn-streamer").onclick = function() {
      fetch("/api/toggle_streamer_chat", { method: "POST" }).then(render);
    };

    setInterval(render, 500);
    render();
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def overlay_page():
    """OBS 브라우저 소스에 넣을 URL. 채팅/대사를 폴링해 표시."""
    return HTMLResponse(OVERLAY_HTML)


TAROT_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>타로 오버레이</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: "Malgun Gothic", sans-serif; background: transparent; color: #1e293b; min-height: 100vh; padding: 12px; }
    .tarot-panel { max-width: 90vw; margin: 0 auto; }
    .phase-select { text-align: center; padding: 20px; }
    .phase-select .deck-img { max-width: 180px; border-radius: 8px; }
    .phase-select .hint { margin-top: 12px; font-size: 15px; color: #334155; }
    .phase-select .requester { font-size: 13px; color: #64748b; margin-top: 6px; }
    .phase-reveal { display: flex; flex-wrap: wrap; gap: 12px; align-items: flex-start; }
    .phase-reveal .cards { display: flex; gap: 8px; flex-wrap: wrap; }
    .phase-reveal .card-img { width: 100px; height: auto; border-radius: 6px; }
    .phase-reveal .interpretation { flex: 1; min-width: 200px; padding: 10px; background: rgba(255,255,255,0.9); border-radius: 8px; font-size: 14px; line-height: 1.5; white-space: pre-wrap; }
    .phase-reveal .visual { margin-top: 8px; font-size: 12px; color: #64748b; }
    .phase-reveal .reveal-footer { margin-top: 10px; font-size: 13px; color: #64748b; }
    .phase-reveal .reveal-timer { font-weight: bold; color: #334155; }
    .phase-failed { text-align: center; padding: 20px; color: #64748b; }
    .hidden { display: none; }
  </style>
</head>
<body>
  <div class="tarot-panel" id="tarot-panel"></div>
  <script>
    var base = window.location.origin || (window.location.protocol + "//" + window.location.host);
    function cardSrc(id, reversed) {
      var path = reversed ? "/tarot-assets/reverse/tarot_" + id + "_r.png" : "/tarot-assets/tarot_" + id + ".png";
      return base + path;
    }
    function render() {
      fetch(base + "/api/state").then(function(r) { return r.json(); }).then(function(data) {
        var tarot = data.tarot || null;
        var el = document.getElementById("tarot-panel");
        if (!tarot || !tarot.visible) {
          el.innerHTML = "";
          el.className = "tarot-panel";
          return;
        }
        if (tarot.phase === "selecting") {
          var need = tarot.spread_count || 3;
          var hintText = need === 1 ? '1~78번 중 번호 하나만 골라주세요.' : ('1~78번 중 번호 ' + need + '개 골라주세요.');
          var deadline = tarot.select_deadline_ts || 0;
          var nowSec = Date.now() / 1000;
          var remain = Math.max(0, Math.floor(deadline - nowSec));
          var min = Math.floor(remain / 60);
          var sec = remain % 60;
          var timeStr = (min > 0 ? min + '분 ' : '') + sec + '초';
          el.innerHTML = '<div class="phase-select">' +
            '<img class="deck-img" src="' + base + '/tarot-assets/tarot_back.png" alt="덱" onerror="this.style.display=\\'none\\'">' +
            '<div class="hint">' + hintText + '</div>' +
            (deadline ? '<div class="requester">남은 시간 ' + timeStr + '</div>' : '') +
            (tarot.requester_nickname ? '<div class="requester">' + (tarot.requester_nickname || "") + '님</div>' : '') +
            '</div>';
          el.className = "tarot-panel";
          return;
        }
        if (tarot.phase === "revealed" && tarot.cards && tarot.cards.length) {
          var cardsHtml = tarot.cards.map(function(c) {
            return '<img class="card-img" src="' + cardSrc(c.id, c.reversed) + '" alt="' + (c.id || "") + '">';
          }).join("");
          var interp = (tarot.interpretation || "").replace(/</g, "&lt;").replace(/>/g, "&gt;");
          var visual = tarot.visual_data ? '<div class="visual">[시각화] ' + (tarot.visual_data.visual_type || "") + '</div>' : "";
          var footer = '';
          if (tarot.auto_reset_at_ts) {
            var nowSec = Date.now() / 1000;
            var left = Math.max(0, Math.floor(tarot.auto_reset_at_ts - nowSec));
            var m = Math.floor(left / 60);
            var s = left % 60;
            footer = '<div class="reveal-footer">궁금하신 점이 있으면 말씀해주세요. <span class="reveal-timer">' + m + ':' + (s < 10 ? '0' : '') + s + '</span> 후 자동으로 닫힙니다.</div>';
          }
          el.innerHTML = '<div class="phase-reveal">' +
            '<div class="cards">' + cardsHtml + '</div>' +
            '<div class="interpretation">' + interp + visual + footer + '</div>' +
            '</div>';
          el.className = "tarot-panel";
          return;
        }
        if (tarot.phase === "failed") {
          var msg = (tarot.message || "해석을 불러오지 못했어요.").replace(/</g, "&lt;").replace(/>/g, "&gt;");
          el.innerHTML = '<div class="phase-failed">' + msg + '</div>';
          el.className = "tarot-panel";
          return;
        }
        el.innerHTML = "";
      }).catch(function() { document.getElementById("tarot-panel").innerHTML = ""; });
    }
    render();
    setInterval(render, 500);
  </script>
</body>
</html>
"""


_TAROT_HTML_PATH = Path(__file__).resolve().parent / "tarot_overlay.html"


@app.get("/tarot", response_class=HTMLResponse)
def tarot_page():
    """타로 전용 오버레이. OBS 브라우저 소스에 http://127.0.0.1:8765/tarot 로 추가."""
    if _TAROT_HTML_PATH.is_file():
        return HTMLResponse(_TAROT_HTML_PATH.read_text(encoding="utf-8"))
    return HTMLResponse(TAROT_HTML)
