"""Test the private account API game-ticket endpoint over HTTP internally.

The external account endpoint must be TLS terminated by a trusted reverse proxy.
"""
import http.client
import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reborn" / "server"))
from accounts import AccountStore
from account_api import handler_factory


class ApiGameTicketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.store = AccountStore(Path(cls.temp.name) / "accounts.sqlite")
        cls.store.register("ApiPlayer", "tested-password-1234")
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_factory(cls.store))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
        cls.store.close()
        cls.temp.cleanup()

    def call(self, path, data, token=""):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=4)
        try:
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = "Bearer " + token
            conn.request("POST", path, json.dumps(data).encode(), headers)
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def test_login_issue_game_ticket_and_consume_once(self):
        status, login = self.call("/v1/login", {
            "username": "ApiPlayer", "password": "tested-password-1234"})
        self.assertEqual(status, 200)
        self.assertTrue(login["token"])
        status, issued = self.call("/v1/game-ticket", {}, login["token"])
        self.assertEqual(status, 200)
        self.assertTrue(issued["ticket"])
        self.assertEqual(self.store.consume_game_login_ticket(issued["ticket"])["username"], "ApiPlayer")
        self.assertIsNone(self.store.consume_game_login_ticket(issued["ticket"]))

    def test_game_ticket_denies_missing_or_invalid_bearer(self):
        for token in ("", "not-valid"):
            status, _ = self.call("/v1/game-ticket", {}, token)
            self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main()
