"""Exercise actual HTTP discovery responses for Steam, PC and Android."""
import http.client
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reborn" / "server"))
from offline_server import HttpHandler, LOGINLIST, ZONELIST


class DiscoveryHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), HttpHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def get(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=4)
        try:
            conn.request("GET", path)
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    def test_steam_and_android_lists(self):
        cases = {
            "/loginlist_rel_steam_na.txt": LOGINLIST,
            "/client_zonelist_rel_steam_na.txt": ZONELIST,
            "/loginlist_rel_na.txt": LOGINLIST,
            "/client_zonelist_rel_na.txt": ZONELIST,
            "/loginlist_rel_pc_na.txt": LOGINLIST,
            "/client_zonelist_rel_pc_na.txt": ZONELIST,
            "/loginlist.txt": LOGINLIST,
            "/client_zonelist.txt": ZONELIST,
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                status, headers, body = self.get(path)
                self.assertEqual(status, 200)
                self.assertEqual(body, expected.encode("utf-8"))
                self.assertEqual(headers.get("Content-Type"), "text/plain; charset=utf-8")
                self.assertIn("no-store", headers.get("Cache-Control", ""))

    def test_zone_newline_and_login_host(self):
        self.assertTrue(ZONELIST.endswith("\n"))
        self.assertFalse(ZONELIST.endswith(r"\n"))
        self.assertEqual(len(ZONELIST.splitlines()), 1)
        self.assertEqual(len(LOGINLIST.splitlines()), 1)

    def test_unknown_path_is_404(self):
        status, _, _ = self.get("/missing-zone-list.txt")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
