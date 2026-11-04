"""Client launcher configuration and DNS bridge unit tests."""
import json
import io
from email.message import Message
from urllib.error import HTTPError
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reborn" / "tools"))
from steam_bridge import validate_game_host, format_account_http_error
from steam_launcher import load_config


class LauncherConfigTests(unittest.TestCase):
    def test_hostname_and_existing_ipv4(self):
        self.assertEqual(validate_game_host("game-cdr.nekosunevr.co.uk"),
                         "game-cdr.nekosunevr.co.uk")
        self.assertEqual(validate_game_host("75.119.148.51"), "75.119.148.51")
        for bad in ("127.0.0.1", "https://game-cdr.nekosunevr.co.uk",
                    "game-cdr.nekosunevr.co.uk:4000", "../bad",
                    "bad..example.com", "a@b.com", ""):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_game_host(bad)

    def test_403_diagnostic_does_not_confuse_proxy_with_waf(self):
        headers = Message()
        headers["Server"] = "cloudflare"
        headers["Content-Type"] = "application/json"
        headers["CF-Ray"] = "a1b2c3d4-LHR"
        err = HTTPError("https://example.invalid/v1/login", 403,
                        "Forbidden", headers,
                        io.BytesIO(b'{"error":"forbidden","token":"SECRET"}'))
        message = format_account_http_error(err)
        self.assertIn("API error=forbidden", message)
        self.assertIn("a1b2c3d4-LHR", message)
        self.assertNotIn("SECRET", message)
        self.assertNotIn("WAF", message)

    def test_valid_cloudflare_config(self):
        config = {
            "game_host": "game-cdr.nekosunevr.co.uk",
            "game_tls_hostname": "game-cdr.nekosunevr.co.uk",
            "auth_url": "https://auth-cdr.nekosunevr.co.uk",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps(config))
            self.assertEqual(load_config(path),
                             ("game-cdr.nekosunevr.co.uk",
                              "game-cdr.nekosunevr.co.uk",
                              "https://auth-cdr.nekosunevr.co.uk"))
            config["auth_url"] = "http://auth-cdr.nekosunevr.co.uk"
            path.write_text(json.dumps(config))
            with self.assertRaises(ValueError):
                load_config(path)
            config["auth_url"] = "https://auth-cdr.nekosunevr.co.uk"
            config["password"] = "should-not-be-here"
            path.write_text(json.dumps(config))
            with self.assertRaises(ValueError):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
