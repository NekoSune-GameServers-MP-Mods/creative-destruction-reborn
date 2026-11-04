"""Private, authenticated registration and login API. Bind to loopback for SSH tunnels."""
import hmac
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from accounts import AccountStore, AuthError

DB_PATH = os.getenv("CDR_ACCOUNT_DB", os.path.join(os.path.dirname(__file__), "save", "accounts.sqlite3"))
HOST = os.getenv("CDR_AUTH_BIND", "127.0.0.1")
PORT = int(os.getenv("CDR_AUTH_PORT", "8090"))
REGISTER_KEY = os.getenv("CDR_REGISTRATION_KEY", "")
_RATE_LOCK = threading.Lock()
_RATE_BUCKETS = {}
MAX_ATTEMPTS = 6
RATE_WINDOW = 300

def allow_attempt(key):
    now = time.monotonic()
    with _RATE_LOCK:
        if len(_RATE_BUCKETS) > 10000:
            for k, data in list(_RATE_BUCKETS.items()):
                if data[1] + RATE_WINDOW < now:
                    del _RATE_BUCKETS[k]
        count, first = _RATE_BUCKETS.get(key, (0, now))
        if first + RATE_WINDOW < now:
            count, first = 0, now
        if count >= MAX_ATTEMPTS:
            return False
        _RATE_BUCKETS[key] = (count + 1, first)
        return True

def reset_attempts(key):
    with _RATE_LOCK:
        _RATE_BUCKETS.pop(key, None)

def bearer(headers):
    value = headers.get("Authorization", "")
    if not value.startswith("Bearer ") or len(value) > 280:
        return ""
    return value[7:]

def handler_factory(store):
    class Handler(BaseHTTPRequestHandler):
        server_version = "CDRAuth/0.1"
        def reply(self, code, value):
            raw = json.dumps(value).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self):
            if self.path not in ("/v1/register", "/v1/login", "/v1/logout", "/v1/game-ticket"):
                return self.reply(404, {"error": "not_found"})
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                return self.reply(415, {"error": "json_required"})
            try:
                n = int(self.headers.get("Content-Length", "0"))
                if not 0 < n <= 4096:
                    return self.reply(413, {"error": "invalid_request_size"})
                data = json.loads(self.rfile.read(n))
                if not isinstance(data, dict):
                    return self.reply(400, {"error": "invalid_json"})
            except (ValueError, UnicodeDecodeError):
                return self.reply(400, {"error": "invalid_json"})
            if self.path == "/v1/logout":
                token = bearer(self.headers)
                if not store.resolve(token):
                    return self.reply(401, {"error": "unauthorized"})
                store.revoke(token)
                return self.reply(200, {"ok": True})
            if self.path == "/v1/game-ticket":
                if not allow_attempt(("game-ticket", self.client_address[0])):
                    return self.reply(429, {"error": "rate_limited"})
                try:
                    issued = store.issue_game_login_ticket(bearer(self.headers))
                except AuthError:
                    return self.reply(401, {"error": "unauthorized"})
                return self.reply(200, issued)
            if self.path == "/v1/register":
                if not allow_attempt(("register", self.client_address[0])):
                    return self.reply(429, {"error": "rate_limited"})
                submitted = self.headers.get("X-Registration-Key", "")
                if len(REGISTER_KEY) < 32 or not hmac.compare_digest(submitted, REGISTER_KEY):
                    return self.reply(403, {"error": "registration_disabled"})
                try:
                    account = store.register(data.get("username"), data.get("password"))
                    return self.reply(201, {"account": account})
                except AuthError as exc:
                    return self.reply(400, {"error": str(exc)})
            rate_key = ("login", self.client_address[0], str(data.get("username", "")).lower()[:32])
            if not allow_attempt(rate_key):
                return self.reply(429, {"error": "rate_limited"})
            try:
                payload = store.login(data.get("username"), data.get("password"))
                reset_attempts(rate_key)
                return self.reply(200, payload)
            except AuthError:
                return self.reply(401, {"error": "invalid_credentials"})

        def do_GET(self):
            if self.path != "/v1/me":
                return self.reply(404, {"error": "not_found"})
            account = store.resolve(bearer(self.headers))
            return self.reply(200, {"account": account}) if account else self.reply(401, {"error": "unauthorized"})

        def log_message(self, fmt, *args):
            pass
    return Handler

def main():
    if HOST != "127.0.0.1" and not (HOST == "0.0.0.0" and os.getenv("CDR_AUTH_ALLOW_CONTAINER") == "1"):
        raise ValueError("Auth API may bind only localhost or isolated Docker interface")
    if REGISTER_KEY and len(REGISTER_KEY) < 32:
        raise ValueError("CDR_REGISTRATION_KEY must contain at least 32 characters")
    if not 1 <= PORT <= 65535:
        raise ValueError("Invalid port")
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    store = AccountStore(DB_PATH)
    server = ThreadingHTTPServer((HOST, PORT), handler_factory(store))
    server.daemon_threads = True
    server.request_queue_size = 16
    print("Account API running on %s:%d (private only)" % (HOST, PORT), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        store.close()

if __name__ == "__main__":
    main()
