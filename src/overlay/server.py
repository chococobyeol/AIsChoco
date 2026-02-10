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
  <title>채팅 오버레이</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: "Malgun Gothic", "Apple SD Gothic Neo", sans-serif;
      background: transparent;
      color: #1e293b;
      height: 100vh;
      padding: 10px 12px;
      display: flex;
      gap: 2px;
      align-items: stretch;
    }
    .col {
      flex: 1;
      min-width: 0;
      max-width: 280px;
      display: flex;
      flex-direction: column;
      min-height: 0;
    }
    .col-content {
      flex: 1;
      min-height: 0;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      justify-content: flex-end;
    }
    .col-content .inner { margin-top: auto; }
    .row {
      padding: 8px 10px;
      margin-bottom: 6px;
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.92);
      box-shadow: 0 1px 2px rgba(0,0,0,0.06);
      word-break: break-word;
      font-size: 13px;
      line-height: 1.4;
      border-left: 3px solid transparent;
    }
    .row.viewer {
      margin-left: auto;
      max-width: 92%;
      text-align: right;
    }
    .row.viewer .name {
      font-weight: 700;
      color: #0f172a;
      font-size: 12px;
      margin-bottom: 3px;
      text-shadow: none;
    }
    .row.viewer .text { color: #334155; }
    .row.viewer.processed {
      background: rgba(248, 250, 252, 0.88);
      border-left-color: #94a3b8;
      opacity: 0.88;
    }
    .row.viewer.processed .name { color: #64748b; font-weight: 600; }
    .row.viewer.processed .text { color: #64748b; }
    .row.assistant {
      max-width: 95%;
      text-align: left;
      border-left-color: #64748b;
    }
    .row.assistant .text { color: #334155; }
    .row.assistant.previous {
      background: rgba(248, 250, 252, 0.88);
      border-left-color: #94a3b8;
      opacity: 0.82;
    }
    .row.assistant.previous .text { color: #64748b; }
    .empty { opacity: 0.7; font-size: 12px; padding: 6px 0; color: #64748b; }
    .btn-clear {
      position: fixed;
      bottom: 8px;
      right: 8px;
      padding: 4px 10px;
      font-size: 12px;
      border-radius: 6px;
      border: 1px solid #94a3b8;
      background: rgba(255,255,255,0.9);
      color: #475569;
      cursor: pointer;
    }
    .btn-clear:hover { background: #f1f5f9; }
    .btn-streamer {
      position: fixed;
      bottom: 8px;
      right: 72px;
      padding: 4px 10px;
      font-size: 12px;
      border-radius: 6px;
      border: 1px solid #94a3b8;
      background: rgba(255,255,255,0.9);
      color: #475569;
      cursor: pointer;
    }
    .btn-streamer:hover { background: #f1f5f9; }
    .btn-streamer.on { background: #e2e8f0; font-weight: 600; }
  </style>
</head>
<body>
  <button type="button" class="btn-streamer" id="btn-streamer">방장 숨김: OFF</button>
  <button type="button" class="btn-clear" id="btn-clear">클리어</button>
  <div class="col">
    <div class="col-content" id="assistant-col"></div>
  </div>
  <div class="col">
    <div class="col-content" id="viewer-col"></div>
  </div>
  <script>
    function escapeHtml(s) {
      if (s == null || s === undefined) return "";
      var div = document.createElement("div");
      div.textContent = String(s);
      return div.innerHTML;
    }
    var MAX_AGE = 600;
    var FADE_START = 480;
    function opacityForAge(ts) {
      if (ts == null) return 1;
      var age = (Date.now() / 1000) - ts;
      if (age <= FADE_START) return 1;
      if (age >= MAX_AGE) return 0;
      return 1 - (age - FADE_START) / (MAX_AGE - FADE_START);
    }
    function render() {
      var base = window.location.origin || (window.location.protocol + "//" + window.location.host);
      fetch(base + "/api/state")
        .then(function(r) { return r.json(); })
        .then(function(data) {
          var ignore = data.ignore_streamer_chat || false;
          var btn = document.getElementById("btn-streamer");
          if (btn) {
            btn.textContent = ignore ? "방장 숨김: ON" : "방장 숨김: OFF";
            btn.className = "btn-streamer" + (ignore ? " on" : "");
          }
          var now = Date.now() / 1000;
          var viewerList = (data.viewer_messages || []).filter(function(item) {
            var age = now - (item.ts != null ? item.ts : now);
            return age <= MAX_AGE;
          });
          var assistantList = (data.assistant_messages || []).filter(function(item) {
            var age = now - (item.ts != null ? item.ts : now);
            return age <= MAX_AGE;
          });
          var vEl = document.getElementById("viewer-col");
          var aEl = document.getElementById("assistant-col");
          vEl.innerHTML = viewerList.length === 0
            ? '<div class="empty">(대기 중)</div>'
            : '<div class="inner">' + viewerList.map(function(item) {
                var cls = "row viewer" + (item.processed ? " processed" : "");
                var user = escapeHtml(item.user || "?");
                var msg = escapeHtml(item.message || "");
                var op = opacityForAge(item.ts);
                return '<div class="' + cls + '" style="opacity:' + op + '"><div class="name">' + user + '</div><div class="text">' + msg + '</div></div>';
              }).join("") + '</div>';
          aEl.innerHTML = assistantList.length === 0
            ? '<div class="empty">(대기 중)</div>'
            : '<div class="inner">' + assistantList.map(function(item, i) {
                var msg = escapeHtml(item.message || "");
                var prev = i < assistantList.length - 1 ? " previous" : "";
                var op = opacityForAge(item.ts);
                return '<div class="row assistant' + prev + '" style="opacity:' + op + '"><div class="text">' + msg + '</div></div>';
              }).join("") + '</div>';
          vEl.scrollTop = vEl.scrollHeight;
          aEl.scrollTop = aEl.scrollHeight;
        })
        .catch(function() {
          document.getElementById("viewer-col").innerHTML = '<div class="empty">(연결 오류)</div>';
          document.getElementById("assistant-col").innerHTML = '';
        });
    }
    document.getElementById("btn-clear").onclick = function() {
      var base = window.location.origin || (window.location.protocol + "//" + window.location.host);
      fetch(base + "/api/clear", { method: "POST" }).then(function() { render(); });
    };
    document.getElementById("btn-streamer").onclick = function() {
      var base = window.location.origin || (window.location.protocol + "//" + window.location.host);
      fetch(base + "/api/toggle_streamer_chat", { method: "POST" }).then(function() { render(); });
    };
    render();
    setInterval(render, 500);
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
