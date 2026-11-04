"""Steam Reborn local network bridge: verified accounts with unchanged switches.nxs.

The existing PC mod sends sauth_json={} for every player. This loopback-only
bridge replaces ONLY that login field with a fresh one-use ticket issued from
the HTTPS account API and rewrites discovered game addresses to localhost.
The original game binary and precompiled switches.nxs remain unchanged.

Usage:
  python reborn/tools/steam_bridge.py --game-server 75.119.148.51 \
      --auth-url https://YOUR-AUTH-DOMAIN --username YOUR_REBORN_ACCOUNT

Before starting, run patch_server.py --game-dir . --server-ip 127.0.0.1.
Do not run the old local offline server on the same ports.
"""
import argparse
import getpass
import http.server
import ipaddress
import json
import socket
import ssl
import socketserver
import subprocess
import struct
import sys
import threading
from pathlib import Path
from urllib.parse import urlsplit
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

SERVER_CODE = Path(__file__).resolve().parents[1] / "server"
sys.path.insert(0, str(SERVER_CODE))
from nexproto import Protocol  # noqa: E402

LOOPBACK = "127.0.0.1"
PORTS = (4000, 4001, 4002)
DISCOVERY_PATHS = frozenset((
    "loginlist_rel_pc_na.txt", "loginlist_rel_steam_na.txt",
    "loginlist_rel_na.txt", "loginlist.txt",
    "client_zonelist_rel_pc_na.txt", "client_zonelist_rel_steam_na.txt",
    "client_zonelist_rel_na.txt", "client_zonelist.txt",
))
PROTO = Protocol(str(SERVER_CODE / "data" / "protocol.json"))


class RefuseRedirect(HTTPRedirectHandler):
    """Do not forward account credentials to a redirected origin or HTTP URL."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected redirect from Reborn account API")


ACCOUNT_OPENER = build_opener(RefuseRedirect)



class AccountLogin:
    def __init__(self, url, username, password):
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("Account API URL must be HTTPS without credentials")
        self.url = url.rstrip("/")
        self.username = username
        self.lock = threading.Lock()
        response = self.post("/v1/login", {
            "username": username, "password": password,
        })
        self.bearer = response["token"]
        if not isinstance(self.bearer, str) or len(self.bearer) < 32:
            raise ValueError("Account API did not return a valid bearer token")

    def post(self, path, data, headers=None):
        body = json.dumps(data).encode("utf-8")
        req = Request(self.url + path, data=body, headers={
            "Content-Type": "application/json", **(headers or {}),
        }, method="POST")
        try:
            with ACCOUNT_OPENER.open(req, timeout=15) as resp:
                return json.loads(resp.read(8192))
        except HTTPError as exc:
            raise ValueError("Account API returned HTTP %d" % exc.code) from exc

    def issue_ticket(self):
        with self.lock:
            reply = self.post("/v1/game-ticket", {},
                              {"Authorization": "Bearer " + self.bearer})
            ticket = reply.get("ticket")
            if not isinstance(ticket, str) or not 32 <= len(ticket) <= 256:
                raise ValueError("Account API did not return a one-use game ticket")
            return ticket


def rewrite_frame(frame, direction, port, account, proto=PROTO):
    """Rewrite only the three known game commands; pass all others verbatim."""
    if len(frame) < 5 or struct.unpack_from("<H", frame)[0] != len(frame):
        raise ValueError("Malformed game protocol frame")
    if direction == "client" and port == 4000:
        name, _, _, body = proto.decode(frame[2:], "C")
        if name == "C_LOGIN_AUTH":
            body["sauth_json"] = json.dumps({
                "game_ticket": account.issue_ticket(),
            }, separators=(",", ":"))
            return proto.encode(name, body)
    if direction == "server" and port == 4000:
        name, _, _, body = proto.decode(frame[2:], "S")
        if name == "S_LOGIN_AUTH" and body and body.get("err_code") == 0:
            for zone in body.get("zone_list", []):
                zone["gate_ip"] = LOOPBACK
            return proto.encode(name, body)
    if direction == "server" and port == 4001:
        name, _, _, body = proto.decode(frame[2:], "S")
        if name == "S_GAME_SWITCH_TO_BATTLE" and body:
            body["ip"] = LOOPBACK
            return proto.encode(name, body)
    return frame


def recv_exact(sock, count):
    out = bytearray()
    while len(out) < count:
        chunk = sock.recv(count - len(out))
        if not chunk:
            raise EOFError("TCP connection closed")
        out.extend(chunk)
    return bytes(out)


def pump(source, destination, direction, port, account):
    try:
        while True:
            header = recv_exact(source, 2)
            frame_size = struct.unpack("<H", header)[0]
            if frame_size < 5 or frame_size > 65535:
                raise ValueError("Invalid game frame length")
            frame = header + recv_exact(source, frame_size - 2)
            outgoing = rewrite_frame(frame, direction, port, account)
            destination.sendall(outgoing)
    except (EOFError, ConnectionError, OSError):
        pass
    except Exception as exc:
        # Never log packet payload, passwords, tokens or handoff tickets.
        print("[bridge:%d] %s error: %s" %
              (port, direction, type(exc).__name__), flush=True)
    finally:
        try:
            destination.shutdown(socket.SHUT_WR)
        except OSError:
            pass


class TcpBridge(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
    request_queue_size = 32


def tcp_handler(port, host, account, tls_hostname):
    tls_context = ssl.create_default_context()

    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            try:
                raw = socket.create_connection((host, port), timeout=10)
                # Certificate verification is mandatory: never use CERT_NONE.
                with tls_context.wrap_socket(raw, server_hostname=tls_hostname) as remote:
                    remote.settimeout(None)
                    self.request.settimeout(None)
                    outbound = threading.Thread(
                        target=pump, args=(self.request, remote, "client", port, account),
                        daemon=True)
                    outbound.start()
                    pump(remote, self.request, "server", port, account)
                    outbound.join(timeout=2)
            except (OSError, ValueError) as exc:
                print("[bridge:%d] failed: %s" % (port, type(exc).__name__), flush=True)
    return Handler


def discovery_handler(host):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            file_name = self.path.split("?", 1)[0].rsplit("/", 1)[-1]
            if file_name not in DISCOVERY_PATHS:
                self.send_error(404)
                return
            try:
                with urlopen("http://%s:8000/%s" % (host, file_name), timeout=8) as remote:
                    body = remote.read(4096).decode("utf-8")
                if file_name.startswith("loginlist"):
                    rows = body.splitlines()
                    if len(rows) != 1 or len(rows[0].split()) != 3:
                        raise ValueError("Unexpected login-list response")
                    parts = rows[0].split()
                    parts[1] = LOOPBACK
                    body = " ".join(parts) + "\n"
                encoded = body.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(encoded)
            except (OSError, UnicodeDecodeError, ValueError):
                self.send_error(502, "VPS discovery service unavailable")

        def log_message(self, fmt, *args):
            pass
    return Handler


def validate_game_host(value):
    """Accept a DNS-only game hostname or a public/VPN IPv4, never a URL."""
    import re
    if not isinstance(value, str):
        raise ValueError("Game host must be a DNS hostname or IPv4")
    value = value.strip().rstrip(".").lower()
    if not value or len(value) > 253 or ":" in value or "/" in value or "@" in value:
        raise ValueError("Invalid game host")
    try:
        ip = ipaddress.IPv4Address(value)
        if ip.is_loopback or ip.is_unspecified or ip.is_multicast:
            raise ValueError("Invalid game server IP")
        return str(ip)
    except ipaddress.AddressValueError:
        pass
    labels = value.split(".")
    if len(labels) < 2 or any(
        not 1 <= len(label) <= 63 or
        not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label)
        for label in labels
    ):
        raise ValueError("Invalid DNS game hostname")
    return value


def run(host, account, tls_hostname, game_executable=None):
    servers = []
    try:
        for port in PORTS:
            srv = TcpBridge((LOOPBACK, port), tcp_handler(port, host, account, tls_hostname))
            servers.append(srv)
        web = http.server.ThreadingHTTPServer((LOOPBACK, 8000),
                                              discovery_handler(host))
        servers.append(web)
        for srv in servers:
            threading.Thread(target=srv.serve_forever, daemon=True).start()
        print("Reborn bridge ready: localhost:8000, 4000, 4001, 4002")
        print("VPS: %s | account: %s" % (host, account.username))
        if game_executable is not None:
            print("Starting Creative Destruction with the authenticated bridge...")
            game = subprocess.Popen([str(game_executable)], cwd=str(Path(game_executable).parent))
            game.wait()
            print("Game exited; closing local bridge.")
        else:
            print("Start Creative Destruction and select the server. Ctrl+C to stop.")
            threading.Event().wait()
    finally:
        for srv in servers:
            srv.shutdown()
            srv.server_close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-server", required=True, help="VPS DNS hostname or IPv4 address")
    parser.add_argument("--auth-url", required=True, help="HTTPS Reborn account API")
    parser.add_argument("--username", required=True, help="Your Reborn account username")
    parser.add_argument("--game-tls-hostname", required=True,
                        help="DNS name on the VPS game TLS certificate (verified)")
    args = parser.parse_args()
    host = validate_game_host(args.game_server)
    tls_name = args.game_tls_hostname.strip()
    if not tls_name or len(tls_name) > 253 or "://" in tls_name or "/" in tls_name:
        parser.error("Invalid TLS hostname")
    if host in ("localhost", "127.0.0.1", "0.0.0.0"):
        parser.error("VPS address must not be localhost")
    try:
        password = getpass.getpass("Reborn account password: ")
        account = AccountLogin(args.auth_url, args.username, password)
        password = None
        run(host, account, tls_name)
    except (ValueError, OSError, URLError) as exc:
        parser.exit(1, "Bridge startup failed: %s\n" % type(exc).__name__)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
