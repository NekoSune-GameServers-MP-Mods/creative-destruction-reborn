import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reborn" / "server"))
from accounts import AccountStore, AuthError

class AccountTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = AccountStore(os.path.join(self.tmp.name, "accounts.sqlite3"))

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_register_and_login(self):
        a = self.db.register("Player_One", "veryStrongPassword!2026")
        self.assertGreater(a["id"], 0)
        logged = self.db.login("player_one", "veryStrongPassword!2026")
        self.assertEqual(self.db.resolve(logged["token"])["id"], a["id"])
        self.assertNotIn(logged["token"].encode(), Path(self.db.path).read_bytes())

    def test_duplicate_case_insensitive(self):
        self.db.register("NekoTest", "veryStrongPassword!2026")
        with self.assertRaises(AuthError):
            self.db.register("NEKOTEST", "veryStrongPassword!2026")

    def test_bad_password_and_revoke(self):
        self.db.register("TestUser", "veryStrongPassword!2026")
        with self.assertRaises(AuthError):
            self.db.login("TestUser", "bad")
        token = self.db.login("TestUser", "veryStrongPassword!2026")["token"]
        self.db.revoke(token)
        self.assertIsNone(self.db.resolve(token))

    def test_validation(self):
        for username in ("a", "Invalid Name", "';DROP TABLE accounts;--"):
            with self.assertRaises(AuthError):
                self.db.register(username, "veryStrongPassword!2026")
        with self.assertRaises(AuthError):
            self.db.register("validUser", "short")

    def test_disable_and_revoke_all(self):
        a = self.db.register("LockMe", "veryStrongPassword!2026")
        token = self.db.login("LockMe", "veryStrongPassword!2026")["token"]
        with self.db.db:
            self.db.db.execute("UPDATE accounts SET disabled=1 WHERE id=?", (a["id"],))
        self.assertIsNone(self.db.resolve(token))
        self.db.revoke_all(a["id"])
        self.assertIsNone(self.db.resolve(token))

if __name__ == "__main__":
    unittest.main()
