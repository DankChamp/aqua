"""
Aqua Bridge Server

Provides HTTP and WebSocket endpoints for Emma to delegate automation tasks to Aqua.
Matches Luna's bridge server interface for consistency.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import struct
from contextlib import asynccontextmanager
from typing import Optional

from aiohttp import web
from aiohttp.web import Request, Response, WebSocketResponse

from core.automation.tools import AUTOMATION_TOOLS


WS_MAGIC = "258EAFA5-E914-47DA-95CA-5AB5FB11B5D3"

# Endpoints that require the shared bridge token
_PRIVILEGED_PATHS = {"/api/chat", "/api/ingest", "/ws", "/api/delegate", "/api/automation"}


def _token_matches(provided: str, expected: str) -> bool:
    """Constant-time comparison so auth can't be brute-forced via timing."""
    if not expected:
        return False
    return hmac.compare_digest(provided or "", expected)


def _ws_accept(key: str) -> str:
    return base64.b64encode(
        hashlib.sha1((key + WS_MAGIC).encode()).digest()
    ).decode()


class BridgeServer:
    """Async bridge server for Aqua automation using aiohttp."""
    
    def __init__(self, bridge_token: str = ""):
        self.bridge_token = bridge_token
        self._ws_clients: set[web.WebSocketResponse] = set()
        self._ws_lock = asyncio.Lock()
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
        
        # Observability
        from core.observability import get_tracer, get_logger, trace_span, get_metrics, MetricNames
        self._tracer = get_tracer("aqua")
        self._logger = get_logger("aqua.bridge")
        self._metrics = get_metrics()
    
    def _bearer_token(self, request: Request) -> str:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[len("Bearer "):].strip()
        return ""

    def _authorized(self, request: Request) -> bool:
        """Only Emma (holder of the shared bridge token) may call privileged routes."""
        if not self.bridge_token:
            return False
        return _token_matches(self._bearer_token(request), self.bridge_token)

    async def _handle_index(self, request: Request) -> Response:
        return web.Response(text=self._get_html_page(), content_type="text/html")

    def _get_html_page(self) -> str:
        return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Aqua Automation</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0d1117; color: #e6edf3; font-family: 'JetBrains Mono', monospace; display: flex; height: 100vh; }
  #sidebar { width: 280px; background: #161b22; padding: 16px; border-right: 1px solid #30363d; display: flex; flex-direction: column; }
  #sidebar h1 { color: #58a6ff; font-size: 18px; margin-bottom: 16px; }
  #main { flex: 1; display: flex; flex-direction: column; }
  #messages { flex: 1; overflow-y: auto; padding: 20px; }
  .msg { margin-bottom: 16px; max-width: 80%; }
  .msg.user { margin-left: auto; }
  .msg.user .bubble { background: #1f6feb; }
  .msg.assistant .bubble { background: #21262d; border: 1px solid #30363d; }
  .bubble { padding: 12px 16px; border-radius: 8px; line-height: 1.5; font-size: 14px; white-space: pre-wrap; }
  .label { font-size: 11px; color: #8b949e; margin-bottom: 4px; }
  #input-area { padding: 16px; border-top: 1px solid #30363d; display: flex; gap: 8px; }
  #input { flex: 1; background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 10px 14px; color: #e6edf3; font-family: inherit; font-size: 14px; outline: none; }
  #input:focus { border-color: #58a6ff; }
  #send { background: #238636; border: none; border-radius: 6px; padding: 10px 20px; color: #fff; font-family: inherit; font-size: 14px; cursor: pointer; }
  #send:hover { background: #2ea043; }
</style>
</head>
<body>
<div id="sidebar">
  <h1>⚙ Aqua Automation</h1>
  <div class="info">Status: <span id="status">connected</span></div>
  <div class="info">Workflows: <span id="wf-count">0</span></div>
  <div class="info">Pipelines: <span id="pipe-count">0</span></div>
</div>
<div id="main">
  <div id="messages"></div>
  <div id="input-area">
    <input id="input" type="text" placeholder="Type automation command..." autofocus>
    <button id="send">Send</button>
  </div>
</div>
<script>
const ws = new WebSocket('ws://' + location.host + '/ws');
const msgs = document.getElementById('messages');
const input = document.getElementById('input');
const send = document.getElementById('send');
ws.onmessage = (e) => {
  const data = JSON.parse(e.data);
  if (data.type === 'chunk') {
    let last = msgs.lastElementChild;
    if (!last || last.dataset.role !== 'assistant') {
      last = addMsg('assistant', '');
    }
    last.querySelector('.bubble').textContent += data.text;
    msgs.scrollTop = msgs.scrollHeight;
  } else if (data.type === 'tool_start') {
    addMsg('assistant', `⚡ Running tool: ${data.tool}(${JSON.stringify(data.args)})`);
  } else if (data.type === 'tool_end') {
    addMsg('assistant', `✓ ${data.tool} completed`);
  } else if (data.type === 'status') {
    document.getElementById('status').textContent = data.status;
  }
};
function addMsg(role, text) {
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  div.dataset.role = role;
  div.innerHTML = '<div class="label">' + role + '</div><div class="bubble">' + escapeHtml(text) + '</div>';
  msgs.appendChild(div);
  return div;
}
function escapeHtml(t) { return t.replace(/&/g,'&').replace(/</g,'<').replace(/>/g,'>'); }
function sendMsg() {
  const text = input.value.trim();
  if (!text) return;
  addMsg('user', text);
  input.value = '';
  ws.send(JSON.stringify({type: 'automation', command: text}));
}
send.addEventListener('click', sendMsg);
input.addEventListener('keydown', (e) => { if (e.key === 'Enter') sendMsg(); });
</script>
</body>
</html>"""

    async def _handle_health(self, request: Request) -> Response:
        return web.json_response({"status": "ok", "service": "aqua-automation"})

    async def _handle_status(self, request: Request) -> Response:
        info = {
            "status": "ok",
            "service": "aqua-automation",
            "tools": len(AUTOMATION_TOOLS),
        }
        return web.json_response(info)

    async def _handle_api_automation(self, request: Request) -> Response:
        if not self._authorized(request):
            return web.json_response({"error": "unauthorized: missing or invalid bridge token"}, status=401)
        
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "invalid JSON body"}, status=400)
        
        command = data.get("command", "")
        tool_name = data.get("tool", "")
        args = data.get("args", {})
        
        if not command and not tool_name:
            return web.json_response({"error": "missing command or tool"}, status=400)
        
        # Execute automation tool
        if tool_name and tool_name in AUTOMATION_TOOLS:
            tool = AUTOMATION_TOOLS[tool_name]
            try:
                result = await tool.execute(**args)
                return web.json_response({
                    "success": result.success,
                    "data": result.data,
                    "error": result.error,
                })
            except Exception as e:
                return web.json_response({"success": False, "error": str(e)}, status=500)
        
        # Parse natural language command for automation
        if command:
            return web.json_response({
                "success": True,
                "data": f"Automation command received: {command}",
                "note": "Natural language automation parsing not fully implemented",
            })
        
        return web.json_response({"error": "unknown command or tool"}, status=400)

    async def _handle_ws(self, request: Request) -> web.WebSocketResponse:
        if not self._authorized(request):
            return web.json_response({"error": "unauthorized: missing or invalid bridge token"}, status=401)
        
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        async with self._ws_lock:
            self._ws_clients.add(ws)
        
        try:
            # Send initial status
            await ws.send_json({
                "type": "status",
                "status": "connected",
                "service": "aqua-automation",
            })
            
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        msg_type = data.get("type")
                        if msg_type == "automation":
                            await self._stream_automation_ws(ws, data)
                        elif msg_type == "chat":
                            await self._stream_chat_ws(ws, data.get("message", ""))
                    except json.JSONDecodeError:
                        pass
                elif msg.type == web.WSMsgType.ERROR:
                    break
                elif msg.type == web.WSMsgType.CLOSE:
                    break
        except Exception:
            pass
        finally:
            async with self._ws_lock:
                self._ws_clients.discard(ws)
        
        return ws

    async def _stream_automation_ws(self, ws: web.WebSocketResponse, data: dict):
        """Stream automation tool execution with real-time events."""
        from core.agent.tools import ToolExecStart, ToolExecEnd
        
        command = data.get("command", "")
        tool_name = data.get("tool", "")
        args = data.get("args", {})
        delegation_id = data.get("delegation_id", "")
        
        if not command and not tool_name:
            await ws.send_json({"type": "error", "message": "missing command or tool"})
            return
        
        # Send started event
        await ws.send_json({
            "type": "automation_started",
            "delegation_id": delegation_id,
        })
        
        try:
            if tool_name and tool_name in AUTOMATION_TOOLS:
                tool = AUTOMATION_TOOLS[tool_name]
                
                await ws.send_json({
                    "type": "tool_start",
                    "tool": tool_name,
                    "args": tool_name,
                })
                
                result = await tool.execute(**args)
                
                await ws.send_json({
                    "type": "tool_end",
                    "tool": tool_name,
                    "result_preview": str(result.data)[:200] if result.data else "",
                    "success": result.success,
                    "error": result.error,
                })
                
                await ws.send_json({
                    "type": "automation_completed",
                    "status": "completed" if result.success else "failed",
                    "summary": str(result.data)[:200] if result.data else result.error,
                })
            else:
                # Natural language command - would parse and route to appropriate tool
                await ws.send_json({
                    "type": "automation_completed",
                    "status": "completed",
                    "summary": f"Automation command received: {command}",
                })
                
        except Exception as e:
            await ws.send_json({
                "type": "automation_failed",
                "error": str(e),
            })

    async def _stream_chat_ws(self, ws: web.WebSocketResponse, message: str):
        """Stream chat response (for compatibility with Luna bridge)."""
        await ws.send_json({
            "type": "chunk",
            "text": "Aqua automation mode. Use 'automation' type for automation commands."
        })
        await ws.send_json({"type": "done", "count": 1})

    async def _broadcast(self, data: dict):
        msg = json.dumps(data)
        async with self._ws_lock:
            clients = list(self._ws_clients)
        for client in clients:
            try:
                await client.send_str(msg)
            except Exception:
                pass

    @asynccontextmanager
    async def _lifespan(self, app: web.Application):
        yield
        async with self._ws_lock:
            for ws in self._ws_clients:
                await ws.close()
            self._ws_clients.clear()

    def create_app(self) -> web.Application:
        app = web.Application()
        app.cleanup_ctx.append(self._lifespan)
        
        app.router.add_get("/", self._handle_index)
        app.router.add_get("/health", self._handle_health)
        app.router.add_get("/status", self._handle_status)
        app.router.add_post("/api/automation", self._handle_api_automation)
        app.router.add_get("/ws", self._handle_ws)
        
        self._app = app
        return app

    async def start(self, host: str = "127.0.0.1", port: int = 8702):
        if host not in ("127.0.0.1", "localhost", "::1"):
            print(
                f"⚠  WARNING: binding to {host} exposes Aqua beyond this machine. "
                "Make sure a bridge token is set and that "
                "this port is firewalled from anything but Emma."
            )
        if not self.bridge_token:
            print(
                "⚠  WARNING: no bridge token configured. "
                "/api/automation and /ws are DISABLED until you set one."
            )

        app = self.create_app()
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, host, port)
        await self._site.start()
        print(f"Aqua Automation bridge listening on http://{host}:{port}")

    async def stop(self):
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()


async def start_server(bridge_token: str = "", host: str = "127.0.0.1", port: int = 8702):
    """Start the Aqua automation bridge server."""
    server = BridgeServer(bridge_token)
    await server.start(host, port)
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        await server.stop()