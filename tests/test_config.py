import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "reborn", "server"))
from server_config import listener_host, connection_limit, advertised_host
from i18n import language, tr

class ServerConfigTests(unittest.TestCase):
    def test_loopback_is_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(listener_host(), "127.0.0.1")

    def test_remote_refused_by_default(self):
        with patch.dict(os.environ, {"CDR_BIND_HOST": "0.0.0.0"}, clear=True):
            with self.assertRaises(ValueError):
                listener_host()

    def test_private_remote_requires_explicit_opt_in(self):
        with patch.dict(os.environ, {"CDR_BIND_HOST": "10.10.1.2", "CDR_ALLOW_REMOTE": "1"}, clear=True):
            self.assertEqual(listener_host(), "10.10.1.2")

    def test_advertised_host_is_loopback_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(advertised_host(), "127.0.0.1")

    def test_advertised_host_must_be_ip(self):
        with patch.dict(os.environ, {"CDR_ADVERTISE_HOST": "example.com"}, clear=True):
            with self.assertRaises(ValueError):
                advertised_host()

    def test_reject_bad_limits(self):
        for value in ("0", "257", "-2"):
            with patch.dict(os.environ, {"CDR_MAX_CONNECTIONS": value}, clear=True):
                with self.assertRaises(ValueError):
                    connection_limit()

    def test_translations_and_fallback(self):
        with patch.dict(os.environ, {"CDR_LANGUAGE": "fr-FR"}, clear=True):
            self.assertEqual(language(), "fr")
            self.assertIn("Démarrage", tr("start"))
        with patch.dict(os.environ, {"CDR_LANGUAGE": "xx"}, clear=True):
            self.assertEqual(language(), "en")
            self.assertIn("starting", tr("start"))

if __name__ == "__main__":
    unittest.main()
