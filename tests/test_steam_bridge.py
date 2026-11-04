"""Steam client bridge packet rewrite regression tests.

These operate on actual framed NeoX protocol messages, not mocked dictionaries.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reborn" / "tools"))
from steam_bridge import rewrite_frame, PROTO, LOOPBACK


class StubAccount:
    def __init__(self):
        self.count = 0
    def issue_ticket(self):
        self.count += 1
        return "a" * 64


class SteamBridgeTests(unittest.TestCase):
    def test_login_rewrites_only_auth_payload_and_fetches_fresh_ticket(self):
        account = StubAccount()
        original = PROTO.encode("C_LOGIN_AUTH", {
            "sauth_json": "{}", "sdkuid": "offline_player",
            "platform": "win32", "client_version": "3.0.248.0",
        })
        updated = rewrite_frame(original, "client", 4000, account)
        name, _, _, decoded = PROTO.decode(updated[2:], "C")
        self.assertEqual(name, "C_LOGIN_AUTH")
        self.assertEqual(json.loads(decoded["sauth_json"])["game_ticket"], "a" * 64)
        self.assertEqual(decoded["sdkuid"], b"offline_player")
        self.assertEqual(account.count, 1)
        self.assertEqual(rewrite_frame(original, "client", 4001, account), original)
        self.assertEqual(account.count, 1)

    def test_steam_success_redirects_gateway_to_localhost(self):
        account = StubAccount()
        message = PROTO.encode("S_LOGIN_AUTH", {
            "err_code": 0,
            "auth_sn": "one-use-gateway-ticket",
            "zone_list": [
                {"zone_id": 1, "gate_hostid": 1, "gate_ip": "75.119.148.51",
                 "gate_port": 4001, "role_uid": 100001}],
            "aid": 1,
        })
        result = rewrite_frame(message, "server", 4000, account)
        name, _, _, decoded = PROTO.decode(result[2:], "S")
        self.assertEqual(name, "S_LOGIN_AUTH")
        self.assertEqual(decoded["zone_list"][0]["gate_ip"], LOOPBACK.encode())
        self.assertEqual(decoded["zone_list"][0]["gate_port"], 4001)
        self.assertEqual(decoded["auth_sn"], b"one-use-gateway-ticket")
        self.assertEqual(account.count, 0)

    def test_battle_handoff_redirects_to_localhost(self):
        account = StubAccount()
        message = PROTO.encode("S_GAME_SWITCH_TO_BATTLE", {
            "ip": "75.119.148.51", "port": 4003,
            "login_key": "one-use-battle-ticket", "tcp_port": 4002})
        result = rewrite_frame(message, "server", 4001, account)
        name, _, _, decoded = PROTO.decode(result[2:], "S")
        self.assertEqual(name, "S_GAME_SWITCH_TO_BATTLE")
        self.assertEqual(decoded["ip"], LOOPBACK.encode())
        self.assertEqual(decoded["login_key"], b"one-use-battle-ticket")
        self.assertEqual(decoded["tcp_port"], 4002)

    def test_unknown_unmodified_frames_and_bad_lengths(self):
        account = StubAccount()
        message = PROTO.encode("S_SYS_GAME_ENCRYPT_SEED", {
            "need_encrypt": 0, "in_seed": 0, "out_seed": 0,
            "need_handshake": 0})
        self.assertEqual(rewrite_frame(message, "server", 4000, account), message)
        with self.assertRaises(ValueError):
            rewrite_frame(b"\x02\x00", "client", 4000, account)


if __name__ == "__main__":
    unittest.main()
