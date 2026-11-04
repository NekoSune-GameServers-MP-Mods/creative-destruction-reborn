"""Tests for safe Android discovery replacement, not a crossplay claim."""
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reborn" / "tools"))
from patch_android_apk import patch_apk, validate_hostname, ASSETS


class AndroidPatchTests(unittest.TestCase):
    def test_two_existing_reborn_configs_are_patched(self):
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "input.apk"
            dst = Path(t) / "output.apk"
            with zipfile.ZipFile(src, "w") as z:
                z.writestr("classes.dex", b"binary unchanged")
                z.writestr("META-INF/CDRTEST.RSA", b"invalid signature")
                for asset in ASSETS:
                    z.writestr(asset, json.dumps({
                        "http_url_prefix": "http://75.119.148.51:8000/",
                        "language": 3,
                    }))
            url = patch_apk(src, dst)
            self.assertEqual(url, "http://game-cdr.nekosunevr.co.uk:8000/")
            with zipfile.ZipFile(dst) as z:
                self.assertEqual(z.read("classes.dex"), b"binary unchanged")
                self.assertNotIn("META-INF/CDRTEST.RSA", z.namelist())
                for asset in ASSETS:
                    body = json.loads(z.read(asset))
                    self.assertEqual(body["http_url_prefix"], url)
                    self.assertEqual(body["language"], 3)

    def test_refuse_missing_config_and_original_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "input.apk"
            with zipfile.ZipFile(src, "w") as z:
                z.writestr("classes.dex", b"x")
            with self.assertRaises(ValueError):
                patch_apk(src, src)
            with self.assertRaises(ValueError):
                patch_apk(src, Path(t) / "out.apk")

    def test_validate_hostname(self):
        self.assertEqual(validate_hostname("GAME-CDR.NEKOSUNEVR.CO.UK"),
                         "game-cdr.nekosunevr.co.uk")
        for host in ("localhost", "http://example.com", "127.0.0.1", "a:8000",
                     "../example", "invalid..hostname"):
            if host == "localhost":
                # A one-label hostname is not accepted.
                pass
            with self.subTest(host=host), self.assertRaises(ValueError):
                validate_hostname(host)


if __name__ == "__main__":
    unittest.main()
