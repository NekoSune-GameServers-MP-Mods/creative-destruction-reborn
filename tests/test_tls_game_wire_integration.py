"""Real TLS socket integration: account ticket -> login -> gateway -> battle.

Runs only where openssl exists; verifies the running server's actual frame
encoding and TLS handshake, not just direct Python handler functions.
"""
import json
import os
import shutil
import socket
import ssl
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "reborn" / "server"
sys.path.insert(0, str(SERVER))
from accounts import AccountStore
from nexproto import Protocol

PROTO = Protocol(str(SERVER / "data" / "protocol.json"))


def read_exact(sock, n):
    result = bytearray()
    while len(result) < n:
        chunk = sock.recv(n - len(result))
        if not chunk:
            raise EOFError("socket closed before complete wire frame")
        result.extend(chunk)
    return bytes(result)


def receive(sock):
    size = struct.unpack("<H", read_exact(sock, 2))[0]
    if not 5 <= size <= 65535:
        raise AssertionError("invalid server packet")
    return PROTO.decode(read_exact(sock, size - 2), "S")


@unittest.skipUnless(shutil.which("openssl"), "needs openssl to generate a temporary TLS cert")
class RealGameTlsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.cert = self.folder / "cert.pem"
        self.key = self.folder / "key.pem"
        subprocess.run([
            "openssl", "req", "-newkey", "rsa:2048", "-x509", "-nodes",
            "-days", "1", "-keyout", str(self.key), "-out", str(self.cert),
            "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        self.db = str(self.folder / "accounts.sqlite3")
        store = AccountStore(self.db)
        store.register("WirePlayer", "strong-wire-password-123")
        bearer = store.login("WirePlayer", "strong-wire-password-123")["token"]
        self.ticket = store.issue_game_login_ticket(bearer)["ticket"]
        store.close()
        env = dict(os.environ, CDR_BIND_HOST="0.0.0.0",
                   CDR_ALLOW_REMOTE="1", CDR_ADVERTISE_HOST="127.0.0.1",
                   CDR_MULTIUSER_ENABLED="1", CDR_ACCOUNT_DB=self.db,
                   CDR_GAME_TLS_CERT=str(self.cert), CDR_GAME_TLS_KEY=str(self.key))
        self.process = subprocess.Popen(
            [sys.executable, "offline_server.py"], cwd=str(SERVER),
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.context = ssl.create_default_context(cafile=str(self.cert))
        self.sockets = []
        for attempt in range(40):
            if self.process.poll() is not None:
                raise AssertionError("server exited during startup")
            try:
                test_sock = self.connect(4000)
                self.sockets.append(test_sock)
                receive(test_sock)  # encryption-seed greeting
                break
            except (OSError, EOFError):
                time.sleep(0.1)
        else:
            raise AssertionError("TLS server did not start")

    def tearDown(self):
        for sock in getattr(self, "sockets", []):
            sock.close()
        if hasattr(self, "process"):
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.temp.cleanup()

    def connect(self, port):
        raw = socket.create_connection(("127.0.0.1", port), timeout=3)
        try:
            sock = self.context.wrap_socket(raw, server_hostname="localhost")
            sock.settimeout(3)
            return sock
        except Exception:
            raw.close()
            raise

    def send(self, sock, name, data):
        sock.sendall(PROTO.encode(name, data))

    def until(self, sock, wanted, maximum=8):
        for _ in range(maximum):
            name, _, _, body = receive(sock)
            if name == wanted:
                return body
        raise AssertionError("did not receive " + wanted)

    def test_actual_tls_verified_login_to_battle(self):
        login = self.sockets[0]
        self.send(login, "C_LOGIN_AUTH", {
            "sauth_json": json.dumps({"game_ticket": self.ticket}),
            "sdkuid": "offline_player",
            "platform": "win32", "client_version": "3.0.248.0"})
        auth = self.until(login, "S_LOGIN_AUTH")
        self.assertEqual(auth["err_code"], 0)
        self.assertEqual(auth["aid"], 1)
        self.assertNotEqual(auth["auth_sn"], b"offline_sn")
        self.assertEqual(auth["zone_list"][0]["gate_port"], 4001)

        # A reused short-lived code cannot become a second authenticated player.
        replay = self.connect(4000)
        self.sockets.append(replay)
        receive(replay)
        self.send(replay, "C_LOGIN_AUTH", {"sauth_json": json.dumps({"game_ticket": self.ticket})})
        self.assertEqual(self.until(replay, "S_LOGIN_AUTH")["err_code"], 1)

        gate = self.connect(4001)
        self.sockets.append(gate)
        self.until(gate, "S_LOGIN_JOIN_QUEUE")
        self.send(gate, "C_LOGIN_ENTER", {"auth_sn": auth["auth_sn"], "uid": 0})
        entered = self.until(gate, "S_AVATAR_GAME_PLAYER")
        self.assertEqual(entered["uid"], 100001)
        self.send(gate, "C_GAME_START_MATCH2",
                  {"match_queues": [{"game_mode": 16, "team_modes": [1]}]})
        transfer = self.until(gate, "S_GAME_SWITCH_TO_BATTLE")
        self.assertEqual(transfer["tcp_port"], 4002)
        self.assertNotEqual(transfer["login_key"], b"offline_battle")

        battle = self.connect(4002)
        self.sockets.append(battle)
        receive(battle)
        self.send(battle, "C_FIGHT_REQ_LOGIN",
                  {"uid": 100001, "login_key": transfer["login_key"]})
        joined = self.until(battle, "S_FIGHT_JOIN_FIGHT")
        self.assertEqual(joined["unit_id"], 100001)


if __name__ == "__main__":
    unittest.main()
