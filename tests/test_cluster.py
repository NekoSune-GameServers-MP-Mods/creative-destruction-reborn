import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reborn" / "server"))
from cluster_api import NodeRegistry, handler_factory
from cluster_agent import validate_control_url


class NodeRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = 100
        self.store = NodeRegistry(str(Path(self.temp.name) / "cluster.db"), clock=lambda: self.now)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_multiple_nodes_and_stale_heartbeat(self):
        one = self.store.register("eu-one", "EU", "100.88.10.11")
        two = self.store.register("us-two", "US", "100.88.10.12")
        self.assertNotEqual(one["node_key"], two["node_key"])
        self.assertFalse(self.store.heartbeat("eu-one", two["node_key"], True))
        self.assertTrue(self.store.heartbeat("eu-one", one["node_key"], True))
        self.assertEqual([n["status"] for n in self.store.list_nodes()], ["reachable", "unavailable"])
        self.now += 91
        self.assertEqual(self.store.list_nodes()[0]["status"], "unavailable")

    def test_validation_revocation_no_key_leak(self):
        with self.assertRaises(ValueError):
            self.store.register("EU 1", "EU", "100.88.10.11")
        with self.assertRaises(ValueError):
            self.store.register("eu-one", "EU", "invalid")
        item = self.store.register("eu-one", "EU", "100.88.10.11")
        self.assertNotIn(item["node_key"], json.dumps(self.store.list_nodes()))
        self.assertFalse(self.store.heartbeat("eu-one", item["node_key"], 1))
        self.assertTrue(self.store.delete("eu-one"))
        self.assertFalse(self.store.heartbeat("eu-one", item["node_key"], True))

    def test_no_plaintext_remote_control_url(self):
        self.assertEqual(validate_control_url("https://cluster.example.com"), "https://cluster.example.com")
        self.assertEqual(validate_control_url("http://127.0.0.1:8092"), "http://127.0.0.1:8092")
        with self.assertRaises(ValueError):
            validate_control_url("http://100.88.10.11:8092")
        with self.assertRaises(ValueError):
            validate_control_url("https://user:pass@example.com")

    def test_private_http_api_authorization(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_factory(self.store, "a"*48))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = "http://127.0.0.1:%d" % server.server_port
        try:
            request = urllib.request.Request(base + "/v1/cluster/nodes")
            with self.assertRaises(urllib.error.HTTPError) as exc:
                urllib.request.urlopen(request, timeout=3)
            self.assertEqual(exc.exception.code, 401)
            payload = json.dumps({"node_id": "eu-one", "region": "EU", "advertised_ip": "100.88.10.11"}).encode()
            request = urllib.request.Request(base + "/v1/cluster/nodes", data=payload, method="POST",
                        headers={"Authorization": "Bearer " + "a"*48, "Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=3) as response:
                key = json.load(response)["node_key"]
            self.assertTrue(self.store.heartbeat("eu-one", key, True))
            request = urllib.request.Request(base + "/v1/cluster/nodes",
                        headers={"Authorization": "Bearer " + "a"*48})
            with urllib.request.urlopen(request, timeout=3) as response:
                body = json.load(response)
            self.assertEqual(body["nodes"][0]["status"], "reachable")
            self.assertFalse(body["game_login_enabled"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
