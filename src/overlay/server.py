"""
방송 오버레이용 로컬 HTTP 서버. /api/state JSON, / 오버레이 HTML.
반드시 chzzk_groq_example.py 안에서만 실행 (같은 프로세스에서 state 공유).
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
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
    cur = bool(overlay_state.get("ignore_streamer_chat"))
    overlay_state["ignore_streamer_chat"] = not cur
    return JSONResponse({"ignore_streamer_chat": overlay_state["ignore_streamer_chat"]})


@app.post("/api/clear")
def clear_chat():
    overlay_state["viewer_messages"] = []
    overlay_state["assistant_messages"] = []
    overlay_state["_next_id"] = 0
    return JSONResponse({"ok": True})


@app.post("/api/tarot/clear")
def clear_tarot():
    overlay_state["tarot"] = None
    return JSONResponse({"ok": True})


# ==============================================================================
# 채팅 오버레이 HTML (최종 수정: 분위기 맞춤형)
# ==============================================================================
OVERLAY_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Chat Overlay Soft</title>
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
      gap: 24px; /* 좌우 간격 조금 더 넓게 */
      overflow: hidden;
    }

    body.obs-mode .btn-area { display: none !important; }

    .col {
      flex: 1;
      display: flex;
      flex-direction: column;
      justify-content: flex-end;
      min-width: 0;
      padding-bottom: 10px;
    }

    /* [메시지 공통 디자인] */
    .row {
      margin-bottom: 14px;
      padding: 12px 16px;
      border-radius: 12px;
      font-size: 17px;
      line-height: 1.5;
      word-break: break-word;
      
      /* 기본 상태: 은은한 그림자 */
      box-shadow: 0 4px 6px rgba(0,0,0,0.1);
      backdrop-filter: blur(5px);
      
      /* 애니메이션 및 트랜지션 */
      opacity: 0;
      transform: translateY(20px);
      animation: slideUp 0.4s cubic-bezier(0.2, 0.8, 0.2, 1) forwards;
      transition: all 0.5s ease;
    }

    @keyframes slideUp {
      to { opacity: 1; transform: translateY(0); }
    }

    /* -----------------------------------------------------------
       [왼쪽: AI] - 웜톤 (방 안 조명 느낌)
       ----------------------------------------------------------- */
    .row.assistant {
      align-self: flex-start;
      text-align: left;
      /* 배경: 짙은 웜그레이 */
      background: rgba(60, 55, 50, 0.85);
      color: #fff8e1; /* 상아색 폰트 */
      max-width: 90%;
      
      /* [Active 효과] 은은한 주황색 발광 (테두리 아님) */
      box-shadow: 0 0 15px rgba(251, 191, 36, 0.2), 0 4px 6px rgba(0,0,0,0.2);
      border-left: 4px solid rgba(251, 191, 36, 0.8);
    }

    /* [AI 이전 답변] - 빛이 꺼진 느낌 */
    .row.assistant.previous {
      background: rgba(45, 40, 35, 0.6); /* 더 투명하게 */
      color: #d1d5db; /* 약간 회색조 */
      box-shadow: none; /* 발광 제거 */
      border-left-color: rgba(255,255,255,0.2); /* 포인트 색상 죽임 */
      transform: scale(0.98);
    }

    /* -----------------------------------------------------------
       [오른쪽: 시청자] - 쿨톤 (창밖 밤하늘 느낌)
       ----------------------------------------------------------- */
    .row.viewer {
      align-self: flex-end;
      text-align: right;
      /* 배경: 짙은 네이비 */
      background: rgba(30, 41, 59, 0.85);
      color: #f1f5f9;
      max-width: 90%;

      /* [Active 효과] 은은한 하늘색 발광 */
      box-shadow: 0 0 15px rgba(56, 189, 248, 0.2), 0 4px 6px rgba(0,0,0,0.2);
      border-right: 4px solid rgba(56, 189, 248, 0.8);
    }

    .row.viewer .name {
      display: block;
      font-size: 13px;
      font-weight: bold;
      color: #bae6fd;
      margin-bottom: 5px;
    }

    /* [답변 완료된 시청자] - 빛이 꺼지고 뒤로 물러난 느낌 */
    .row.viewer.processed {
      background: rgba(15, 23, 42, 0.5); /* 투명도 높여서 배경에 묻히게 */
      color: #94a3b8; /* 글자색 회색으로 */
      box-shadow: none; /* 발광 제거 */
      border-right-color: rgba(255,255,255,0.1); /* 포인트 색상 죽임 */
      transform: scale(0.98); /* 살짝 작아짐 */
      filter: grayscale(0.5); /* 채도 뺌 */
    }

    /* [사라질 때] */
    .row.removing {
      opacity: 0 !important;
      transform: translateY(-10px) scale(0.9) !important;
      margin-bottom: -30px !important;
      pointer-events: none;
    }

    /* [버튼] */
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
      border: 1px solid rgba(255,255,255,0.2);
      background: rgba(0, 0, 0, 0.6);
      color: #cbd5e1;
      cursor: pointer;
      font-family: "Gowun Dodum", sans-serif;
    }
    .btn-common:hover { background: rgba(255,255,255,0.2); color: white; }
    .btn-common.on { background: rgba(220, 38, 38, 0.5); border-color: #ef4444; }

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
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('obs')) {
      document.body.classList.add('obs-mode');
    }

    const MAX_AGE = 600; // 10분

    function escapeHtml(text) {
      if (!text) return "";
      return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }

    function render() {
      var base = window.location.origin || (window.location.protocol + "//" + window.location.host);
      
      fetch(base + "/api/state")
        .then(function(r) { return r.json(); })
        .then(function(data) {
          var ignore = data.ignore_streamer_chat || false;
          var btn = document.getElementById("btn-streamer");
          if(btn) {
             btn.className = "btn-common" + (ignore ? " on" : "");
             btn.innerText = ignore ? "방장 숨김: ON" : "방장 숨김: OFF";
          }

          var now = Date.now() / 1000;
          var viewerList = (data.viewer_messages || []).filter(function(m) { return (now - (m.ts || now)) <= MAX_AGE; });
          var assistantList = (data.assistant_messages || []).filter(function(m) { return (now - (m.ts || now)) <= MAX_AGE; });

          updateColumn("col-viewer", viewerList, "viewer");
          updateColumn("col-assistant", assistantList, "assistant");
        })
        .catch(function(err) { console.error(err); });
    }

    function updateColumn(colId, messages, type) {
      var col = document.getElementById(colId);
      var validIds = new Set();

      messages.forEach(function(msg, index) {
        var msgId = type + "-" + (msg.ts || 0) + "-" + index; 
        validIds.add(msgId);

        var el = document.getElementById(msgId);

        if (!el) {
          el = document.createElement("div");
          el.id = msgId;
          el.className = "row " + type;
          var html = "";
          if (type === "viewer") { html += '<span class="name">' + escapeHtml(msg.user) + '</span>'; }
          html += '<div class="text">' + escapeHtml(msg.message) + '</div>';
          el.innerHTML = html;
          col.appendChild(el); 
        }

        if (el.classList.contains("removing")) return;

        // [상태 업데이트]
        if (type === "viewer") {
           if (msg.processed && !el.classList.contains("processed")) {
              el.classList.add("processed");
           }
        }
        if (type === "assistant") {
           var isLast = (index === messages.length - 1);
           if (!isLast && !el.classList.contains("previous")) {
              el.classList.add("previous");
           } else if (isLast && el.classList.contains("previous")) {
              el.classList.remove("previous");
           }
        }
      });

      var children = Array.from(col.children);
      children.forEach(function(child) {
        if (!validIds.has(child.id) && !child.classList.contains("removing")) {
           child.classList.add("removing");
           setTimeout(function() { if(child.parentNode) child.parentNode.removeChild(child); }, 500); 
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
    return HTMLResponse(OVERLAY_HTML)


_TAROT_HTML_PATH = Path(__file__).resolve().parent / "tarot_overlay.html"


@app.get("/tarot", response_class=HTMLResponse)
def tarot_page():
    if _TAROT_HTML_PATH.is_file():
        return HTMLResponse(_TAROT_HTML_PATH.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Error: tarot_overlay.html 파일을 찾을 수 없습니다.</h1>", status_code=404)