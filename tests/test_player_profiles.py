"""Account-service tests for independent persistent player profiles."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reborn" / "server"))
from player_profiles import PlayerProfileStore, VersionConflict


class PlayerProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = PlayerProfileStore(Path(self.tmp.name) / "profiles.sqlite")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_accounts_never_share_profiles(self):
        one = self.store.load_or_create(1)
        two = self.store.load_or_create(2)
        self.assertNotEqual(one["account_id"], two["account_id"])
        modified = dict(one["profile"], name="Alice", gold=100)
        self.store.save(1, one["version"], modified)
        self.assertEqual(self.store.load_or_create(1)["profile"]["gold"], 100)
        self.assertEqual(self.store.load_or_create(2)["profile"]["gold"], 0)

    def test_conflicting_writes_and_invalid_ids(self):
        one = self.store.load_or_create(1)
        profile = dict(one["profile"], name="Player")
        self.store.save(1, one["version"], profile)
        with self.assertRaises(VersionConflict):
            self.store.save(1, one["version"], profile)
        with self.assertRaises(ValueError):
            self.store.load_or_create(0)

    def test_unexpected_keys_and_negative_currency(self):
        one = self.store.load_or_create(1)
        for bad in (dict(one["profile"], gold=-1),
                    dict(one["profile"], moderator=True)):
            with self.assertRaises(ValueError):
                self.store.save(1, one["version"], bad)


if __name__ == "__main__":
    unittest.main()
