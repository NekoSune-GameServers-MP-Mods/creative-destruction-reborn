"""Private multi-VPS node registry for operators; not a multiplayer router."""
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

NODE_ID_RE = re.compile(r"^[a-z][a-z0-9-]{2,39}$")
TOKEN_HEADER = "X-CDR-Node-Key"
HEARTBEAT_TTL = 90
MAX_NODES = 100
MAX_BODY = 2048


def valid_ip(value):
    try:
        ip = ipaddress.ip_address(value)
        return ip.version == 4 and not (ip.is_unspecified or ip.is_multicast or ip.is_loopback)
    except ValueError:
        return False


class NodeRegistry:
    def __init__(self, path, clock=None):
        self.clock = clock or time.time
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=10)
        self.db.row_factory = sqlite3.Row
        with self.db:
            self.db.execute("""CREATE TABLE IF NOT EXISTS cluster_nodes (
                node_id TEXT PRIMARY KEY,
                region TEXT NOT NULL,
                advertised_ip TEXT NOT NULL,
                secret_hash BLOB NOT NULL,
                created_at INTEGER NOT NULL,
                last_seen INTEGER,
                game_reachable INTEGER NOT NULL DEFAULT 0
            )""")

    @staticmethod
    def _digest(raw):
        return hashlib.sha256(raw.encode("ascii")).digest()

    def register(self, node_id, region, advertised_ip):
        if not isinstance(node_id, str) or not NODE_ID_RE.fullmatch(node_id):
            raise ValueError("node_id must be 3-40 lowercase letters, numbers or hyphens")
        if not isinstance(region, str) or not 1 <= len(region) <= 32 or not re.fullmatch(r"[A-Za-z0-9_-]+", region):
            raise ValueError("Invalid region")
        if not isinstance(advertised_ip, str) or not valid_ip(advertised_ip):
            raise ValueError("Invalid advertised IPv4")
        key = secrets.token_urlsafe(48)
        now = int(self.clock())
        with self.lock, self.db:
            if self.db.execute("SELECT count(*) FROM cluster_nodes").fetchone()[0] >= MAX_NODES:
                raise ValueError("Cluster node capacity reached")
            try:
                self.db.execute(
                    "INSERT INTO cluster_nodes(node_id,region,advertised_ip,secret_hash,created_at) VALUES(?,?,?,?,?)",
                    (node_id, region, advertised_ip, self._digest(key), now),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("Node ID already exists") from exc
        return {"node_id": node_id, "node_key": key}

    def heartbeat(self, node_id, key, game_reachable):
        if not isinstance(node_id, str) or not NODE_ID_RE.fullmatch(node_id):
            return False
        if not isinstance(key, str) or not 32 <= len(key) <= 256 or not key.isascii():
            return False
        if type(game_reachable) is not bool:
            return False
        with self.lock, self.db:
            row = self.db.execute("SELECT secret_hash FROM cluster_nodes WHERE node_id=?", (node_id,)).fetchone()
            if row is None or not hmac.compare_digest(self._digest(key), row["secret_hash"]):
                return False
            self.db.execute("UPDATE cluster_nodes SET last_seen=?,game_reachable=? WHERE node_id=?",
                            (int(self.clock()), int(game_reachable), node_id))
            return True

    def list_nodes(self):
        now = int(self.clock())
        with self.lock:
            rows = self.db.execute("SELECT node_id,region,advertised_ip,created_at,last_seen,game_reachable FROM cluster_nodes ORDER BY node_id").fetchall()
        return [{"node_id": r["node_id"], "region": r["region"], "advertised_ip": r["advertised_ip"],
                 "last_seen": r["last_seen"],
                 "status": "reachable" if r["last_seen"] is not None and now-r["last_seen"] <= HEARTBEAT_TTL and r["game_reachable"] else "unavailable",
                 "note": "TCP reachability only; gameplay login not verified"} for r in rows]

    def delete(self, node_id):
        with self.lock, self.db:
            return self.db.execute("DELETE FROM cluster_nodes WHERE node_id=?", (node_id,)).rowcount > 0

    def close(self):
        self.db.close()


def handler_factory(registry, admin_token):
    class Handler(BaseHTTPRequestHandler):
        server_version = "CDRCluster/0.1"

        def reply(self, status, payload):
            raw = json.dumps(payload, separators=(",", ":")).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(raw)

        def admin(self):
            value = self.headers.get("Authorization", "")
            return len(admin_token) >= 32 and hmac.compare_digest(value, "Bearer " + admin_token)

        def read_json(self):
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                raise ValueError("JSON required")
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError as exc:
                raise ValueError("Invalid size") from exc
            if not 0 < size <= MAX_BODY:
                raise ValueError("Request too large or empty")
            obj = json.loads(self.rfile.read(size))
            if not isinstance(obj, dict):
                raise ValueError("JSON object required")
            return obj

        def do_GET(self):
            if self.path != "/v1/cluster/nodes":
                return self.reply(404, {"error": "not_found"})
            if not self.admin():
                return self.reply(401, {"error": "unauthorized"})
            return self.reply(200, {"nodes": registry.list_nodes(), "game_login_enabled": False})

        def do_POST(self):
            if self.path not in ("/v1/cluster/nodes", "/v1/cluster/heartbeat", "/v1/cluster/remove"):
                return self.reply(404, {"error": "not_found"})
            if self.path != "/v1/cluster/heartbeat" and not self.admin():
                return self.reply(401, {"error": "unauthorized"})
            try:
                data = self.read_json()
            except (ValueError, UnicodeError):
                return self.reply(400, {"error": "invalid_request"})
            if self.path == "/v1/cluster/heartbeat":
                if not registry.heartbeat(data.get("node_id"), self.headers.get(TOKEN_HEADER, ""), data.get("game_reachable")):
                    return self.reply(401, {"error": "unauthorized"})
                return self.reply(200, {"ok": True})
            if self.path == "/v1/cluster/remove":
                node_id = data.get("node_id")
                if not isinstance(node_id, str):
                    return self.reply(400, {"error": "invalid_node"})
                return self.reply(200, {"removed": registry.delete(node_id)})
            try:
                result = registry.register(data.get("node_id"), data.get("region"), data.get("advertised_ip"))
            except ValueError as exc:
                return self.reply(400, {"error": str(exc)})
            return self.reply(201, result)

        def log_message(self, fmt, *args):
            pass
    return Handler


def main():
    host = os.getenv("CDR_CLUSTER_BIND", "127.0.0.1")
    port = int(os.getenv("CDR_CLUSTER_PORT", "8092"))
    token = os.getenv("CDR_CLUSTER_ADMIN_TOKEN", "")
    if host not in ("127.0.0.1", "0.0.0.0") or host == "0.0.0.0" and os.getenv("CDR_CLUSTER_ALLOW_CONTAINER") != "1":
        raise ValueError("Cluster API may only bind to localhost or an explicitly isolated container interface")
    if len(token) < 32 or not 1 <= port <= 65535:
        raise ValueError("Strong CDR_CLUSTER_ADMIN_TOKEN and valid port required")
    path = os.getenv("CDR_CLUSTER_DB", os.path.join(os.path.dirname(__file__), "save", "cluster.sqlite3"))
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    registry = NodeRegistry(path)
    server = ThreadingHTTPServer((host, port), handler_factory(registry, token))
    server.daemon_threads = True
    print("Private cluster registry listening on %s:%d" % (host, port), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        registry.close()


if __name__ == "__main__":
    main()
