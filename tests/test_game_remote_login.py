"""Cross-account Steam game-ticket, lobby and battle integration tests."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reborn" / "server"))
from accounts import AccountStore
from game_identity import GameIdentity
from player_state import GameStates, ContextMapping, CURRENT_SESSION
import offline_server


class ConnectionStub:
    def __init__(self):
        self.alive = True
        self.addr = ("198.51.100.3", 40000)
        self.session_id = None
        self.sent = []

    def send(self, name, data=None):
        self.sent.append((name, data or {}))

    def payload(self, command):
        return next(v for n, v in self.sent if n == command)


class AccountToGameTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "accounts.sqlite3")
        self.ident = GameIdentity(self.db)
        self.state = GameStates(self.db, {})
        self.ident.accounts.register("AliceReborn", "a-strong-password-123")
        self.ident.accounts.register("BobReborn", "b-strong-password-456")
        self.patches = [
            patch.object(offline_server, "HOST", "0.0.0.0"),
            patch.object(offline_server, "MULTIUSER", True),
            patch.object(offline_server, "IDENTITY", self.ident),
            patch.object(offline_server, "STATES", self.state),
            patch.object(offline_server, "SAVE", ContextMapping(self.state, "save", {})),
            patch.object(offline_server, "GATE", ContextMapping(self.state, "gate", {})),
            patch.object(offline_server, "FIGHT_STATE", ContextMapping(self.state, "fight", {})),
        ]
        for change in self.patches:
            change.start()
        self.ctx = None

    def tearDown(self):
        if self.ctx is not None:
            CURRENT_SESSION.reset(self.ctx)
        for change in reversed(self.patches):
            change.stop()
        self.ident.close()
        self.state.db.close()
        self.tmp.cleanup()

    def new_ticket(self, username, password):
        bearer = self.ident.accounts.login(username, password)["token"]
        return self.ident.accounts.issue_game_login_ticket(bearer)["ticket"]

    def test_login_requires_real_verified_account_ticket(self):
        conn = ConnectionStub()
        offline_server.on_login_auth(conn, {"sauth_json": b"{}"})
        self.assertFalse(conn.alive)
        self.assertEqual(conn.payload("S_LOGIN_AUTH")["err_code"], 1)
        ticket = self.new_ticket("AliceReborn", "a-strong-password-123")
        conn = ConnectionStub()
        offline_server.on_login_auth(conn, {
            "sauth_json": json.dumps({"game_ticket": ticket}).encode("ascii"),
            "client_version": b"3.0.248.0"})
        self.assertEqual(conn.payload("S_LOGIN_AUTH")["err_code"], 0)
        self.assertNotEqual(conn.payload("S_LOGIN_AUTH")["auth_sn"], "offline_sn")
        self.assertEqual(conn.payload("S_LOGIN_AUTH")["aid"], 1)
        self.assertEqual(conn.payload("S_LOGIN_AUTH")["zone_list"][0]["gate_ip"], offline_server.ADVERTISE_HOST)
        again = ConnectionStub()
        offline_server.on_login_auth(again, {"sauth_json": json.dumps({"game_ticket": ticket}).encode()})
        self.assertEqual(again.payload("S_LOGIN_AUTH")["err_code"], 1)

    def test_gateway_battle_handoff_and_state_persistence(self):
        ticket = self.new_ticket("AliceReborn", "a-strong-password-123")
        login = ConnectionStub()
        offline_server.on_login_auth(login, {"sauth_json": json.dumps({"game_ticket": ticket}).encode()})
        gate_ticket = login.payload("S_LOGIN_AUTH")["auth_sn"]
        gate = ConnectionStub()
        self.ctx = CURRENT_SESSION.set(None)
        offline_server.on_login_enter(gate, {"auth_sn": gate_ticket.encode(), "uid": 0})
        self.assertTrue(gate.alive)
        self.assertEqual(gate.payload("S_AVATAR_GAME_PLAYER")["uid"], 100001)
        offline_server.on_start_match(gate, {"match_queues": [{"game_mode": 16, "team_modes": [1]}]})
        fight_ticket = gate.payload("S_GAME_SWITCH_TO_BATTLE")["login_key"]
        battle = ConnectionStub()
        self.assertIsNone(offline_server.IDENTITY.battle(b"not-a-real-ticket", battle))
        offline_server.on_fight_login(battle, {"uid": 100001, "login_key": fight_ticket.encode()})
        self.assertEqual(battle.payload("S_FIGHT_JOIN_FIGHT")["unit_id"], 100001)
        self.assertIsNone(offline_server.IDENTITY.battle(fight_ticket, ConnectionStub()))
        offline_server.SAVE["name"] = "Alice"
        offline_server.write_save(offline_server.SAVE)
        self.assertEqual(self.state.db.execute("SELECT count(*) FROM game_player_saves").fetchone()[0], 1)

    def test_two_players_cannot_cross_sessions(self):
        alice = self.new_ticket("AliceReborn", "a-strong-password-123")
        bob = self.new_ticket("BobReborn", "b-strong-password-456")
        a = self.ident.authenticate(json.dumps({"game_ticket": alice}))
        b = self.ident.authenticate(json.dumps({"game_ticket": bob}))
        self.assertEqual(a["account_id"], 1)
        self.assertEqual(b["account_id"], 2)
        self.state.attach(a["session_id"], 1, "Alice")
        self.state.attach(b["session_id"], 2, "Bob")
        with self.assertRaises(PermissionError):
            CURRENT_SESSION.set("unknown")
            offline_server.SAVE["name"]
        CURRENT_SESSION.set(a["session_id"])
        offline_server.SAVE["name"] = "Alice"
        offline_server.write_save(offline_server.SAVE)
        CURRENT_SESSION.set(b["session_id"])
        self.assertEqual(offline_server.SAVE["name"], "")
        self.assertEqual(offline_server.SAVE["uid"], 100002)
        offline_server.SAVE["name"] = "Bob"
        offline_server.write_save(offline_server.SAVE)
        self.assertEqual(self.state.db.execute("SELECT count(*) FROM game_player_saves").fetchone()[0], 2)
        self.ctx = CURRENT_SESSION.set(None)

    def test_expired_and_invalid_game_tickets(self):
        token = self.ident.accounts.login("BobReborn", "b-strong-password-456")["token"]
        issued = self.ident.accounts.issue_game_login_ticket(token)["ticket"]
        with patch("accounts.time.time", return_value=99999999999):
            self.assertIsNone(self.ident.accounts.consume_game_login_ticket(issued))
        self.assertIsNone(self.ident.authenticate("not JSON"))
        self.assertIsNone(self.ident.authenticate('{"game_ticket": 12}'))


if __name__ == "__main__":
    unittest.main()
