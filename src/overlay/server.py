"""
방송 오버레이용 로컬 HTTP 서버. /api/state JSON, / 오버레이 HTML.
반드시 chzzk_groq_example.py 안에서만 실행 (같은 프로세스에서 state 공유).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from src.overlay.state import overlay_state

logger = logging.getLogger(__name__)
app = FastAPI(title="AIsChoco Overlay", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
)


@app.get("/api/state")
def get_state():
    """오버레이: 시청자 채팅 컬럼 / AI 답변 컬럼 각각 반환."""
    viewer = list(overlay_state.get("viewer_messages") or [])
    assistant = list(overlay_state.get("assistant_messages") or [])
    logger.info("Overlay API: viewer=%d assistant=%d", len(viewer), len(assistant))
    return JSONResponse({"viewer_messages": viewer, "assistant_messages": assistant})


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
  </style>
</head>
<body>
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
    function render() {
      var base = window.location.origin || (window.location.protocol + "//" + window.location.host);
      fetch(base + "/api/state")
        .then(function(r) { return r.json(); })
        .then(function(data) {
          var viewerList = data.viewer_messages || [];
          var assistantList = data.assistant_messages || [];
          var vEl = document.getElementById("viewer-col");
          var aEl = document.getElementById("assistant-col");
          vEl.innerHTML = viewerList.length === 0
            ? '<div class="empty">(대기 중)</div>'
            : '<div class="inner">' + viewerList.map(function(item) {
                var cls = "row viewer" + (item.processed ? " processed" : "");
                var user = escapeHtml(item.user || "?");
                var msg = escapeHtml(item.message || "");
                return '<div class="' + cls + '"><div class="name">' + user + '</div><div class="text">' + msg + '</div></div>';
              }).join("") + '</div>';
          aEl.innerHTML = assistantList.length === 0
            ? '<div class="empty">(대기 중)</div>'
            : '<div class="inner">' + assistantList.map(function(item, i) {
                var msg = escapeHtml(item.message || "");
                var prev = i < assistantList.length - 1 ? " previous" : "";
                return '<div class="row assistant' + prev + '"><div class="text">' + msg + '</div></div>';
              }).join("") + '</div>';
          vEl.scrollTop = vEl.scrollHeight;
          aEl.scrollTop = aEl.scrollHeight;
        })
        .catch(function() {
          document.getElementById("viewer-col").innerHTML = '<div class="empty">(연결 오류)</div>';
          document.getElementById("assistant-col").innerHTML = '';
        });
    }
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
