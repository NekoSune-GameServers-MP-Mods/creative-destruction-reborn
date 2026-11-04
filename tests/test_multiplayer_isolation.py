"""Verify two users cannot share save files, handoffs, or room permissions."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reborn" / "server"))
from accounts import AccountStore
from player_profiles import PlayerProfileStore, VersionConflict
from multiplayer_sessions import MultiplayerRegistry, SessionRejected


class MultiplayerIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        folder = Path(self.temp.name)
        self.accounts = AccountStore(folder / "accounts.sqlite")
        self.profiles = PlayerProfileStore(folder / "profiles.sqlite")
        self.registry = MultiplayerRegistry(self.accounts, self.profiles,
                                            max_players=2, max_rooms=2,
                                            max_room_players=2)
        self.a = self.accounts.register("AliceCDR", "long-secret-password-11")
        self.b = self.accounts.register("BobCDR", "long-secret-password-22")
        self.ta = self.accounts.login("AliceCDR", "long-secret-password-11")["token"]
        self.tb = self.accounts.login("BobCDR", "long-secret-password-22")["token"]

    def tearDown(self):
        self.profiles.close()
        self.accounts.close()
        self.temp.cleanup()

    def test_profiles_are_account_scoped_and_persistent(self):
        alice = self.profiles.load_or_create(self.a["id"])
        bob = self.profiles.load_or_create(self.b["id"])
        self.assertNotEqual(alice["account_id"], bob["account_id"])
        new = dict(alice["profile"], name="Alice", gold=250)
        version = self.profiles.save(self.a["id"], alice["version"], new)
        self.assertEqual(version, alice["version"] + 1)
        self.assertEqual(self.profiles.load_or_create(self.a["id"])["profile"]["gold"], 250)
        self.assertEqual(self.profiles.load_or_create(self.b["id"])["profile"]["gold"], 0)
        with self.assertRaises(VersionConflict):
            self.profiles.save(self.a["id"], alice["version"], new)
        with self.assertRaises(ValueError):
            self.profiles.load_or_create(0)

    def test_malformed_profile_data_is_rejected(self):
        a = self.profiles.load_or_create(self.a["id"])
        for broken in (dict(a["profile"], gold=-1),
                       dict(a["profile"], gold=True),
                       dict(a["profile"], admin=True),
                       dict(a["profile"], name="x"*25)):
            with self.assertRaises(ValueError):
                self.profiles.save(self.a["id"], a["version"], broken)

    def test_two_users_same_room_and_independent_identity(self):
        aa = self.registry.open_authenticated(self.ta)
        bb = self.registry.open_authenticated(self.tb)
        self.assertNotEqual(aa["session_id"], bb["session_id"])
        self.assertFalse(self.registry.redeem_gateway(bb["session_id"], aa["gateway_ticket"], object()))
        self.assertTrue(self.registry.redeem_gateway(aa["session_id"], aa["gateway_ticket"], object()))
        self.assertTrue(self.registry.redeem_gateway(bb["session_id"], bb["gateway_ticket"], object()))
        self.registry.join_room(aa["session_id"], "eu-001")
        self.registry.join_room(bb["session_id"], "eu-001")
        self.assertEqual(self.registry.room_members(aa["session_id"]),
                         frozenset((self.a["id"], self.b["id"])))
        self.assertNotEqual(self.registry.account_snapshot(aa["session_id"])["account_id"],
                            self.registry.account_snapshot(bb["session_id"])["account_id"])
        one = self.registry.issue_battle(aa["session_id"])
        two = self.registry.issue_battle(bb["session_id"])
        self.assertFalse(self.registry.redeem_battle(bb["session_id"], one, object()))
        self.assertTrue(self.registry.redeem_battle(aa["session_id"], one, object()))
        self.assertTrue(self.registry.redeem_battle(bb["session_id"], two, object()))
        self.assertFalse(self.registry.redeem_battle(aa["session_id"], one, object()))

    def test_reconnect_cleanup_and_duplicate_login(self):
        a = self.registry.open_authenticated(self.ta)
        with self.assertRaises(SessionRejected):
            self.registry.open_authenticated(self.ta)
        self.registry.redeem_gateway(a["session_id"], a["gateway_ticket"], object())
        self.registry.join_room(a["session_id"], "r-1")
        self.registry.disconnect(a["session_id"])
        self.assertFalse(self.registry.redeem_gateway(a["session_id"], a["gateway_ticket"], object()))
        self.assertEqual(self.registry.rooms, {})
        another = self.registry.open_authenticated(self.ta)
        self.assertNotEqual(a["session_id"], another["session_id"])

    def test_auth_token_required_and_capacity(self):
        with self.assertRaises(SessionRejected):
            self.registry.open_authenticated("fake")
        self.registry.open_authenticated(self.ta)
        self.registry.open_authenticated(self.tb)
        with self.assertRaises(SessionRejected):
            self.registry.open_authenticated(self.ta)

    def test_room_permissions_and_capacity(self):
        a = self.registry.open_authenticated(self.ta)
        with self.assertRaises(SessionRejected):
            self.registry.join_room(a["session_id"], "eu")
        with self.assertRaises(SessionRejected):
            self.registry.room_members(a["session_id"])
        self.assertTrue(self.registry.redeem_gateway(a["session_id"], a["gateway_ticket"], object()))
        self.registry.join_room(a["session_id"], "eu")
        self.registry.join_room(a["session_id"], "us")
        self.assertEqual(self.registry.room_members(a["session_id"]), frozenset((self.a["id"],)))
        self.assertNotIn("eu", self.registry.rooms)


if __name__ == "__main__":
    unittest.main()
