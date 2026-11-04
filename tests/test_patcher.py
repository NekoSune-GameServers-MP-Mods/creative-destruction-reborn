import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reborn" / "tools"))
from patch_server import patch, validate_url

class PatcherTests(unittest.TestCase):
    def test_validation(self):
        self.assertEqual(validate_url("http://100.88.2.3:8000/"), "http://100.88.2.3:8000/")
        for item in ("https://100.88.2.3:8000/", "http://evil.example:8000/",
                     "http://100.88.2.3:8000/path", "http://100.88.2.3:4000/",
                     "http://user:pass@100.88.2.3:8000/"):
            with self.subTest(item=item), self.assertRaises(ValueError):
                validate_url(item)

    def test_patch_and_restore(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "client.exe").touch()
            (root / "script.npk").touch()
            target = root / "Documents" / "nonpatch_user_data.dat"
            target.parent.mkdir()
            original = b'{"http_url_prefix": "http://127.0.0.1:8000/"}'
            target.write_bytes(original)
            patch(root, "http://100.88.2.3:8000/")
            self.assertEqual(json.loads(target.read_text())["http_url_prefix"], "http://100.88.2.3:8000/")
            self.assertEqual((root / "reborn/backup/server_endpoint_original.dat").read_bytes(), original)
            patch(root, None, restore=True)
            self.assertEqual(target.read_bytes(), original)

if __name__ == "__main__":
    unittest.main()
