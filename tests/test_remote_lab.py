import unittest
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reborn" / "server"))
import offline_server
from remote_lab import RemoteLab, wire_str


class FakeConnection:
    def __init__(self, ip):
        self.addr = (ip, 40000)
        self.alive = True
        self.sent = []
    def send(self, message, payload):
        self.sent.append((message, payload))


class RemoteLabTests(unittest.TestCase):
    IP = "198.51.100.22"
    OTHER = "198.51.100.23"
    VERSION = "3.0.248.0"

    def setUp(self):
        self.now = 500
        self.lab = RemoteLab(True, self.IP, clock=lambda: self.now)

    def issue(self):
        ticket = self.lab.issue_login(self.IP, self.VERSION, "offline_player", "{}")
        self.assertTrue(ticket)
        return ticket

    def test_remote_disabled_by_default(self):
        self.assertIsNone(RemoteLab().issue_login(self.IP, self.VERSION, "offline_player", "{}"))
        with self.assertRaises(ValueError):
            RemoteLab(True, "0.0.0.0")
        with self.assertRaises(ValueError):
            RemoteLab(True, "127.0.0.1")

    def test_source_version_and_sdk_restrictions(self):
        for ip, version, sdk, auth in (
            (self.OTHER, self.VERSION, "offline_player", "{}"),
            (self.IP, "2.0.210.0", "offline_player", "{}"),
            (self.IP, self.VERSION, "someone_else", "{}"),
            (self.IP, self.VERSION, "offline_player", '{"token":"x"}'),
        ):
            self.assertIsNone(self.lab.issue_login(ip, version, sdk, auth))
        self.assertTrue(self.issue())

    def test_one_time_login_and_battle_handoff(self):
        login_ticket = self.issue()
        gate = FakeConnection(self.IP)
        self.assertFalse(self.lab.enter_gateway(gate, "wrong"))
        self.assertFalse(self.lab.enter_gateway(FakeConnection(self.OTHER), login_ticket))
        self.assertTrue(self.lab.enter_gateway(gate, login_ticket))
        self.assertFalse(self.lab.enter_gateway(FakeConnection(self.IP), login_ticket))
        self.assertIsNone(self.lab.issue_login(self.IP, self.VERSION, "offline_player", "{}"))
        battle_ticket = self.lab.issue_battle(gate)
        self.assertTrue(battle_ticket)
        battle = FakeConnection(self.IP)
        self.assertFalse(self.lab.enter_battle(battle, "invalid"))
        self.assertFalse(self.lab.enter_battle(FakeConnection(self.OTHER), battle_ticket))
        self.assertTrue(self.lab.enter_battle(battle, battle_ticket))
        self.assertFalse(self.lab.enter_battle(FakeConnection(self.IP), battle_ticket))
        self.lab.disconnect(gate)
        self.assertTrue(self.issue())

    def test_expired_tickets(self):
        ticket = self.issue()
        self.now += 61
        self.assertFalse(self.lab.enter_gateway(FakeConnection(self.IP), ticket))
        ticket2 = self.issue()
        gate = FakeConnection(self.IP)
        self.assertTrue(self.lab.enter_gateway(gate, ticket2))
        battle_ticket = self.lab.issue_battle(gate)
        self.now += 61
        self.assertFalse(self.lab.enter_battle(FakeConnection(self.IP), battle_ticket))

    def test_wire_str(self):
        self.assertEqual(wire_str(b'{}'), "{}")
        self.assertIsNone(wire_str(b'\xff'))
        self.assertIsNone(wire_str("x" * 257))

    def test_remote_login_handler_rejects_without_allowlist(self):
        msg = {"client_version": self.VERSION.encode(), "sdkuid": b"offline_player",
               "sauth_json": b"{}"}
        with patch.object(offline_server, "HOST", "0.0.0.0"), patch.object(offline_server, "REMOTE_LAB", self.lab):
            conn = FakeConnection(self.OTHER)
            offline_server.on_login_auth(conn, msg)
            self.assertFalse(conn.alive)
            self.assertEqual(conn.sent[0][1]["err_code"], 1)
            conn = FakeConnection(self.IP)
            offline_server.on_login_auth(conn, msg)
            self.assertEqual(conn.sent[0][1]["err_code"], 0)
            self.assertTrue(conn.sent[0][1]["auth_sn"])
            self.assertNotEqual(conn.sent[0][1]["auth_sn"], "offline_sn")

    def test_sensitive_wire_logging_redaction(self):
        payload = {"auth_sn": "secret", "sauth_json": b'{"token":"private"}',
                   "key": "game-key", "sdkuid": "offline_player"}
        cleaned = offline_server.redact_wire_data(payload)
        self.assertEqual(cleaned["auth_sn"], "[REDACTED]")
        self.assertEqual(cleaned["key"], "[REDACTED]")
        self.assertEqual(cleaned["sdkuid"], "offline_player")
        self.assertNotIn("private", str(cleaned))


if __name__ == "__main__":
    unittest.main()
