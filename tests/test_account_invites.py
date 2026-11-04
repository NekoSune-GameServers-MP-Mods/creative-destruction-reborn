"""Independent account invitation tests: one-time signup, expiry and admin auth."""
import http.client
import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reborn" / "server"))
import account_api
from accounts import AccountStore, AuthError


class AccountInvitationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = AccountStore(Path(self.tmp.name) / "accounts.sqlite")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0),
                                          account_api.handler_factory(self.store))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        with account_api._RATE_LOCK:
            account_api._RATE_BUCKETS.clear()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.store.close()
        self.tmp.cleanup()

    def request(self, path, data, key=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=4)
        try:
            headers = {"Content-Type": "application/json"}
            if key is not None:
                headers["X-Registration-Key"] = key
            conn.request("POST", path, json.dumps(data).encode(), headers)
            res = conn.getresponse()
            return res.status, json.loads(res.read())
        finally:
            conn.close()

    def test_one_time_invite_and_duplicate_rollback(self):
        invite = self.store.create_invitation()["invite_code"]
        with self.assertRaises(AuthError):
            self.store.register_with_invite("Rejected", "strong-password-123", "bad")
        self.store.register("Existing", "strong-password-123")
        with self.assertRaises(AuthError):
            self.store.register_with_invite("Existing", "strong-password-123", invite)
        created = self.store.register_with_invite("NewMember", "strong-password-456", invite)
        self.assertEqual(created["username"], "NewMember")
        with self.assertRaises(AuthError):
            self.store.register_with_invite("Another", "strong-password-123", invite)

    def test_invite_admin_api_and_player_signup(self):
        secret = "A" * 48
        with patch.object(account_api, "REGISTER_KEY", secret):
            status, _ = self.request("/v1/admin/invitations", {})
            self.assertEqual(status, 403)
            status, invite = self.request("/v1/admin/invitations", {"lifetime_seconds": 3600}, secret)
            self.assertEqual(status, 201)
            status, registered = self.request("/v1/register", {
                "username": "PlayerThree", "password": "strong-password-111",
                "invite_code": invite["invite_code"]})
            self.assertEqual(status, 201)
            self.assertEqual(registered["account"]["username"], "PlayerThree")
            status, _ = self.request("/v1/register", {
                "username": "PlayerFour", "password": "strong-password-222",
                "invite_code": invite["invite_code"]})
            self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
