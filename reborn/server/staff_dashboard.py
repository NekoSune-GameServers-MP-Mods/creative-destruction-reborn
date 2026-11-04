"""Read-only authenticated operations dashboard. Expose via SSH tunnel ONLY."""
import hmac
import json
import os
from pathlib import Path
import secrets
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
PORT = int(os.getenv("CDR_STAFF_PORT", "8088"))
HOST = os.getenv("CDR_STAFF_BIND", "127.0.0.1")
TOKEN = os.getenv("CDR_STAFF_TOKEN", "")
MAX_LOG = 100
HTML = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Creative Destruction • Staff</title><style>
:root{font:16px system-ui;background:#101725;color:#f5f7fb;color-scheme:dark}
body{max-width:960px;margin:auto;padding:2rem}h1{color:#a4c7ff}section{background:#1d2b42;padding:1.2rem;border-radius:12px;margin:1rem 0}
input,button{padding:.7rem;border-radius:8px;background:#293d59;color:white;border:1px solid #6c8cba}
button{cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px ui-monospace}small{color:#aebed5}
</style><h1>Creative Destruction · Staff</h1><small>Read-only development dashboard • Access over SSH tunnel only</small>
<section><label>Admin token <input id="token" type="password" autocomplete="off"></label>
<button id="load">Refresh status</button><button id="clear">Clear token</button><p id="status">Not connected</p></section>
<section><h2>Service</h2><pre id="health">—</pre></section><section><h2>Local player snapshot</h2><pre id="player">—</pre></section>
<section><h2>Recent server log</h2><pre id="logs">—</pre></section>
<script>
let token = "";
const el=id=>document.getElementById(id);
el("load").onclick=async()=>{
 token=el("token").value;el("token").value="";
 el("status").textContent="Loading…";
 try{
  for(const [path,id] of [["/api/health","health"],["/api/player","player"],["/api/logs","logs"]]){
   const response=await fetch(path,{headers:{"Authorization":"Bearer "+token},cache:"no-store"});
   if(!response.ok)throw Error("HTTP "+response.status+" on "+path);
   el(id).textContent=JSON.stringify(await response.json(),null,2);
  }el("status").textContent="Connected (read-only)";
 }catch(e){el("status").textContent="Request failed: "+e.message;}
};
el("clear").onclick=()=>{token="";el("token").value="";el("status").textContent="Token cleared"};
</script></html>"""

def require_token():
    if len(TOKEN) < 32:
        raise ValueError("CDR_STAFF_TOKEN must contain at least 32 characters")
    if not (1 <= PORT <= 65535):
        raise ValueError("Invalid staff port")
    if HOST not in ("127.0.0.1", "0.0.0.0"):
        raise ValueError("CDR_STAFF_BIND must be 127.0.0.1 or 0.0.0.0")

def read_logs():
    path = ROOT / "logs" / "server.log"
    if not path.is_file():
        return []
    # Read only the last 64 KiB to avoid unbounded memory use.
    with path.open("rb") as f:
        f.seek(0, 2)
        size = f.tell()
        f.seek(max(0, size - 65536))
        raw = f.read()
    return raw.decode("utf-8", "replace").splitlines()[-MAX_LOG:]

class Handler(BaseHTTPRequestHandler):
    server_version = "CDRStaff/0.1"
    def reply(self, code, payload, content_type="application/json; charset=utf-8"):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/":
            return self.reply(200, HTML.encode(), "text/html; charset=utf-8")
        if path not in ("/api/health", "/api/player", "/api/logs"):
            return self.reply(404, {"error": "not found"})
        auth = self.headers.get("Authorization", "")
        if not hmac.compare_digest(auth, "Bearer " + TOKEN):
            return self.reply(401, {"error": "unauthorized"})
        if path == "/api/health":
            return self.reply(200, {"status": "dashboard running", "server_state": "not verified", "time": int(time.time()), "mode": "private-development"})
        if path == "/api/player":
            try:
                data = json.loads((ROOT / "save" / "player.json").read_text(encoding="utf-8"))
                safe = {k: data.get(k) for k in ("uid", "name", "gender") if k in data}
            except (OSError, ValueError):
                safe = None
            return self.reply(200, {"player": safe, "warning": "Shared single-player save, not multiplayer accounts"})
        return self.reply(200, {"lines": read_logs()})
    def do_POST(self):
        return self.reply(405, {"error": "read only"})
    def log_message(self, fmt, *args):
        pass

def main():
    require_token()
    print("Staff dashboard on %s:%s (SSH tunnel only)" % (HOST, PORT), flush=True)
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    httpd.daemon_threads = True
    httpd.serve_forever()

if __name__ == "__main__":
    main()
